.PHONY: help l1 l1-install l1-run l1-test l1-stop l2 l2-run l2-test l2-down l3 l3-run l3-test l3-down down-all

help:
	@echo "fwdays — AI Reliability Engineering 2.0"
	@echo "Lab 1: Basic Agentic Infrastructure"
	@echo ""
	@echo "  l1-install   Install agentgateway binary"
	@echo "  l1-run       Run agentgateway standalone  (requires OPENAI_API_KEY)"
	@echo "  l1-test      Test Level 1 chat completions"
	@echo "  l1-stop      Stop agentgateway"
	@echo ""
	@echo "  l2-run       Deploy Level 2: KinD + agentgateway + kagent via Helm"
	@echo "  l2-test      Run Level 2 integration tests"
	@echo "  l2-down      Destroy Level 2 cluster"
	@echo ""
	@echo "  l3-run       Deploy Level 3: Level 2 + Gateway API"
	@echo "  l3-test      Run Level 3 integration tests"
	@echo "  l3-down      Destroy Level 3 cluster"
	@echo ""
	@echo "  down-all     Stop and destroy all levels"
	@echo ""
	@echo "Requires: export OPENAI_API_KEY=sk-..."

# ─── Level 1 ─────────────────────────────────────────────────────────────────
l1:
	@$(MAKE) -C lab-1/level-1 help

l1-install:
	@$(MAKE) -C lab-1/level-1 install

l1-run:
	@$(MAKE) -C lab-1/level-1 run

l1-test:
	@$(MAKE) -C lab-1/level-1 test

l1-stop:
	@$(MAKE) -C lab-1/level-1 stop

# ─── Level 2 ─────────────────────────────────────────────────────────────────
l2:
	@$(MAKE) -C lab-1/level-2 help

l2-run:
	@$(MAKE) -C lab-1/level-2 run

l2-test:
	@$(MAKE) -C lab-1/level-2 test

l2-down:
	@$(MAKE) -C lab-1/level-2 down

# ─── Level 3 ─────────────────────────────────────────────────────────────────
l3:
	@$(MAKE) -C lab-1/level-3 help

l3-run:
	@$(MAKE) -C lab-1/level-3 run

l3-test:
	@$(MAKE) -C lab-1/level-3 test

l3-down:
	@$(MAKE) -C lab-1/level-3 down

# ─── Teardown all ─────────────────────────────────────────────────────────────
down-all:
	@$(MAKE) l1-stop  2>/dev/null || true
	@$(MAKE) l2-down  2>/dev/null || true
	@$(MAKE) l3-down  2>/dev/null || true
