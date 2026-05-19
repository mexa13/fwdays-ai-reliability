# Level-1 — Beginner: A2A Agent Card + AI infra on abox

**Goal (certificate task):**
1. Read the [A2A spec](https://a2a-protocol.org/latest/specification/).
2. Stand up **your own A2A agent** with an Agent Card served from the canonical Well-Known URI `/.well-known/agent-card.json`.
3. Deploy three pieces of AI infrastructure on `abox` and confirm they are healthy:
   - **agentregistry-inventory** — agent/MCP registry that should pick up the agent above.
   - **mcp-security-governance (MCPG)** — scores the security posture of MCP servers / kagent agents.
   - **qdrant** — vector DB via the official Helm chart (used as the knowledge store in level-2).

No LLM is required at this level — the goal is to make the **wire** work.

---

## What you build

`reliability-knowledge-agent` — an A2A agent with one skill, `reliability_qa`. The implementation is intentionally a regex-driven SRE FAQ: that keeps the agent fully deterministic so we can focus on the protocol mechanics.

```
                                 ┌────────────────────────────────┐
GET /.well-known/agent-card.json ──▶ AgentCard JSON (name, skills,│
                                 │   supportedInterfaces…)        │
                                 └────────────────────────────────┘
POST /            (JSON-RPC)
  ├── message/send   ──▶ Task object (state machine)
  ├── tasks/get      ──▶ Task object
  └── tasks/cancel   ──▶ Task object
```

The agent is built on the **official Python `a2a-sdk`** (v1.0.3). All we hand-write is:
- `ReliabilityAgentExecutor` (`execute()` + `cancel()`),
- an `AgentCard` description,
- and a 5-line Starlette wiring that bolts the SDK-provided routes onto `/`.

---

## Steps

### 0. Prerequisites

```bash
# abox cluster up (same one used in labs 1-3)
cd /path/to/abox && make run
kubectl --context kind-abox get nodes
```

Needed: `kubectl`, `helm`, `docker`, `kind`, `python3.10+`, `jq`.

### 1. Run the agent locally

```bash
make install                 # creates .venv with a2a-sdk + starlette + uvicorn
make run-local               # serves on http://localhost:9000
```

In a second terminal:

```bash
make agent-card
make test-task
```

Expected: `agent-card` prints the Agent Card JSON; `test-task` prints a `Task` whose `status.state` is `TASK_STATE_COMPLETED` and whose `status.message.parts[0].text` is the FAQ answer.

> The spec calls the well-known path `/.well-known/agent-card.json` — that's the only URL a peer needs in order to discover you. Everything else (`url`, `protocolBinding`, `protocolVersion`, supported skills) is *advertised by the card itself*.

### 2. Build and deploy the agent to abox

```bash
export IMAGE=ghcr.io/<your-org>/reliability-a2a
make deploy-agent IMAGE=$IMAGE TAG=v0.1.0
```

**No registry?** Use `make load`:

```bash
make load IMAGE=reliability-a2a TAG=local
kubectl --context kind-abox apply -f manifests/agent-deploy.yaml
# (and patch the image / imagePullPolicy in the manifest before applying)
```

Verify:

```bash
kubectl --context kind-abox -n a2a-lab get all
make port-forward                  # in one terminal
make agent-card                    # in another
```

### 3. Deploy agentregistry-inventory

```bash
make deploy-inventory
make port-forward-inventory        # opens UI/API on :8080
make inventory-list                # GET /api/v1/resources?type=agent
```

What to look for:
- The agent we just deployed should appear under "Agents" or "MCP Servers" once the controller's discovery loop kicks in (default sync is ~30s; the deploy manifest sets the label `agent.a2a.dev/protocol=1.0` to make the agent discoverable).
- The UI lives at <http://localhost:8080> if you'd rather click than `jq`.

### 4. Deploy MCP Security Governance (MCPG)

```bash
make deploy-mcpg                   # first run also builds & kind-loads the images (~3-5 min)
make port-forward-mcpg             # dashboard on :3000
# open http://localhost:3000
```

> The upstream chart hard-codes `pullPolicy: Never` against `localhost/...` image names, so the controller and dashboard have to be built locally. `deploy-mcpg` depends on `build-mcpg-images`, which runs `docker build` + `kind load docker-image` for both. To rebuild just the images (e.g. after changing controller code) without touching the Helm release, run `make build-mcpg-images` directly.

MCPG scores MCP servers / kagent agents in the cluster. From lab-2 / lab-3 you already have `reliability-tools` and `reliability-mcp-apps` running — those should show up in the scoring view with an OWASP-MCP-Top-10 breakdown.

### 5. Deploy qdrant

```bash
make deploy-qdrant
make port-forward-qdrant           # REST :6333
curl -s http://localhost:6333/collections | jq .
```

Expected: `{ "result": { "collections": [] }, "status": "ok", ... }`. Level-2 will create a collection here.

### 6. Tie the loop

Once all four are up:

| Surface | URL (after port-forward) | What you see |
|---|---|---|
| Your agent's card | http://localhost:9000/.well-known/agent-card.json | JSON: name, skills, supportedInterfaces |
| Inventory UI | http://localhost:8080 | reliability-a2a listed under Agents |
| MCPG dashboard | http://localhost:3000 | OWASP-MCP score per discovered MCP server |
| qdrant API | http://localhost:6333/collections | empty list (level-2 will fill this) |

---

## Files

```
level-1/
├── README.md
├── Makefile
├── agent-a2a/
│   ├── server.py             # AgentExecutor + AgentCard + Starlette wiring
│   ├── requirements.txt
│   └── Dockerfile
└── manifests/
    ├── agent-deploy.yaml     # Namespace + Deployment + Service for the A2A agent
    └── qdrant-values.yaml    # values for qdrant/qdrant helm chart
```

The inventory and MCPG charts are not vendored — `make deploy-inventory` / `make deploy-mcpg` clone them on demand into `./.work/`.

---

## Notes & gotchas

**Why `protocol_binding="JSONRPC"` and not `"jsonrpc"`.** A2A v1.0 changed the case convention — the well-known card now emits `"protocolBinding": "JSONRPC"`. The `TransportProtocol` enum constant in `a2a.utils.constants` is what you should always use to avoid spelling drift.

**`PUBLIC_URL` vs in-cluster URL.** The `url` field inside the Agent Card has to be what peers can resolve. In the deploy manifest we set `PUBLIC_URL=http://reliability-a2a.a2a-lab.svc.cluster.local:9000` so kagent and other in-cluster peers can call us directly; when running locally we use `http://localhost:9000` so curl works without DNS gymnastics.

**Discovery via the registry.** The inventory controller scans the cluster for resources matching certain labels/annotations. Our Deployment carries `agent.a2a.dev/protocol=1.0` and `a2a.dev/agent-card: /.well-known/agent-card.json` — those are conventional hints (different registries use different selectors; check the inventory's docs if your build is more selective).

**MCPG images are local.** The chart ships with `pullPolicy: Never` and image refs like `localhost/mcp-governance-controller:latest`, so the cluster cannot pull them from a registry. `make deploy-mcpg` therefore depends on `build-mcpg-images`, which `docker build`s the controller + dashboard out of `./.work/mcp-security-governance/` and `kind load`s them into the `abox` cluster. First run takes ~3-5 min; subsequent runs reuse Docker's layer cache.

**MCPG sample policy not installed.** We intentionally skip `--set samples.install=true`. The bundled sample `MCPGovernancePolicy` references fields (`maxToolsCritical`, `scoringWeights`, etc.) that depend on the chart's CRD landing first — but Helm's `crds/` directory silently skips CRDs that already exist in the cluster, so any stale CRD from an earlier MCPG run trips Helm with `field not declared in schema`. If you hit that after rerunning: `kubectl delete crd mcpgovernancepolicies.governance.mcp.io governanceevaluations.governance.mcp.io && helm uninstall mcp-governance -n mcp-governance`, then redeploy. Create your own `MCPGovernancePolicy` once the controller is up.

**qdrant persistence.** `qdrant-values.yaml` requests a 1Gi PVC against the `standard` storage class (kind's default via local-path-provisioner). If your cluster has no default SC, override with `--set persistence.storageClassName=...` or `--set persistence.size=0` to drop the PVC entirely.

---

## Teardown

```bash
make teardown
```

Removes the agent, the inventory release + namespace, the MCPG release + namespace, and the qdrant release + namespace. The cloned source trees in `./.work/` remain — `rm -rf .work` to drop them as well.
