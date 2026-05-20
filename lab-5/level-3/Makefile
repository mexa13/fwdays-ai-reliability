CONTEXT     ?= kind-abox
NAMESPACE   ?= a5-sandbox

.PHONY: help install-local run-local deploy-tracing test-trace \
        port-forward-agentgateway teardown teardown-tracing

help:
	@echo "Lab-5 / level-3 targets (agentgateway → Phoenix + Sandbox SDK demo):"
	@echo "  deploy-tracing         apply AgentgatewayPolicy that routes frontend tracing → Phoenix"
	@echo "  install-local          venv with google-adk + agentic-sandbox-client + phoenix-otel"
	@echo "  run-local              python code_interpreter_agent.py (uses your kubeconfig)"
	@echo "  test-trace             curl the agentgateway with a sample chat to generate a trace"
	@echo "  port-forward-agentgateway   svc → localhost so test-trace works from the laptop"
	@echo "  teardown               remove tracing policy"

# ─── agentgateway tracing wired to Phoenix ───────────────────────────────────

deploy-tracing:
	@if ! kubectl --context $(CONTEXT) -n phoenix get svc otel-collector >/dev/null 2>&1; then \
	  echo "[deploy-tracing] otel-collector not found in ns/phoenix — run 'make -C ../level-2 deploy-collector' first."; \
	  exit 1; \
	fi
	kubectl --context $(CONTEXT) apply -f manifests/agentgateway-tracing.yaml

GATEWAY_SVC  ?= agentgateway-external
GATEWAY_NS   ?= agentgateway-system
GATEWAY_PORT ?= 80
LOCAL_PORT   ?= 8080

port-forward-agentgateway:
	# Defaults match the abox stack (agentgateway-external on :80). For the
	# Gateway from lab-1/level-3 (`agentgateway-proxy`), override:
	#   make port-forward-agentgateway GATEWAY_SVC=agentgateway-proxy
	kubectl --context $(CONTEXT) -n $(GATEWAY_NS) port-forward \
	  svc/$(GATEWAY_SVC) $(LOCAL_PORT):$(GATEWAY_PORT)

# Sends a probe through the gateway. The route /api/version goes to the
# kagent-controller backend (HTTPRoute/kagent). Any request through the
# Gateway produces a frontend trace, regardless of backend.
test-trace:
	@echo "── GET /api/version through the gateway ──"
	@curl -fsS -o /dev/null -w 'HTTP %{http_code} in %{time_total}s\n' \
	  http://localhost:$(LOCAL_PORT)/api/version || true
	@echo "── HEAD / (UI root) ──"
	@curl -fsS -o /dev/null -w 'HTTP %{http_code} in %{time_total}s\n' \
	  -I http://localhost:$(LOCAL_PORT)/ || true
	@echo "==> Check Phoenix (port-forward 6006) — new spans should appear under a new project."

# ─── SDK demo (local) ─────────────────────────────────────────────────────────

install-local:
	python3 -m venv .venv && \
	  ./.venv/bin/pip install -q -U pip && \
	  ./.venv/bin/pip install -q -r sdk-demo/requirements.txt

run-local:
	PHOENIX_COLLECTOR_ENDPOINT=$${PHOENIX_COLLECTOR_ENDPOINT:-http://localhost:6006/v1/traces} \
	  ./.venv/bin/python sdk-demo/code_interpreter_agent.py

# ─── Combined deploy ─────────────────────────────────────────────────────────

deploy: deploy-tracing
	@echo "==> level-3 wired: agentgateway tracing → Collector → Phoenix."
	@echo "    Run the SDK demo locally:  make install-local && make run-local"

# ─── Teardown ─────────────────────────────────────────────────────────────────

teardown-tracing:
	kubectl --context $(CONTEXT) delete -f manifests/agentgateway-tracing.yaml --ignore-not-found

teardown: teardown-tracing
