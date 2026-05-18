# Research: MCP Sampling / Elicitation / Apps — Real-World Cases

**Spec references**
- Sampling — [`2025-06-18/client/sampling`](https://modelcontextprotocol.io/specification/2025-06-18/client/sampling)
- Elicitation — [`2025-06-18/client/elicitation`](https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation)
- Apps — [`ext-apps 2026-01-26`](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx) ([launch blog](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/))

**SDK references**
- [FastMCP — Sampling](https://gofastmcp.com/servers/sampling)
- [FastMCP — Elicitation](https://gofastmcp.com/servers/elicitation)
- [FastMCP — Apps quickstart](https://gofastmcp.com/apps/quickstart)

---

## 1. MCP Sampling

**Mechanic.** Server sends `sampling/createMessage` to the client; client (with optional human-in-the-loop approval) routes the request to whichever LLM it owns and returns the completion. The server consumes the host's LLM seat — no API keys, no extra spend, no model lock-in on the server side.

### Technical cases

| # | Case | Why sampling fits |
|---|---|---|
| 1 | **Log-cluster root-cause hypotheses** — server clusters errors, asks the host LLM "what's the most likely root cause?" | Server has the data, host has the model; avoids embedding a second LLM in the tool. |
| 2 | **Stakeholder explainer** — server converts numeric SLO/latency data into a one-paragraph executive summary | Tone & length depend on the user; their model is already tuned for their style. |
| 3 | **Agentic sub-step** — a "find owner" tool that samples with `tools=[...]` to traverse multiple internal directories until it finds the on-call engineer | Loops belong on the server (deterministic), reasoning belongs on the host (capable). |
| 4 | **Hypothetical Document Embedding (HyDE)** — retrieval tool asks the LLM to write a fake answer first, then embeds it for search | Lets the server stay model-agnostic. |
| 5 | **Diff critique** — code-review tool asks for inline critique before annotating | Critique quality scales with the user's model tier; server doesn't have to. |

### Business cases

| # | Case | Value driver |
|---|---|---|
| 1 | Customer-support MCP drafts ticket replies using the agent's existing LLM seat | Zero marginal LLM cost; one SaaS bill instead of two. |
| 2 | Compliance tool summarizes contracts on demand | Privacy: data never leaves the org's LLM contract. |
| 3 | Sales-CRM personalizes outreach with the rep's tuned model | Personalization without each tool shipping fine-tunes. |
| 4 | Marketing dashboard generates executive narratives from KPI snapshots | "Bring your own model" — works with whichever LLM Finance approves. |
| 5 | HR policy plain-language rewriter | No vendor lock; user-side model can be swapped per region. |

---

## 2. MCP Elicitation

**Mechanic.** Server sends `elicitation/create` with a flat, restricted JSON Schema (scalars + enums + format strings; no nested objects, no arrays of objects). Client renders a form, user returns `accept | decline | cancel`. Spec **forbids** asking for secrets/PII this way.

### Technical cases

| # | Case | Why elicitation fits |
|---|---|---|
| 1 | **Confirm destructive ops** — `DROP TABLE`, `kubectl delete`, force-push, prod deploy | Human gate without scripting another approval flow. |
| 2 | **Disambiguation** — same name matches 4 services; pick one from an enum | Constrained choice the model can't hallucinate. |
| 3 | **Missing required parameter** — tool needs a namespace; ask once instead of failing | Fewer round-trips than re-prompting the model. |
| 4 | **Policy-mandated human authorship** — commit messages, PR descriptions, release notes | Compliance: humans must be in the chain of custody. |
| 5 | **Test scope selection** — which test suite / parallelism / target env | Faster than re-prompting the LLM in chat. |

### Business cases

| # | Case | Value driver |
|---|---|---|
| 1 | Expense filing — elicit cost center & project code mid-flow | Captures structured data accountants can actually use. |
| 2 | Travel booking — passenger name, DoB, seat preference | Replaces a separate booking form. |
| 3 | Marketing approval — budget & campaign window | Approver in the loop on every spend. |
| 4 | Procurement — PO line items with vendor-validated enum choices | Eliminates free-text typos that break ERPs. |
| 5 | Onboarding — KYC-lite fields collected inline | Faster than email-form ping-pong. |

---

## 3. MCP Apps

**Mechanic.** Server attaches a `ui://` resource (HTML/JS) to a tool result via `_meta.ui`. Host renders it in a sandboxed iframe; iframe is itself an MCP client over `postMessage` JSON-RPC and can call `tools/call`, `resources/read`, `ui/open-link`, `ui/request-display-mode`, etc. Three display modes: `inline`, `fullscreen`, `pip`. Stable spec dated **2026-01-26**, FastMCP 3.0 ships first-class support.

### Technical cases

| # | Case | Why Apps fit |
|---|---|---|
| 1 | **Live pod/SLO dashboard** — `kubectl get` polled from inside the iframe via in-chat MCP tool calls | Real-time UI without leaving the chat. |
| 2 | **Sortable/filterable SQL result table** | Avoids re-prompting the model to page or sort. |
| 3 | **Side-by-side diff viewer** with approve/reject buttons that fire MCP tool calls | One-click code review inline. |
| 4 | **Drag-and-drop file uploader** | Multipart upload mid-conversation. |
| 5 | **Embedded chart (Plotly/ECharts)** for time-series data | Visual analytics > a markdown table. |

### Business cases

| # | Case | Value driver |
|---|---|---|
| 1 | Asana/monday.com task-board widget in chat | In-flow project management — no context switch. |
| 2 | Canva-style mini-editor for marketing creative tweaks | Reduces creative review cycle. |
| 3 | Slack channel picker for one-click announcement | Friction-free internal comms from inside the assistant. |
| 4 | Salesforce opportunity card editable in chat | Reps update CRM without leaving their workflow. |
| 5 | Box/Drive file browser inline for document retrieval & approvals | Eliminates window juggling during reviews. |

---

## How the three combine for reliability engineering

The labs in this directory ship a concrete reliability-engineering case for each:

| Level | Capability | Concrete tool |
|---|---|---|
| level-1 | (none — baseline KMCP) | Extended `reliability-mcp` with 5 deterministic tools + google-agents-cli playground |
| level-2 | **Apps** | `incident_dashboard` returns a live, sortable HTML widget of recent failures |
| level-3 | **Elicitation + Sampling** | `triage_incident` elicits severity/service from the user, then samples the host LLM to draft a stakeholder update + postmortem skeleton |

---

## Client support snapshot (May 2026)

| Client | Sampling | Elicitation | Apps |
|---|---|---|---|
| Claude Desktop / Code | ✅ | ✅ | ✅ |
| ChatGPT | ⚠ partial | ⚠ | ✅ |
| VS Code Copilot (Agent Mode) | ✅ | ✅ | ⚠ insiders |
| Cursor 0.45+ | ✅ | ✅ | — |
| Goose | ✅ | ✅ | ✅ |
| kagent (in-cluster) | ⚠ relies on server-side `sampling_handler` fallback | ⚠ no UI; auto-decline or pre-filled defaults | — |

**Implication for kagent deployments:** when an MCP server is invoked by a kagent Agent (no UI, no per-call human-in-the-loop), elicitation has no one to ask and sampling has no host LLM to route to. FastMCP gives us two escape hatches:

1. **Sampling handler fallback** — `FastMCP(..., sampling_handler=OpenAISamplingHandler(...), sampling_handler_behavior="fallback")` lets the server call an LLM directly when the client lacks support.
2. **Elicitation `decline` / default** — wrap `ctx.elicit()` and on `DeclinedElicitation` fall back to deterministic defaults (severity=`unknown`, namespace=`default`).

Level-3 implements both fallbacks so the same server is usable from Claude Desktop (full interactivity) and from kagent (best-effort headless).

---

## Companion tooling

- **`google-agents-cli`** — Google's CLI for building/evaluating/deploying agents (typically ADK on GCP). For this lab we use the local **playground** mode (`uvx google-agents-cli playground`) to exercise our in-cluster MCP server via port-forward. Docs: <https://google.github.io/agents-cli/>.
- **`kmcp`** (Solo.io) — `kmcp init` / `build` / `deploy` operationalize FastMCP servers on Kubernetes via the `MCPServer` CRD. Pairs with kagent. Blog: <https://www.solo.io/blog/introducing-kmcp>.
- **`@modelcontextprotocol/inspector@0.21.1`** — official MCP debugger; the lab uses it to introspect tool schemas, capabilities, and exercise sampling/elicitation interactively against our server.
