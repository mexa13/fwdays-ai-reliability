#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-kind-abox}"
MANIFESTS_DIR="$(dirname "$0")/manifests"
PROVIDER="${PROVIDER:-openai}"

echo "==> Checking cluster connection..."
kubectl --context "${CONTEXT}" cluster-info --request-timeout=5s >/dev/null

echo ""
echo "==> Provider: ${PROVIDER}"
echo ""

case "${PROVIDER}" in
  openai)
    if [ -z "${OPENAI_API_KEY:-}" ]; then
      echo "ERROR: Set OPENAI_API_KEY env var or pass it explicitly:"
      echo "  OPENAI_API_KEY=sk-... bash setup.sh"
      exit 1
    fi
    echo "==> Patching kagent-openai secret with OpenAI API key..."
    kubectl --context "${CONTEXT}" create secret generic kagent-openai \
      --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY}" \
      -n kagent --dry-run=client -o yaml | kubectl --context "${CONTEXT}" apply -f -
    ;;
  anthropic)
    if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
      echo "ERROR: Set ANTHROPIC_API_KEY env var:"
      echo "  ANTHROPIC_API_KEY=sk-ant-... PROVIDER=anthropic bash setup.sh"
      exit 1
    fi
    echo "==> Creating kagent-anthropic secret..."
    kubectl --context "${CONTEXT}" create secret generic kagent-anthropic \
      --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
      -n kagent --dry-run=client -o yaml | kubectl --context "${CONTEXT}" apply -f -

    echo "==> Applying Anthropic ModelConfig..."
    kubectl --context "${CONTEXT}" apply -f - <<EOF
apiVersion: kagent.dev/v1alpha2
kind: ModelConfig
metadata:
  name: default-model-config
  namespace: kagent
spec:
  provider: Anthropic
  model: claude-haiku-4-5-20251001
  apiKeySecret: kagent-anthropic
  apiKeySecretKey: ANTHROPIC_API_KEY
EOF
    ;;
  *)
    echo "ERROR: Unknown provider '${PROVIDER}'. Use: openai or anthropic"
    exit 1
    ;;
esac

if [ "${PROVIDER}" = "openai" ]; then
  echo "==> Applying OpenAI ModelConfig..."
  kubectl --context "${CONTEXT}" apply -f "${MANIFESTS_DIR}/02-modelconfig.yaml"
fi

echo "==> Deploying MCPServer..."
kubectl --context "${CONTEXT}" apply -f "${MANIFESTS_DIR}/03-mcp-server.yaml"

echo "==> Deploying Agent..."
kubectl --context "${CONTEXT}" apply -f "${MANIFESTS_DIR}/04-agent.yaml"

echo ""
echo "==> Waiting for MCPServer pod (up to 120s)..."
kubectl --context "${CONTEXT}" wait --for=condition=available \
  deployment/fetch-mcp -n kagent --timeout=120s 2>/dev/null || \
  echo "(still starting — check: kubectl --context ${CONTEXT} get pods -n kagent)"

echo ""
echo "==> Status:"
kubectl --context "${CONTEXT}" get agent,mcpserver -n kagent
echo ""
echo "==> Open Kagent UI:"
echo "    kubectl --context ${CONTEXT} port-forward -n kagent svc/kagent-ui 8080:8080"
echo "    http://localhost:8080"
