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

## Quick Start

```bash
export OPENAI_API_KEY=sk-...
make run
```

After setup completes (~10–15 min):
```bash
make test      # verify all components
make status    # show pods / services / agents
```

## Architecture

```
┌──────────────────────── KinD Cluster: lab1-l2 ───────────────────────────┐
│                                                                            │
│  Namespace: agentgateway-system                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  agentgateway v1.1.0 (Helm)                                         │  │
│  │  ├── Deployment: agentgateway                                        │  │
│  │  ├── Service: agentgateway  (ClusterIP :80)                          │  │
│  │  ├── Secret: openai-secret  ← $OPENAI_API_KEY                       │  │
│  │  └── AgentgatewayBackend: openai  (gpt-4o-mini)                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  Namespace: kagent                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  kagent v0.9.2 (Helm)                                               │  │
│  │  ├── providers.openAI.baseURL → agentgateway:80/v1  ←──────────────┼──┤
│  │  ├── Built-in Kubernetes agent                                       │  │
│  │  └── kagent-ui  (port 8080)                                          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘

LLM request path:  kagent → agentgateway (ClusterIP) → OpenAI API
```

## Deployment Steps

### Automated (recommended)

```bash
make run
```

`scripts/setup.sh` runs these steps in order:
1. `kind create cluster` — 1 control-plane + 2 worker nodes
2. `helm install agentgateway-crds` — agentgateway CRDs
3. `helm install agentgateway` — proxy deployment + Service
4. `kubectl create secret` — injects `$OPENAI_API_KEY`
5. `kubectl apply manifests/llm-backend.yaml` — `AgentgatewayBackend` CRD
6. `helm install kagent-crds` + `helm install kagent` — agent runtime

### Manual (step by step)

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

# Secret
kubectl create secret generic openai-secret \
  -n agentgateway-system \
  --from-literal="Authorization=$OPENAI_API_KEY"

# LLM backend CRD
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

## Verification

```bash
make test

# Or manually:
kubectl get pods -A
kubectl get agents -n kagent
kubectl get svc -n agentgateway-system
```

Access kagent UI:
```bash
kubectl port-forward svc/kagent-ui -n kagent 8080:8080
# Open: http://localhost:8080
```

## Teardown

```bash
make down
```

## File Reference

| File | Purpose |
|------|---------|
| `kind-config.yaml` | KinD cluster spec (3 nodes) |
| `manifests/llm-backend.yaml` | `AgentgatewayBackend` CRD — OpenAI provider |
| `manifests/llm-secret.yaml` | Secret template (key injected by setup.sh) |
| `helm/kagent-values.yaml` | kagent Helm values with agentgateway baseURL |
| `scripts/setup.sh` | Full deployment script |
| `scripts/test.sh` | Integration test |
| `scripts/teardown.sh` | Cluster teardown |

## Component Versions

| Component | Version | Chart |
|-----------|---------|-------|
| agentgateway | v1.1.0 | `oci://cr.agentgateway.dev/charts/agentgateway` |
| kagent | 0.9.2 | `oci://ghcr.io/kagent-dev/kagent/helm/kagent` |
| KinD | v0.31.0 | — |
