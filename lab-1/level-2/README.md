# Level 2 — Experienced: Helm Deployment in Kubernetes

## Objectives

1. Deploy agentgateway as a Helm release in a KinD cluster
2. Configure Secrets and ConfigMap for API keys and settings
3. Deploy kagent
4. Configure model routing through agentgateway
5. Verify a built-in agent works end-to-end

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker | 24+ | https://docs.docker.com/engine/install/ |
| kind | v0.31.0 | https://github.com/kubernetes-sigs/kind/releases/tag/v0.31.0 |
| kubectl | 1.30+ | https://kubernetes.io/docs/tasks/tools/ |
| helm | 3.16+ | https://helm.sh/docs/intro/install/ |

> **GitHub Codespaces**: all tools are installed automatically by the devcontainer. Open a Codespace with **4-core · 16 GB RAM** and skip this section.

---

## LLM Providers

| Command | Provider | Requires | How kagent connects |
|---------|----------|----------|---------------------|
| `make run` | OpenAI | `OPENAI_API_KEY` | kagent → agentgateway (ClusterIP) → OpenAI API |
| `make run-anthropic` | Anthropic | `ANTHROPIC_API_KEY` | kagent → agentgateway (ClusterIP) → Anthropic API |
| `make run-lmstudio` | LM Studio (local) | LM Studio on port 1234 | kagent → `host.docker.internal:1234` directly |

**LM Studio** lets you run models locally without any API key. Tested with `google/gemma-3-4b`.
Set `LMSTUDIO_MODEL=<name>` to use a different model loaded in LM Studio.

For LM Studio, kagent connects directly to the host machine (`host.docker.internal:1234`) and bypasses
the agentgateway backend — the gateway is still deployed but not used for LLM routing.

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
make test      # verify all components
make down      # destroy the cluster
```

---

## Architecture

```
┌──────────────────────── KinD Cluster: lab1-l2 ───────────────────────────┐
│                                                                            │
│  Namespace: agentgateway-system                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  agentgateway v1.1.0 (Helm)                                         │  │
│  │  ├── Deployment: agentgateway                                        │  │
│  │  ├── Service: agentgateway  (ClusterIP)                              │  │
│  │  ├── Secret: openai-secret  ← $OPENAI_API_KEY   (run)               │  │
│  │  ├── Secret: anthropic-secret  ← $ANTHROPIC_API_KEY  (run-anthropic) │  │
│  │  ├── AgentgatewayBackend: openai  (gpt-4o-mini)      (run)          │  │
│  │  └── AgentgatewayBackend: anthropic  (claude-sonnet-4-6) (run-anth.) │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  Namespace: kagent                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  kagent v0.9.2 (Helm)                                               │  │
│  │  ├── run / run-anthropic: baseURL → agentgateway:ClusterIP/v1  ─────┼──┤
│  │  ├── run-lmstudio: baseUrl → host.docker.internal:1234/v1           │  │
│  │  ├── Built-in Kubernetes agent                                       │  │
│  │  └── kagent-ui  (port 8080)                                          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Steps (manual)

```bash
# Create cluster
kind create cluster --name lab1-l2 --config kind-config.yaml

# agentgateway
helm upgrade --install agentgateway-crds \
  oci://cr.agentgateway.dev/charts/agentgateway-crds \
  -n agentgateway-system --create-namespace --version v1.1.0 --wait

helm upgrade --install agentgateway \
  oci://cr.agentgateway.dev/charts/agentgateway \
  -n agentgateway-system --version v1.1.0 --wait

# Secret + Backend (OpenAI example)
kubectl create secret generic openai-secret \
  -n agentgateway-system \
  --from-literal="Authorization=$OPENAI_API_KEY"
kubectl apply -f manifests/llm-backend.yaml

# kagent
helm upgrade --install kagent-crds \
  oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds \
  -n kagent --create-namespace --version 0.9.2 --wait

helm upgrade --install kagent \
  oci://ghcr.io/kagent-dev/kagent/helm/kagent \
  -n kagent --version 0.9.2 \
  --set providers.default=openAI \
  --set "providers.openAI.apiKey=$OPENAI_API_KEY" \
  --set "providers.openAI.baseURL=http://agentgateway.agentgateway-system.svc.cluster.local/v1" \
  --wait
```

---

## Verification

```bash
make test

# Individual checks:
kubectl get pods -A
kubectl get agents -n kagent
kubectl get svc -n agentgateway-system
kubectl get modelconfig -n kagent -o yaml
```

Access kagent UI:
```bash
kubectl port-forward svc/kagent-ui -n kagent 8080:8080
# Open: http://localhost:8080
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
| `manifests/llm-secret.yaml` | Secret template (key injected by setup.sh) |
| `scripts/setup.sh` | Full deployment script (provider-aware) |
| `scripts/test.sh` | Integration test (provider-aware) |
| `scripts/teardown.sh` | Cluster teardown |

---

## Component Versions

| Component | Version | Chart |
|-----------|---------|-------|
| agentgateway | v1.1.0 | `oci://cr.agentgateway.dev/charts/agentgateway` |
| kagent | 0.9.2 | `oci://ghcr.io/kagent-dev/kagent/helm/kagent` |
| KinD | v0.31.0 | — |
