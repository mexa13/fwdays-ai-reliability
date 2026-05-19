# Lab-4 — A2A: Agent-to-Agent communication

A three-level walk through the [Agent2Agent (A2A) protocol](https://a2a-protocol.org). The story across levels:

1. **Level-1 — Beginner.** Build your own A2A agent that publishes an **Agent Card** at the [well-known URI](https://a2a-protocol.org/latest/specification/#well-known-uri) `/.well-known/agent-card.json`. Stand up three pieces of supporting AI infrastructure on `abox`:
   - [agentregistry-inventory](https://github.com/den-vasyliev/agentregistry-inventory) — Kubernetes-native registry that auto-discovers MCP servers, agents, skills, and models.
   - [mcp-security-governance](https://github.com/techwithhuz/mcp-security-governance) (MCPG) — security/posture scoring for the MCP control plane.
   - [qdrant](https://github.com/qdrant/qdrant-helm) — vector database via the official Helm chart.
2. **Level-2 — Experienced.** Two A2A agents talking to each other. A **coordinator** agent receives a high-level request, then opens an A2A task with a **worker** agent via blocking `message/send` (the server holds the request until the task reaches a terminal state and returns the final `Task` in the response). Both publish Agent Cards; the worker uses qdrant from level-1 as a tiny knowledge store.
3. **Level-3 — Max.** A heterogeneous **A2A team**: your own team-lead plus existing **kagent** agents (from lab-3 levels 1 and 3) speaking A2A natively. One composite incident-triage task is fanned out across the team; the lead aggregates partial results.

```
                                              ┌──────────────────────────────────────────────┐
   User request ──▶ team-lead (own a2a-sdk) ──┤ reliability-worker          (own a2a, lvl-2) │  ← knowledge
                                  │           │ reliability-agent           (kagent, lab-3/1)│  ← probe
                                  └── A2A ───▶│ reliability-agent-sampling  (kagent, lab-3/3)│  ← triage
                                              └──────────────────────────────────────────────┘
```

## Framework choice

Own agents use the **official `a2a-sdk` (Python)** — it bundles the spec types as protobuf, ships a Starlette-friendly Agent Card route at the canonical well-known path, and implements both JSON-RPC and REST transports. `kagent` agents already expose A2A via the `Agent` CRD's `a2aConfig`, so the protocol is the lingua franca across levels.

## Files

```
lab-4/
├── README.md                              # this file
├── level-1/
│   ├── README.md
│   ├── Makefile
│   ├── agent-a2a/                         # own A2A agent with Agent Card
│   └── manifests/                         # agent + inventory + MCPG + qdrant
├── level-2/
│   ├── README.md
│   ├── Makefile
│   ├── agent-coordinator/
│   ├── agent-worker/
│   └── manifests/
└── level-3/
    ├── README.md
    ├── Makefile
    ├── agent-team-lead/
    ├── scenarios/                         # composite task definition
    └── manifests/
```

## Recommended path

- Begin with [level-1](./level-1/README.md). Get the well-known URI returning a valid Agent Card and confirm the inventory sees it.
- Then [level-2](./level-2/README.md) — same agent code template, but now you instantiate the **A2A client** to drive another agent's task lifecycle.
- Finally [level-3](./level-3/README.md) — register `kagent` agents as A2A peers and fan out one task across the team.

## A2A in 30 seconds

- **Agent Card** — a JSON document describing the agent's identity, skills, transports, auth. Lives at `/.well-known/agent-card.json` so a peer can discover it just from the base URL.
- **Task lifecycle** — `message/send` opens a task (or continues one); the server replies with a `Task` object whose `status.state` transitions through `submitted → working → input-required | completed | failed | canceled`.
- **Streaming** — peers can also use SSE via `message/stream` for incremental updates, identical state machine.
- **Discovery** — beyond the well-known URI, agents can be listed in a **registry** (level-1 deploys one) and a **gateway** can enforce policy (level-1 deploys MCPG, the MCP-adjacent governor).

A2A is intentionally LLM-agnostic — your agent's `execute()` does whatever it wants (call an LLM, query qdrant, run a probe). A2A is just the wire format that lets agents call each other without bespoke client code on each side.