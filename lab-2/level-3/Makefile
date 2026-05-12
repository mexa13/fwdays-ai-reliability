IMAGE    ?= ghcr.io/$(shell git config user.name | tr '[:upper:]' '[:lower:]' | tr ' ' '-')/reliability-mcp
TAG      ?= latest
CONTEXT  ?= kind-abox
ABOX_DIR ?= ../../../../abox

.PHONY: build push-image load test-local deploy gitlessops teardown

build:
	docker build -t $(IMAGE):$(TAG) mcp-server/

push-image: build
	docker push $(IMAGE):$(TAG)

# Load image directly into kind cluster (no registry needed for local dev)
load: build
	kind load docker-image $(IMAGE):$(TAG) --name abox
	@echo "==> Image loaded into kind-abox cluster"
	@echo "    Update manifests/mcp-server.yaml image to: $(IMAGE):$(TAG)"
	@echo "    Add imagePullPolicy: Never for local images"

test-local:
	@echo "==> Running MCP server locally on http://localhost:8000"
	cd mcp-server && pip install -r requirements.txt -q && \
	  python server.py --port 8000 --transport streamableHttp &
	@sleep 2
	@echo "==> Testing tools via HTTP..."
	curl -sf http://localhost:8000/mcp 2>/dev/null || echo "(use MCP client to connect)"

deploy: push-image
	@sed 's|ghcr.io/REPLACE_ORG|$(IMAGE)|g; s|:latest|:$(TAG)|g' \
	  manifests/mcp-server.yaml | kubectl --context $(CONTEXT) apply -f -
	kubectl --context $(CONTEXT) apply -f manifests/agent.yaml
	@echo "==> Deployed reliability-mcp + reliability-agent"

# GitLessOps: push manifests as OCI artifact to GHCR (no git push)
gitlessops: push-image
	@echo "==> GitLessOps: publishing manifests as OCI artifact..."
	@LATEST_TAG=$(shell cd $(ABOX_DIR) && git tag --list 'v*' | sort -V | tail -1 | sed 's/^v//'); \
	PATCH=$$(echo $${LATEST_TAG} | cut -d. -f3); \
	NEW_TAG=v$$(echo $${LATEST_TAG} | cut -d. -f1-2).$$(( $${PATCH} + 1 )); \
	echo "New tag: $${NEW_TAG}"; \
	cp manifests/mcp-server.yaml $(ABOX_DIR)/releases/lab2-mcp-server.yaml; \
	cp manifests/agent.yaml $(ABOX_DIR)/releases/lab2-agent.yaml; \
	sed -i '' "s|ghcr.io/REPLACE_ORG/reliability-mcp:latest|$(IMAGE):$(TAG)|g" \
	  $(ABOX_DIR)/releases/lab2-mcp-server.yaml; \
	flux push artifact \
	  oci://ghcr.io/den-vasyliev/abox/releases:$${NEW_TAG} \
	  --path=$(ABOX_DIR)/releases \
	  --source=local \
	  --revision=$${NEW_TAG} && \
	echo "==> OCI artifact pushed. Cluster will reconcile within ~1 minute."

teardown:
	kubectl --context $(CONTEXT) delete agent reliability-agent -n kagent --ignore-not-found
	kubectl --context $(CONTEXT) delete mcpserver reliability-mcp -n kagent --ignore-not-found
