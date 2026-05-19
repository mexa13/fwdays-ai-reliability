CONTEXT ?= kind-abox

.PHONY: help l4l1-deploy l4l2-deploy l4l3-deploy l4-down

help:
	@echo "Lab-4 targets (A2A — Agent-to-Agent):"
	@echo "  l4l1-deploy      Build + deploy level-1 (Beginner: own A2A agent + inventory + MCPG + qdrant)"
	@echo "  l4l2-deploy      Build + deploy level-2 (Experienced: coordinator ↔ worker over A2A)"
	@echo "  l4l3-deploy      Build + deploy level-3 (Max: heterogeneous team-lead + kagent peers)"
	@echo "  l4-down          Remove all level-1/2/3 resources from $(CONTEXT)"

l4l1-deploy:
	$(MAKE) -C level-1 deploy-all

l4l2-deploy:
	$(MAKE) -C level-2 deploy

l4l3-deploy:
	$(MAKE) -C level-3 deploy

l4-down:
	$(MAKE) -C level-3 teardown
	$(MAKE) -C level-2 teardown
	$(MAKE) -C level-1 teardown
