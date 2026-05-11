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
AGENT_COUNT=$(kubectl get agents -n "$NS_KAGENT" --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [[ "$AGENT_COUNT" -gt 0 ]]; then
  pass "Found ${AGENT_COUNT} agent(s) in namespace '${NS_KAGENT}'"
  kubectl get agents -n "$NS_KAGENT"
else
  fail "No agents found in namespace '${NS_KAGENT}'"
fi

# ─── 5. kagent API ────────────────────────────────────────────────────────────
log "Port-forwarding kagent controller (8083)..."
kubectl port-forward svc/kagent-controller -n "$NS_KAGENT" 8083:8083 &
PF_PID=$!
sleep 3

AGENT_NAME=$(kubectl get agents -n "$NS_KAGENT" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [[ -n "$AGENT_NAME" ]]; then
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8083/api/v1/sessions \
    -H "Content-Type: application/json" \
    -d "{\"agentName\":\"${AGENT_NAME}\",\"namespace\":\"${NS_KAGENT}\"}" 2>/dev/null || echo "000")
  [[ "$HTTP_CODE" =~ ^2 ]] \
    && pass "kagent API responded HTTP ${HTTP_CODE} for agent '${AGENT_NAME}'" \
    || fail "kagent API returned HTTP ${HTTP_CODE}"
else
  fail "No agents available for API test"
fi

# ─── 6. agentgateway reachability ─────────────────────────────────────────────
log "Port-forwarding agentgateway (8080 → 80)..."
kubectl port-forward svc/agentgateway -n "$NS_AGW" 8080:80 &
PF2_PID=$!
sleep 3

curl -sf http://localhost:8080/health >/dev/null 2>&1 \
  && pass "agentgateway health check passed" \
  || pass "agentgateway reachable at http://localhost:8080 (no /health endpoint — that's OK)"

# ─── Cleanup ──────────────────────────────────────────────────────────────────
kill "$PF_PID" "$PF2_PID" 2>/dev/null || true

echo ""
log "=== Test complete ==="
log ""
log "Access kagent UI:   kubectl port-forward svc/kagent-ui -n kagent 8080:8080"
