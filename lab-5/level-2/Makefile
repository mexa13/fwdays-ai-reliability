IMAGE_PREFIX  ?= ghcr.io/$(shell git config user.name | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
MCP_IMG       ?= $(IMAGE_PREFIX)/reliability-mcp-traced
TAG           ?= latest
CONTEXT       ?= kind-abox
PHOENIX_NS    ?= phoenix
APP_NS        ?= a5-observe
PHOENIX_VER   ?= 12.5.0

.PHONY: help deploy-phoenix deploy-collector deploy-mcp build load deploy \
        port-forward-phoenix port-forward-otel test-trace install-local run-local \
        teardown teardown-phoenix teardown-collector teardown-mcp

help:
	@echo "Lab-5 / level-2 targets (Phoenix + Sandbox metrics + MCP tracing):"
	@echo "  deploy-phoenix         helm install phoenix in ns/$(PHOENIX_NS)"
	@echo "  deploy-collector       OTel Collector → Phoenix, plus Prom scrape for Sandbox metrics"
	@echo "  build                  docker build the instrumented MCP server"
	@echo "  load                   kind load the MCP image into abox"
	@echo "  deploy-mcp             apply MCP server Deployment in ns/$(APP_NS)"
	@echo "  deploy                 phoenix + collector + MCP (full level-2)"
	@echo "  port-forward-phoenix   svc/phoenix:6006 → localhost (UI)"
	@echo "  port-forward-otel      svc/otel-collector:4317 → localhost"
	@echo "  test-trace             call the MCP server inside the cluster to emit a span"
	@echo "  install-local / run-local   venv-based local dev (no kind required)"
	@echo "  teardown               remove MCP + Collector + Phoenix"

# ─── Phoenix ──────────────────────────────────────────────────────────────────

deploy-phoenix:
	kubectl --context $(CONTEXT) get ns $(PHOENIX_NS) >/dev/null 2>&1 \
	  || kubectl --context $(CONTEXT) create ns $(PHOENIX_NS)
	helm --kube-context $(CONTEXT) upgrade --install phoenix \
	  oci://registry-1.docker.io/arizephoenix/phoenix-helm \
	  --version $(PHOENIX_VER) \
	  -n $(PHOENIX_NS) \
	  -f manifests/phoenix-values.yaml
	kubectl --context $(CONTEXT) -n $(PHOENIX_NS) rollout status \
	  deploy --selector=app.kubernetes.io/name=phoenix --timeout=300s || true

# ─── OTel Collector (Phoenix sink + Sandbox metrics scrape) ───────────────────

deploy-collector:
	kubectl --context $(CONTEXT) apply -f manifests/otel-collector.yaml
	kubectl --context $(CONTEXT) -n $(PHOENIX_NS) rollout status \
	  deploy/otel-collector --timeout=180s

# ─── MCP server build/deploy ─────────────────────────────────────────────────

build:
	docker build -t $(MCP_IMG):$(TAG) mcp-traced/

load: build
	kind load docker-image $(MCP_IMG):$(TAG) --name abox

deploy-mcp: load
	@sed "s|REPLACE_ME/reliability-mcp-traced:latest|$(MCP_IMG):$(TAG)|g" \
	  manifests/mcp-traced-deploy.yaml | kubectl --context $(CONTEXT) apply -f -
	kubectl --context $(CONTEXT) -n $(APP_NS) rollout status deploy/reliability-mcp-traced --timeout=120s

# ─── Combo ────────────────────────────────────────────────────────────────────

deploy: deploy-phoenix deploy-collector deploy-mcp
	@echo "==> Phoenix + Collector + traced MCP deployed."
	@echo "    Open the UI:   make port-forward-phoenix   →  http://localhost:6006"
	@echo "    Emit a trace:  make test-trace"

# ─── Port-forwards & smoke test ──────────────────────────────────────────────

port-forward-phoenix:
	kubectl --context $(CONTEXT) -n $(PHOENIX_NS) port-forward svc/phoenix 6006:6006 4317:4317

port-forward-otel:
	kubectl --context $(CONTEXT) -n $(PHOENIX_NS) port-forward svc/otel-collector 4317:4317

# Calls the MCP server in-cluster via stdio is awkward; instead we exec into the
# pod and import + invoke the tool directly, which goes through the same tracer.
test-trace:
	@POD=$$(kubectl --context $(CONTEXT) -n $(APP_NS) get pod \
	    -l app=reliability-mcp-traced -o jsonpath='{.items[0].metadata.name}'); \
	  kubectl --context $(CONTEXT) -n $(APP_NS) exec "$$POD" -- python -c \
	    "import server, json; print(json.dumps(server.error_budget(99.9, 30))); print(json.dumps(server.toy_incident_triage('Database connection errors after the deploy')))"

# ─── Local dev (no cluster) ──────────────────────────────────────────────────

install-local:
	python3 -m venv .venv && \
	  ./.venv/bin/pip install -q -U pip && \
	  ./.venv/bin/pip install -q -r mcp-traced/requirements.txt

run-local:
	PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006 \
	  ./.venv/bin/python mcp-traced/server.py

# ─── Teardown ─────────────────────────────────────────────────────────────────

teardown-mcp:
	kubectl --context $(CONTEXT) delete -f manifests/mcp-traced-deploy.yaml --ignore-not-found

teardown-collector:
	kubectl --context $(CONTEXT) delete -f manifests/otel-collector.yaml --ignore-not-found

teardown-phoenix:
	helm --kube-context $(CONTEXT) uninstall phoenix -n $(PHOENIX_NS) --ignore-not-found || true
	kubectl --context $(CONTEXT) delete ns $(PHOENIX_NS) --ignore-not-found

teardown: teardown-mcp teardown-collector teardown-phoenix
