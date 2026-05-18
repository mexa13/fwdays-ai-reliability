"""
Reliability MCP Server v2 — extended toolset for lab-3 level-1.

Tools:
  check_http_status   — HTTP 2xx probe with latency
  check_tcp_port      — TCP connect probe with latency
  get_timestamp       — current UTC timestamp
  parse_error_rate    — error rate + SLO compliance from counts
  calc_error_budget   — remaining error budget for a given SLO/window
  classify_severity   — map metric values to incident severity

Transport: streamable HTTP on :8000 (matches kagent MCPServer CRD).
"""

import asyncio
import datetime
import socket
from typing import Optional

import httpx
from fastmcp import FastMCP

mcp = FastMCP("reliability-tools-v2")


@mcp.tool()
async def check_http_status(url: str, timeout: int = 10) -> dict:
    """Check if a URL returns a 2xx HTTP status. Returns status_code, success, latency_ms."""
    if not url.startswith(("http://", "https://")):
        return {"error": "URL must start with http:// or https://"}
    start = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, timeout=timeout)
        latency_ms = round((asyncio.get_event_loop().time() - start) * 1000, 1)
        return {
            "url": url,
            "status_code": response.status_code,
            "success": 200 <= response.status_code < 300,
            "latency_ms": latency_ms,
        }
    except httpx.TimeoutException:
        return {"url": url, "error": f"timeout after {timeout}s", "success": False}
    except Exception as e:
        return {"url": url, "error": str(e), "success": False}


@mcp.tool()
async def check_tcp_port(host: str, port: int, timeout: float = 3.0) -> dict:
    """TCP connect probe. Returns open (bool), latency_ms, and error if any."""
    start = asyncio.get_event_loop().time()
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return {
            "host": host,
            "port": port,
            "open": True,
            "latency_ms": round((asyncio.get_event_loop().time() - start) * 1000, 1),
        }
    except (asyncio.TimeoutError, socket.gaierror, OSError) as e:
        return {"host": host, "port": port, "open": False, "error": str(e) or "timeout"}


@mcp.tool()
def get_timestamp(format: Optional[str] = "iso") -> str:
    """Current UTC timestamp. format: 'iso' | 'unix' | 'human'."""
    now = datetime.datetime.now(datetime.timezone.utc)
    if format == "unix":
        return str(int(now.timestamp()))
    if format == "human":
        return now.strftime("%Y-%m-%d %H:%M:%S UTC")
    return now.isoformat()


@mcp.tool()
def parse_error_rate(success_count: int, total_count: int) -> dict:
    """Error rate + 99.9% SLO compliance from success/total counts."""
    if total_count <= 0:
        return {"error": "total_count must be greater than 0"}
    if success_count > total_count:
        return {"error": "success_count cannot exceed total_count"}
    error_count = total_count - success_count
    error_rate = round(error_count / total_count * 100, 4)
    success_rate = round(success_count / total_count * 100, 4)
    return {
        "success_count": success_count,
        "error_count": error_count,
        "total_count": total_count,
        "error_rate_pct": error_rate,
        "success_rate_pct": success_rate,
        "slo_compliant_99_9": success_rate >= 99.9,
    }


@mcp.tool()
def calc_error_budget(
    slo_pct: float,
    total_requests: int,
    failed_requests: int,
    window_days: int = 30,
) -> dict:
    """Remaining error budget for a given SLO over a window.

    Args:
        slo_pct: target success rate, e.g. 99.9 for 99.9%
        total_requests: total requests in the window
        failed_requests: failed requests in the window
        window_days: window length in days (informational)
    """
    if not 0 < slo_pct < 100:
        return {"error": "slo_pct must be between 0 and 100"}
    if total_requests <= 0:
        return {"error": "total_requests must be > 0"}
    if failed_requests < 0 or failed_requests > total_requests:
        return {"error": "failed_requests out of range"}

    allowed_failures = total_requests * (1 - slo_pct / 100)
    remaining = allowed_failures - failed_requests
    burn_pct = round(failed_requests / allowed_failures * 100, 2) if allowed_failures > 0 else None
    return {
        "slo_pct": slo_pct,
        "window_days": window_days,
        "total_requests": total_requests,
        "failed_requests": failed_requests,
        "allowed_failures": round(allowed_failures, 2),
        "remaining_budget": round(remaining, 2),
        "burn_pct": burn_pct,
        "exhausted": remaining <= 0,
    }


@mcp.tool()
def classify_severity(
    error_rate_pct: float,
    p95_latency_ms: Optional[float] = None,
    affected_users: Optional[int] = None,
) -> dict:
    """Map metric values to an incident severity (SEV1..SEV4).

    Heuristic:
      SEV1: error_rate >= 5% OR p95 latency >= 5000ms OR affected_users >= 10000
      SEV2: error_rate >= 1% OR p95 latency >= 2000ms OR affected_users >= 1000
      SEV3: error_rate >= 0.1% OR p95 latency >= 1000ms OR affected_users >= 100
      SEV4: anything else
    """
    score = 4
    reasons = []
    if error_rate_pct >= 5 or (p95_latency_ms or 0) >= 5000 or (affected_users or 0) >= 10000:
        score = min(score, 1)
        reasons.append("breach of SEV1 thresholds")
    elif error_rate_pct >= 1 or (p95_latency_ms or 0) >= 2000 or (affected_users or 0) >= 1000:
        score = min(score, 2)
        reasons.append("breach of SEV2 thresholds")
    elif error_rate_pct >= 0.1 or (p95_latency_ms or 0) >= 1000 or (affected_users or 0) >= 100:
        score = min(score, 3)
        reasons.append("breach of SEV3 thresholds")
    else:
        reasons.append("within nominal bounds")
    return {
        "severity": f"SEV{score}",
        "error_rate_pct": error_rate_pct,
        "p95_latency_ms": p95_latency_ms,
        "affected_users": affected_users,
        "reasons": reasons,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--transport",
        default="streamableHttp",
        choices=["streamableHttp", "sse", "stdio"],
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=args.port)
