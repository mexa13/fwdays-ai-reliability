# Level-2 — Experienced: MCP Apps case

**Goal:** ship a tool whose result includes a rich, interactive **UI widget** that the host renders inline in chat — the MCP Apps extension (spec [`2026-01-26`](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx)).

## The case: Incident Dashboard

`incident_dashboard(service=None, severity=None)` returns:

1. **Structured payload** — `as_of`, `rows`, `summary` (open / mitigating / resolved counts). LLMs without Apps support can answer questions from this directly.
2. **UI annotation** — `_meta.ui.resourceUri = "ui://reliability/incident-dashboard.html"`. Apps-capable hosts (Claude, Goose, ChatGPT, …) load that resource and render it in a sandboxed iframe inline with the chat.

Inside the iframe, the UI is itself an **MCP client** (over `postMessage` JSON-RPC). The "Refresh" button and the filter selects call `tools/call → incident_dashboard` **directly**, with **no LLM round-trip** — sub-100ms refresh and zero token cost.

```
┌─ Chat ──────────────────────────────────────────────┐
│ User: any SEV1 incidents right now?                 │
│ Agent: 2 open SEV1s. Dashboard:                     │
│ ┌─[ iframe: ui://reliability/incident-dashboard ]─┐ │
│ │  Incident Dashboard                             │ │
│ │  [service▾] [SEV▾]                  [Refresh]   │ │
│ │  open 4   mitigating 2   resolved 6             │ │
│ │  ID       Service       Sev   Err%  Status     │ │
│ │  INC-1011 checkout-api  SEV1  4.21  open       │ │
│ │  ...                                            │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
       ▲                          │
       │  tools/call refresh      │  postMessage JSON-RPC
       └──────────────────────────┘
```

## Why this design fits Apps

| Question | Without Apps | With Apps |
|---|---|---|
| "Show open SEV1s for checkout-api" | LLM re-prompted, paginates by tokens, slow & expensive | One click in the iframe, instant |
| "Sort by p95 latency" | "Reverse sort the previous output" → hallucination risk | Click column header, deterministic |
| "Refresh in 5 min" | New prompt | Refresh button (no LLM cost) |

## Steps

### 0. Prerequisites

abox cluster with kagent (see [lab-2 README](../../lab-2/README.md)). Level-1 is **not** required first.

### 1. Inspect the code

```bash
cat mcp-server/server.py
```

Key sections:
- `incident_dashboard` tool: returns `{...rows..., _meta: {ui: {resourceUri: DASHBOARD_URI, ...}}}`
- `incident_dashboard_ui` resource (`@mcp.resource(uri="ui://...", mime_type="text/html")`): returns the HTML+JS widget
- The iframe's JS does `window.parent.postMessage({jsonrpc, method:"tools/call", ...})` to re-call the tool when filters change

### 2. Build & deploy

```bash
export IMAGE=ghcr.io/<your-org>/reliability-mcp-apps
make deploy IMAGE=$IMAGE TAG=v0.1.0
```

No registry? `make load IMAGE=reliability-mcp-apps TAG=local` and set `imagePullPolicy: Never` in `manifests/mcp-server.yaml`.

### 3. Verify with MCP Inspector

```bash
make port-forward                # terminal 1
make inspector                   # terminal 2
```

In Inspector:
- **Tools** → call `incident_dashboard` → confirm result contains `_meta.ui.resourceUri`
- **Resources** → confirm `ui://reliability/incident-dashboard.html` is listed → click it → HTML preview should render

The Inspector 0.21.2 does **not** render MCP Apps widgets inline (it's a protocol debugger, not a chat host), but it confirms the resource is wired correctly.

### 4. Render the widget in a real host

The widget needs an Apps-capable host. Options:

> **Apps widget rendering** is GUI-only — Claude Desktop, ChatGPT, Cursor (Composer), Goose Desktop. **Claude Code (terminal) and the Kagent UI execute the tool and surface the structured `rows` / `summary`, but do not render the iframe.** Use them to validate the headless fallback; use a GUI host to see the widget itself.

**A. Claude Code (terminal CLI)**

Keep `make port-forward` running, then add the server via CLI:

```bash
# user scope — available in every Claude Code session
claude mcp add --scope user --transport http reliability-apps http://localhost:8000/mcp

# verify
claude mcp list
```

Or project-scope by committing `.mcp.json` to the repo:

```json
{
  "mcpServers": {
    "reliability-apps": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

In a Claude Code session: *"Show me current incidents"* → the tool fires and Claude answers from the structured payload. The widget itself does **not** render (terminal); flip to a GUI host below to see it.

**B. Cursor**

Edit `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (per-repo):

```json
{
  "mcpServers": {
    "reliability-apps": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Restart Cursor → open the Agent/Composer pane → check that `reliability-apps` is listed under MCP tools → ask *"Show me current incidents"*. Cursor renders the Apps iframe inline if your build supports it; otherwise it falls back to the structured payload (same as Claude Code).

**C. Claude Desktop**

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) / `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "reliability-apps": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Restart Claude Desktop. This is the reference Apps host — the dashboard widget renders inline.

**D. Goose (open-source)**

Goose is no longer published via `block/tap`. Install the CLI from the upstream release script, or grab the Desktop app from [releases](https://github.com/block/goose/releases):

```bash
# CLI
curl -fsSL https://github.com/block/goose/releases/download/stable/download_cli.sh | bash

goose configure          # → "Add Extension" → "Remote Extension (Streaming HTTP)"
                         #   name: reliability-apps
                         #   url:  http://localhost:8000/mcp
goose session
> show current incidents
```

The Desktop app renders MCP Apps widgets inline; the CLI executes the tool but prints the structured payload.

**E. kagent in-cluster Agent**

```bash
kubectl --context kind-abox port-forward -n kagent svc/kagent-ui 8080:8080
# open http://localhost:8080 → reliability-agent-apps → "show incidents"
```

> The Kagent UI **does not yet render MCP Apps widgets**; it shows the structured payload as JSON. Use this path to confirm the headless fallback works (LLM can still answer questions from `rows` + `summary`).

### 5. Try interactive features in an Apps-capable host

1. Click a column header → table sorts; no chat message is sent
2. Pick a service in the dropdown → row count drops; `tools/call` fires under the hood
3. Click "Refresh" → `as_of` timestamp updates

Open the host's devtools network inspector (where available) to see the JSON-RPC frames flowing over `postMessage`.

---

## Files

```
level-2/
├── README.md
├── Makefile
├── mcp-server/
│   ├── server.py            # FastMCP server: tool + @mcp.resource ui://...
│   ├── requirements.txt
│   └── Dockerfile
└── manifests/
    ├── mcp-server.yaml      # MCPServer + RemoteMCPServer
    └── agent.yaml           # kagent Agent that uses the tool
```

---

## Implementation notes

**Why a plain `@mcp.resource()` + `_meta.ui` annotation rather than `@mcp.tool(app=...)`?**
The protocol-level pattern (resource URI + meta annotation on the tool result) is what the MCP Apps spec actually defines. The `@mcp.tool(app=...)` decorator in FastMCP 3.0 is sugar over the same protocol moves. The explicit pattern works on FastMCP 2.x and 3.x and makes the spec mapping obvious.

**CSP.** The HTML uses only inline `<style>` and `<script type="module">` — no external CDNs — so the default Apps CSP works without declaring `connect_domains`/`resource_domains`. If you fetch from a CDN, you'd add `_meta.ui.csp` on the resource result.

**Theming.** The CSS uses `var(--mcp-color-background, fallback)` — the host injects these CSS variables per spec so the widget matches the host theme.

**Fallback for non-Apps clients.** The tool's structured payload is complete and self-describing; the LLM can summarize without the widget.

---

## Cleanup

```bash
make teardown
```
