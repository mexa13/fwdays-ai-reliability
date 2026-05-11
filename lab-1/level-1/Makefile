.PHONY: help install run run-multi run-lmstudio test test-lmstudio test-ui stop

help:
	@echo "Level 1 — AgentGateway Standalone"
	@echo ""
	@echo "  install        Install agentgateway binary"
	@echo "  run            Start gateway with OpenAI config (requires OPENAI_API_KEY)"
	@echo "  run-multi      Start multi-provider gateway (requires OPENAI_API_KEY + ANTHROPIC_API_KEY)"
	@echo "  run-lmstudio   Start gateway with LM Studio (no API key needed, LM Studio must be running)"
	@echo "  test           Test OpenAI/Anthropic gateway  — port 4000"
	@echo "  test-lmstudio  Test LM Studio gateway         — port 3000"
	@echo "  stop           Kill running agentgateway process"
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

run-lmstudio:
	agentgateway -f config.lmstudio.yaml

test:
	@echo "Testing chat completions endpoint (port 4000)..."
	curl -s http://localhost:4000/v1/chat/completions \
		-H "Content-Type: application/json" \
		-d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Say hello in one word"}]}' \
		| jq .

test-lmstudio:
	@echo "Testing LM Studio gateway (port 3000)..."
	@echo "Override model with: make test-lmstudio MODEL=<name>"
	curl -s http://localhost:3000/v1/chat/completions \
		-H "Content-Type: application/json" \
		-d "{\"model\":\"$${MODEL:-google/gemma-4-e4b}\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one word\"}]}" \
		| jq .

test-ui:
	@echo "Checking UI availability..."
	curl -sf http://localhost:15000/ui/ > /dev/null && echo "UI is up: http://localhost:15000/ui/" || echo "UI not available"

stop:
	@pkill agentgateway 2>/dev/null && echo "agentgateway stopped" || echo "agentgateway not running"
