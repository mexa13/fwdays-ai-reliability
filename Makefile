.PHONY: help \
  l1 l1-install l1-run l1-test l1-stop \
  l2 l2-run l2-run-anthropic l2-run-lmstudio l2-test l2-down \
  l3 l3-run l3-run-anthropic l3-run-lmstudio l3-test l3-down \
  lab3 lab3-l1 lab3-l2 lab3-l3 lab3-down \
  lab4 lab4-l1 lab4-l2 lab4-l3 lab4-down \
  lab5 lab5-l1 lab5-l2 lab5-l3 lab5-apikey lab5-guardrails lab5-down \
  down-all

help:
	@echo "fwdays — AI Reliability Engineering 2.0"
	@echo "Lab 1: Basic Agentic Infrastructure"
	@echo ""
	@echo "Level 1 (standalone binary):"
	@echo "  l1-install          Install agentgateway binary"
	@echo "  l1-run              OpenAI     (OPENAI_API_KEY)"
	@echo "  l1-run-multi        Multi-provider (OPENAI_API_KEY + ANTHROPIC_API_KEY)"
	@echo "  l1-run-lmstudio     LM Studio  (no key, port 1234)"
	@echo "  l1-test             Test port 4000"
	@echo "  l1-test-lmstudio    Test port 3000"
	@echo ""
	@echo "Level 2 (Helm on KinD):"
	@echo "  l2-run              OpenAI     (OPENAI_API_KEY)"
	@echo "  l2-run-anthropic    Anthropic  (ANTHROPIC_API_KEY)"
	@echo "  l2-run-lmstudio     LM Studio  (no key, port 1234)"
	@echo "  l2-test / l2-down"
	@echo ""
	@echo "Level 3 (Helm + Gateway API):"
	@echo "  l3-run              OpenAI     (OPENAI_API_KEY)"
	@echo "  l3-run-anthropic    Anthropic  (ANTHROPIC_API_KEY)"
	@echo "  l3-run-lmstudio     LM Studio  (no key, port 1234)"
	@echo "  l3-test / l3-down"
	@echo ""
	@echo ""
	@echo "Lab 3: MCP Sampling / Elicitation / Apps (runs against abox):"
	@echo "  lab3                Lab-3 help"
	@echo "  lab3-l1             Deploy level-1 (KMCP + agents-cli)"
	@echo "  lab3-l2             Deploy level-2 (MCP Apps)"
	@echo "  lab3-l3             Deploy level-3 (Sampling + Elicitation)"
	@echo "  lab3-down           Tear down all lab-3 resources"
	@echo ""
	@echo "Lab 4: Agent-to-Agent (runs against abox):"
	@echo "  lab4                Lab-4 help"
	@echo "  lab4-l1             Deploy level-1 (own A2A agent + inventory + MCPG + qdrant)"
	@echo "  lab4-l2             Deploy level-2 (coordinator ↔ worker over A2A)"
	@echo "  lab4-l3             Deploy level-3 (heterogeneous team-lead + kagent peers)"
	@echo "  lab4-down           Tear down all lab-4 resources"
	@echo ""
	@echo "Lab 5: Sandboxing & Observability (runs against abox):"
	@echo "  lab5                Lab-5 help"
	@echo "  lab5-l1             Deploy level-1 (Agent Sandbox + NetworkPolicy example)"
	@echo "  lab5-l2             Deploy level-2 (Phoenix + OTel Collector + traced MCP)"
	@echo "  lab5-l3             Deploy level-3 (agentgateway → Phoenix + Sandbox SDK demo)"
	@echo "  lab5-apikey         Apply the agentgateway API key extra"
	@echo "  lab5-guardrails     Apply the agentgateway webhook guardrails extra"
	@echo "  lab5-down           Tear down all lab-5 resources"
	@echo ""
	@echo "  down-all            Stop and destroy all levels"

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

l2-run-anthropic:
	@$(MAKE) -C lab-1/level-2 run-anthropic

l2-run-lmstudio:
	@$(MAKE) -C lab-1/level-2 run-lmstudio

l2-test:
	@$(MAKE) -C lab-1/level-2 test

l2-down:
	@$(MAKE) -C lab-1/level-2 down

# ─── Level 3 ─────────────────────────────────────────────────────────────────
l3:
	@$(MAKE) -C lab-1/level-3 help

l3-run:
	@$(MAKE) -C lab-1/level-3 run

l3-run-anthropic:
	@$(MAKE) -C lab-1/level-3 run-anthropic

l3-run-lmstudio:
	@$(MAKE) -C lab-1/level-3 run-lmstudio

l3-test:
	@$(MAKE) -C lab-1/level-3 test

l3-down:
	@$(MAKE) -C lab-1/level-3 down

# ─── Lab 3 ───────────────────────────────────────────────────────────────────
lab3:
	@$(MAKE) -C lab-3 help

lab3-l1:
	@$(MAKE) -C lab-3 l3l1-deploy

lab3-l2:
	@$(MAKE) -C lab-3 l3l2-deploy

lab3-l3:
	@$(MAKE) -C lab-3 l3l3-deploy

lab3-down:
	@$(MAKE) -C lab-3 l3-down

# ─── Lab 4 ───────────────────────────────────────────────────────────────────
lab4:
	@$(MAKE) -C lab-4 help

lab4-l1:
	@$(MAKE) -C lab-4 l4l1-deploy

lab4-l2:
	@$(MAKE) -C lab-4 l4l2-deploy

lab4-l3:
	@$(MAKE) -C lab-4 l4l3-deploy

lab4-down:
	@$(MAKE) -C lab-4 l4-down

# ─── Lab 5 ───────────────────────────────────────────────────────────────────
lab5:
	@$(MAKE) -C lab-5 help

lab5-l1:
	@$(MAKE) -C lab-5 l5l1-deploy

lab5-l2:
	@$(MAKE) -C lab-5 l5l2-deploy

lab5-l3:
	@$(MAKE) -C lab-5 l5l3-deploy

lab5-apikey:
	@$(MAKE) -C lab-5 l5-extras-apikey

lab5-guardrails:
	@$(MAKE) -C lab-5 l5-extras-guardrails

lab5-down:
	@$(MAKE) -C lab-5 l5-down

# ─── Teardown all ─────────────────────────────────────────────────────────────
down-all:
	@$(MAKE) l1-stop   2>/dev/null || true
	@$(MAKE) l2-down   2>/dev/null || true
	@$(MAKE) l3-down   2>/dev/null || true
	@$(MAKE) lab3-down 2>/dev/null || true
	@$(MAKE) lab4-down 2>/dev/null || true
	@$(MAKE) lab5-down 2>/dev/null || true
