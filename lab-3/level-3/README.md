# Level-3 — Max: MCP Sampling + Elicitation

**Goal:** ship a tool server where the **server** drives interactive flows:
- **Elicitation** — server requests structured input from the user via the client
- **Sampling** — server requests an LLM completion from the host

Spec: [MCP 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/) — both capabilities live in the `client/*` section because the client is what executes them on behalf of the server.

## The case: Incident Commander assistant

Three tools, each demonstrating a different capability mix:

| Tool | Elicit | Sample | What it does |
|---|---|---|---|
| `confirm_runbook_step` | ✅ | — | Human gate before a destructive operation (DROP TABLE, restart prod pods). Server pauses and asks the user via a typed form. |
| `explain_anomaly` | — | ✅ | Server gives the host LLM numeric data + audience (engineer/exec/customer) and asks it to write a 2-4 sentence explanation. |
| `triage_incident` | ✅ | ✅ | End-to-end: elicit severity / impact / start time / symptoms → sample a stakeholder Slack update + postmortem skeleton → return both plus next-step recommendations. |

### Why server-driven flows matter

- **Elicitation** keeps the LLM out of decisions humans must own (severity, target namespace, destructive approval) — the model can't hallucinate a SEV1 into a SEV3.
- **Sampling** lets the server stay model-agnostic and free of API keys. The tool uses whichever LLM the user is paying for; tone matches the user's existing prompt-engineering choices.

### Headless fallback

When invoked from a kagent Agent (no UI, no per-call human in the loop), both capabilities have no one to ask:
- `safe_elicit()` catches the failure and returns a default value (e.g. severity=`SEV3`) plus a `fallback=true` note.
- `safe_sample()` catches the failure and returns a deterministic template plus a `fallback=true` note.

This makes the same server usable both from Claude Desktop (full interactivity) and from kagent (best-effort headless).

---

## Steps

### 0. Prerequisites

```bash
cd /path/to/abox && make run
kubectl --context kind-abox get pods -n kagent
```

### 1. Inspect the code

```bash
cat mcp-server/server.py
```

Key sections:
- `safe_elicit()` / `safe_sample()` — defensive wrappers with deterministic fallback
- `confirm_runbook_step` — pure elicitation, returns `{approved, reason, fallback}`
- `explain_anomaly` — pure sampling, returns audience-tailored prose
- `triage_incident` — both in sequence; the elicited inputs become facts for the sampling prompt

### 2. Run locally

```bash
make install
make run-local
```

### 3. Test interactively with MCP Inspector

```bash
# terminal 1
make run-local

# terminal 2
make inspector
```

`@modelcontextprotocol/inspector@0.21.2` is **the right client for this lab** — unlike the kagent UI, it actually implements `sampling` and `elicitation` capabilities, so you'll see the elicitation form pop up and the sampling request fire.

What to try in the Inspector:
- **Capabilities** tab → confirm the client advertises `sampling` + `elicitation`
- **Tools** → call `confirm_runbook_step({step_description: "restart all checkout pods"})` → an Elicitation form appears asking for `approve` + `reason`
- **Tools** → call `explain_anomaly({metric: "p95 latency", before: 200, after: 1800, unit: "ms", audience: "exec"})` → a Sampling approval prompt appears showing the prompt to be sent to your configured LLM (set OpenAI/Anthropic API key in Inspector settings)
- **Tools** → call `triage_incident({service: "checkout-api"})` → first an Elicitation form, then a Sampling request, then a Sampling request again

### 4. Deploy to abox

```bash
export IMAGE=ghcr.io/<your-org>/reliability-mcp-sampling
make deploy IMAGE=$IMAGE TAG=v0.1.0
```

No registry? `make load IMAGE=reliability-mcp-sampling TAG=local` and set `imagePullPolicy: Never`.

### 5. Exercise from kagent (headless)

```bash
kubectl --context kind-abox port-forward -n kagent svc/kagent-ui 8080:8080
# open http://localhost:8080 → reliability-agent-sampling
> Start a triage for checkout-api
```

Watch for `"fallback": true` in the tool result — that means the kagent Agent did not implement elicitation/sampling and the server fell back to templates / defaults. The agent's prompt instructs it to **surface the templated output and ask the user inline for missing details**, so the conversation still works.

### 6. Exercise from an interactive client (full capabilities)

For the full effect (real elicitation forms, real sampled stakeholder updates), connect from Claude Desktop, Claude Code, Cursor, Goose, or VS Code Copilot Agent Mode:

```bash
make port-forward
# point your MCP client at http://localhost:8000/mcp
> Start incident triage for checkout-api
```

You'll see:
1. An elicitation form pop up in the client UI (severity dropdown, affected_users number input, started_at, symptoms text)
2. After you submit, a sampling approval showing the prompt → confirm → LLM generates the Slack update
3. A second sampling approval for the postmortem skeleton
4. The final structured tool result with `stakeholder_update`, `postmortem_skeleton`, `next_steps`

---

## Files

```
level-3/
├── README.md
├── Makefile
├── mcp-server/
│   ├── server.py            # Sampling + Elicitation tools with safe fallbacks
│   ├── requirements.txt
│   └── Dockerfile
└── manifests/
    ├── mcp-server.yaml      # MCPServer + RemoteMCPServer
    └── agent.yaml           # kagent Agent that uses the tools (headless fallback path)
```

---

## Capability discovery — how the Inspector knows

When the inspector initializes the connection, the **client** advertises which capabilities it supports:

```json
{
  "method": "initialize",
  "params": {
    "capabilities": {
      "sampling":    {},
      "elicitation": {},
      "roots": { "listChanged": true }
    }
  }
}
```

The server reads this from `ctx.client_capabilities` and could choose to disable tools that require missing capabilities. We took a softer path: every tool still runs, but degrades to a deterministic fallback. That's typically the right call for production — the server should not vanish when a less-capable client connects.

---

## Cleanup

```bash
make teardown
```

---

## Common issues

**Inspector "Sampling rejected"** — the inspector prompts you for an LLM provider on first use. Pick one (OpenAI / Anthropic / etc.), paste a key, and approve the request.

**`safe_sample()` returns a template even from Inspector** — your inspector version doesn't have an LLM configured, or you rejected the approval. Check the inspector Settings tab.

**Tool result shows `"fallback": true` from kagent** — expected. kagent does not yet route sampling back to the model serving the agent (would require a Sampling reflection loop). The server's templated fallback keeps the agent useful.
