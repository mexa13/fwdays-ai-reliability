# Level-2 — Experienced: A2A task between two agents

**Goal:** prove that two independently-deployed A2A agents can drive each other's task lifecycle over the wire. A **coordinator** receives a high-level reliability question; it decomposes the question, then opens an A2A task with a **worker** for each sub-question and rolls up the results.

```
user ──HTTP JSON-RPC──▶ coordinator (:9002) ──A2A──▶ worker (:9001)
                              │                          │
                              │                          └──▶ qdrant (:6333)
                              ◀───── streamed Task status / final answer
```

Both agents publish Agent Cards at `/.well-known/agent-card.json` and speak the same JSON-RPC transport. The coordinator is implemented as an A2A **server** for its caller *and* an A2A **client** for the worker — that bidirectional shape is the level-2 lesson.

Level-1 must be deployed first (qdrant is reused; inventory/MCPG will pick up both new agents automatically).

---

## What you build

| Agent | Port | Skill | What it actually does |
|---|---|---|---|
| `reliability-coordinator` | 9002 | `reliability_brief` | Trigger-keyword decomposition → fan out → roll-up |
| `reliability-worker`      | 9001 | `reliability_qa`    | FAQ regex + qdrant `sre-runbooks` collection search |

The coordinator's **client-side** code is intentionally small — see `agent-coordinator/server.py:_ask_worker()`:

```python
client = await create_client(WORKER_URL, ClientConfig(streaming=False, polling=True))
req = SendMessageRequest(
    message=Message(message_id=str(uuid.uuid4()), role=Role.ROLE_USER,
                    parts=[Part(text=question)])
)
async for resp in client.send_message(req):
    if resp.HasField("task"):
        final_task = resp.task
```

That's the whole peer call. `create_client` fetches the worker's Agent Card, inspects `supportedInterfaces`, picks the JSON-RPC binding, and constructs a transport for you. The async iterator collapses to a single final `Task` on a non-streaming peer.

---

## Steps

### 0. Prerequisites

- level-1 deployed (`make -C ../level-1 deploy-all`).
- `qdrant` reachable in-cluster at `qdrant.qdrant.svc.cluster.local:6333`.
- `kubectl`, `helm`, `docker`, `jq`.

### 1. Run locally

```bash
make install
# terminal 1
make run-worker-local            # uvicorn worker on :9001
# terminal 2
make run-coord-local             # coordinator on :9002, WORKER_URL=http://localhost:9001
# terminal 3
make test-task                   # POST to coordinator → triggers two A2A calls to worker
```

You should see the coordinator log `decomposed '...' into 2 sub-question(s)` and the worker log two `message/send` round-trips. The final response prints the rolled-up answer.

### 2. Deploy to abox

```bash
export IMAGE_PREFIX=ghcr.io/<your-org>
make deploy IMAGE_PREFIX=$IMAGE_PREFIX TAG=v0.2.0
```

Or, without a registry:

```bash
make load TAG=local
kubectl --context kind-abox apply -f manifests/agents-deploy.yaml   # remember to patch images
kubectl --context kind-abox apply -f manifests/qdrant-seed-job.yaml
```

`make deploy` also runs the `qdrant-seed-sre-runbooks` Job once — it creates the `sre-runbooks` collection in qdrant and inserts a handful of points so the worker's `_qdrant_search` returns hits even without an embedding model.

### 3. Exercise

```bash
make port-forward-coord
# in another terminal:
make test-task
```

Try varying the question. The coordinator accepts two equivalent JSON-RPC dialects on the same endpoint — pick whichever feels natural:

**v0.3 spec style** (what `make test-task` uses):

```bash
curl -s http://localhost:9002/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"kind":"message","role":"user","parts":[{"kind":"text","text":"Tell me about postmortems and retries"}],"messageId":"m2"}}}' \
  | jq -r '.result.status.message.parts[0].text'
```

**gRPC-native style** (matches the SDK's `create_client` traffic on the wire):

```bash
curl -s http://localhost:9002/ \
  -H 'Content-Type: application/json' \
  -H 'a2a-version: 1.0' \
  -d '{"jsonrpc":"2.0","id":1,"method":"SendMessage","params":{"message":{"role":"ROLE_USER","parts":[{"text":"Tell me about postmortems and retries"}],"messageId":"m2"}}}' \
  | jq -r '.result.task.status.message.parts[0].text'
```

> Two things to watch out for if you copy-paste these curls and get `null`:
> 1. **Don't mix dialects.** Method `message/send` requires lowercase `role:"user"`, `kind:"message"`, and `Part:{kind:"text",text:...}`. Method `SendMessage` requires `role:"ROLE_USER"` (proto enum) and no `kind` fields. The response shape also differs (`result.*` vs `result.task.*`).
> 2. **`SendMessage` needs the `a2a-version: 1.0` header.** Without it, the SDK treats the client as 0.3-compatible and the 1.0-native handler rejects the call with `VERSION_NOT_SUPPORTED`. `message/send` does not need the header because it routes through the explicit v0.3 compat shim.
>
> If you keep your message body on one line (no shell wrapping that inserts a literal newline into the JSON string), both curls return a `completed` task whose answer text is at the jq path above.

What to look for:

- The coordinator's response begins with `Routed N sub-question(s) to http://reliability-worker.a2a-lab.svc.cluster.local:9001` — proof the peer URL came from the worker's Agent Card, not from your code.
- Worker pod logs show one `POST /` per sub-question with `Q: ...  →  A: ...`.
- The worker mixes a FAQ answer with one or more `Runbook hits:` lines pulled from qdrant.

### 4. (Optional) Inspect via the inventory

```bash
make -C ../level-1 port-forward-inventory
make -C ../level-1 inventory-list
```

Both `reliability-coordinator` and `reliability-worker` should appear in the inventory's agent list after its next discovery sync.

---

## Files

```
level-2/
├── README.md
├── Makefile
├── agent-coordinator/
│   ├── server.py          # AgentExecutor + A2A client to the worker
│   ├── requirements.txt
│   └── Dockerfile
├── agent-worker/
│   ├── server.py          # AgentExecutor + qdrant search
│   ├── requirements.txt
│   └── Dockerfile
└── manifests/
    ├── agents-deploy.yaml      # both Deployments + Services in a2a-lab
    └── qdrant-seed-job.yaml    # one-shot Job to create + seed sre-runbooks
```

---

## Why a Job to seed qdrant?

Two reasons:

1. **No embedding model in the lab.** Both worker and seed job hash the input into the same 32-dim toy vector, so vector search returns deterministic hits without dragging an embedding service into level-2.
2. **Idempotent.** The Job's create-collection is `PUT` (qdrant accepts a re-create on a matching schema as a no-op), and the upserts use stable ids. Re-running `make seed-qdrant` is safe.

When you wire a real embedding model in later labs, replace `_toy_vector` and the seed-job vectors; everything else stays the same.

---

## Teardown

```bash
make teardown
```

Removes both deployments + services and the seed Job, but leaves the `a2a-lab` namespace, level-1's agent, and the qdrant/inventory/MCPG stacks intact.
