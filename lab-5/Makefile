CONTEXT ?= kind-abox

.PHONY: help l5l1-deploy l5l2-deploy l5l3-deploy l5-extras-apikey l5-extras-guardrails l5-down

help:
	@echo "Lab-5 targets (Sandboxing & Observability):"
	@echo "  l5l1-deploy           Build + deploy level-1 (Beginner: Agent Sandbox + NetworkPolicy example)"
	@echo "  l5l2-deploy           Build + deploy level-2 (Experienced: Phoenix + Sandbox metrics + MCP tracing)"
	@echo "  l5l3-deploy           Build + deploy level-3 (Max: agentgateway → Phoenix + Sandbox SDK demo)"
	@echo "  l5-extras-apikey      Apply the agentgateway API key extra"
	@echo "  l5-extras-guardrails  Apply the agentgateway webhook guardrails extra"
	@echo "  l5-down               Remove all level-1/2/3 + extras from $(CONTEXT)"

l5l1-deploy:
	$(MAKE) -C level-1 deploy

l5l2-deploy:
	$(MAKE) -C level-2 deploy

l5l3-deploy:
	$(MAKE) -C level-3 deploy

l5-extras-apikey:
	$(MAKE) -C extras apikey-apply

l5-extras-guardrails:
	$(MAKE) -C extras guardrails-apply

l5-down:
	$(MAKE) -C level-3 teardown
	$(MAKE) -C level-2 teardown
	$(MAKE) -C level-1 teardown
	$(MAKE) -C extras teardown-all  2>/dev/null || true
