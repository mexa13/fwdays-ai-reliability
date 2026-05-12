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

Test with curl:
```bash
# List available tools
curl http://localhost:8000/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# Call check_http_status
curl http://localhost:8000/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"check_http_status","arguments":{"url":"https://kagent.dev"}}}'
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

Publish your manifests as an OCI artifact directly — no GitHub, no CI:

```bash
# Install Flux CLI
brew install fluxcd/tap/flux

# Push manifests as OCI artifact
make gitlessops IMAGE=ghcr.io/<your-org>/reliability-mcp TAG=v0.1.0
```

This uses `flux push artifact` to publish to GHCR and bumps the abox OCI artifact version. The cluster reconciles automatically within ~1 minute via the Flux ResourceSet.

### How it works

```
make gitlessops
  → docker push <image>
  → flux push artifact oci://ghcr.io/.../abox/releases:<new-tag>
        → RSIP detects new tag
        → Flux ResourceSet reconciles
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
