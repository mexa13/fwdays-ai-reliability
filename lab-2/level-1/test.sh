#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-kind-abox}"

echo "==> Checking MCPServer..."
kubectl --context "${CONTEXT}" get mcpserver fetch-mcp -n kagent -o wide

echo ""
echo "==> Checking MCPServer pod..."
kubectl --context "${CONTEXT}" get pods -n kagent -l app.kubernetes.io/name=fetch-mcp 2>/dev/null || \
  kubectl --context "${CONTEXT}" get pods -n kagent | grep fetch-mcp || true

echo ""
echo "==> Checking Agent..."
kubectl --context "${CONTEXT}" get agent web-researcher -n kagent -o wide

echo ""
echo "==> Checking ModelConfig..."
kubectl --context "${CONTEXT}" get modelconfig default-model-config -n kagent -o wide

echo ""
echo "==> Checking Agent pod logs (last 10 lines)..."
POD=$(kubectl --context "${CONTEXT}" get pods -n kagent -l app.kubernetes.io/name=web-researcher \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "${POD}" ]; then
  kubectl --context "${CONTEXT}" logs -n kagent "${POD}" --tail=10 2>/dev/null || true
else
  echo "(pod not found yet)"
fi

echo ""
echo "==> Test complete. Open UI to chat with the web-researcher agent:"
echo "    kubectl --context ${CONTEXT} port-forward -n kagent svc/kagent-ui 8080:8080"
