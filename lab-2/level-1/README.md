# Level-1: Beginners — Declarative MCP Server + Agent

**Goal:** Connect a model, deploy an MCPServer, and create an AI agent — all declaratively with `kubectl`.

---

## Steps

### 1. Set your API key

**OpenAI:**
```bash
kubectl --context kind-abox create secret generic kagent-openai \
  --from-literal=OPENAI_API_KEY="sk-..." \
  -n kagent --dry-run=client -o yaml | kubectl --context kind-abox apply -f -
```

**Anthropic:**
```bash
kubectl --context kind-abox create secret generic kagent-anthropic \
  --from-literal=ANTHROPIC_API_KEY="sk-ant-..." \
  -n kagent --dry-run=client -o yaml | kubectl --context kind-abox apply -f -
```

### 2. Configure the model

The `default-model-config` already exists in the cluster (created by abox).  
Check it:
```bash
kubectl --context kind-abox get modelconfig default-model-config -n kagent -o yaml
```

**Switch to Anthropic** (optional):
```bash
kubectl --context kind-abox apply -f manifests/02-modelconfig.yaml
# Edit 02-modelconfig.yaml first: uncomment the Anthropic section
```

Or apply directly:
```bash
kubectl --context kind-abox apply -f - <<EOF
apiVersion: kagent.dev/v1alpha2
kind: ModelConfig
metadata:
  name: default-model-config
  namespace: kagent
spec:
  provider: Anthropic
  model: claude-haiku-4-5-20251001
  apiKeySecret: kagent-anthropic
  apiKeySecretKey: ANTHROPIC_API_KEY
EOF
```

### 3. Deploy MCPServer and Agent

```bash
kubectl --context kind-abox apply -f manifests/03-mcp-server.yaml
kubectl --context kind-abox apply -f manifests/04-agent.yaml
```

Or use `make`:
```bash
OPENAI_API_KEY=sk-... make setup
# Anthropic: ANTHROPIC_API_KEY=sk-ant-... PROVIDER=anthropic make setup
```

### 4. Verify

```bash
make test
```

Expected:
```
NAME         ...   ACCEPTED
fetch-mcp    ...   True

NAME             TYPE          RUNTIME   READY   ACCEPTED
web-researcher   Declarative   python    True    True
```

### 5. Open Kagent UI

```bash
make ui
# → http://localhost:8080
```

Chat with `web-researcher`:
> Fetch https://kagent.dev and summarize what kagent does

---

## What was created

| Resource | Kind | API Version | Purpose |
|---|---|---|---|
| `fetch-mcp` | MCPServer | `kagent.dev/v1alpha1` | Deploys `mcp/fetch` container (KMCP creates Deployment + Service) |
| `fetch-mcp` | RemoteMCPServer | `kagent.dev/v1alpha2` | Points agent at the MCPServer's service URL |
| `web-researcher` | Agent | `kagent.dev/v1alpha2` | AI agent with access to the fetch tool |

The **KMCP controller** (`kagent-kmcp-controller-manager`) sees the `MCPServer` CRD and automatically creates a Kubernetes Deployment + Service named `fetch-mcp`.

## Architecture

```
User → Kagent UI → web-researcher Agent
                        │
                        ▼ resolves RemoteMCPServer
                   fetch-mcp (RemoteMCPServer → http://fetch-mcp.kagent:8000/mcp)
                        │
                        ▼
                   fetch-mcp pod (mcp/fetch image)
                   ← created by KMCP controller from MCPServer CRD
```

## Troubleshooting

```bash
# MCPServer pod status
kubectl --context kind-abox get pods -n kagent | grep fetch

# MCPServer events
kubectl --context kind-abox describe mcpserver fetch-mcp -n kagent

# MCPServer pod logs
kubectl --context kind-abox logs -n kagent -l app.kubernetes.io/name=fetch-mcp

# Agent events
kubectl --context kind-abox describe agent web-researcher -n kagent

# Agent pod logs
kubectl --context kind-abox logs -n kagent -l app.kubernetes.io/name=web-researcher
```

## Cleanup

```bash
make teardown
```
