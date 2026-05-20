"""Reliability MCP server with OpenTelemetry tracing → Phoenix.

Spans:
    - one root span per JSON-RPC request (auto from openinference-instrumentation-mcp)
    - one child span per @tool invocation, with input args + return value as
      span attributes (decorator handles serialization)

The OTLP endpoint defaults to the in-cluster OTel Collector service so it works
both in-cluster (DNS name) and through `kubectl port-forward svc/phoenix 6006:6006
4317:4317` from a laptop (override with PHOENIX_COLLECTOR_ENDPOINT).
"""

from __future__ import annotations

import os
import time

from mcp.server.fastmcp import FastMCP
from phoenix.otel import register

PHOENIX_ENDPOINT = os.environ.get(
    "PHOENIX_COLLECTOR_ENDPOINT",
    "http://phoenix.phoenix.svc.cluster.local:6006",
)
PROJECT_NAME = os.environ.get("PHOENIX_PROJECT_NAME", "lab-5-mcp")

tracer_provider = register(
    project_name=PROJECT_NAME,
    endpoint=PHOENIX_ENDPOINT,
    auto_instrument=True,
)
tracer = tracer_provider.get_tracer("reliability-mcp")

mcp = FastMCP("reliability-mcp")


@mcp.tool()
@tracer.tool(name="MCP.error_budget")
def error_budget(slo_percent: float, window_days: int = 30) -> dict:
    """Compute the error budget in minutes for an SLO over a rolling window."""
    minutes_in_window = window_days * 24 * 60
    budget = round(minutes_in_window * (100 - slo_percent) / 100, 2)
    return {
        "slo_percent": slo_percent,
        "window_days": window_days,
        "budget_minutes": budget,
        "window_minutes": minutes_in_window,
    }


@mcp.tool()
@tracer.tool(name="MCP.toy_incident_triage")
def toy_incident_triage(signal: str) -> dict:
    """A deterministic 'triage' that buckets a free-text signal."""
    s = signal.lower()
    severity = "p3"
    if any(k in s for k in ("crash", "outage", "down", "fatal")):
        severity = "p1"
    elif any(k in s for k in ("error", "5xx", "latency", "degraded")):
        severity = "p2"
    time.sleep(0.05)  # so the span has visible duration in the UI
    return {"signal": signal, "severity": severity}


if __name__ == "__main__":
    mcp.run()
