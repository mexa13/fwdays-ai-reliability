#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LOG=/tmp/lab1-l2-setup.log
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date '+%H:%M:%S')] $*"; }
err() { echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2; exit 1; }

# ─── Prerequisites ────────────────────────────────────────────────────────────
[[ -z "${OPENAI_API_KEY:-}" ]] && err "OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY=sk-..."

for tool in kind kubectl helm; do
  command -v "$tool" >/dev/null 2>&1 || err "$tool is not installed"
done

CLUSTER_NAME="lab1-l2"
AGENTGW_VERSION="v1.1.0"
KAGENT_VERSION="0.9.2"

log "=== Lab 1 Level 2 — Setup ==="

# ─── 1. KinD cluster ─────────────────────────────────────────────────────────
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  log "Cluster '${CLUSTER_NAME}' already exists — skipping creation"
else
  log "Creating KinD cluster '${CLUSTER_NAME}'..."
  kind create cluster --name "$CLUSTER_NAME" --config "$ROOT/kind-config.yaml"
fi

kubectl cluster-info --context "kind-${CLUSTER_NAME}"
log "Cluster ready"

# ─── 2. AgentGateway CRDs ────────────────────────────────────────────────────
log "Installing agentgateway CRDs (${AGENTGW_VERSION})..."
helm upgrade --install agentgateway-crds \
  oci://cr.agentgateway.dev/charts/agentgateway-crds \
  --namespace agentgateway-system \
  --create-namespace \
  --version "$AGENTGW_VERSION" \
  --timeout 5m \
  --wait
log "agentgateway CRDs installed"

# ─── 3. AgentGateway ─────────────────────────────────────────────────────────
log "Installing agentgateway (${AGENTGW_VERSION})..."
helm upgrade --install agentgateway \
  oci://cr.agentgateway.dev/charts/agentgateway \
  --namespace agentgateway-system \
  --version "$AGENTGW_VERSION" \
  --timeout 5m \
  --wait
log "agentgateway installed"

# ─── 4. LLM API key Secret ───────────────────────────────────────────────────
log "Creating Secret 'openai-secret'..."
kubectl create secret generic openai-secret \
  --namespace agentgateway-system \
  --from-literal="Authorization=${OPENAI_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -
log "Secret created"

# ─── 5. AgentgatewayBackend CRD ──────────────────────────────────────────────
log "Applying AgentgatewayBackend (openai)..."
kubectl apply -f "$ROOT/manifests/llm-backend.yaml"
log "AgentgatewayBackend applied"

# ─── 6. kagent CRDs ──────────────────────────────────────────────────────────
log "Installing kagent CRDs (${KAGENT_VERSION})..."
helm upgrade --install kagent-crds \
  oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds \
  --namespace kagent \
  --create-namespace \
  --version "$KAGENT_VERSION" \
  --timeout 5m \
  --wait
log "kagent CRDs installed"

# ─── 7. kagent — LLM routed through agentgateway ─────────────────────────────
# Traffic path: kagent → agentgateway Service (ClusterIP:80/v1) → OpenAI
AGENTGW_URL="http://agentgateway.agentgateway-system.svc.cluster.local/v1"

log "Installing kagent (${KAGENT_VERSION}), baseURL=${AGENTGW_URL}..."
helm upgrade --install kagent \
  oci://ghcr.io/kagent-dev/kagent/helm/kagent \
  --namespace kagent \
  --version "$KAGENT_VERSION" \
  --set "providers.default=openAI" \
  --set "providers.openAI.apiKey=${OPENAI_API_KEY}" \
  --set "providers.openAI.baseURL=${AGENTGW_URL}" \
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
log "  kubectl get pods -A"
log "  kubectl get agents -n kagent"
log "  make test      — run integration checks"
log "  make down      — destroy the cluster"
