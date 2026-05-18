"""
Reliability MCP Server — MCP Apps edition (lab-3 level-2).

Demonstrates the MCP Apps extension (spec 2026-01-26):
  - `incident_dashboard` returns structured rows + attaches an HTML UI resource
  - The host renders the UI inline; from inside the iframe the UI itself acts as
    an MCP client and re-calls `incident_dashboard` to refresh data without
    re-prompting the LLM.

Falls back gracefully on clients that do NOT support MCP Apps: the structured
JSON payload is still returned and the LLM can answer from it directly.

Requires: fastmcp>=3.0 (Apps support). On older FastMCP we still emit the
spec-level `_meta.ui` annotation manually so Apps-capable clients can render it.
"""

import asyncio
import datetime
import json
import random
from typing import Optional

import httpx
from fastmcp import FastMCP

mcp = FastMCP("reliability-tools-apps")

# ---------------------------------------------------------------------------
# Mock incident store (in a real deployment this would be Loki/Tempo/Datadog)
# ---------------------------------------------------------------------------

_SERVICES = ["checkout-api", "payments", "search", "auth", "cart", "inventory"]
_SEVS = ["SEV1", "SEV2", "SEV2", "SEV3", "SEV3", "SEV3", "SEV4"]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _mock_incidents(n: int = 12) -> list[dict]:
    rng = random.Random(42)
    out = []
    base = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    for i in range(n):
        started = base + datetime.timedelta(minutes=rng.randint(0, 24 * 60))
        out.append({
            "id": f"INC-{1000 + i}",
            "service": rng.choice(_SERVICES),
            "severity": rng.choice(_SEVS),
            "error_rate_pct": round(rng.uniform(0.01, 8.5), 2),
            "p95_latency_ms": rng.randint(120, 4500),
            "affected_users": rng.randint(0, 12000),
            "started_at": started.isoformat(),
            "status": rng.choice(["open", "mitigating", "resolved"]),
        })
    return sorted(out, key=lambda r: r["started_at"], reverse=True)


# ---------------------------------------------------------------------------
# Deterministic helpers reused from level-1
# ---------------------------------------------------------------------------

@mcp.tool()
async def check_http_status(url: str, timeout: int = 10) -> dict:
    """HTTP 2xx probe with latency_ms."""
    if not url.startswith(("http://", "https://")):
        return {"error": "URL must start with http:// or https://"}
    start = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, timeout=timeout)
        return {
            "url": url,
            "status_code": response.status_code,
            "success": 200 <= response.status_code < 300,
            "latency_ms": round((asyncio.get_event_loop().time() - start) * 1000, 1),
        }
    except Exception as e:
        return {"url": url, "error": str(e), "success": False}


@mcp.tool()
def list_incidents(
    service: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """Return the current incident list filtered by service/severity/status."""
    rows = _mock_incidents()
    if service:
        rows = [r for r in rows if r["service"] == service]
    if severity:
        rows = [r for r in rows if r["severity"] == severity]
    if status:
        rows = [r for r in rows if r["status"] == status]
    return {"as_of": _now_iso(), "count": len(rows), "incidents": rows}


# ---------------------------------------------------------------------------
# MCP Apps tool — returns structured data AND attaches an HTML UI resource.
#
# Spec: the tool result MAY include `_meta.ui.resourceUri` pointing at a
# `ui://...` resource the host should render in a sandboxed iframe. The
# iframe is itself an MCP client and can call back into this server.
# ---------------------------------------------------------------------------

DASHBOARD_URI = "ui://reliability/incident-dashboard.html"


@mcp.tool()
def incident_dashboard(
    service: Optional[str] = None,
    severity: Optional[str] = None,
) -> dict:
    """Interactive incident dashboard — renders an inline UI widget on
    Apps-capable hosts; returns structured rows for everyone else.

    Args:
        service: optional service filter (e.g. "checkout-api")
        severity: optional severity filter (e.g. "SEV1")
    """
    rows = _mock_incidents()
    if service:
        rows = [r for r in rows if r["service"] == service]
    if severity:
        rows = [r for r in rows if r["severity"] == severity]

    payload = {
        "as_of": _now_iso(),
        "filters": {"service": service, "severity": severity},
        "rows": rows,
        "summary": {
            "open": sum(1 for r in rows if r["status"] == "open"),
            "mitigating": sum(1 for r in rows if r["status"] == "mitigating"),
            "resolved": sum(1 for r in rows if r["status"] == "resolved"),
        },
    }
    # The `_meta.ui.resourceUri` annotation is what makes this an MCP App.
    # Apps-capable clients fetch DASHBOARD_URI and render it; others ignore it.
    return {
        **payload,
        "_meta": {
            "ui": {
                "resourceUri": DASHBOARD_URI,
                "initialDisplayMode": "inline",
                "preferredHeight": 520,
            }
        },
    }


# ---------------------------------------------------------------------------
# The UI resource — plain HTML + JS, talks MCP over postMessage when embedded.
#
# The page is intentionally self-contained: no external CDNs, no build step.
# CSP is declared via `_meta.ui.csp` on the resource so the host can sandbox.
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Incident Dashboard</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: var(--mcp-color-background, #0b0f17);
      --fg: var(--mcp-color-foreground, #e6edf3);
      --muted: var(--mcp-color-muted, #8b949e);
      --accent: var(--mcp-color-accent, #2f81f7);
      --row: var(--mcp-color-surface, #161b22);
      --border: var(--mcp-color-border, #30363d);
    }
    body {
      margin: 0;
      font: 13px/1.45 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--fg);
      padding: 12px 16px 20px;
    }
    h2 { margin: 0 0 4px; font-size: 15px; }
    .meta { color: var(--muted); font-size: 12px; margin-bottom: 12px; }
    .filters { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
    .filters input, .filters select {
      background: var(--row); color: var(--fg);
      border: 1px solid var(--border); border-radius: 6px;
      padding: 4px 8px; font: inherit;
    }
    .filters button {
      background: var(--accent); color: white; border: 0;
      border-radius: 6px; padding: 4px 12px; font: inherit; cursor: pointer;
    }
    .summary {
      display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap;
    }
    .pill {
      background: var(--row); border: 1px solid var(--border);
      border-radius: 999px; padding: 3px 10px; font-size: 12px;
    }
    table { width: 100%; border-collapse: collapse; }
    th, td {
      text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border);
      font-size: 12px; vertical-align: middle;
    }
    th { color: var(--muted); font-weight: 500; cursor: pointer; user-select: none; }
    tr:hover td { background: var(--row); }
    .sev-SEV1 { color: #f85149; font-weight: 600; }
    .sev-SEV2 { color: #ff9b50; font-weight: 600; }
    .sev-SEV3 { color: #d29922; }
    .sev-SEV4 { color: var(--muted); }
    .status-open       { color: #f85149; }
    .status-mitigating { color: #d29922; }
    .status-resolved   { color: #3fb950; }
    .err { color: #f85149; padding: 10px; }
  </style>
</head>
<body>
  <h2>Incident Dashboard</h2>
  <div class="meta" id="meta">connecting…</div>

  <div class="filters">
    <select id="f-service"><option value="">all services</option></select>
    <select id="f-severity">
      <option value="">all severities</option>
      <option>SEV1</option><option>SEV2</option><option>SEV3</option><option>SEV4</option>
    </select>
    <button id="refresh">Refresh</button>
  </div>

  <div class="summary" id="summary"></div>

  <table>
    <thead>
      <tr>
        <th data-key="id">ID</th>
        <th data-key="service">Service</th>
        <th data-key="severity">Sev</th>
        <th data-key="error_rate_pct">Error %</th>
        <th data-key="p95_latency_ms">p95 ms</th>
        <th data-key="affected_users">Users</th>
        <th data-key="status">Status</th>
        <th data-key="started_at">Started</th>
      </tr>
    </thead>
    <tbody id="rows"></tbody>
  </table>

<script type="module">
  // Minimal MCP-over-postMessage client (matches ext-apps 2026-01-26).
  // The host posts JSON-RPC; we post back JSON-RPC. We use this to call
  // `tools/call` for `incident_dashboard` so the UI can refresh itself
  // without going through the LLM.
  const pending = new Map();
  let nextId = 1;
  function send(method, params) {
    const id = nextId++;
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
      window.parent.postMessage(
        { jsonrpc: "2.0", id, method, params }, "*"
      );
    });
  }
  window.addEventListener("message", (ev) => {
    const msg = ev.data;
    if (!msg || msg.jsonrpc !== "2.0") return;
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message));
      else resolve(msg.result);
    }
    if (msg.method === "ui/notifications/tool-result") {
      const r = msg.params?.result?.content;
      if (r) render(r);
    }
  });

  const rowsEl = document.getElementById("rows");
  const metaEl = document.getElementById("meta");
  const sumEl = document.getElementById("summary");
  const svcEl = document.getElementById("f-service");
  const sevEl = document.getElementById("f-severity");

  let sortKey = "started_at";
  let sortDir = -1;

  function render(payload) {
    metaEl.textContent =
      `as of ${payload.as_of}  ·  ${payload.rows.length} incident(s)`;
    sumEl.innerHTML =
      `<span class="pill"><span class="status-open">open</span> ${payload.summary.open}</span>` +
      `<span class="pill"><span class="status-mitigating">mitigating</span> ${payload.summary.mitigating}</span>` +
      `<span class="pill"><span class="status-resolved">resolved</span> ${payload.summary.resolved}</span>`;

    // populate service filter from data once
    if (svcEl.options.length <= 1) {
      const services = [...new Set(payload.rows.map(r => r.service))].sort();
      for (const s of services) {
        const o = document.createElement("option");
        o.value = s; o.textContent = s;
        svcEl.appendChild(o);
      }
    }

    const rows = [...payload.rows].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      return (av < bv ? -1 : av > bv ? 1 : 0) * sortDir;
    });
    rowsEl.innerHTML = rows.map(r => `
      <tr>
        <td>${r.id}</td>
        <td>${r.service}</td>
        <td class="sev-${r.severity}">${r.severity}</td>
        <td>${r.error_rate_pct}</td>
        <td>${r.p95_latency_ms}</td>
        <td>${r.affected_users.toLocaleString()}</td>
        <td class="status-${r.status}">${r.status}</td>
        <td>${new Date(r.started_at).toLocaleString()}</td>
      </tr>`).join("");
  }

  // Standalone demo data — used when the page is opened directly in a browser
  // (no MCP Apps host listening). Lets you preview layout/CSS without a host.
  function standaloneMock() {
    const now = Date.now();
    const t = (mins) => new Date(now - mins * 60_000).toISOString();
    const rows = [
      {id:"INC-1011", service:"checkout-api", severity:"SEV1", error_rate_pct:4.21, p95_latency_ms:1820, affected_users:8400, status:"open",       started_at:t(35)},
      {id:"INC-1010", service:"payments",     severity:"SEV1", error_rate_pct:3.10, p95_latency_ms:1450, affected_users:5200, status:"open",       started_at:t(110)},
      {id:"INC-1009", service:"search",       severity:"SEV2", error_rate_pct:1.05, p95_latency_ms: 780, affected_users:1200, status:"mitigating", started_at:t(180)},
      {id:"INC-1008", service:"auth",         severity:"SEV2", error_rate_pct:0.62, p95_latency_ms: 410, affected_users: 300, status:"mitigating", started_at:t(240)},
      {id:"INC-1007", service:"inventory",    severity:"SEV3", error_rate_pct:0.34, p95_latency_ms: 220, affected_users:  80, status:"open",       started_at:t(420)},
      {id:"INC-1006", service:"cart",         severity:"SEV3", error_rate_pct:0.21, p95_latency_ms: 195, affected_users:  40, status:"open",       started_at:t(540)},
      {id:"INC-1005", service:"checkout-api", severity:"SEV4", error_rate_pct:0.08, p95_latency_ms: 165, affected_users:   0, status:"resolved",   started_at:t(700)},
      {id:"INC-1004", service:"payments",     severity:"SEV3", error_rate_pct:0.45, p95_latency_ms: 310, affected_users: 120, status:"resolved",   started_at:t(820)},
      {id:"INC-1003", service:"search",       severity:"SEV4", error_rate_pct:0.04, p95_latency_ms: 150, affected_users:   0, status:"resolved",   started_at:t(940)},
      {id:"INC-1002", service:"auth",         severity:"SEV2", error_rate_pct:1.30, p95_latency_ms: 920, affected_users: 800, status:"resolved",   started_at:t(1100)},
    ];
    return {
      as_of: new Date().toISOString(),
      filters: {service: null, severity: null},
      rows,
      summary: {
        open:       rows.filter(r => r.status === "open").length,
        mitigating: rows.filter(r => r.status === "mitigating").length,
        resolved:   rows.filter(r => r.status === "resolved").length,
      },
      _demo: true,
    };
  }

  const isStandalone = window.parent === window;

  async function refresh() {
    try {
      let payload;
      if (isStandalone) {
        payload = standaloneMock();
        // Apply current filter selections client-side in demo mode.
        if (svcEl.value) payload.rows = payload.rows.filter(r => r.service === svcEl.value);
        if (sevEl.value) payload.rows = payload.rows.filter(r => r.severity === sevEl.value);
        payload.summary = {
          open:       payload.rows.filter(r => r.status === "open").length,
          mitigating: payload.rows.filter(r => r.status === "mitigating").length,
          resolved:   payload.rows.filter(r => r.status === "resolved").length,
        };
      } else {
        const r = await send("tools/call", {
          name: "incident_dashboard",
          arguments: {
            service: svcEl.value || null,
            severity: sevEl.value || null,
          },
        });
        const content = r?.structuredContent || r?.content?.[0]?.text;
        payload = typeof content === "string" ? JSON.parse(content) : content;
        if (!payload) throw new Error("host returned no result for tools/call");
      }
      render(payload);
      if (payload._demo) {
        metaEl.innerHTML += ` &nbsp;<span style="color:var(--muted)">(demo mode — open inside an MCP Apps host for live data)</span>`;
      }
    } catch (e) {
      metaEl.innerHTML = `<span class="err">refresh failed: ${e.message}</span>`;
    }
  }

  document.getElementById("refresh").onclick = refresh;
  svcEl.onchange = refresh;
  sevEl.onchange = refresh;
  document.querySelectorAll("th[data-key]").forEach(th => {
    th.onclick = () => {
      const k = th.dataset.key;
      if (sortKey === k) sortDir = -sortDir;
      else { sortKey = k; sortDir = 1; }
      refresh();
    };
  });

  // The host pushes the initial tool result that triggered this UI via
  // `ui/notifications/tool-result` — we handle it in the message listener
  // above. As a fallback (e.g. for the inspector), trigger a refresh.
  setTimeout(refresh, 250);
</script>
</body>
</html>
"""


@mcp.resource(
    uri=DASHBOARD_URI,
    name="Incident Dashboard UI",
    description="HTML widget for the incident_dashboard MCP tool (MCP Apps).",
    mime_type="text/html",
)
def incident_dashboard_ui() -> str:
    """Return the dashboard HTML. The host renders it in a sandboxed iframe."""
    return _DASHBOARD_HTML


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
