CONTEXT   ?= kind-abox
NAMESPACE ?= a5-sandbox

# Namespace the python-sandbox-template lives in. Upstream YAML uses
# ${SANDBOX_NAMESPACE} which we substitute before apply. The SDK demo in
# level-3 looks here by default (SANDBOX_NAMESPACE env in code_interpreter_agent.py).
SANDBOX_NAMESPACE     ?= default
SANDBOX_TEMPLATE_NAME ?= python-sandbox-template

# Track the released version of the agent-sandbox controller. The upstream
# install guide pins to "latest"; override with `make VERSION=v0.x.y deploy`.
VERSION   ?= latest

# Resolved at runtime from the GitHub releases API when VERSION=latest.
RESOLVED_VERSION = $(shell if [ "$(VERSION)" = "latest" ]; then \
  curl -fsSL https://api.github.com/repos/kubernetes-sigs/agent-sandbox/releases/latest | jq -r '.tag_name'; \
else echo $(VERSION); fi)

.PHONY: help install-controller install-extensions install-router install-template deploy-example \
        deploy verify exec-sandbox teardown teardown-example teardown-controller

help:
	@echo "Lab-5 / level-1 targets (Agent Sandbox + NetworkPolicy):"
	@echo "  install-controller      kubectl apply manifest.yaml for the agent-sandbox controller"
	@echo "  install-extensions      kubectl apply extensions.yaml (AgenticSandbox CRD lives here)"
	@echo "  install-router          deploy the sandbox-router (used by the SDK in level-3)"
	@echo "  install-template        apply the python-sandbox-template runtime"
	@echo "  deploy-example          create namespace + AgenticSandbox 'demo' + deny-by-default + allow-DNS"
	@echo "  deploy                  full chain: controller + extensions + router + template + example"
	@echo "  verify                  list CRDs, controller pods, and the demo sandbox"
	@echo "  exec-sandbox            open a shell inside the demo sandbox pod"
	@echo "  teardown                remove the example + router + template + controller"

# ─── Controller install (one-time per cluster) ────────────────────────────────

install-controller:
	@VERSION=$(RESOLVED_VERSION); \
	  echo "==> installing agent-sandbox $$VERSION core manifest"; \
	  kubectl --context $(CONTEXT) apply -f \
	    https://github.com/kubernetes-sigs/agent-sandbox/releases/download/$$VERSION/manifest.yaml
	kubectl --context $(CONTEXT) -n agent-sandbox-system rollout status \
	  deploy/agent-sandbox-controller --timeout=180s

install-extensions:
	@VERSION=$(RESOLVED_VERSION); \
	  echo "==> installing agent-sandbox $$VERSION extensions (AgenticSandbox via KRO)"; \
	  kubectl --context $(CONTEXT) apply -f \
	    https://github.com/kubernetes-sigs/agent-sandbox/releases/download/$$VERSION/extensions.yaml

install-router:
	@VERSION=$(RESOLVED_VERSION); \
	  echo "==> deploying sandbox-router ($$VERSION)"; \
	  curl -sSL https://raw.githubusercontent.com/kubernetes-sigs/agent-sandbox/refs/tags/$$VERSION/clients/python/agentic-sandbox-client/sandbox-router/sandbox_router.yaml \
	    | sed 's|$${ROUTER_IMAGE}|us-central1-docker.pkg.dev/k8s-staging-images/agent-sandbox/sandbox-router:latest-main|g' \
	    | kubectl --context $(CONTEXT) apply -f -

install-template:
	@VERSION=$(RESOLVED_VERSION); \
	  echo "==> applying $(SANDBOX_TEMPLATE_NAME) ($$VERSION) into ns/$(SANDBOX_NAMESPACE)"; \
	  kubectl --context $(CONTEXT) get ns $(SANDBOX_NAMESPACE) >/dev/null 2>&1 \
	    || kubectl --context $(CONTEXT) create ns $(SANDBOX_NAMESPACE); \
	  curl -sSL https://raw.githubusercontent.com/kubernetes-sigs/agent-sandbox/refs/tags/$$VERSION/clients/python/agentic-sandbox-client/python-sandbox-template.yaml \
	    | sed -e 's|$${SANDBOX_NAMESPACE}|$(SANDBOX_NAMESPACE)|g' \
	          -e 's|$${SANDBOX_TEMPLATE_NAME}|$(SANDBOX_TEMPLATE_NAME)|g' \
	    | kubectl --context $(CONTEXT) apply -f -

# ─── Example workload ─────────────────────────────────────────────────────────

deploy-example:
	kubectl --context $(CONTEXT) apply -f manifests/network-policy-example.yaml
	@echo "==> waiting up to 120s for the sandbox pod in ns/$(NAMESPACE) to become Ready"
	@for i in $$(seq 1 60); do \
	  POD=$$(kubectl --context $(CONTEXT) -n $(NAMESPACE) get pod -o jsonpath='{.items[0].metadata.name}' 2>/dev/null); \
	  if [ -n "$$POD" ]; then \
	    kubectl --context $(CONTEXT) -n $(NAMESPACE) wait --for=condition=Ready pod/$$POD --timeout=120s && break; \
	  fi; \
	  sleep 2; \
	done

deploy: install-controller install-extensions install-router install-template deploy-example
	@echo "==> level-1 deployed; see README for the verification & Phoenix Colab steps."

# ─── Smoke tests ──────────────────────────────────────────────────────────────

verify:
	@echo "── controller pods ──"
	kubectl --context $(CONTEXT) -n agent-sandbox-system get pods
	@echo
	@echo "── CRDs registered ──"
	kubectl --context $(CONTEXT) get crd | grep -E 'sandbox|agents\.x-k8s\.io' || true
	@echo
	@echo "── demo Sandbox ──"
	kubectl --context $(CONTEXT) -n $(NAMESPACE) get sandboxes demo -o yaml || true
	@echo
	@echo "── sandbox pod ──"
	kubectl --context $(CONTEXT) -n $(NAMESPACE) get pods
	@echo
	@echo "── NetworkPolicies in $(NAMESPACE) ──"
	kubectl --context $(CONTEXT) -n $(NAMESPACE) get networkpolicy

# Open an interactive shell in the demo sandbox to poke at NP behaviour.
# Pod-name lookup is dynamic so this works regardless of the controller's
# naming scheme (demo, demo-xxxxx, ...).
exec-sandbox:
	@POD=$$(kubectl --context $(CONTEXT) -n $(NAMESPACE) get pod -o jsonpath='{.items[0].metadata.name}'); \
	  echo "==> exec into $$POD"; \
	  kubectl --context $(CONTEXT) -n $(NAMESPACE) exec -it "$$POD" -- bash

# ─── Teardown ─────────────────────────────────────────────────────────────────

teardown-example:
	kubectl --context $(CONTEXT) delete -f manifests/network-policy-example.yaml --ignore-not-found

teardown-controller:
	@VERSION=$(RESOLVED_VERSION); \
	  kubectl --context $(CONTEXT) delete -f \
	    https://github.com/kubernetes-sigs/agent-sandbox/releases/download/$$VERSION/extensions.yaml \
	    --ignore-not-found; \
	  kubectl --context $(CONTEXT) delete -f \
	    https://github.com/kubernetes-sigs/agent-sandbox/releases/download/$$VERSION/manifest.yaml \
	    --ignore-not-found

teardown: teardown-example teardown-controller
