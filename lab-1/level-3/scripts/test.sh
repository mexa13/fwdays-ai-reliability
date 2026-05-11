#!/bin/bash
set -euo pipefail

CLUSTER_NAME="lab1-l3"
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

# ─── 2. Gateway API CRDs ──────────────────────────────────────────────────────
kubectl get crd gateways.gateway.networking.k8s.io >/dev/null 2>&1 \
  && pass "Gateway API CRDs installed" \
  || fail "Gateway API CRDs missing"

# ─── 3. GatewayClass ──────────────────────────────────────────────────────────
GC_STATUS=$(kubectl get gatewayclass agentgateway \
  -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}' 2>/dev/null || echo "Unknown")
[[ "$GC_STATUS" == "True" ]] \
  && pass "GatewayClass 'agentgateway' Accepted" \
  || fail "GatewayClass 'agentgateway' status: ${GC_STATUS}"

# ─── 4. Gateway ───────────────────────────────────────────────────────────────
GW_STATUS=$(kubectl get gateway agentgateway-proxy -n "$NS_AGW" \
  -o jsonpath='{.status.conditions[?(@.type=="Programmed")].status}' 2>/dev/null || echo "Unknown")
[[ "$GW_STATUS" == "True" ]] \
  && pass "Gateway 'agentgateway-proxy' Programmed" \
  || fail "Gateway Programmed status: ${GW_STATUS} (may still be reconciling)"

# ─── 5. HTTPRoute ─────────────────────────────────────────────────────────────
HR_STATUS=$(kubectl get httproute openai-route -n "$NS_AGW" \
  -o jsonpath='{.status.parents[0].conditions[?(@.type=="Accepted")].status}' 2>/dev/null || echo "Unknown")
[[ "$HR_STATUS" == "True" ]] \
  && pass "HTTPRoute 'openai-route' Accepted by Gateway" \
  || fail "HTTPRoute Accepted status: ${HR_STATUS} (may still be reconciling)"

# ─── 6. agentgateway pods ─────────────────────────────────────────────────────
log "Waiting for agentgateway pods..."
kubectl wait pods \
  --namespace "$NS_AGW" \
  --selector "app.kubernetes.io/name=agentgateway" \
  --for=condition=Ready \
  --timeout="${TIMEOUT}s" 2>/dev/null \
  && pass "agentgateway pods Ready" \
  || fail "agentgateway pods not Ready (timeout ${TIMEOUT}s)"

# ─── 7. kagent pods ───────────────────────────────────────────────────────────
log "Waiting for kagent pods..."
kubectl wait pods \
  --namespace "$NS_KAGENT" \
  --selector "app.kubernetes.io/name=kagent" \
  --for=condition=Ready \
  --timeout="${TIMEOUT}s" 2>/dev/null \
  && pass "kagent pods Ready" \
  || fail "kagent pods not Ready (timeout ${TIMEOUT}s)"

# ─── 8. Chat completions via Gateway API ─────────────────────────────────────
GW_SVC=$(kubectl get svc -n "$NS_AGW" -o name 2>/dev/null \
  | grep -i "proxy\|gateway-proxy" | head -1 | sed 's|service/||')

if [[ -n "$GW_SVC" ]]; then
  log "Port-forwarding Gateway service '${GW_SVC}' → localhost:8080..."
  kubectl port-forward "svc/${GW_SVC}" -n "$NS_AGW" 8080:80 &
  PF_PID=$!
  sleep 3

  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Reply with just: OK"}]}' \
    2>/dev/null || echo "000")

  if [[ "$HTTP_CODE" == "200" ]]; then
    pass "Chat completions via Gateway API: HTTP 200"
  else
    fail "Gateway returned HTTP ${HTTP_CODE}"
  fi

  kill "$PF_PID" 2>/dev/null || true
else
  fail "Gateway Service not found — run: kubectl get svc -n ${NS_AGW}"
fi

# ─── 9. kagent agents ─────────────────────────────────────────────────────────
AGENT_COUNT=$(kubectl get agents -n "$NS_KAGENT" --no-headers 2>/dev/null | wc -l | tr -d ' ')
[[ "$AGENT_COUNT" -gt 0 ]] \
  && pass "Found ${AGENT_COUNT} agent(s) in namespace '${NS_KAGENT}'" \
  || fail "No agents found"

kubectl get agents -n "$NS_KAGENT" 2>/dev/null || true

echo ""
log "=== Test complete ==="
log ""
log "Full Gateway API status:"
kubectl get gateway,httproute -n "$NS_AGW"
