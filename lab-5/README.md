# Lab-5 — Sandboxing & Observability

A three-level walk through the **two pillars of agent reliability in production**: isolating untrusted agent code with **[Agent Sandbox](https://agent-sandbox.sigs.k8s.io)** (a Kubernetes-SIG project) and seeing what your agents actually do with **[Arize Phoenix](https://arize.com/docs/phoenix)** (an OpenTelemetry-native LLM observability backend).

The story across levels:

1. **Level-1 — Beginner.** Install the Agent Sandbox controller on `abox` and reproduce the **[NetworkPolicy example](https://agent-sandbox.sigs.k8s.io/docs/use-cases/examples/network-policies/)** — an `AgenticSandbox` whose egress is locked down to a deny-by-default policy. Separately, run the **[Phoenix LangChain tracing Colab](https://colab.research.google.com/github/Arize-ai/phoenix/blob/main/tutorials/tracing/langchain_tracing_tutorial.ipynb)** to feel what OpenTelemetry traces of an LLM chain look like.
2. **Level-2 — Experienced.** Deploy **Arize Phoenix** into `abox` via the official Helm chart, expose the OTLP endpoint, and instrument your own **MCP server** (from lab-2 / lab-3) with `openinference-instrumentation-mcp` so each tool call shows up as a span in Phoenix. Bonus: enable the OpenTelemetry auto-instrumentation hooks in your Sandbox runtime and verify the SDK metrics land in Phoenix too.
3. **Level-3 — Max.** Wire `agentgateway` itself to emit OTLP traces into Phoenix (per the upstream **[telemetry tutorial](https://agentgateway.dev/docs/kubernetes/latest/tutorials/telemetry/)**) and manage Agent Sandbox **programmatically** via the Python SDK — a Code Interpreter ADK agent that spawns a Python sandbox per task and tears it down on completion, with traces flowing end-to-end.

```
                                       ┌────────────────────────────────────┐
   end-user request ─▶ agentgateway ──▶│  OTLP   ──▶  Phoenix (UI :6006)    │
                          │            │  spans                              │
                          ▼            └────────────────────────────────────┘
                       kagent / ADK ──▶  MCP server (instrumented)
                                │
                                └─▶ AgenticSandbox (NetworkPolicy-locked, SDK-managed)
```

## Why these two together

Sandboxing and observability sit on opposite sides of the same trust boundary. Sandboxing says *"contain the blast radius if the agent does something bad."* Observability says *"tell me what the agent actually did."* Without both, you can't run agents in production: an unisolated agent is a liability, and an unobserved agent is a black box. Lab-5 wires both into `abox` so the rest of your labs (own MCP servers from lab-2/3, A2A agents from lab-4) can run under proper guardrails.

## Framework choice

- **Agent Sandbox** — Kubernetes-SIG project. Ships CRDs (`Sandbox`, `SandboxTemplate`, plus the `AgenticSandbox` higher-level wrapper) and a controller; isolation is delegated to standard Pod features (NetworkPolicy, gVisor, Kata) so you keep using your cluster's existing primitives.
- **Arize Phoenix** — open-source, self-hostable. Speaks **OTLP** natively, so anything that exports OpenTelemetry (kagent, agentgateway, openinference-instrumented MCP servers, the Python SDK from a sandbox) lands in the same UI without bespoke adapters.

## Files

```
lab-5/
├── README.md                              # this file
├── Makefile
├── level-1/
│   ├── README.md
│   ├── Makefile
│   └── manifests/                         # Agent Sandbox install + NetworkPolicy use-case
├── level-2/
│   ├── README.md
│   ├── Makefile
│   ├── manifests/                         # Phoenix Helm values + Collector + ServiceMonitor
│   └── mcp-traced/                        # MCP server instrumented with openinference + phoenix.otel
├── level-3/
│   ├── README.md
│   ├── Makefile
│   ├── manifests/                         # agentgateway tracing policy → Phoenix
│   └── sdk-demo/                          # ADK code-interpreter agent that manages sandboxes via SDK
└── extras/
    ├── apikey/                            # *  agentgateway API key auth
    └── guardrails/                        # ** agentgateway webhook guardrails
```

## Recommended path

- Start with [level-1](./level-1/README.md). Stand up Agent Sandbox, run the `AgenticSandbox` + `NetworkPolicy` example, then take a coffee break with the Phoenix Colab so the rest of the lab makes sense.
- Then [level-2](./level-2/README.md) — Phoenix on cluster, point your MCP server at it, see your own tool calls as traces.
- Finally [level-3](./level-3/README.md) — agentgateway traces + a Python SDK demo that wires the whole picture together.

## Agent Sandbox + Phoenix in 30 seconds

- **Agent Sandbox CRDs.** A `SandboxTemplate` describes a pod-spec template (image, env, resources). A `Sandbox` is one running instance; a higher-level `AgenticSandbox` wires Sandbox + Service + (optionally) NetworkPolicy together. The controller lives in `agent-sandbox-system`.
- **Phoenix.** A FastAPI app that speaks **OTLP** (HTTP `/v1/traces`, gRPC port 4317) and serves the trace UI on port 6006. It stores spans in a relational store; the Helm chart defaults to a built-in SQLite that's fine for labs.
- **openinference.** Anthropic/OpenAI-ecosystem auto-instrumentations published by Arize. The MCP one wraps `FastMCP` so every `@tool` call becomes a span with input/output captured.
- **OTLP at agentgateway.** Configured via an `AgentgatewayPolicy` whose `frontend.tracing.backendRef` points at a gRPC OTLP listener — Phoenix exposes one on port 4317.

OTLP is the wire format; everything in this lab speaks it natively, so there is no custom collector code to write.

## Optional extras

- [`extras/apikey`](./extras/apikey/) — bolt an API key on the agentgateway Gateway so only authenticated clients can call the LLM backend (uses the upstream [API key tutorial](https://agentgateway.dev/docs/kubernetes/latest/security/apikey/)).
- [`extras/guardrails`](./extras/guardrails/) — register a webhook guardrail that scans prompts/responses for unsafe content before they reach the LLM (uses the upstream [webhook guardrails tutorial](https://agentgateway.dev/docs/kubernetes/latest/llm/guardrails/webhook/guardrails/)).

Both extras are independent of the level progression — apply them on top of `abox` whenever you want.
