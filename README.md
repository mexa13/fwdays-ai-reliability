# fwdays — AI Reliability Engineering 2.0

## Lab 1: Deploying Basic Agentic Infrastructure

| Level | What you build | Where to run |
|-------|---------------|--------------|
| **Level 1** — Beginners | agentgateway binary, config.yaml, Admin UI | Local / Codespace |
| **Level 2** — Experienced | Helm in KinD, Secrets, kagent, LLM routing | Codespace (4-core · 16 GB) |
| **Level 3** — Max | Level 2 + Gateway API (GatewayClass, Gateway, HTTPRoute) | Codespace (4-core · 16 GB) |

---

## Quick Start

### Requirements

- `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` for multi-provider config)
- **Level 1**: any machine with `curl`
- **Level 2 / 3**: Docker + kind + kubectl + helm — or open a Codespace

### GitHub Codespaces (recommended for Level 2 / 3)

1. Click **Code → Codespaces → Create codespace**
2. Select **4-core · 16 GB RAM**
3. Wait for post-create setup (~2 min)
4. In the terminal:

```bash
export OPENAI_API_KEY=sk-...
make l2-run      # Level 2
# or
make l3-run      # Level 3
```

---

## Level 1 — Beginners

Install and run agentgateway as a standalone binary.

```bash
cd lab-1/level-1
make install
export OPENAI_API_KEY=sk-...
make run
```

| Endpoint | URL |
|----------|-----|
| Admin UI | http://localhost:15000/ui/ |
| Chat API | http://localhost:4000/v1/chat/completions |

```bash
make test
```

See [lab-1/level-1/README.md](lab-1/level-1/README.md)

---

## Level 2 — Experienced

Helm deployment in a Kubernetes cluster (KinD).

**Stack:**
- KinD v0.31.0 (1 control-plane + 2 worker nodes)
- agentgateway v1.1.0 (Helm)
- kagent v0.9.2 (Helm)
- LLM API key stored in a Kubernetes Secret
- kagent routes all LLM calls through agentgateway

```bash
export OPENAI_API_KEY=sk-...
make l2-run     # create cluster + deploy everything
make l2-test    # verify all components
make l2-down    # destroy the cluster
```

See [lab-1/level-2/README.md](lab-1/level-2/README.md)

---

## Level 3 — Max

Everything from Level 2, plus Kubernetes **Gateway API**.

**Additional resources:**
- Gateway API CRDs v1.5.1
- `GatewayClass: agentgateway`
- `Gateway: agentgateway-proxy`
- `HTTPRoute: openai-route` — routes `/v1/*` to `AgentgatewayBackend`

```bash
export OPENAI_API_KEY=sk-...
make l3-run     # create cluster + deploy + Gateway API
make l3-test    # verify GatewayClass, Gateway, HTTPRoute, agents
make l3-down    # destroy the cluster
```

See [lab-1/level-3/README.md](lab-1/level-3/README.md)

---

## Repository Layout

```
.
├── .devcontainer/
│   ├── devcontainer.json       # Codespaces: 4-core 16GB, Docker-in-Docker
│   └── post-create.sh          # Installs kind v0.31.0, jq, agentgateway
├── lab-1/
│   ├── level-1/                # Beginners
│   │   ├── config.yaml         # OpenAI LLM gateway config
│   │   ├── config.anthropic.yaml  # Multi-provider config (OpenAI + Anthropic)
│   │   └── Makefile
│   ├── level-2/                # Experienced
│   │   ├── kind-config.yaml    # KinD cluster spec
│   │   ├── helm/               # Helm values files
│   │   ├── manifests/          # AgentgatewayBackend CRD + Secret template
│   │   └── scripts/            # setup.sh / test.sh / teardown.sh
│   └── level-3/                # Max
│       ├── kind-config.yaml
│       ├── manifests/          # + Gateway, HTTPRoute, ReferenceGrant
│       └── scripts/
└── Makefile                    # Root entrypoint: make l1-run / l2-run / l3-run
```

---

## Component Versions

| Component | Version | Source |
|-----------|---------|--------|
| [agentgateway](https://agentgateway.dev) | v1.1.0 | `oci://cr.agentgateway.dev/charts/agentgateway` |
| [kagent](https://kagent.dev) | 0.9.2 | `oci://ghcr.io/kagent-dev/kagent/helm/kagent` |
| Gateway API CRDs | v1.5.1 | `github.com/kubernetes-sigs/gateway-api` |
| KinD | v0.31.0 | `github.com/kubernetes-sigs/kind` |

---

## Troubleshooting

**Helm OCI pull fails:**
```bash
helm registry login cr.agentgateway.dev --username "" --password ""
```

**kind cluster fails to start in Codespace:**
```bash
docker info   # verify Docker daemon is running
sudo service docker start
```

**kagent pods in CrashLoopBackOff:**
```bash
kubectl logs -n kagent -l app.kubernetes.io/name=kagent --previous
# Common causes: invalid OPENAI_API_KEY or agentgateway endpoint unreachable
```

**Verify kagent → agentgateway connectivity:**
```bash
kubectl exec -n kagent deploy/kagent-controller -- \
  wget -qO- http://agentgateway.agentgateway-system.svc.cluster.local/health \
  || echo "Cannot reach agentgateway"
```
