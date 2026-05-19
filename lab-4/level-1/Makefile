IMAGE       ?= ghcr.io/$(shell git config user.name | tr '[:upper:]' '[:lower:]' | tr ' ' '-')/reliability-a2a
TAG         ?= latest
CONTEXT     ?= kind-abox
NAMESPACE   ?= a2a-lab

# Where to clone the third-party stacks. Override to use an existing checkout.
WORK_DIR        ?= $(CURDIR)/.work
INVENTORY_DIR   ?= $(WORK_DIR)/agentregistry-inventory
MCPG_DIR        ?= $(WORK_DIR)/mcp-security-governance

.PHONY: help install run-local build push-image load deploy-agent \
        deploy-inventory deploy-discovery build-mcpg-images deploy-mcpg deploy-qdrant deploy-all \
        agent-card test-task \
        port-forward port-forward-inventory port-forward-mcpg port-forward-qdrant \
        inventory-list teardown teardown-agent teardown-inventory teardown-mcpg teardown-qdrant

help:
	@echo "Lab-4 / level-1 targets:"
	@echo "  install              python venv with a2a-sdk + starlette + uvicorn"
	@echo "  run-local            run the A2A agent on :9000"
	@echo "  build                docker build the agent image"
	@echo "  push-image           docker push the agent image"
	@echo "  load                 kind load image into abox (no registry needed)"
	@echo "  deploy-agent         apply agent Deployment + Service to $(CONTEXT)"
	@echo "  deploy-inventory     helm install agentregistry-inventory + apply DiscoveryConfig"
	@echo "  deploy-discovery     apply just the DiscoveryConfig CR (a2a-lab + kagent)"
	@echo "  build-mcpg-images    docker build + kind load MCPG controller & dashboard"
	@echo "  deploy-mcpg          helm install mcp-security-governance (builds images first)"
	@echo "  deploy-qdrant        helm install qdrant via the upstream chart"
	@echo "  deploy-all           agent + inventory + MCPG + qdrant in one go"
	@echo "  agent-card           curl the agent's Agent Card (requires port-forward)"
	@echo "  test-task            send a message via JSON-RPC and print the result"
	@echo "  port-forward         agent :9000 → localhost"
	@echo "  port-forward-inventory   inventory UI/API port-forward"
	@echo "  port-forward-mcpg        MCPG dashboard port-forward"
	@echo "  port-forward-qdrant      qdrant REST :6333 port-forward"
	@echo "  inventory-list       list AI resources via the inventory's API"
	@echo "  teardown             remove agent + inventory + MCPG + qdrant"

# ---------- agent build / run ----------

install:
	python3 -m venv .venv && \
	  ./.venv/bin/pip install -q -U pip && \
	  ./.venv/bin/pip install -q -r agent-a2a/requirements.txt

run-local:
	./.venv/bin/python agent-a2a/server.py --port 9000 --public-url http://localhost:9000

build:
	docker build -t $(IMAGE):$(TAG) agent-a2a/

push-image: build
	docker push $(IMAGE):$(TAG)

load: build
	kind load docker-image $(IMAGE):$(TAG) --name abox

# ---------- agent deploy ----------

deploy-agent: push-image
	@sed 's|ghcr.io/REPLACE_ORG/reliability-a2a:latest|$(IMAGE):$(TAG)|g' \
	  manifests/agent-deploy.yaml | kubectl --context $(CONTEXT) apply -f -
	kubectl --context $(CONTEXT) -n $(NAMESPACE) rollout status deploy/reliability-a2a

# ---------- inventory ----------

$(INVENTORY_DIR):
	mkdir -p $(WORK_DIR)
	git clone --depth 1 https://github.com/den-vasyliev/agentregistry-inventory.git $(INVENTORY_DIR)

deploy-inventory: $(INVENTORY_DIR)
	helm --kube-context $(CONTEXT) upgrade --install agentregistry \
	  $(INVENTORY_DIR)/charts/agentregistry \
	  -n agentregistry --create-namespace
	kubectl --context $(CONTEXT) -n agentregistry rollout status \
	  deploy --selector=app.kubernetes.io/instance=agentregistry --timeout=180s || true
	$(MAKE) deploy-discovery

deploy-discovery:
	kubectl --context $(CONTEXT) apply -f manifests/discoveryconfig.yaml

# ---------- MCPG ----------

$(MCPG_DIR):
	mkdir -p $(WORK_DIR)
	git clone --depth 1 https://github.com/techwithhuz/mcp-security-governance.git $(MCPG_DIR)

build-mcpg-images: $(MCPG_DIR)
	docker build -t mcp-governance-controller:latest $(MCPG_DIR)/controller
	docker build -t mcp-governance-dashboard:latest $(MCPG_DIR)/dashboard
	kind load docker-image mcp-governance-controller:latest --name abox
	kind load docker-image mcp-governance-dashboard:latest --name abox

deploy-mcpg: $(MCPG_DIR) build-mcpg-images
	helm --kube-context $(CONTEXT) upgrade --install mcp-governance \
	  $(MCPG_DIR)/charts/mcp-governance \
	  -n mcp-governance --create-namespace \
	  --set controller.image.repository=mcp-governance-controller \
	  --set dashboard.image.repository=mcp-governance-dashboard
	kubectl --context $(CONTEXT) -n mcp-governance rollout status \
	  deploy --selector=app.kubernetes.io/name=mcp-governance --timeout=180s || true

# ---------- qdrant ----------

deploy-qdrant:
	helm repo add qdrant https://qdrant.github.io/qdrant-helm >/dev/null 2>&1 || true
	helm repo update qdrant
	helm --kube-context $(CONTEXT) upgrade --install qdrant qdrant/qdrant \
	  -n qdrant --create-namespace \
	  -f manifests/qdrant-values.yaml
	kubectl --context $(CONTEXT) -n qdrant rollout status statefulset/qdrant --timeout=180s

# ---------- combo ----------

deploy-all: deploy-qdrant deploy-inventory deploy-mcpg deploy-agent
	@echo "==> all four stacks deployed; see README for the smoke-test sequence."

# ---------- port-forwards ----------

port-forward:
	kubectl --context $(CONTEXT) -n $(NAMESPACE) port-forward svc/reliability-a2a 9000:9000

port-forward-inventory:
	kubectl --context $(CONTEXT) -n agentregistry port-forward svc/agentregistry-api 8080:8080

port-forward-mcpg:
	kubectl --context $(CONTEXT) -n mcp-governance port-forward svc/mcp-governance-dashboard 3000:3000

port-forward-qdrant:
	kubectl --context $(CONTEXT) -n qdrant port-forward svc/qdrant 6333:6333

# ---------- smoke tests ----------

agent-card:
	@curl -fsS http://localhost:9000/.well-known/agent-card.json | jq .

test-task:
	@curl -fsS http://localhost:9000/ -H 'Content-Type: application/json' \
	  -d '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"kind":"message","role":"user","parts":[{"kind":"text","text":"What is an error budget?"}],"messageId":"m1"}}}' \
	  | jq .

inventory-list:
	@curl -fsS http://localhost:8080/v0/agents | jq .
	@echo
	@curl -fsS http://localhost:8080/v0/servers | jq .

# ---------- teardown ----------

teardown-agent:
	kubectl --context $(CONTEXT) delete -n $(NAMESPACE) deploy/reliability-a2a svc/reliability-a2a --ignore-not-found

teardown-inventory:
	helm --kube-context $(CONTEXT) uninstall agentregistry -n agentregistry --ignore-not-found || true
	kubectl --context $(CONTEXT) delete ns agentregistry --ignore-not-found

teardown-mcpg:
	helm --kube-context $(CONTEXT) uninstall mcp-governance -n mcp-governance --ignore-not-found || true
	kubectl --context $(CONTEXT) delete ns mcp-governance --ignore-not-found

teardown-qdrant:
	helm --kube-context $(CONTEXT) uninstall qdrant -n qdrant --ignore-not-found || true
	kubectl --context $(CONTEXT) delete ns qdrant --ignore-not-found

teardown: teardown-agent teardown-inventory teardown-mcpg teardown-qdrant
