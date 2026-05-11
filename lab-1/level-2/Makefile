.PHONY: help run test down ui logs status

help:
	@echo "Level 2 — agentgateway + kagent on Kubernetes (Helm)"
	@echo ""
	@echo "  run       Create KinD cluster and deploy all components"
	@echo "  test      Verify deployment and run integration checks"
	@echo "  down      Destroy the cluster and all resources"
	@echo "  ui        Port-forward kagent UI to http://localhost:8080"
	@echo "  logs      Tail agentgateway logs"
	@echo "  status    Show pods / services / agents"
	@echo ""
	@echo "Requires: export OPENAI_API_KEY=sk-..."

run:
	@bash scripts/setup.sh

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
