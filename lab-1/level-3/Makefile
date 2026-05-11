.PHONY: help run test down ui gw-status logs status

help:
	@echo "Level 3 (Max) — agentgateway + kagent + Gateway API"
	@echo ""
	@echo "  run         Create KinD cluster and deploy all components + Gateway API"
	@echo "  test        Verify: GatewayClass, Gateway, HTTPRoute, agents, chat completions"
	@echo "  down        Destroy the cluster and all resources"
	@echo "  ui          Port-forward kagent UI to http://localhost:8080"
	@echo "  gw-status   Show Gateway API resource status"
	@echo "  logs        Tail agentgateway logs"
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

gw-status:
	@echo "=== GatewayClass ==="
	kubectl get gatewayclass agentgateway -o wide
	@echo ""
	@echo "=== Gateway ==="
	kubectl get gateway -n agentgateway-system -o wide
	@echo ""
	@echo "=== HTTPRoutes ==="
	kubectl get httproute -n agentgateway-system -o wide
	@echo ""
	@echo "=== AgentgatewayBackends ==="
	kubectl get agentgatewaybackend -n agentgateway-system 2>/dev/null || echo "(no backends)"

logs:
	kubectl logs -n agentgateway-system -l app.kubernetes.io/name=agentgateway -f --tail=100

status:
	@echo "=== Nodes ==="
	kubectl get nodes
	@echo ""
	@echo "=== Pods ==="
	kubectl get pods -A
	@echo ""
	@echo "=== Gateway API ==="
	kubectl get gateway,httproute -n agentgateway-system
	@echo ""
	@echo "=== Agents ==="
	kubectl get agents -n kagent 2>/dev/null || echo "(no agents)"
