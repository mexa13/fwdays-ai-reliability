# Lab-2: MCP Tool Servers & Kagent Agents

**Platform:** [abox](https://github.com/den-vasyliev/abox) — Kubernetes AI infrastructure sandbox  
**Stack:** agentgateway v2.2.1 · kagent 0.7.23 · Flux CD 2.x · KinD

---

## Prerequisites

abox cluster running (`kind-abox` context):

```bash
cd /path/to/abox && make run
```

Verify:

```bash
kubectl --context kind-abox get pods -A | grep -E 'kagent|agentgateway|flux'
```

---

## Access to UIs

> **macOS note:** KinD node IPs (`172.19.0.x`) are inside the Docker Linux VM — not reachable from the host. Use `kubectl port-forward` which bypasses NodePort and connects directly to the pod.

### Kagent UI

```bash
kubectl --context kind-abox port-forward -n kagent svc/kagent-ui 8080:8080
# http://localhost:8080
```

### Agentgateway (Kagent via Gateway API)

```bash
# port-forward works even on LoadBalancer services — goes directly to the pod on targetPort 80
kubectl --context kind-abox port-forward -n agentgateway-system svc/agentgateway-external 8181:80
# Kagent UI:  http://localhost:8181/
# Kagent API: http://localhost:8181/api
```

### Agentgateway Admin UI (built-in)

The agentgateway binary has an internal UI served on `localhost:15000` inside the pod:

```bash
kubectl --context kind-abox port-forward -n agentgateway-system \
  pod/$(kubectl --context kind-abox get pod -n agentgateway-system \
    -l 'gateway.networking.k8s.io/gateway-name=agentgateway-external' \
    -o jsonpath='{.items[0].metadata.name}') 15000:15000
# http://localhost:15000/ui
```

### Flux UI (flux-operator)

```bash
kubectl --context kind-abox port-forward -n flux-system svc/flux-operator 9080:9080
# http://localhost:9080
```

### Flux CLI

```bash
kubectl --context kind-abox get kustomizations,helmreleases -A
```

---

## Tracks

| Level | Track | Task |
|---|---|---|
| [level-1](./level-1/) | Beginners | `kubectl apply` — connect model + declarative MCPServer + Agent |
| [level-2](./level-2/) | Experienced | GitOps — deploy MCPServer + Agent via Flux/abox `make push` |
| [level-3](./level-3/) | Development | Custom KMCP server + GitLessOps OCI deployment |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  abox KinD Cluster                  │
│                                                     │
│  ┌──────────────────┐    ┌──────────────────────┐   │
│  │  agentgateway    │    │   kagent-controller   │   │
│  │  (Gateway API)   │───▶│   Agent CRDs          │   │
│  │  port 80         │    │   MCPServer CRDs      │   │
│  └──────────────────┘    └──────────┬───────────┘   │
│                                     │               │
│                            ┌────────▼────────┐      │
│                            │   MCPServer Pod │      │
│                            │  (your tools)   │      │
│                            └─────────────────┘      │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  Flux CD (GitOps / GitLessOps via OCI)       │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```
