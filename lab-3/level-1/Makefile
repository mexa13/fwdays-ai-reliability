IMAGE   ?= ghcr.io/$(shell git config user.name | tr '[:upper:]' '[:lower:]' | tr ' ' '-')/reliability-mcp-v2
TAG     ?= latest
CONTEXT ?= kind-abox

INSPECTOR_VERSION ?= 0.21.2
AGENTS_CLI_VERSION ?= latest

.PHONY: help install run-local build push-image load deploy port-forward inspector playground teardown

help:
	@echo "Targets:"
	@echo "  install        pip install fastmcp + httpx into a local venv"
	@echo "  run-local      run the MCP server on http://localhost:8000"
	@echo "  build          docker build the server image"
	@echo "  push-image     docker push the server image (needs registry auth)"
	@echo "  load           kind load image into the abox cluster (no registry)"
	@echo "  deploy         build, push (or load), apply MCPServer + Agent"
	@echo "  port-forward   open port-forward to the in-cluster MCP server"
	@echo "  inspector      run @modelcontextprotocol/inspector against the server"
	@echo "  playground     run google-agents-cli playground against the server"
	@echo "  teardown       remove Agent + MCPServer from the cluster"

install:
	python3 -m venv .venv && \
	  ./.venv/bin/pip install -q -U pip && \
	  ./.venv/bin/pip install -q -r mcp-server/requirements.txt
	@echo "==> venv ready. Activate: source .venv/bin/activate"

run-local:
	./.venv/bin/python mcp-server/server.py --port 8000 --transport streamableHttp

build:
	docker build -t $(IMAGE):$(TAG) mcp-server/

push-image: build
	docker push $(IMAGE):$(TAG)

load: build
	kind load docker-image $(IMAGE):$(TAG) --name abox
	@echo "==> Image loaded into kind-abox cluster as $(IMAGE):$(TAG)"
	@echo "    Set imagePullPolicy: Never in manifests/mcp-server.yaml if pulling fails"

deploy: push-image
	@sed 's|ghcr.io/REPLACE_ORG/reliability-mcp-v2:latest|$(IMAGE):$(TAG)|g' \
	  manifests/mcp-server.yaml | kubectl --context $(CONTEXT) apply -f -
	kubectl --context $(CONTEXT) apply -f manifests/agent.yaml
	@echo "==> Deployed reliability-mcp-v2 + reliability-agent-v2 to $(CONTEXT)"

# Open a port-forward in the foreground. Stop with Ctrl-C.
port-forward:
	kubectl --context $(CONTEXT) port-forward -n kagent svc/reliability-mcp-v2 8000:8000

# Run the inspector. Requires port-forward in another terminal.
inspector:
	@echo "==> Make sure 'make port-forward' is running in another terminal"
	npx -y @modelcontextprotocol/inspector@$(INSPECTOR_VERSION) \
	  --transport streamable-http \
	  --server-url http://localhost:8000/mcp

# Run google-agents-cli playground against the in-cluster MCP server.
# Requires `uv` (pip install uv) and 'make port-forward' in another terminal.
# agents-cli wraps `adk web .` and discovers the agent via pyproject.toml's
# [tool.agents-cli] section, so we must cd into the agents-cli project root.
playground:
	@echo "==> Make sure 'make port-forward' is running in another terminal"
	cd agents-cli && uvx google-agents-cli@$(AGENTS_CLI_VERSION) playground

teardown:
	kubectl --context $(CONTEXT) delete agent reliability-agent-v2 -n kagent --ignore-not-found
	kubectl --context $(CONTEXT) delete remotemcpserver reliability-mcp-v2 -n kagent --ignore-not-found
	kubectl --context $(CONTEXT) delete mcpserver reliability-mcp-v2 -n kagent --ignore-not-found
