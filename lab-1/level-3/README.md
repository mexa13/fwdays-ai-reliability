# Level 3 — Max: Gateway API

## Objectives

Complete Level 2, but route LLM traffic through the **Kubernetes Gateway API** instead of directly addressing the agentgateway ClusterIP Service.

## What's Different from Level 2

| Level 2 | Level 3 |
|---------|---------|
| kagent → agentgateway Service (ClusterIP) | kagent → Gateway → HTTPRoute → AgentgatewayBackend |
| Direct Service connection | Traffic flows through a GatewayClass controller |
| No Gateway API CRDs | Gateway API CRDs v1.5.1 |

---

## LLM Providers

| Command | Provider | Requires | How kagent connects |
|---------|----------|----------|---------------------|
| `make run` | OpenAI | `OPENAI_API_KEY` | kagent → Gateway → `openai-route` → `openai` backend → OpenAI API |
| `make run-anthropic` | Anthropic | `ANTHROPIC_API_KEY` | kagent → Gateway → `anthropic-route` → `anthropic` backend → Anthropic API |
| `make run-lmstudio` | LM Studio (local) | LM Studio on port 1234 | kagent → `host.docker.internal:1234` directly |

For `run` and `run-anthropic`, LLM traffic passes through the full Gateway API chain. The
Gateway is a single entry point; the HTTPRoute selects which `AgentgatewayBackend` handles
the request based on the provider.

For `run-lmstudio`, the Gateway API resources (GatewayClass, Gateway) are still created so
you can inspect them, but no HTTPRoute is applied — kagent connects directly to LM Studio on
the host machine. Tested with `google/gemma-3-4b`.

---

## Quick Start

```bash
# OpenAI
export OPENAI_API_KEY=sk-...
make run

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
make run-anthropic

# LM Studio (LM Studio must be running on port 1234)
make run-lmstudio
# or with a specific model:
LMSTUDIO_MODEL=google/gemma-3-4b make run-lmstudio
```

After setup completes (~10–15 min):
```bash
make test      # verify GatewayClass, Gateway, HTTPRoute, agents
make down      # destroy the cluster
```

---

## Architecture

```
┌──────────────────────── KinD Cluster: lab1-l3 ───────────────────────────┐
│                                                                            │
│  Namespace: agentgateway-system                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  GatewayClass: agentgateway                                         │  │
│  │       │                                                             │  │
│  │  Gateway: agentgateway-proxy  (HTTP :80, allowedRoutes: All)        │  │
│  │       │                                                             │  │
│  │  HTTPRoute: openai-route      /v1/* → openai backend  (run)         │  │
│  │  HTTPRoute: anthropic-route   /v1/* → anthropic backend (run-anth.) │  │
│  │       │                                                             │  │
│  │  AgentgatewayBackend: openai      (gpt-4o-mini)       + Secret      │  │
│  │  AgentgatewayBackend: anthropic   (claude-sonnet-4-6) + Secret      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  Namespace: kagent                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  run / run-anthropic: baseURL → agentgateway-proxy:80/v1  ──────────┼──┤
│  │  run-lmstudio:        baseUrl → host.docker.internal:1234/v1        │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘

LLM request path (OpenAI):
  kagent → Gateway (agentgateway-proxy :80) → openai-route /v1
         → AgentgatewayBackend (openai) → OpenAI API

LLM request path (Anthropic):
  kagent → Gateway (agentgateway-proxy :80) → anthropic-route /v1
         → AgentgatewayBackend (anthropic) → Anthropic API
```

---

## Deployment Steps (manual)

```bash
# 1. Create cluster
kind create cluster --name lab1-l3 --config kind-config.yaml

# 2. Gateway API CRDs — standard channel
kubectl apply --server-side -f \
  https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.5.1/standard-install.yaml

# 3. agentgateway CRDs + agentgateway (Gateway API experimental features on)
helm upgrade --install agentgateway-crds \
  oci://cr.agentgateway.dev/charts/agentgateway-crds \
  -n agentgateway-system --create-namespace --version v1.1.0 --wait

helm upgrade --install agentgateway \
  oci://cr.agentgateway.dev/charts/agentgateway \
  -n agentgateway-system --version v1.1.0 \
  --set "controller.extraEnv.KGW_ENABLE_GATEWAY_API_EXPERIMENTAL_FEATURES=true" \
  --wait

# 4. Secret + AgentgatewayBackend + Gateway API resources (OpenAI example)
kubectl create secret generic openai-secret \
  -n agentgateway-system \
  --from-literal="Authorization=$OPENAI_API_KEY"
kubectl apply -f manifests/llm-backend.yaml
kubectl apply -f manifests/gateway.yaml
kubectl apply -f manifests/httproute.yaml       # OpenAI route

# 5. kagent — routed through the Gateway
helm upgrade --install kagent-crds \
  oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds \
  -n kagent --create-namespace --version 0.9.2 --wait

helm upgrade --install kagent \
  oci://ghcr.io/kagent-dev/kagent/helm/kagent \
  -n kagent --version 0.9.2 \
  --set providers.default=openAI \
  --set "providers.openAI.apiKey=$OPENAI_API_KEY" \
  --set "providers.openAI.baseURL=http://agentgateway-proxy.agentgateway-system.svc.cluster.local/v1" \
  --wait
```

---

## Verifying Gateway API Resources

```bash
make test

# Individual checks:
kubectl get gatewayclass agentgateway
kubectl get gateway -n agentgateway-system
kubectl get httproute -n agentgateway-system

# Detailed status:
kubectl describe gateway agentgateway-proxy -n agentgateway-system
kubectl describe httproute openai-route -n agentgateway-system
```

Expected conditions:
- `GatewayClass`: `Accepted: True`
- `Gateway`: `Programmed: True`
- `HTTPRoute`: `Accepted: True`

---

## Testing via Gateway

```bash
make test

# Or manually — port-forward the Gateway:
kubectl port-forward svc/agentgateway-proxy -n agentgateway-system 8080:80

# OpenAI:
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello from Gateway API!"}]}'

# Anthropic (same endpoint — agentgateway translates the protocol):
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-sonnet-4-6","messages":[{"role":"user","content":"Hello from Gateway API!"}]}'
```

---

## Teardown

```bash
make down
```

---

## File Reference

| File | Purpose |
|------|---------|
| `kind-config.yaml` | KinD cluster spec (3 nodes) |
| `manifests/llm-backend.yaml` | `AgentgatewayBackend` — OpenAI (gpt-4o-mini) |
| `manifests/llm-backend-anthropic.yaml` | `AgentgatewayBackend` — Anthropic (claude-sonnet-4-6) |
| `manifests/gateway.yaml` | `Gateway` — GatewayClass agentgateway, listener :80 |
| `manifests/httproute.yaml` | `HTTPRoute` openai-route: /v1/* → openai backend |
| `manifests/httproute-anthropic.yaml` | `HTTPRoute` anthropic-route: /v1/* → anthropic backend |
| `scripts/setup.sh` | Full deployment script (provider-aware) |
| `scripts/test.sh` | GatewayClass / Gateway / HTTPRoute / agents checks (provider-aware) |
| `scripts/teardown.sh` | Cluster teardown |

---

## Component Versions

| Component | Version | Source |
|-----------|---------|--------|
| agentgateway | v1.1.0 | `oci://cr.agentgateway.dev/charts/agentgateway` |
| kagent | 0.9.2 | `oci://ghcr.io/kagent-dev/kagent/helm/kagent` |
| Gateway API CRDs | v1.5.1 | `github.com/kubernetes-sigs/gateway-api` |
| KinD | v0.31.0 | `github.com/kubernetes-sigs/kind` |
