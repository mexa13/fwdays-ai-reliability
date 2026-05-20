"""Reliability MCP server with OpenTelemetry tracing → Phoenix.

Spans:
    - one root span per JSON-RPC request (auto from openinference-instrumentation-mcp)
    - one child span per @tool invocation, with input args + return value as
      span attributes (decorator handles serialization)

The OTLP endpoint defaults to the in-cluster OTel Collector service so it works
both in-cluster (DNS name) and through `kubectl port-forward svc/phoenix-svc 6006:6006
4317:4317` from a laptop (override with PHOENIX_COLLECTOR_ENDPOINT).
"""

from __future__ import annotations

import os
import time

from mcp.server.fastmcp import FastMCP
from phoenix.otel import register

# Port 6006 multiplexes the Phoenix UI (GET /) and the OTLP HTTP receiver
# (POST /v1/traces). `phoenix.otel.register(protocol="http/protobuf")` ought to
# append `/v1/traces` for us, but in some versions it doesn't — exporter then
# POSTs to `/` and gets 405. Spelling out the full path side-steps that.
PHOENIX_ENDPOINT = os.environ.get(
    "PHOENIX_COLLECTOR_ENDPOINT",
    "http://phoenix-svc.phoenix.svc.cluster.local:6006/v1/traces",
)
PROJECT_NAME = os.environ.get("PHOENIX_PROJECT_NAME", "lab-5-mcp")

# `protocol="http/protobuf"` matches the :6006 endpoint (Phoenix UI = HTTP OTLP
# receiver). Without it phoenix.otel warns "Could not infer collector endpoint
# protocol, defaulting to HTTP" — same default, just noisier in the logs.
tracer_provider = register(
    project_name=PROJECT_NAME,
    endpoint=PHOENIX_ENDPOINT,
    protocol="http/protobuf",
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


def _demo_loop() -> None:
    """Drive the tools in a loop so Phoenix has something to show.

    Running FastMCP via stdio inside a Pod exits immediately (no stdin = EOF on
    the first read), which is why a naked `mcp.run()` would CrashLoopBackOff in
    a Deployment. The loop lets the same module serve double duty: a Pod-
    friendly trace emitter, or a real MCP server when launched without `--demo`.
    """
    import time

    signals = [
        "Database connection errors after the deploy",
        "Latency spike on /checkout to 1.2s p95",
        "Pod OOMKilled in payments-api",
        "5xx surge on /api/v1/orders",
    ]
    i = 0
    while True:
        error_budget(slo_percent=99.9 - (i % 5) * 0.1, window_days=30)
        toy_incident_triage(signals[i % len(signals)])
        time.sleep(15)
        i += 1


if __name__ == "__main__":
    import sys

    if "--demo" in sys.argv:
        print("[server] tracer initialized; entering demo loop", flush=True)
        _demo_loop()
    else:
        mcp.run()
