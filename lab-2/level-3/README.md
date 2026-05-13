# Level-3: Development — Custom KMCP Server + GitLessOps

**Goal:** Build a custom Python MCP server using FastMCP, deploy it via the MCPServer CRD (KMCP), and publish manifests via GitLessOps (OCI artifact, no git push).

---

## What you'll build

A **Reliability MCP Server** with three tools:

| Tool | Description |
|---|---|
| `check_http_status` | Checks if a URL returns HTTP 2xx and measures latency |
| `get_timestamp` | Returns current UTC timestamp |
| `parse_error_rate` | Calculates error rate and 99.9% SLO compliance |

---

> **All commands below must be run from the `lab-2/level-3/` directory.**
> ```bash
> cd lab-2/level-3
> ```

## Steps

### 1. Understand the server code

```bash
cat mcp-server/server.py
```

Key concepts:
- Built with [FastMCP](https://github.com/jlowin/fastmcp) — Pythonic MCP framework
- `@mcp.tool()` decorator registers each function as an MCP tool
- Runs as a Streamable HTTP server on port 8000

### 2. Test locally

```bash
pip install fastmcp httpx
python mcp-server/server.py --port 8000 --transport streamableHttp
```

Test with curl. Streamable HTTP requires two things: the `Accept` header with both `application/json` and `text/event-stream`, and a session ID obtained via `initialize`.

```bash
# Step 1: initialize session and capture Mcp-Session-Id
SESSION_ID=$(curl -si http://localhost:8000/mcp -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl-test","version":"0.1"}}}' \
  | grep -i "mcp-session-id" | awk '{print $2}' | tr -d '\r')

# Step 2: list available tools
curl http://localhost:8000/mcp -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# Step 3: call check_http_status
curl http://localhost:8000/mcp -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"check_http_status","arguments":{"url":"https://kagent.dev"}}}'
```

One-liner (init + tools/list chained):
```bash
SESSION_ID=$(curl -si http://localhost:8000/mcp -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl-test","version":"0.1"}}}' \
  | grep -i "mcp-session-id" | awk '{print $2}' | tr -d '\r') && \
curl http://localhost:8000/mcp -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

### 3. Build and push Docker image

```bash
# Set your image registry
export IMAGE=ghcr.io/<your-org>/reliability-mcp

# Build + push
make build push-image IMAGE=$IMAGE TAG=v0.1.0
```

**Local dev (no registry):** load directly into kind:
```bash
make load IMAGE=reliability-mcp TAG=local
# Then add imagePullPolicy: Never to manifests/mcp-server.yaml
```

### 4. Deploy to cluster

```bash
# Update image in manifest
sed -i '' 's|ghcr.io/REPLACE_ORG|ghcr.io/<your-org>|g' manifests/mcp-server.yaml

# Deploy MCPServer + Agent
make deploy IMAGE=ghcr.io/<your-org>/reliability-mcp TAG=v0.1.0
```

The KMCP controller creates the Deployment and Service automatically.

### 5. Verify

```bash
kubectl --context kind-abox get mcpserver reliability-mcp -n kagent
kubectl --context kind-abox get agent reliability-agent -n kagent
kubectl --context kind-abox get pods -n kagent | grep reliability
```

### 6. Chat with the agent

```bash
kubectl --context kind-abox port-forward -n kagent svc/kagent-ui 8080:8080
```

Try these prompts:
- "Check if https://fluxcd.io is healthy"
- "Is my SLO met if I had 9990 successes out of 10000 requests?"
- "What time is it in UTC?"

---

## GitLessOps: Deploy without Git

Publish your manifests as an OCI artifact to **your own** GHCR registry — no git push, no CI.

> **Note:** `make gitlessops` in this Makefile is hardcoded to push to `ghcr.io/den-vasyliev/abox/releases` (the instructor's registry). Use the manual steps below instead.

### Prerequisites

```bash
brew install fluxcd/tap/flux

export GITHUB_USER=<your-github-username>
export GITHUB_TOKEN=<your-pat-with-packages:write>

echo $GITHUB_TOKEN | docker login ghcr.io \
  --username $GITHUB_USER \
  --password-stdin
```

### 1. Copy manifests into abox/releases

```bash
cd /path/to/abox

cp /path/to/lab-2/level-3/manifests/mcp-server.yaml releases/lab2-mcp-server.yaml
cp /path/to/lab-2/level-3/manifests/agent.yaml      releases/lab2-agent.yaml
```

Add to `releases/kustomization.yaml`:
```yaml
resources:
  - agentgateway.yaml
  - kagent.yaml
  - lab2-agent.yaml
  - lab2-mcp-server.yaml
```

> If `lab2-mcp-server.yaml` already exists from a previous step, skip the copy — it may already contain the correct content.

### 2. Push OCI artifact

Pick a tag higher than any existing one in your registry:

```bash
flux push artifact \
  oci://ghcr.io/$GITHUB_USER/abox-releases:v0.2.0 \
  --path=./releases \
  --source="oci://ghcr.io/$GITHUB_USER/abox-releases" \
  --revision="v0.2.0"
```

Make the package **Public** on GitHub: Profile → Packages → `abox-releases` → Package settings → Change visibility → Public.

### 3. Create OCIRepository + Kustomization in cluster

```bash
kubectl --context kind-abox apply -f - <<EOF
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: lab2-releases
  namespace: flux-system
spec:
  interval: 1m
  url: oci://ghcr.io/$GITHUB_USER/abox-releases
  ref:
    tag: "v0.2.0"
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: lab2-releases
  namespace: flux-system
spec:
  interval: 1m
  sourceRef:
    kind: OCIRepository
    name: lab2-releases
  path: ./
  prune: true
EOF
```

### 4. Force reconcile and verify

```bash
flux reconcile source oci lab2-releases --context kind-abox
flux reconcile kustomization lab2-releases --context kind-abox

# Expected: READY True
kubectl --context kind-abox get kustomization lab2-releases -n flux-system
kubectl --context kind-abox get mcpserver,remotemcpserver,agent -n kagent | grep reliability
```

### Updating (new tag)

When you push a new image version, push a new OCI tag and patch the OCIRepository:

```bash
flux push artifact \
  oci://ghcr.io/$GITHUB_USER/abox-releases:v0.3.0 \
  --path=./releases \
  --source="oci://ghcr.io/$GITHUB_USER/abox-releases" \
  --revision="v0.3.0"

kubectl --context kind-abox patch ocirepository lab2-releases -n flux-system \
  --type=merge -p '{"spec":{"ref":{"tag":"v0.3.0"}}}'

flux reconcile source oci lab2-releases --context kind-abox
flux reconcile kustomization lab2-releases --context kind-abox
```

### How it works

```
flux push artifact → ghcr.io/<user>/abox-releases:<tag>
  → OCIRepository detects new digest
  → Kustomization reconciles
  → kubectl apply (in-cluster)
```

No git commit. No CI pipeline. Pure OCI GitOps.

---

## Extending the server

Add a new tool by adding a function to `server.py`:

```python
@mcp.tool()
def check_latency_slo(latency_ms: float, threshold_ms: float = 200) -> dict:
    """Check if latency meets the SLO threshold."""
    return {
        "latency_ms": latency_ms,
        "threshold_ms": threshold_ms,
        "compliant": latency_ms <= threshold_ms,
    }
```

Then rebuild and redeploy:
```bash
make deploy IMAGE=ghcr.io/<your-org>/reliability-mcp TAG=v0.2.0
```

---

## Cleanup

```bash
make teardown
```
