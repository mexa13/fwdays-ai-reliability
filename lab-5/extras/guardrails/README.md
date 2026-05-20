# Extras: agentgateway webhook guardrails

Per the upstream [webhook guardrails tutorial](https://agentgateway.dev/docs/kubernetes/latest/llm/guardrails/webhook/guardrails/). Deploys the sample `ai-guardrail-webhook` next to the gateway and binds an `AgentgatewayPolicy` that runs the webhook against every prompt and response heading through the `openai` HTTPRoute (from lab-1/level-3).

```bash
make apply              # webhook + Service + Policy + tunables
make test               # benign prompt → 200; injection prompt → 4xx
make teardown
```

Resources:

- **`AgentgatewayParameters/agw-guardrail-tunables`** — bumps webhook keepalive & connection pool so the proxy doesn't bottleneck.
- **`Deployment/Service ai-guardrail-webhook`** — the upstream reference scanner image. Replace with your own webhook (any HTTP server that implements the [guardrails webhook spec](https://agentgateway.dev/docs/kubernetes/latest/llm/guardrails/webhook/)) once you outgrow the demo.
- **`AgentgatewayPolicy/openai-prompt-guard`** — `request` and `response` arrays both point at the same webhook; the proxy calls the webhook **before** and **after** the LLM, so blocked content never reaches the model and unsafe model output never reaches the user.

If you have the level-3 tracing policy enabled, every guardrail-blocked request still produces a Phoenix span — the rejection shows up as an error status, so you can graph "blocked prompts per hour" without extra plumbing.
