# Level-2: Experienced — GitOps Deployment

**Goal:** Deploy MCPServer + Agent via Flux GitLessOps — publish an OCI artifact directly, no Git push required.

**Prerequisites:** GitHub account, `flux` CLI, running abox cluster (`kind-abox`).

---

## Steps

### 1. Install flux CLI

```bash
brew install fluxcd/tap/flux
```

### 2. Login to GHCR

Create a GitHub Personal Access Token with `packages:write`:  
Settings → Developer settings → Personal access tokens → **Tokens (classic)** → check `write:packages`

> **Note:** Fine-grained tokens do not support Packages — use classic tokens only.

```bash
export GITHUB_USER=<your-github-username>
export GITHUB_TOKEN=<your-pat>

echo $GITHUB_TOKEN | docker login ghcr.io \
  --username $GITHUB_USER \
  --password-stdin
```

### 3. Prepare manifests

```bash
git clone https://github.com/den-vasyliev/abox.git
cd abox

cp /path/to/fwdays-ai-reliability/lab-2/level-2/releases/mcp-server.yaml releases/lab2-mcp-server.yaml
cp /path/to/fwdays-ai-reliability/lab-2/level-2/releases/agent.yaml      releases/lab2-agent.yaml
```

Add the new files to `releases/kustomization.yaml` — Flux only applies what is listed there:

```yaml
# releases/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - agentgateway.yaml
  - kagent.yaml
  - lab2-mcp-server.yaml
  - lab2-agent.yaml
```

### 4. Apply secrets (secrets never go into OCI artifacts)

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

### 5. Push OCI artifact

```bash
# Pick a tag — RSIP sorts semver lexicographically, so it must be higher than the current one
flux push artifact \
  oci://ghcr.io/$GITHUB_USER/abox-releases:v0.1.0 \
  --path=./releases \
  --source="oci://ghcr.io/$GITHUB_USER/abox-releases" \
  --revision="v0.1.0"
```

### 6. Point the cluster at your artifact

Create a new `OCIRepository` + `Kustomization` that reads from your artifact:

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
    tag: "v0.1.0"
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

> **Note:** The package on GHCR is private by default. Make it public before Flux can pull it:  
> github.com → Profile → Packages → `abox-releases` → Package settings → **Change visibility → Public**

### 7. Force reconciliation

```bash
flux reconcile source oci lab2-releases --context kind-abox
flux reconcile kustomization lab2-releases --context kind-abox
```

### 8. Watch reconciliation

```bash
kubectl --context kind-abox get kustomizations -n flux-system -w

# Verify resources appeared
kubectl --context kind-abox get agent,mcpserver,remotemcpserver -n kagent
```

---

## Useful Flux commands

| ArgoCD equivalent | Flux |
|---|---|
| `argocd app sync` | `flux reconcile kustomization lab2-releases --context kind-abox` |
| `argocd app get` | `flux get kustomizations --context kind-abox` |
| `argocd app suspend` | `flux suspend kustomization lab2-releases --context kind-abox` |
| App logs | `kubectl logs -n flux-system deploy/kustomize-controller` |

---

## Level-1 vs Level-2

| | Level-1 | Level-2 |
|---|---|---|
| Deployment | `kubectl apply` manually | Flux reconciles from OCI automatically |
| Drift correction | Manual | Automatic |
| Audit trail | None | OCI tags + Flux events |
| Rollback | Manual | Re-apply `OCIRepository` with previous tag |
| Secrets | `kubectl apply` manually | Same — never in OCI |
