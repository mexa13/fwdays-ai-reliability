# Scenario — Composite incident triage

A single, realistic on-call request that exercises every team role at once. Use it as the message payload when you `make test-task` against the team-lead.

```
Incident: checkout-api is degraded.
Symptoms:
  - Error rate jumped from 0.2% to 2.1% over the last 15 minutes
  - p95 latency for POST /api/orders climbed from 380 ms to 1820 ms
  - ~800 users affected (estimate from auth-svc session counts)
  - Started: 10:14 UTC, still ongoing
  - Last deploy: 09:58 UTC (canary at 25%, full rollout 10:02)
  - Public health endpoint: https://checkout.example.com/health
What should we do next?
```

The team-lead will forward this incident text **as-is** to every peer (the per-peer `ask` is prepended). Expected per-role replies:

| Role | Expected response shape |
|---|---|
| `knowledge` (own a2a worker) | 3-4 bullet runbook snippets pulled from qdrant + FAQ — focus on canary-abort criteria and burn-rate alerting. |
| `probe`     (kagent `reliability-agent`)          | HTTP probe result for `https://checkout.example.com/health` with status code + latency_ms. |
| `triage`    (kagent `reliability-agent-sampling`) | SEV classification + concrete next steps (likely SEV2: roll back canary, page payments on-call, open IR channel). |

The team-lead then prints all three replies as a single rolled-up answer keyed by role. No fan-in summarization is required at this level — the user reads the per-role replies and decides.

## Variations

- Drop one peer (set its `role` to a non-existent URL) and confirm the rest of the team still completes — partial failure should degrade gracefully, not crash.
- Replace the `triage` role's URL with a non-kagent A2A endpoint (e.g. a second copy of your own agent) — the team is heterogeneous by design.
- Push two incidents back-to-back through the team-lead; each `message/send` opens a new task (own `task_id`), so they cannot tangle in the in-memory task store.
