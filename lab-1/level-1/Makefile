.PHONY: help install run run-multi test stop

help:
	@echo "Level 1 — AgentGateway Standalone"
	@echo ""
	@echo "  install    Install agentgateway binary"
	@echo "  run        Start gateway with OpenAI config (requires OPENAI_API_KEY)"
	@echo "  run-multi  Start multi-provider gateway (requires OPENAI_API_KEY + ANTHROPIC_API_KEY)"
	@echo "  test       Send a test chat completion request"
	@echo "  stop       Kill running agentgateway process"
	@echo ""
	@echo "Admin UI: http://localhost:15000/ui/"

install:
	curl -sL https://agentgateway.dev/install | bash

run:
	@if [ -z "$${OPENAI_API_KEY:-}" ]; then \
		echo "ERROR: OPENAI_API_KEY is not set"; \
		exit 1; \
	fi
	agentgateway -f config.yaml

run-multi:
	@if [ -z "$${OPENAI_API_KEY:-}" ]; then \
		echo "ERROR: OPENAI_API_KEY is not set"; \
		exit 1; \
	fi
	agentgateway -f config.anthropic.yaml

test:
	@echo "Testing chat completions endpoint..."
	curl -s http://localhost:4000/v1/chat/completions \
		-H "Content-Type: application/json" \
		-d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Say hello in one word"}]}' \
		| jq .

test-ui:
	@echo "Checking UI availability..."
	curl -sf http://localhost:15000/ui/ > /dev/null && echo "UI is up: http://localhost:15000/ui/" || echo "UI not available"

stop:
	@pkill agentgateway 2>/dev/null && echo "agentgateway stopped" || echo "agentgateway not running"
