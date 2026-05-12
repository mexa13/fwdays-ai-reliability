ABOX_DIR ?= $(shell cd ../../.. && find . -name "abox" -type d 2>/dev/null | head -1)
CONTEXT  ?= kind-abox

.PHONY: deploy status watch

deploy:
	@if [ -z "$(ABOX_DIR)" ]; then \
	  echo "ERROR: abox directory not found. Set ABOX_DIR=/path/to/abox"; \
	  exit 1; \
	fi
	@echo "==> Copying manifests to $(ABOX_DIR)/releases/..."
	cp releases/mcp-server.yaml $(ABOX_DIR)/releases/lab2-mcp-server.yaml
	cp releases/agent.yaml      $(ABOX_DIR)/releases/lab2-agent.yaml
	@echo "==> Pushing via abox GitOps..."
	cd $(ABOX_DIR) && make push
	@echo "==> Watch reconciliation:"
	@echo "    make watch"

status:
	kubectl --context $(CONTEXT) get kustomization releases -n flux-system
	kubectl --context $(CONTEXT) get agent,mcpserver -n kagent

watch:
	kubectl --context $(CONTEXT) get kustomization releases -n flux-system -w

gitlessops:
	@echo "==> GitLessOps: push manifests as OCI artifact without git push"
	@echo "    flux push artifact oci://ghcr.io/<your-org>/abox/releases:<tag> \\"
	@echo "      --path=$(ABOX_DIR)/releases \\"
	@echo "      --source=oci://ghcr.io/<your-org>/abox/releases:<tag> \\"
	@echo "      --revision=<tag>"
