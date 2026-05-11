# ADR: Lab 1 — Agentic Infrastructure Stack

**Status:** Accepted  
**Date:** 2026-05-11  
**Project:** fwdays — AI Reliability Engineering 2.0 / Lab 1: DevOps Bot/Agent

---

## Context

We need a reproducible, observable infrastructure for running AI agents that operate on Kubernetes clusters — inspecting workloads, applying policies, and responding to operational events. The infrastructure must:

- Run entirely on a laptop or a GitHub Codespace (4-core, 16 GB RAM)
- Support multiple LLM providers without changing agent code
- Route LLM traffic through a controllable, observable layer
- Follow Kubernetes-native patterns so the setup reflects real production architecture
- Be reachable without a paid API key (local model option required)

---

## Decision 1: agentgateway as the LLM Gateway

**Chosen:** [agentgateway](https://agentgateway.dev) v1.1.0

### Why agentgateway

agentgateway is purpose-built for AI traffic. Unlike a generic HTTP proxy, it understands LLM-specific concepts: providers, models, token budgets, and AI policies. Key reasons for choosing it:

- **Provider abstraction** — clients always speak OpenAI-compatible API regardless of the backend (OpenAI, Anthropic, local models). No code changes needed to switch providers.
- **Auth centralization** — API keys live in Kubernetes Secrets attached to `AgentgatewayBackend` CRDs. Agents never see the keys.
- **AI-aware policies** — rate limiting per model, token budgets, content filtering — configured declaratively via CRDs.
- **Kubernetes-native** — deploys via Helm, manages resources through Kubernetes CRDs (`AgentgatewayBackend`), integrates with Gateway API.
- **Gateway API support** — implements `GatewayClass`, enabling standard Kubernetes routing on top of LLM traffic (Level 3).

### Alternatives considered

| Alternative | Reason not chosen |
|------------|-------------------|
| **Direct API calls** (no gateway) | No centralized auth, no observability, provider change requires code modification |
| **LiteLLM proxy** | Generic HTTP proxy, no Kubernetes-native CRDs, no Gateway API integration |
| **OpenRouter** | External SaaS dependency, not self-hosted, no control over routing in-cluster |
| **Envoy / Istio** | Not AI-aware, requires custom filters to handle token-level policies |

---

## Decision 2: kagent as the Agent Runtime

**Chosen:** [kagent](https://kagent.dev) v0.9.2

### Why kagent

kagent is a Kubernetes-native agent framework: agents, tools, and model configuration are all defined as Kubernetes CRDs. This makes the agent infrastructure observable and manageable with standard Kubernetes tooling.

- **CRD-first** — agents defined as `Agent` CRDs, model routing as `ModelConfig` CRD. `kubectl get agents` shows all agents and their readiness like any other workload.
- **MCP support** — built-in integration with Model Context Protocol servers. Agents can call MCP tools (kubectl, helm, Prometheus) without custom code.
- **Multi-provider** — `ModelConfig` points to any OpenAI-compatible endpoint, including agentgateway. Switching providers is a config change, not a code change.
- **Built-in Kubernetes agents** — ships with pre-built agents for Kubernetes operations (k8s-agent, helm-agent, observability-agent, etc.) which are directly useful for a DevOps bot use case.
- **kagent UI** — built-in web UI for sending queries to agents and viewing responses, useful for demos and testing.

### Alternatives considered

| Alternative | Reason not chosen |
|------------|-------------------|
| **LangChain** | Python library, not Kubernetes-native, no CRD model, requires custom deployment glue |
| **AutoGen / CrewAI** | Framework-level, no Kubernetes operator, not designed for in-cluster operation |
| **LlamaIndex** | Data-focused, less suited for operational/DevOps agent patterns |
| **Custom operator** | High implementation cost, reinvents what kagent already provides |

---

## Decision 3: Kubernetes Gateway API (Level 3)

**Chosen:** [Gateway API](https://gateway-api.sigs.k8s.io) v1.5.1 — GatewayClass, Gateway, HTTPRoute

### Why Gateway API over direct Service routing

Level 2 connects kagent directly to the agentgateway ClusterIP Service. Level 3 introduces Gateway API to demonstrate production-grade traffic routing:

- **Declarative routing** — `HTTPRoute` defines which backend handles `/v1/*` requests. Changing the provider means updating an HTTPRoute, not redeploying kagent.
- **Separation of concerns** — the `Gateway` object is managed by the infrastructure team; `HTTPRoute` objects are managed per-application. This reflects real multi-tenant cluster patterns.
- **Standard Kubernetes API** — Gateway API is the official successor to Ingress. Learning it here transfers directly to production workloads.
- **agentgateway implements GatewayClass** — the gateway controller is agentgateway itself, meaning the same component that proxies LLM traffic also implements the Gateway API controller. No extra components needed.

### Alternatives considered

| Alternative | Reason not chosen |
|------------|-------------------|
| **Ingress** | Deprecated in favor of Gateway API, less expressive for L7 routing |
| **Direct ClusterIP** | Already done in Level 2, no routing abstraction, provider is hardcoded in kagent config |
| **Service Mesh (Istio)** | Significant added complexity, not necessary to demonstrate LLM routing patterns |

---

## Decision 4: KinD for Local Kubernetes

**Chosen:** [KinD](https://kind.sigs.k8s.io) v0.31.0 (1 control-plane + 2 worker nodes)

### Why KinD

- **Docker-based** — runs inside Docker, works in GitHub Codespaces (Docker-in-Docker) without any additional hypervisor or VM.
- **Multi-node** — supports multiple worker nodes in a single config, which matters for scheduling agentgateway and kagent on separate nodes.
- **Lightweight** — the full 3-node cluster runs within the 16 GB Codespace RAM budget alongside agentgateway, kagent, and PostgreSQL.
- **Fast cluster creation** — cluster is up in ~30 seconds.

### Alternatives considered

| Alternative | Reason not chosen |
|------------|-------------------|
| **minikube** | VM-based by default, more RAM overhead, not ideal for Codespaces |
| **k3s / k3d** | Lighter but fewer features; k3d also works in Docker but has less community tooling around testing |
| **Docker Desktop Kubernetes** | Not available in Codespaces, macOS/Windows only |

---

## Decision 5: Multi-Provider Support with LM Studio as Local Option

**Chosen:** OpenAI / Anthropic / LM Studio — selected via `LLM_PROVIDER` environment variable

### Why three providers

A Kubernetes lab should not require a paid API key. Many students have free-tier accounts with quota limits or no credits.

- **OpenAI** — reference provider, most familiar to participants
- **Anthropic** — demonstrates that the gateway abstracts provider differences (same kagent config, different backend)
- **LM Studio** — free, runs entirely offline. No API key, no quota. Tested with `google/gemma-3-4b`.

Provider selection drives: which Kubernetes Secret is created, which `AgentgatewayBackend` CRD is applied, and how `ModelConfig` is patched post-install. The switching mechanism is entirely in infrastructure (setup.sh + CRDs), not in agent code.

### Consequence

LM Studio connects directly from the KinD cluster to `host.docker.internal:1234`, bypassing the agentgateway backend. This is a deliberate trade-off: local models are fast and free, but the full gateway routing chain (Level 3) only exercises with cloud providers.

---

## Consequences

**Positive:**
- Provider can be swapped without changing any agent code — only infrastructure config changes
- API keys are never exposed to application pods
- Standard Kubernetes tooling (`kubectl get agents`, `kubectl describe gateway`) works for observability
- The lab runs on a free Codespace; no cloud account required when using LM Studio

**Negative / Trade-offs:**
- agentgateway-proxy Service is type `LoadBalancer` — stays `<pending>` in KinD without MetalLB; port-forward is required for direct access
- LM Studio provider bypasses the Gateway API chain (Level 3), so the routing demo requires a cloud provider
- kagent v0.9.2 does not surface `providers.openAI.baseURL` in `ModelConfig.spec.openAI.baseUrl` via Helm values — requires a manual `kubectl patch` after install
