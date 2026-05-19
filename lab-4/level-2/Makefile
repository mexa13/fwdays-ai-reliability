IMAGE_PREFIX ?= ghcr.io/$(shell git config user.name | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
WORKER_IMG       ?= $(IMAGE_PREFIX)/reliability-worker
COORD_IMG        ?= $(IMAGE_PREFIX)/reliability-coordinator
TAG              ?= latest
CONTEXT          ?= kind-abox
NAMESPACE        ?= a2a-lab

.PHONY: help install run-worker-local run-coord-local \
        build push load deploy ensure-discovery port-forward-worker port-forward-coord \
        seed-qdrant test-task teardown

help:
	@echo "Lab-4 / level-2 targets:"
	@echo "  install              python venv for both agents"
	@echo "  run-worker-local     uvicorn worker on :9001"
	@echo "  run-coord-local      uvicorn coordinator on :9002 (WORKER_URL=http://localhost:9001)"
	@echo "  build                docker build both agent images"
	@echo "  push                 docker push both"
	@echo "  load                 kind load both into abox"
	@echo "  deploy               apply manifests + seed qdrant + ensure DiscoveryConfig"
	@echo "  ensure-discovery     apply DiscoveryConfig CR if inventory is deployed"
	@echo "  seed-qdrant          run the seed job standalone"
	@echo "  port-forward-worker  svc/reliability-worker:9001 → localhost"
	@echo "  port-forward-coord   svc/reliability-coordinator:9002 → localhost"
	@echo "  test-task            send a task to the coordinator (requires port-forward-coord)"
	@echo "  teardown             delete level-2 deployments"

install:
	python3 -m venv .venv && \
	  ./.venv/bin/pip install -q -U pip && \
	  ./.venv/bin/pip install -q -r agent-worker/requirements.txt

run-worker-local:
	./.venv/bin/python agent-worker/server.py --port 9001 --public-url http://localhost:9001

run-coord-local:
	WORKER_URL=http://localhost:9001 ./.venv/bin/python agent-coordinator/server.py \
	  --port 9002 --public-url http://localhost:9002

build:
	docker build -t $(WORKER_IMG):$(TAG) agent-worker/
	docker build -t $(COORD_IMG):$(TAG)  agent-coordinator/

push: build
	docker push $(WORKER_IMG):$(TAG)
	docker push $(COORD_IMG):$(TAG)

load: build
	kind load docker-image $(WORKER_IMG):$(TAG) --name abox
	kind load docker-image $(COORD_IMG):$(TAG)  --name abox

deploy: push
	@sed -e 's|ghcr.io/REPLACE_ORG/reliability-worker:latest|$(WORKER_IMG):$(TAG)|g' \
	     -e 's|ghcr.io/REPLACE_ORG/reliability-coordinator:latest|$(COORD_IMG):$(TAG)|g' \
	  manifests/agents-deploy.yaml | kubectl --context $(CONTEXT) apply -f -
	kubectl --context $(CONTEXT) -n $(NAMESPACE) rollout status deploy/reliability-worker
	kubectl --context $(CONTEXT) -n $(NAMESPACE) rollout status deploy/reliability-coordinator
	$(MAKE) seed-qdrant
	$(MAKE) ensure-discovery

# Apply the DiscoveryConfig CR so the agentregistry-inventory controller scans
# `a2a-lab` and `kagent` namespaces. Idempotent. Skips silently with a hint if
# the inventory hasn't been installed yet (i.e. CRD missing) — level-1 owns the
# inventory install, but each level reapplies the CR so it survives teardowns.
ensure-discovery:
	@if kubectl --context $(CONTEXT) get crd discoveryconfigs.agentregistry.dev >/dev/null 2>&1; then \
	  kubectl --context $(CONTEXT) apply -f manifests/discoveryconfig.yaml; \
	else \
	  echo "[ensure-discovery] DiscoveryConfig CRD not found — run 'make -C ../level-1 deploy-inventory' first if you want auto-discovery of kagent agents in the inventory."; \
	fi

seed-qdrant:
	kubectl --context $(CONTEXT) apply -f manifests/qdrant-seed-job.yaml
	kubectl --context $(CONTEXT) -n $(NAMESPACE) wait --for=condition=Complete job/qdrant-seed-sre-runbooks --timeout=120s

port-forward-worker:
	kubectl --context $(CONTEXT) -n $(NAMESPACE) port-forward svc/reliability-worker 9001:9001

port-forward-coord:
	kubectl --context $(CONTEXT) -n $(NAMESPACE) port-forward svc/reliability-coordinator 9002:9002

# Send a high-level question to the coordinator. The coordinator will fan it out
# to the worker over A2A and return a rolled-up answer.
test-task:
	@curl -fsS http://localhost:9002/ -H 'Content-Type: application/json' \
	  -d '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"kind":"message","role":"user","parts":[{"kind":"text","text":"Brief me on error budgets and canaries"}],"messageId":"m1"}}}' \
	  | jq -r '.result.status.message.parts[0].text // .'

teardown:
	kubectl --context $(CONTEXT) -n $(NAMESPACE) delete \
	  deploy/reliability-worker svc/reliability-worker \
	  deploy/reliability-coordinator svc/reliability-coordinator \
	  job/qdrant-seed-sre-runbooks --ignore-not-found
