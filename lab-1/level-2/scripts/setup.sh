#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LOG=/tmp/lab1-l2-setup.log
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date '+%H:%M:%S')] $*"; }
err() { echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2; exit 1; }

# ─── LLM Provider selection ───────────────────────────────────────────────────
# Supported values: openai | anthropic | lmstudio
# Usage:
#   LLM_PROVIDER=anthropic make run
#   LLM_PROVIDER=lmstudio  make run
LLM_PROVIDER="${LLM_PROVIDER:-openai}"

case "$LLM_PROVIDER" in
  openai)
    [[ -z "${OPENAI_API_KEY:-}" ]] && err "OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY=sk-..."
    ;;
  anthropic)
    [[ -z "${ANTHROPIC_API_KEY:-}" ]] && err "ANTHROPIC_API_KEY is not set. Run: export ANTHROPIC_API_KEY=sk-ant-..."
    ;;
  lmstudio)
    log "LM Studio selected — LM Studio must be running on port 1234"
    log "kagent will connect to host.docker.internal:1234 (bypasses agentgateway backend)"
    ;;
  *)
    err "Unknown LLM_PROVIDER '${LLM_PROVIDER}'. Supported: openai | anthropic | lmstudio"
    ;;
esac

# ─── Prerequisites ────────────────────────────────────────────────────────────
for tool in kind kubectl helm; do
  command -v "$tool" >/dev/null 2>&1 || err "$tool is not installed"
done

CLUSTER_NAME="lab1-l2"
AGENTGW_VERSION="v1.1.0"
KAGENT_VERSION="0.9.2"
AGENTGW_SVC="http://agentgateway.agentgateway-system.svc.cluster.local/v1"

log "=== Lab 1 Level 2 — Setup (provider: ${LLM_PROVIDER}) ==="

# ─── 1. KinD cluster ─────────────────────────────────────────────────────────
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  log "Cluster '${CLUSTER_NAME}' already exists — skipping creation"
else
  log "Creating KinD cluster '${CLUSTER_NAME}'..."
  kind create cluster --name "$CLUSTER_NAME" --config "$ROOT/kind-config.yaml"
fi

kubectl cluster-info --context "kind-${CLUSTER_NAME}"
log "Cluster ready"

# ─── 2. agentgateway CRDs ────────────────────────────────────────────────────
log "Installing agentgateway CRDs (${AGENTGW_VERSION})..."
helm upgrade --install agentgateway-crds \
  oci://cr.agentgateway.dev/charts/agentgateway-crds \
  --namespace agentgateway-system \
  --create-namespace \
  --version "$AGENTGW_VERSION" \
  --timeout 5m \
  --wait
log "agentgateway CRDs installed"

# ─── 3. agentgateway ─────────────────────────────────────────────────────────
log "Installing agentgateway (${AGENTGW_VERSION})..."
helm upgrade --install agentgateway \
  oci://cr.agentgateway.dev/charts/agentgateway \
  --namespace agentgateway-system \
  --version "$AGENTGW_VERSION" \
  --timeout 5m \
  --wait
log "agentgateway installed"

# ─── 4. Provider-specific: Secret + AgentgatewayBackend ──────────────────────
case "$LLM_PROVIDER" in
  openai)
    log "Creating Secret 'openai-secret'..."
    kubectl create secret generic openai-secret \
      --namespace agentgateway-system \
      --from-literal="Authorization=${OPENAI_API_KEY}" \
      --dry-run=client -o yaml | kubectl apply -f -
    kubectl apply -f "$ROOT/manifests/llm-backend.yaml"
    log "AgentgatewayBackend (openai) applied"
    KAGENT_PROVIDER_FLAGS=(
      "--set" "providers.default=openAI"
      "--set" "providers.openAI.apiKey=${OPENAI_API_KEY}"
      "--set" "providers.openAI.baseURL=${AGENTGW_SVC}"
    )
    ;;
  anthropic)
    log "Creating Secret 'anthropic-secret'..."
    kubectl create secret generic anthropic-secret \
      --namespace agentgateway-system \
      --from-literal="x-api-key=${ANTHROPIC_API_KEY}" \
      --dry-run=client -o yaml | kubectl apply -f -
    kubectl apply -f "$ROOT/manifests/llm-backend-anthropic.yaml"
    log "AgentgatewayBackend (anthropic) applied"
    # kagent routes through agentgateway which forwards to Anthropic
    KAGENT_PROVIDER_FLAGS=(
      "--set" "providers.default=anthropic"
      "--set" "providers.anthropic.apiKey=${ANTHROPIC_API_KEY}"
    )
    ;;
  lmstudio)
    # LM Studio runs on the host; pods reach it via host.docker.internal.
    # The helm chart does not expose ModelConfig.spec.openAI.baseUrl — we patch it after install.
    LMSTUDIO_MODEL="${LMSTUDIO_MODEL:-google/gemma-4-e4b}"
    KAGENT_PROVIDER_FLAGS=(
      "--set" "providers.default=openAI"
      "--set" "providers.openAI.apiKey=lmstudio"
    )
    ;;
esac

# ─── 5. kagent CRDs ──────────────────────────────────────────────────────────
log "Installing kagent CRDs (${KAGENT_VERSION})..."
helm upgrade --install kagent-crds \
  oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds \
  --namespace kagent \
  --create-namespace \
  --version "$KAGENT_VERSION" \
  --timeout 5m \
  --wait
log "kagent CRDs installed"

# ─── 6. kagent ───────────────────────────────────────────────────────────────
log "Installing kagent (${KAGENT_VERSION})..."
helm upgrade --install kagent \
  oci://ghcr.io/kagent-dev/kagent/helm/kagent \
  --namespace kagent \
  --version "$KAGENT_VERSION" \
  "${KAGENT_PROVIDER_FLAGS[@]}" \
  --set "agents.cilium-policy-agent.enabled=false" \
  --set "agents.cilium-manager-agent.enabled=false" \
  --set "agents.cilium-debug-agent.enabled=false" \
  --set "agents.istio-agent.enabled=false" \
  --set "agents.istio-policy-agent.enabled=false" \
  --set "agents.istio-manager-agent.enabled=false" \
  --timeout 10m \
  --wait
log "kagent installed"

# ─── LM Studio: patch ModelConfig with baseUrl ───────────────────────────────
# The helm chart creates ModelConfig but does not set spec.openAI.baseUrl.
# We patch it directly so kagent routes LLM calls to the host machine.
if [[ "$LLM_PROVIDER" == "lmstudio" ]]; then
  log "Patching ModelConfig: baseUrl=http://host.docker.internal:1234/v1, model=${LMSTUDIO_MODEL}..."
  kubectl patch modelconfig default-model-config -n kagent --type=merge -p "{
    \"spec\": {
      \"model\": \"${LMSTUDIO_MODEL}\",
      \"openAI\": {
        \"baseUrl\": \"http://host.docker.internal:1234/v1\"
      }
    }
  }"
  log "ModelConfig patched"
fi

# ─── Done ─────────────────────────────────────────────────────────────────────
log ""
log "=== Setup complete (provider: ${LLM_PROVIDER}) ==="
log ""
log "  kubectl get pods -A"
log "  kubectl get agents -n kagent"
log "  make test      — run integration checks"
log "  make down      — destroy the cluster"
