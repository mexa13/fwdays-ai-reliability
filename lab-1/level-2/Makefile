.PHONY: help run run-anthropic run-lmstudio test down ui logs status

help:
	@echo "Level 2 — agentgateway + kagent on Kubernetes (Helm)"
	@echo ""
	@echo "  run              Deploy with OpenAI     (requires OPENAI_API_KEY)"
	@echo "  run-anthropic    Deploy with Anthropic  (requires ANTHROPIC_API_KEY)"
	@echo "  run-lmstudio     Deploy with LM Studio  (LM Studio must run on port 1234)"
	@echo ""
	@echo "  test      Verify deployment and run integration checks"
	@echo "  down      Destroy the cluster and all resources"
	@echo "  ui        Port-forward kagent UI to http://localhost:8080"
	@echo "  logs      Tail agentgateway logs"
	@echo "  status    Show pods / services / agents"

run:
	@bash scripts/setup.sh

run-anthropic:
	@LLM_PROVIDER=anthropic bash scripts/setup.sh

run-lmstudio:
	@LLM_PROVIDER=lmstudio bash scripts/setup.sh

test:
	@bash scripts/test.sh

down:
	@bash scripts/teardown.sh

ui:
	@echo "kagent UI → http://localhost:8080"
	kubectl port-forward svc/kagent-ui -n kagent 8080:8080

logs:
	kubectl logs -n agentgateway-system -l app.kubernetes.io/name=agentgateway -f --tail=100

status:
	@echo "=== Nodes ==="
	kubectl get nodes
	@echo ""
	@echo "=== Pods ==="
	kubectl get pods -A
	@echo ""
	@echo "=== Agents ==="
	kubectl get agents -n kagent 2>/dev/null || echo "(no agents)"
	@echo ""
	@echo "=== Services ==="
	kubectl get svc -n agentgateway-system
	kubectl get svc -n kagent
