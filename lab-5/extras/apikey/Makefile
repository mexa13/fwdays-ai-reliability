CONTEXT ?= kind-abox

.PHONY: help apply test teardown

help:
	@echo "Lab-5 / extras/apikey:"
	@echo "  apply        kubectl apply Secret + AgentgatewayPolicy (Strict)"
	@echo "  test         curl with / without the api-key to verify behaviour"
	@echo "  teardown     remove both resources"

apply:
	kubectl --context $(CONTEXT) apply -f apikey.yaml

# Assumes lab-1/level-3 is up and you've port-forwarded the gateway on :3000.
# The api-key string lives in apikey.yaml — keep them in sync.
test:
	@echo "── without key (expect 401) ──"
	@curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/v1/models || true
	@echo "── with key (expect 200) ──"
	@curl -s -o /dev/null -w '%{http_code}\n' \
	  -H 'x-api-key: N2YwMDIxZTEtNGUzNS1jNzgzLTRkYjAtYjE2YzRkZGVmNjcy' \
	  http://localhost:3000/v1/models || true

teardown:
	kubectl --context $(CONTEXT) delete -f apikey.yaml --ignore-not-found
