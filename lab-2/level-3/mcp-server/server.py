"""
Reliability MCP Server — custom tool server for fwdays AI Reliability lab.

Tools:
  check_http_status  — check if a URL returns a successful HTTP status
  get_timestamp      — return current UTC timestamp
  parse_error_rate   — calculate error rate from success/total counts
"""

import asyncio
import datetime
from typing import Optional

import httpx
from fastmcp import FastMCP

mcp = FastMCP("reliability-tools")


@mcp.tool()
async def check_http_status(url: str, timeout: int = 10) -> dict:
    """Check if a URL returns a successful HTTP status (2xx).

    Args:
        url: The URL to check (must start with http:// or https://)
        timeout: Request timeout in seconds (default: 10)

    Returns:
        dict with status_code, success (bool), latency_ms, and error if any
    """
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
def get_timestamp(format: Optional[str] = "iso") -> str:
    """Return the current UTC timestamp.

    Args:
        format: Output format — 'iso' (default), 'unix', or 'human'

    Returns:
        Current UTC time as a string
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    if format == "unix":
        return str(int(now.timestamp()))
    if format == "human":
        return now.strftime("%Y-%m-%d %H:%M:%S UTC")
    return now.isoformat()


@mcp.tool()
def parse_error_rate(success_count: int, total_count: int) -> dict:
    """Calculate error rate and SLO compliance from request counts.

    Args:
        success_count: Number of successful requests
        total_count: Total number of requests

    Returns:
        dict with error_rate, success_rate, and slo_compliant (99.9% threshold)
    """
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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--transport", default="streamableHttp",
                        choices=["streamableHttp", "sse", "stdio"])
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=args.port)
