# Level-1 — Beginners: KMCP + google-agents-cli + MCP Inspector

**Goal:** deploy an extended FastMCP server to abox via the kmcp/`MCPServer` CRD, then exercise it from **two** clients:
1. `@modelcontextprotocol/inspector@0.21.2` — schema/tool debugger
2. `google-agents-cli playground` — local agent UI talking to the in-cluster MCP server

The same MCP server is also wired into a kagent `Agent` for in-cluster chat via the Kagent UI.

---

## What you build

`reliability-mcp-v2` — six deterministic tools:

| Tool | Purpose |
|---|---|
| `check_http_status` | HTTP 2xx probe + latency |
| `check_tcp_port`    | TCP connect probe + latency |
| `get_timestamp`     | UTC timestamp (`iso` / `unix` / `human`) |
| `parse_error_rate`  | error/success rate, 99.9% SLO check |
| `calc_error_budget` | remaining error budget for an SLO over a window |
| `classify_severity` | SEV1..SEV4 from error rate / p95 latency / impact |

---

## Steps

### 0. Prerequisites

```bash
# abox cluster up
cd /path/to/abox && make run
kubectl --context kind-abox get pods -n kagent
```

### 1. Inspect the code

```bash
cat mcp-server/server.py
```

Key points:
- FastMCP `@mcp.tool()` decorator
- Streamable HTTP on `:8000` — same transport as the kagent `MCPServer` CRD
- Tools are pure: no external state, fully deterministic except the network probes

### 2. Run locally

```bash
make install            # creates ./.venv with fastmcp + httpx
make run-local          # serves on http://localhost:8000/mcp
```

Quick smoke test in a second terminal:

```bash
SESSION_ID=$(curl -si http://localhost:8000/mcp -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"0.1"}}}' \
  | grep -i "mcp-session-id" | awk '{print $2}' | tr -d '\r')

curl -s http://localhost:8000/mcp -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | sed -n 's/^data: //p' | jq '.result.tools[].name'
```

Expected: 6 tool names.

> The MCP Streamable HTTP transport replies with SSE framing (`event: message\ndata: {...}`), not raw JSON. The `sed -n 's/^data: //p'` step strips the SSE prefix so `jq` sees pure JSON. If you want the full response instead, drop the `sed`+`jq` and just pipe to `cat`.

### 3. Build, push, deploy

```bash
export IMAGE=ghcr.io/<your-org>/reliability-mcp-v2
make deploy IMAGE=$IMAGE TAG=v0.1.0
```

**No registry?** Use `make load`:

```bash
make load IMAGE=reliability-mcp-v2 TAG=local
# then in manifests/mcp-server.yaml change:
#   image: reliability-mcp-v2:local
# and add:
#   imagePullPolicy: Never
kubectl --context kind-abox apply -f manifests/mcp-server.yaml
kubectl --context kind-abox apply -f manifests/agent.yaml
```

Verify:

```bash
kubectl --context kind-abox get mcpserver,remotemcpserver,agent -n kagent | grep v2
kubectl --context kind-abox get pods -n kagent | grep reliability-mcp-v2
```

### 4. Exercise the server with MCP Inspector

The inspector ships a web UI for browsing tools, invoking them, and inspecting raw JSON-RPC.

In one terminal:

```bash
make port-forward       # kubectl port-forward svc/reliability-mcp-v2 8000:8000
```

In another:

```bash
make inspector
# opens the Inspector UI prefilled with http://localhost:8000/mcp
```

In the Inspector UI, **set "Connection Type" to `Via Proxy`** (not `Direct`) before clicking **Connect**. `Direct` makes the browser talk to the MCP server itself — FastMCP doesn't enable CORS and the browser won't send the `Accept: application/json, text/event-stream` header the streamable-HTTP transport requires, so you'll get `Connection Error - Check if your MCP server is running…`. `Via Proxy` routes through the inspector proxy on `:6277`, which speaks MCP properly server-side.

Things to try in the Inspector UI:
- **Tools** tab → click each tool → fill arguments → run. Confirm schemas match `server.py`.
- **Resources** tab → empty (this server exposes no resources; level-2 will).
- **Capabilities** tab → confirm `tools` capability is advertised, `sampling`/`elicitation` are **not** (level-3 will).

### 5. Exercise the server with google-agents-cli playground

`google-agents-cli` is Google's CLI for building/evaluating agents. The `playground` subcommand spins a local chat UI that connects to whatever MCP server you point it at — perfect for prototyping against an in-cluster server.

In one terminal (keep the port-forward running):

```bash
make port-forward
```

In another:

```bash
# Pick a provider you have credentials for
export GEMINI_API_KEY=...   # or OPENAI_API_KEY / ANTHROPIC_API_KEY
export AGENT_PROVIDER=gemini     # gemini | openai | anthropic
export AGENT_MODEL=gemini-2.5-flash

make playground
```

`google-agents-cli playground` wraps `adk web` and discovers the agent from a `pyproject.toml` with `[tool.agents-cli]` — see [`agents-cli/`](./agents-cli/) for the minimal project (one `pyproject.toml` + a `reliability_agent/agent.py` defining `root_agent` with an ADK `McpToolset` pointing at `http://localhost:8000/mcp`).

Try the suggested prompts (also listed in the agent's `INSTRUCTION` in [`agents-cli/reliability_agent/agent.py`](./agents-cli/reliability_agent/agent.py)):
- "Check whether https://kagent.dev is healthy."
- "30-day budget: 100k requests, 80 failures, target 99.9%. How much budget remains?"
- "Classify this incident: 2% error rate, p95 1800ms, 500 users affected."

For OpenAI/Anthropic instead of Gemini, the agent uses LiteLLM under the hood:
```bash
export AGENT_PROVIDER=openai     # gemini | openai | anthropic
export AGENT_MODEL=gpt-4o-mini   # provider-specific model id (no provider/ prefix)
export OPENAI_API_KEY=...
```

### 6. Exercise the server via kagent Agent (in-cluster)

The same MCP server is wired to `reliability-agent-v2` (see [`manifests/agent.yaml`](./manifests/agent.yaml)).

```bash
kubectl --context kind-abox port-forward -n kagent svc/kagent-ui 8080:8080
# open http://localhost:8080 → pick reliability-agent-v2 → start chatting
```

---

## How the three client surfaces compare

| Client | Surface | Use it for |
|---|---|---|
| **MCP Inspector** | Tool/schema browser, raw JSON-RPC | Debugging: "is my tool schema correct?", "what does the server return for X?" |
| **agents-cli playground** | Local chat UI, you bring the LLM key | Iterating on prompts and tool descriptions before promoting to a real agent |
| **kagent Agent** | In-cluster, governed via Agent CRD, accessible via kagent UI | Production-shaped agent that other agents/users can call |

All three hit the same in-cluster MCP server pod — only the **client** changes.

---

## Files

```
level-1/
├── README.md
├── Makefile
├── mcp-server/
│   ├── server.py            # FastMCP server with 6 tools
│   ├── requirements.txt
│   └── Dockerfile
├── manifests/
│   ├── mcp-server.yaml      # MCPServer (KMCP CRD) + RemoteMCPServer
│   └── agent.yaml           # kagent Agent CRD using the MCP server
└── agents-cli/
    ├── pyproject.toml                 # [tool.agents-cli] points at reliability_agent
    └── reliability_agent/
        ├── __init__.py
        └── agent.py                   # ADK Agent + McpToolset(streamable_http)
```

---

## Cleanup

```bash
make teardown
```

---

## Common issues

**`uvx: command not found`** — install with `pip install uv` or `brew install uv`.

**Inspector shows "Connection refused"** — port-forward isn't running. Check `make port-forward` in another terminal.

**Inspector shows "Connection Error - Check if your MCP server is running and proxy token is correct"** — the **Connection Type** dropdown is set to `Direct`. Switch it to `Via Proxy` so traffic flows through the inspector proxy (`:6277`) instead of the browser hitting FastMCP directly without CORS / SSE headers.

**`agents-cli playground` exits with "no credentials"** — set the provider key matching `AGENT_PROVIDER` (e.g. `GEMINI_API_KEY`).

**Pod stuck `ImagePullBackOff`** — the registry isn't accessible from kind. Use `make load` and `imagePullPolicy: Never`.

**`jq: parse error: Invalid numeric literal at line 1, column 6`** — the MCP Streamable HTTP transport returns SSE framing (`event: message\ndata: {...}`), so piping the raw body straight into `jq` fails. Strip the `data: ` prefix first: `... | sed -n 's/^data: //p' | jq ...`.
