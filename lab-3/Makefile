CONTEXT ?= kind-abox

.PHONY: help l3l1-deploy l3l2-deploy l3l3-deploy l3-down

help:
	@echo "Lab-3 targets:"
	@echo "  l3l1-deploy      Build + deploy level-1 (Beginners: KMCP + agents-cli)"
	@echo "  l3l2-deploy      Build + deploy level-2 (Experienced: MCP Apps)"
	@echo "  l3l3-deploy      Build + deploy level-3 (Max: Sampling + Elicitation)"
	@echo "  l3l1-inspector   Open MCP Inspector against level-1 server"
	@echo "  l3l1-playground  Start google-agents-cli playground against level-1 server"
	@echo "  l3-down          Remove all level-1/2/3 resources from $(CONTEXT)"

l3l1-deploy:
	$(MAKE) -C level-1 deploy

l3l2-deploy:
	$(MAKE) -C level-2 deploy

l3l3-deploy:
	$(MAKE) -C level-3 deploy

l3l1-inspector:
	$(MAKE) -C level-1 inspector

l3l1-playground:
	$(MAKE) -C level-1 playground

l3-down:
	$(MAKE) -C level-3 teardown
	$(MAKE) -C level-2 teardown
	$(MAKE) -C level-1 teardown
