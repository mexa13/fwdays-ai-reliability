# fwdays — AI Reliability Engineering 2.0

## Labs

| Lab | Topic |
|---|---|
| [Lab 1](#lab-1-deploying-basic-agentic-infrastructure) | Deploying basic agentic infrastructure (agentgateway, kagent, Gateway API) |
| [Lab 2](./lab-2/README.md) | MCP tool servers, kagent Agents, GitOps + GitLessOps |
| [Lab 3](./lab-3/README.md) | MCP **Sampling / Elicitation / Apps** on abox — built on `kmcp` + `google-agents-cli` + MCP Inspector |

## Lab 1: Deploying Basic Agentic Infrastructure

| Level | What you build | Where to run |
|-------|---------------|--------------|
| **Level 1** — Beginners | agentgateway binary, config.yaml, Admin UI | Local / Codespace |
| **Level 2** — Experienced | Helm in KinD, Secrets, kagent, LLM routing | Codespace (4-core · 16 GB) |
| **Level 3** — Max | Level 2 + Gateway API (GatewayClass, Gateway, HTTPRoute) | Codespace (4-core · 16 GB) |

---

## LLM Providers

Each level supports three providers. Choose the one you have access to:

| Command suffix | Provider | Requires | Port / routing |
|----------------|----------|----------|----------------|
| `run` | **OpenAI** | `OPENAI_API_KEY` | cloud API |
| `run-anthropic` | **Anthropic** | `ANTHROPIC_API_KEY` | cloud API |
| `run-lmstudio` | **LM Studio** | LM Studio running on port 1234 | local, no key |

**LM Studio** is a free option for running models locally — no API key or internet access needed. The labs were tested locally with model `google/gemma-3-4b`. Any model loaded in LM Studio works; set `LMSTUDIO_MODEL=<name>` to override the default.

> LM Studio must be running before you start the lab. Download it at [lmstudio.ai](https://lmstudio.ai).

---

## Quick Start

### Requirements

- **Level 1**: any machine with `curl` + an LLM provider (see table above)
- **Level 2 / 3**: Docker + kind + kubectl + helm — or open a Codespace

### GitHub Codespaces (recommended for Level 2 / 3)

1. Click **Code → Codespaces → Create codespace**
2. Select **4-core · 16 GB RAM**
3. Wait for post-create setup (~2 min)
4. In the terminal:

```bash
# OpenAI
export OPENAI_API_KEY=sk-...
make l2-run

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
make l2-run-anthropic

# LM Studio (LM Studio must be running on the host machine)
make l2-run-lmstudio
```

---

## Level 1 — Beginners

Install and run agentgateway as a standalone binary.

```bash
cd lab-1/level-1
make install

# OpenAI
export OPENAI_API_KEY=sk-...
make run          # starts on port 4000
make test

# Anthropic — multi-provider mode
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
make run-multi    # starts on port 3000, routes by x-provider header

# LM Studio — no API key
make run-lmstudio # starts on port 3000
make test-lmstudio
```

| Endpoint | run / run-multi | run-lmstudio |
|----------|----------------|--------------|
| Admin UI | http://localhost:15000/ui/ | http://localhost:15000/ui/ |
| Chat API | http://localhost:4000/v1/chat/completions | http://localhost:3000/v1/chat/completions |

See [lab-1/level-1/README.md](lab-1/level-1/README.md)

---

## Level 2 — Experienced

Helm deployment in a Kubernetes cluster (KinD).

**Stack:** KinD v0.31.0 · agentgateway v1.1.0 · kagent v0.9.2

```bash
# OpenAI
export OPENAI_API_KEY=sk-...
make l2-run

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
make l2-run-anthropic

# LM Studio
make l2-run-lmstudio            # optionally: LMSTUDIO_MODEL=google/gemma-3-4b make l2-run-lmstudio

make l2-test    # verify all components
make l2-down    # destroy the cluster
```

**How each provider connects:**

- `run` — kagent routes through agentgateway (ClusterIP) → OpenAI API
- `run-anthropic` — kagent routes through agentgateway (ClusterIP) → Anthropic API
- `run-lmstudio` — kagent routes directly to `host.docker.internal:1234` (LM Studio on the host)

See [lab-1/level-2/README.md](lab-1/level-2/README.md)

---

## Level 3 — Max

Everything from Level 2, plus Kubernetes **Gateway API**.

**Additional resources:** Gateway API CRDs v1.5.1 · GatewayClass · Gateway · HTTPRoute

```bash
# OpenAI
export OPENAI_API_KEY=sk-...
make l3-run

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
make l3-run-anthropic

# LM Studio
make l3-run-lmstudio

make l3-test    # verify GatewayClass, Gateway, HTTPRoute, agents
make l3-down    # destroy the cluster
```

**How each provider connects:**

- `run` — kagent → Gateway (agentgateway-proxy) → HTTPRoute `/v1/*` → `openai` backend → OpenAI API
- `run-anthropic` — kagent → Gateway → HTTPRoute `/v1/*` → `anthropic` backend → Anthropic API
- `run-lmstudio` — kagent routes directly to `host.docker.internal:1234`; Gateway API resources are created but not used for LLM routing

See [lab-1/level-3/README.md](lab-1/level-3/README.md)

---

## Repository Layout

```
.
├── .devcontainer/
│   ├── devcontainer.json          # Codespaces: 4-core 16GB, Docker-in-Docker
│   └── post-create.sh             # Installs kind v0.31.0, jq, agentgateway
├── lab-1/
│   ├── level-1/                   # Beginners
│   │   ├── config.yaml            # OpenAI config (port 4000)
│   │   ├── config.anthropic.yaml  # Multi-provider config (port 3000)
│   │   ├── config.lmstudio.yaml   # LM Studio config (port 3000)
│   │   └── Makefile
│   ├── level-2/                   # Experienced
│   │   ├── manifests/             # AgentgatewayBackend (openai + anthropic)
│   │   └── scripts/               # setup.sh / test.sh
│   └── level-3/                   # Max
│       ├── manifests/             # + GatewayClass, Gateway, HTTPRoute × 2
│       └── scripts/               # setup.sh / test.sh
├── lab-2/                         # MCP tool servers + kagent agents
│   ├── level-1/                   # Beginners: declarative MCPServer + Agent
│   ├── level-2/                   # Experienced: GitOps via Flux/abox
│   └── level-3/                   # Development: custom KMCP + GitLessOps
├── lab-3/                         # MCP Sampling / Elicitation / Apps
│   ├── docs/research.md           # Real-world cases for each capability
│   ├── level-1/                   # Beginners: KMCP + agents-cli + Inspector
│   ├── level-2/                   # Experienced: MCP Apps (incident dashboard widget)
│   └── level-3/                   # Max: Sampling + Elicitation (triage flow)
└── Makefile                       # Root entrypoint
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
# Common causes: invalid API key or agentgateway endpoint unreachable
```

**LM Studio unreachable from the cluster:**
```bash
# Verify LM Studio is running on the host:
curl http://localhost:1234/v1/models
# In Codespaces, use host.docker.internal:
curl http://host.docker.internal:1234/v1/models
```
