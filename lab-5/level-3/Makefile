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

port-forward-agentgateway:
	# The Gateway Service name comes from lab-1/level-3 (`agentgateway-proxy`).
	# Override $(GATEWAY_SVC) / $(GATEWAY_PORT) if your topology differs.
	kubectl --context $(CONTEXT) -n agentgateway-system port-forward \
	  svc/agentgateway-proxy 3000:80

# Fires a request through agentgateway. Assumes lab-1/level-3 is up and that
# you've already exported OPENAI_API_KEY (the backend the gateway routes to).
test-trace:
	@curl -fsS http://localhost:3000/v1/chat/completions \
	  -H 'Content-Type: application/json' \
	  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hello from lab-5"}]}' \
	  | jq -r '.choices[0].message.content // .'

# ─── SDK demo (local) ─────────────────────────────────────────────────────────

install-local:
	python3 -m venv .venv && \
	  ./.venv/bin/pip install -q -U pip && \
	  ./.venv/bin/pip install -q -r sdk-demo/requirements.txt

run-local:
	PHOENIX_COLLECTOR_ENDPOINT=$${PHOENIX_COLLECTOR_ENDPOINT:-http://localhost:6006} \
	  ./.venv/bin/python sdk-demo/code_interpreter_agent.py

# ─── Combined deploy ─────────────────────────────────────────────────────────

deploy: deploy-tracing
	@echo "==> level-3 wired: agentgateway tracing → Collector → Phoenix."
	@echo "    Run the SDK demo locally:  make install-local && make run-local"

# ─── Teardown ─────────────────────────────────────────────────────────────────

teardown-tracing:
	kubectl --context $(CONTEXT) delete -f manifests/agentgateway-tracing.yaml --ignore-not-found

teardown: teardown-tracing
