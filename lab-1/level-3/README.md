# Level 3 — Max: Gateway API

## Objectives

Complete Level 2, but route LLM traffic through the **Kubernetes Gateway API** instead of directly addressing the agentgateway ClusterIP Service.

## What's Different from Level 2

| Level 2 | Level 3 |
|---------|---------|
| kagent → agentgateway Service (ClusterIP) | kagent → Gateway → HTTPRoute → AgentgatewayBackend |
| Direct Service connection | Traffic flows through a GatewayClass controller |
| No Gateway API CRDs | Gateway API CRDs v1.5.1 |

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
│  │  HTTPRoute: openai-route  (/v1/* → AgentgatewayBackend)             │  │
│  │       │                                                             │  │
│  │  AgentgatewayBackend: openai  (gpt-4o-mini + openai-secret)         │  │
│  │       │                                                             │  │
│  │  Secret: openai-secret  ← $OPENAI_API_KEY                          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  Namespace: kagent                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  providers.openAI.baseURL → agentgateway-proxy:80/v1  ←────────────┼──┤
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘

LLM request path:
  kagent → Gateway (agentgateway-proxy :80) → HTTPRoute match /v1
         → AgentgatewayBackend (openai) → OpenAI API
```

## Quick Start

```bash
export OPENAI_API_KEY=sk-...
make run
```

## Deployment Steps

### Automated (recommended)

```bash
make run
```

### Manual (step by step)

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

# 4. Secret + Gateway API resources
kubectl create secret generic openai-secret \
  -n agentgateway-system \
  --from-literal="Authorization=$OPENAI_API_KEY"

kubectl apply -f manifests/llm-backend.yaml
kubectl apply -f manifests/gateway.yaml
kubectl apply -f manifests/httproute.yaml

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

## Verifying Gateway API Resources

```bash
make gw-status

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

## Testing via Gateway

```bash
make test

# Or manually — port-forward the Gateway:
kubectl port-forward svc/agentgateway-proxy -n agentgateway-system 8080:80

curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello from Gateway API!"}]}'
```

## Teardown

```bash
make down
```

## File Reference

| File | Purpose |
|------|---------|
| `kind-config.yaml` | KinD cluster spec (3 nodes) |
| `manifests/llm-backend.yaml` | `AgentgatewayBackend` CRD |
| `manifests/llm-secret.yaml` | Secret template |
| `manifests/gateway.yaml` | `Gateway` — GatewayClass agentgateway, listener :80 |
| `manifests/httproute.yaml` | `HTTPRoute` /v1/* → AgentgatewayBackend + ReferenceGrant |
| `scripts/setup.sh` | Full deployment script |
| `scripts/test.sh` | GatewayClass / Gateway / HTTPRoute / agents checks |
| `scripts/teardown.sh` | Cluster teardown |

## Component Versions

| Component | Version | Source |
|-----------|---------|--------|
| agentgateway | v1.1.0 | `oci://cr.agentgateway.dev/charts/agentgateway` |
| kagent | 0.9.2 | `oci://ghcr.io/kagent-dev/kagent/helm/kagent` |
| Gateway API CRDs | v1.5.1 | `github.com/kubernetes-sigs/gateway-api` |
| KinD | v0.31.0 | `github.com/kubernetes-sigs/kind` |
