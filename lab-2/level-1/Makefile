CONTEXT  ?= kind-abox
PROVIDER ?= openai

.PHONY: setup test teardown ui

setup:
	@KUBE_CONTEXT=$(CONTEXT) PROVIDER=$(PROVIDER) bash setup.sh

test:
	@KUBE_CONTEXT=$(CONTEXT) bash test.sh

ui:
	@echo "Opening Kagent UI → http://localhost:8080"
	kubectl --context $(CONTEXT) port-forward -n kagent svc/kagent-ui 8080:8080

teardown:
	kubectl --context $(CONTEXT) delete agent web-researcher -n kagent --ignore-not-found
	kubectl --context $(CONTEXT) delete mcpserver fetch-mcp -n kagent --ignore-not-found

# Example usage:
#   OPENAI_API_KEY=sk-... make setup
#   ANTHROPIC_API_KEY=sk-ant-... PROVIDER=anthropic make setup
