IMAGE      ?= ghcr.io/$(shell git config user.name | tr '[:upper:]' '[:lower:]' | tr ' ' '-')/reliability-team-lead
TAG        ?= latest
CONTEXT    ?= kind-abox
NAMESPACE  ?= a2a-lab

.PHONY: help install run-local build push load deploy port-forward test-task discover-peers teardown

help:
	@echo "Lab-4 / level-3 targets:"
	@echo "  install            python venv with a2a-sdk + starlette + uvicorn"
	@echo "  run-local          uvicorn team-lead on :9100 (uses ./agent-team-lead/peers.json)"
	@echo "  build              docker build the team-lead image"
	@echo "  push               docker push the team-lead image"
	@echo "  load               kind load into abox"
	@echo "  deploy             apply ConfigMap + Deployment + Service"
	@echo "  port-forward       team-lead :9100 → localhost"
	@echo "  test-task          send the canonical incident from scenarios/incident-triage.md"
	@echo "  discover-peers     curl every peer's Agent Card to sanity-check URLs"
	@echo "  teardown           delete team-lead Deployment + Service + ConfigMap"

install:
	python3 -m venv .venv && \
	  ./.venv/bin/pip install -q -U pip && \
	  ./.venv/bin/pip install -q -r agent-team-lead/requirements.txt

run-local:
	cd agent-team-lead && ../.venv/bin/python server.py --port 9100 --public-url http://localhost:9100

build:
	docker build -t $(IMAGE):$(TAG) agent-team-lead/

push: build
	docker push $(IMAGE):$(TAG)

load: build
	kind load docker-image $(IMAGE):$(TAG) --name abox

deploy: push
	@sed 's|ghcr.io/REPLACE_ORG/reliability-team-lead:latest|$(IMAGE):$(TAG)|g' \
	  manifests/team-deploy.yaml | kubectl --context $(CONTEXT) apply -f -
	kubectl --context $(CONTEXT) -n $(NAMESPACE) rollout status deploy/reliability-team-lead

port-forward:
	kubectl --context $(CONTEXT) -n $(NAMESPACE) port-forward svc/reliability-team-lead 9100:9100

# Send the canonical scenario. The team-lead fans it out to all peers and rolls up.
test-task:
	@payload=$$(jq -Rs . <scenarios/incident-triage.md); \
	curl -fsS http://localhost:9100/ -H 'Content-Type: application/json' \
	  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"message/send\",\"params\":{\"message\":{\"kind\":\"message\",\"role\":\"user\",\"parts\":[{\"kind\":\"text\",\"text\":$$payload}],\"messageId\":\"m-triage\"}}}" \
	  | jq -r '.result.status.message.parts[0].text // .'

# Walk the configured peers and check each Agent Card resolves. Run from a host
# that can reach the URLs in peers.json (i.e. with port-forwards open, or from a
# pod inside the cluster).
define DISCOVER_PY
import json, os, urllib.request
peers = json.load(open(os.environ.get("PEERS_FILE", "/etc/team-lead/peers.json")))
for p in peers:
    url = p["url"].rstrip("/") + "/.well-known/agent-card.json"
    print(f"==> {url}")
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            c = json.load(r)
        skills = [s.get("id") for s in c.get("skills") or []]
        print(f"    name={c.get('name')!r} version={c.get('version')!r} skills={skills}")
    except Exception as e:
        print(f"    (failed: {type(e).__name__}: {e})")
endef
export DISCOVER_PY

# Resolves each peer's Agent Card from inside the cluster, where the in-cluster
# DNS names in peers.json actually resolve. Requires `make deploy` first so the
# team-lead Deployment exists (we exec into it and reuse its mounted peers.json).
discover-peers:
	@kubectl --context $(CONTEXT) -n $(NAMESPACE) get deploy reliability-team-lead >/dev/null 2>&1 || { \
	  echo "team-lead Deployment not found in $(NAMESPACE). Run 'make deploy' first."; exit 1; \
	}
	@kubectl --context $(CONTEXT) -n $(NAMESPACE) exec deploy/reliability-team-lead -- python -c "$$DISCOVER_PY"

teardown:
	kubectl --context $(CONTEXT) -n $(NAMESPACE) delete \
	  deploy/reliability-team-lead svc/reliability-team-lead \
	  configmap/reliability-team-lead-peers --ignore-not-found
