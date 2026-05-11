#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LOG=/tmp/lab1-l3-setup.log
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date '+%H:%M:%S')] $*"; }
err() { echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2; exit 1; }

# ─── Prerequisites ────────────────────────────────────────────────────────────
[[ -z "${OPENAI_API_KEY:-}" ]] && err "OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY=sk-..."

for tool in kind kubectl helm; do
  command -v "$tool" >/dev/null 2>&1 || err "$tool is not installed"
done

CLUSTER_NAME="lab1-l3"
AGENTGW_VERSION="v1.1.0"
GATEWAY_API_VERSION="v1.5.1"
KAGENT_VERSION="0.9.2"

log "=== Lab 1 Level 3 (Max) — Setup ==="

# ─── 1. KinD cluster ─────────────────────────────────────────────────────────
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  log "Cluster '${CLUSTER_NAME}' already exists — skipping creation"
else
  log "Creating KinD cluster '${CLUSTER_NAME}'..."
  kind create cluster --name "$CLUSTER_NAME" --config "$ROOT/kind-config.yaml"
fi

kubectl cluster-info --context "kind-${CLUSTER_NAME}"
log "Cluster ready"

# ─── 2. Kubernetes Gateway API CRDs (standard channel) ───────────────────────
log "Installing Gateway API CRDs (${GATEWAY_API_VERSION}, standard channel)..."
kubectl apply --server-side -f \
  "https://github.com/kubernetes-sigs/gateway-api/releases/download/${GATEWAY_API_VERSION}/standard-install.yaml"
log "Gateway API CRDs installed"

# ─── 3. agentgateway CRDs ────────────────────────────────────────────────────
log "Installing agentgateway CRDs (${AGENTGW_VERSION})..."
helm upgrade --install agentgateway-crds \
  oci://cr.agentgateway.dev/charts/agentgateway-crds \
  --namespace agentgateway-system \
  --create-namespace \
  --version "$AGENTGW_VERSION" \
  --timeout 5m \
  --wait
log "agentgateway CRDs installed"

# ─── 4. agentgateway (Gateway API experimental features enabled) ──────────────
log "Installing agentgateway (${AGENTGW_VERSION}) with Gateway API support..."
helm upgrade --install agentgateway \
  oci://cr.agentgateway.dev/charts/agentgateway \
  --namespace agentgateway-system \
  --version "$AGENTGW_VERSION" \
  --set "controller.extraEnv.KGW_ENABLE_GATEWAY_API_EXPERIMENTAL_FEATURES=true" \
  --timeout 5m \
  --wait
log "agentgateway installed"

# ─── 5. LLM API key Secret ───────────────────────────────────────────────────
log "Creating Secret 'openai-secret'..."
kubectl create secret generic openai-secret \
  --namespace agentgateway-system \
  --from-literal="Authorization=${OPENAI_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -
log "Secret created"

# ─── 6. Gateway API resources ────────────────────────────────────────────────
log "Applying AgentgatewayBackend..."
kubectl apply -f "$ROOT/manifests/llm-backend.yaml"

log "Applying Gateway (GatewayClass: agentgateway)..."
kubectl apply -f "$ROOT/manifests/gateway.yaml"

log "Waiting for GatewayClass to be accepted..."
kubectl wait gatewayclass agentgateway \
  --for=condition=Accepted \
  --timeout=60s 2>/dev/null || log "GatewayClass not yet Accepted — continuing"

log "Applying HTTPRoute..."
kubectl apply -f "$ROOT/manifests/httproute.yaml"
log "Gateway API resources applied"

# ─── 7. kagent CRDs ──────────────────────────────────────────────────────────
log "Installing kagent CRDs (${KAGENT_VERSION})..."
helm upgrade --install kagent-crds \
  oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds \
  --namespace kagent \
  --create-namespace \
  --version "$KAGENT_VERSION" \
  --timeout 5m \
  --wait
log "kagent CRDs installed"

# ─── 8. kagent — LLM routed through Gateway API ──────────────────────────────
# Traffic path:
#   kagent → Gateway Service (agentgateway-proxy:80) → HTTPRoute /v1 → AgentgatewayBackend → OpenAI
GATEWAY_URL="http://agentgateway-proxy.agentgateway-system.svc.cluster.local/v1"

log "Installing kagent (${KAGENT_VERSION}), baseURL=${GATEWAY_URL}..."
helm upgrade --install kagent \
  oci://ghcr.io/kagent-dev/kagent/helm/kagent \
  --namespace kagent \
  --version "$KAGENT_VERSION" \
  --set "providers.default=openAI" \
  --set "providers.openAI.apiKey=${OPENAI_API_KEY}" \
  --set "providers.openAI.baseURL=${GATEWAY_URL}" \
  --set "agents.cilium-policy-agent.enabled=false" \
  --set "agents.cilium-manager-agent.enabled=false" \
  --set "agents.cilium-debug-agent.enabled=false" \
  --set "agents.istio-agent.enabled=false" \
  --set "agents.istio-policy-agent.enabled=false" \
  --set "agents.istio-manager-agent.enabled=false" \
  --timeout 10m \
  --wait
log "kagent installed"

# ─── Done ─────────────────────────────────────────────────────────────────────
log ""
log "=== Setup complete ==="
log ""
log "  kubectl get gateway,httproute -n agentgateway-system"
log "  kubectl get gatewayclass agentgateway"
log "  make test      — verify the deployment"
log "  make down      — destroy the cluster"
