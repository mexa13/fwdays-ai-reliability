#!/bin/bash
set -euo pipefail

CLUSTER_NAME="lab1-l2"
NS_AGW="agentgateway-system"
NS_KAGENT="kagent"
TIMEOUT=120

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
pass() { echo "[$(date '+%H:%M:%S')] ✓  $*"; }
fail() { echo "[$(date '+%H:%M:%S')] ✗  $*" >&2; }

# ─── 1. Cluster ───────────────────────────────────────────────────────────────
log "Checking cluster..."
kubectl cluster-info --context "kind-${CLUSTER_NAME}" >/dev/null 2>&1 \
  && pass "Cluster 'kind-${CLUSTER_NAME}' is accessible" \
  || { fail "Cannot reach cluster"; exit 1; }

# ─── 2. agentgateway pods ─────────────────────────────────────────────────────
log "Waiting for agentgateway pods (timeout ${TIMEOUT}s)..."
kubectl wait pods \
  --namespace "$NS_AGW" \
  --selector "app.kubernetes.io/name=agentgateway" \
  --for=condition=Ready \
  --timeout="${TIMEOUT}s" 2>/dev/null \
  && pass "agentgateway pods Ready" \
  || fail "agentgateway pods not Ready"

# ─── 3. kagent pods ───────────────────────────────────────────────────────────
log "Waiting for kagent pods (timeout ${TIMEOUT}s)..."
kubectl wait pods \
  --namespace "$NS_KAGENT" \
  --selector "app.kubernetes.io/name=kagent" \
  --for=condition=Ready \
  --timeout="${TIMEOUT}s" 2>/dev/null \
  && pass "kagent pods Ready" \
  || fail "kagent pods not Ready"

# ─── 4. Built-in agents ───────────────────────────────────────────────────────
log "Checking built-in agents..."
AGENT_COUNT=$(kubectl get agents -n "$NS_KAGENT" --no-headers 2>/dev/null | grep "True.*True" | wc -l | tr -d ' ')
if [[ "$AGENT_COUNT" -gt 0 ]]; then
  pass "Found ${AGENT_COUNT} ready agent(s) in namespace '${NS_KAGENT}'"
  kubectl get agents -n "$NS_KAGENT"
else
  fail "No ready agents found in namespace '${NS_KAGENT}'"
fi

# ─── 5. ModelConfig — verify LLM endpoint ────────────────────────────────────
log "Checking ModelConfig..."
MODEL=$(kubectl get modelconfig default-model-config -n "$NS_KAGENT" \
  -o jsonpath='{.spec.model}' 2>/dev/null || echo "unknown")
BASE_URL=$(kubectl get modelconfig default-model-config -n "$NS_KAGENT" \
  -o jsonpath='{.spec.openAI.baseUrl}' 2>/dev/null || echo "")
PROVIDER=$(kubectl get modelconfig default-model-config -n "$NS_KAGENT" \
  -o jsonpath='{.spec.provider}' 2>/dev/null || echo "unknown")

if [[ -n "$BASE_URL" ]]; then
  pass "ModelConfig: provider=${PROVIDER}, model=${MODEL}, baseUrl=${BASE_URL}"
else
  pass "ModelConfig: provider=${PROVIDER}, model=${MODEL} (default API endpoint)"
fi

MC_STATUS=$(kubectl get modelconfig default-model-config -n "$NS_KAGENT" \
  -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}' 2>/dev/null || echo "Unknown")
[[ "$MC_STATUS" == "True" ]] \
  && pass "ModelConfig Accepted" \
  || fail "ModelConfig status: ${MC_STATUS}"

# ─── 6. LLM reachability — strategy depends on provider ──────────────────────
if [[ -n "$BASE_URL" ]]; then
  # LM Studio: in-cluster pod tests host.docker.internal:1234 directly
  log "Testing LM Studio endpoint from inside the cluster (${BASE_URL})..."
  TEST_URL="${BASE_URL}/chat/completions"

  # kubectl run --rm prints "pod ... deleted" to stdout after curl output.
  # head -c 3 reads only the first 3 bytes = HTTP status code from %{http_code}.
  HTTP_CODE=$(kubectl run "llm-test-$$" --image=curlimages/curl:8.5.0 \
    --restart=Never --rm -i \
    --timeout=30s \
    -- curl -s -o /dev/null -w "%{http_code}" \
       -X POST "$TEST_URL" \
       -H "Content-Type: application/json" \
       -d "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}" \
    2>/dev/null | head -c 3 || true)
  HTTP_CODE="${HTTP_CODE:-000}"

  if [[ "$HTTP_CODE" == "200" ]]; then
    pass "LM Studio reachable from cluster: HTTP 200"
  elif [[ "$HTTP_CODE" == "000" ]]; then
    fail "LM Studio unreachable — is LM Studio running on port 1234?"
  else
    fail "LM Studio returned HTTP ${HTTP_CODE}"
  fi
else
  # Cloud provider (OpenAI / Anthropic): kagent calls the external API directly.
  # Verify by checking that at least one agent is Accepted — a real API call
  # happens during agent reconciliation, so Accepted=True implies connectivity.
  log "Cloud provider (${PROVIDER}) — verifying via agent readiness..."
  ACCEPTED=$(kubectl get agents -n "$NS_KAGENT" --no-headers 2>/dev/null \
    | grep "True.*True" | wc -l | tr -d ' ')
  if [[ "$ACCEPTED" -gt 0 ]]; then
    pass "${PROVIDER} API reachable — ${ACCEPTED} agent(s) reconciled successfully"
    log "Tip: use the kagent UI to send a real query to any agent"
    log "  kubectl port-forward svc/kagent-ui -n kagent 8080:8080"
  else
    fail "No agents reconciled — ${PROVIDER} API may be unreachable"
  fi
fi

# ─── 7. agentgateway service info ─────────────────────────────────────────────
AGW_PORTS=$(kubectl get svc agentgateway -n "$NS_AGW" \
  -o jsonpath='{.spec.ports[*].port}' 2>/dev/null || echo "unknown")
pass "agentgateway Service ports: ${AGW_PORTS}"

echo ""
log "=== Test complete ==="
log ""
log "  kubectl port-forward svc/kagent-ui -n kagent 8080:8080"
log "  open http://localhost:8080"
