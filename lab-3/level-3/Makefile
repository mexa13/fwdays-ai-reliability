IMAGE   ?= ghcr.io/$(shell git config user.name | tr '[:upper:]' '[:lower:]' | tr ' ' '-')/reliability-mcp-sampling
TAG     ?= latest
CONTEXT ?= kind-abox

INSPECTOR_VERSION ?= 0.21.2

.PHONY: help install run-local build push-image load deploy port-forward inspector teardown

help:
	@echo "level-3 (Sampling + Elicitation) targets:"
	@echo "  install        pip install fastmcp into a local venv"
	@echo "  run-local      run the MCP server on http://localhost:8000"
	@echo "  build          docker build the server image"
	@echo "  push-image     docker push the server image"
	@echo "  load           kind load the image into abox"
	@echo "  deploy         push + apply MCPServer + Agent"
	@echo "  port-forward   forward svc/reliability-mcp-sampling:8000"
	@echo "  inspector      run MCP Inspector against the server"
	@echo "  teardown       remove resources from $(CONTEXT)"

install:
	python3 -m venv .venv && \
	  ./.venv/bin/pip install -q -U pip && \
	  ./.venv/bin/pip install -q -r mcp-server/requirements.txt

run-local:
	./.venv/bin/python mcp-server/server.py --port 8000 --transport streamableHttp

build:
	docker build -t $(IMAGE):$(TAG) mcp-server/

push-image: build
	docker push $(IMAGE):$(TAG)

load: build
	kind load docker-image $(IMAGE):$(TAG) --name abox

deploy: push-image
	@sed 's|ghcr.io/REPLACE_ORG/reliability-mcp-sampling:latest|$(IMAGE):$(TAG)|g' \
	  manifests/mcp-server.yaml | kubectl --context $(CONTEXT) apply -f -
	kubectl --context $(CONTEXT) apply -f manifests/agent.yaml
	@echo "==> Deployed reliability-mcp-sampling + reliability-agent-sampling"

port-forward:
	kubectl --context $(CONTEXT) port-forward -n kagent svc/reliability-mcp-sampling 8000:8000

inspector:
	npx -y @modelcontextprotocol/inspector@$(INSPECTOR_VERSION) \
	  --transport streamable-http \
	  --server-url http://localhost:8000/mcp

teardown:
	kubectl --context $(CONTEXT) delete agent reliability-agent-sampling -n kagent --ignore-not-found
	kubectl --context $(CONTEXT) delete remotemcpserver reliability-mcp-sampling -n kagent --ignore-not-found
	kubectl --context $(CONTEXT) delete mcpserver reliability-mcp-sampling -n kagent --ignore-not-found
