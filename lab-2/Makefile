CONTEXT ?= kind-abox

.PHONY: ui status level-1 level-2 level-3

# Open Kagent UI
ui:
	@echo "Opening Kagent UI → http://localhost:8080"
	kubectl --context $(CONTEXT) port-forward -n kagent svc/kagent-ui 8080:8080

# Show cluster status
status:
	@echo "=== Pods ==="
	kubectl --context $(CONTEXT) get pods -n kagent
	@echo ""
	@echo "=== Agents ==="
	kubectl --context $(CONTEXT) get agents -n kagent
	@echo ""
	@echo "=== MCPServers ==="
	kubectl --context $(CONTEXT) get mcpservers -n kagent 2>/dev/null || echo "(none)"
	@echo ""
	@echo "=== RemoteMCPServers ==="
	kubectl --context $(CONTEXT) get remotemcpservers -n kagent 2>/dev/null || echo "(none)"
	@echo ""
	@echo "=== ModelConfig ==="
	kubectl --context $(CONTEXT) get modelconfigs -n kagent

# Run individual levels
level-1:
	$(MAKE) -C level-1 setup CONTEXT=$(CONTEXT)

level-2:
	$(MAKE) -C level-2 status CONTEXT=$(CONTEXT)

level-3:
	$(MAKE) -C level-3 deploy CONTEXT=$(CONTEXT)
