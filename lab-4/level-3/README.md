# Level-3 — Max: heterogeneous A2A team (own agent + kagent agents)

**Goal:** one composite reliability task — an incident triage request — is fanned out across a **team** of A2A agents and a single rolled-up answer is returned to the caller.

The team is intentionally mixed:

- **`knowledge`** — your own `reliability-worker` from level-2 (a2a-sdk Python, no LLM).
- **`probe`** — the kagent `reliability-agent` from lab-3 level-1 (LLM-backed, MCP tools, has the `health-check` skill).
- **`triage`** — the kagent `reliability-agent-sampling` from lab-3 level-3 (uses MCP Sampling + Elicitation for severity classification + human-in-the-loop).

The lead agent — your **own** A2A agent built on `a2a-sdk` — only knows each peer by a URL plus a per-role *ask* prompt. Everything else (schema, transport, skills) it discovers from each peer's Agent Card. That's the level-3 lesson: once two agents speak A2A, your team-lead does not care which framework powers each peer.

```
incident ──┐
           ├──HTTP JSON-RPC─▶ team-lead (:9100, own a2a-sdk)
           │                       │  asyncio.gather:
           │                       ├──A2A──▶ reliability-worker          (a2a-sdk)
           │                       ├──A2A──▶ reliability-agent           (kagent, lab-3 level-1)
           │                       └──A2A──▶ reliability-agent-sampling  (kagent, lab-3 level-3)
           ◀── rolled-up reply ────┘
```

---

## What you build

`reliability-team-lead` — an A2A agent with one skill, `incident_triage`. Internally:

1. Reads peer config from `PEERS_FILE` / `PEERS_CONFIG` (`peers.json`).
2. For each peer, opens a parallel A2A task via `create_client(peer.url).send_message(...)`.
3. Concatenates per-role replies into a single answer; failures show up as the role's reply text so partial team output is still useful.

The peer-config approach decouples the team membership from the code — swap kagent agents in/out by editing `peers.json` or the ConfigMap; no rebuild required.

---

## Steps

### 0. Prerequisites

- **level-1 deployed** (agent + qdrant + inventory + MCPG).
- **level-2 deployed** (`reliability-worker` is `knowledge` in the default team).
- **lab-3 level-1 + level-3 deployed** — `reliability-agent` and `reliability-agent-sampling` in the `kagent` namespace.
- `kubectl` access to `kind-abox`.

If you don't have one of the kagent agents, edit `agent-team-lead/peers.json` (or the ConfigMap in `manifests/team-deploy.yaml`) and drop that entry, or point the role at another A2A endpoint you do have.

### 1. Deploy to the cluster (recommended path)

This is the only fully-working path when the team includes kagent peers. See [Why not local?](#why-not-local) below for the reason.

```bash
export IMAGE=ghcr.io/<your-org>/reliability-team-lead
make deploy IMAGE=$IMAGE TAG=v0.3.0
make port-forward                                # svc/reliability-team-lead:9100 → localhost
make test-task                                   # in another terminal
```

The in-cluster `peers.json` (mounted from the ConfigMap in `manifests/team-deploy.yaml`) defaults to the kagent and level-2 agent URLs. Tweak the ConfigMap and re-apply if your kagent agents live in a different namespace or have different names.

### 2. (Optional) Run team-lead locally — only when ALL peers are your own a2a-sdk agents

Local mode is useful for iterating on team-lead logic when every peer is also under your control (e.g. three copies of the level-2 worker on different ports). It does **not** work with kagent peers — see [Why not local?](#why-not-local) below.

```bash
make install
# edit agent-team-lead/peers.json to point at three a2a-sdk agents you control,
# e.g. all running on localhost:90XX with PUBLIC_URL=http://localhost:90XX
make run-local                                   # team-lead on :9100
make test-task                                   # in another terminal
```

#### Why not local?

A2A clients always trust the URL inside the peer's Agent Card, not the URL you connect to. Two concrete leaks:

1. **kagent agent cards publish in-cluster DNS.** `curl http://localhost:8080/.well-known/agent-card.json` (via your port-forward) returns `"url": "http://reliability-agent.kagent:8080"`. `create_client(peer.url)` fetches the card from `localhost:8080`, then uses `card.url` for every subsequent `send_message` — and that hostname does not resolve outside the cluster.

2. **The level-2 worker's tail dependencies are in-cluster too.** Running `agent-worker/server.py` locally still has it dialing `qdrant.qdrant.svc.cluster.local:6333` (no DNS locally → 3s timeout per request → the team-lead's A2A client gives up before the worker responds).

Deploying team-lead into the cluster fixes both: every URL the SDK pulls out of every card now resolves through in-cluster DNS.

### 3. Inspect

```bash
make discover-peers
```

Prints each configured peer's `Agent Card` (`name`, `version`, declared `skills`). If one of those fails, the team-lead will too — fix the URL first.

You can also see the team-lead in the level-1 inventory UI alongside the worker and any kagent agents.

---

## Files

```
level-3/
├── README.md
├── Makefile
├── scenarios/
│   └── incident-triage.md       # the canonical composite task used by `make test-task`
├── agent-team-lead/
│   ├── server.py                # AgentExecutor + asyncio.gather over A2A peers
│   ├── peers.json               # default team wiring (in-cluster URLs)
│   ├── requirements.txt
│   └── Dockerfile
└── manifests/
    └── team-deploy.yaml         # ConfigMap with peers.json + Deployment + Service
```

---

## Notes

**Why one prompt per role rather than one per peer call?** Each role has a stable specialty (`knowledge` reads runbooks, `probe` performs reachability checks, `triage` classifies severity). The team-lead doesn't need to know what's behind a role — it just appends the user-supplied incident context to the role's pre-baked ask. Adding a new role is a config edit, not a code change.

**Graceful degradation.** `_ask_peer` catches everything and turns failures into the peer's reply text. A network blip in one peer should not kill triage for the rest of the team — see `scenarios/incident-triage.md` for the "drop one peer" variation.

**kagent A2A URLs.** kagent serves an agent's A2A endpoint behind `Service/<agent-name>` in the namespace it was deployed to (typically `kagent`). The exact port can vary between kagent builds — `make discover-peers` is your fastest way to verify. If kagent uses a gateway/proxy in front of agents, point `peers.json` at the proxy URL, not the Service.

**Aggregation is intentionally dumb.** Level-3's value is the *wire pattern* and the *graceful degradation*, not a fancy roll-up. Replace the simple concatenation with an LLM-driven summarizer the moment that adds value (e.g. another `ctx.sample` call à la lab-3 level-3).

---

## Teardown

```bash
make teardown                    # team-lead Deployment + Service + ConfigMap
make -C ../level-2 teardown      # worker + coordinator + qdrant seed Job
make -C ../level-1 teardown      # agent + inventory + MCPG + qdrant
```
