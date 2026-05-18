"""ADK agent backed by the in-cluster reliability-mcp-v2 MCP server.

Run via `make playground` from lab-3/level-1 with `make port-forward` active
in another terminal — agents-cli will boot `adk web` against this package
and connect to http://localhost:8000/mcp.

Provider selection via env:
  AGENT_PROVIDER=gemini    AGENT_MODEL=gemini-2.5-flash         (default)
  AGENT_PROVIDER=openai    AGENT_MODEL=gpt-4o-mini
  AGENT_PROVIDER=anthropic AGENT_MODEL=claude-sonnet-4-5
Plus the matching API key: GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StreamableHTTPConnectionParams,
)

MCP_URL = os.getenv("RELIABILITY_MCP_URL", "http://localhost:8000/mcp")
PROVIDER = os.getenv("AGENT_PROVIDER", "gemini").lower()
MODEL_NAME = os.getenv("AGENT_MODEL", "gemini-2.5-flash")

INSTRUCTION = """\
You are a senior AI Reliability Engineering agent operating against a
Kubernetes lab cluster (abox). You have access to MCP tools exposed by the
in-cluster `reliability-mcp-v2` server.

Always:
  1. Probe reachability before commenting on health.
  2. Cite concrete numbers (status code, latency_ms, error_rate_pct).
  3. Classify severity when impact data is given.
  4. Ask for missing inputs rather than inventing numbers.

Try-it prompts:
  - "Check whether https://kagent.dev is healthy."
  - "I had 9990 successes out of 10000 — am I meeting a 99.9% SLO?"
  - "30-day budget: 100k requests, 80 failures, target 99.9%. How much remains?"
  - "Classify this incident: 2% error rate, p95 1800ms, 500 users affected."
  - "Is TCP port 443 open on cloudflare.com?"
"""


def _build_model():
    if PROVIDER == "gemini":
        return MODEL_NAME
    from google.adk.models.lite_llm import LiteLlm

    return LiteLlm(model=f"{PROVIDER}/{MODEL_NAME}")


root_agent = Agent(
    name="reliability_agent",
    model=_build_model(),
    description="Reliability engineer with MCP-backed probing and SLO tools.",
    instruction=INSTRUCTION,
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=MCP_URL),
        ),
    ],
)
