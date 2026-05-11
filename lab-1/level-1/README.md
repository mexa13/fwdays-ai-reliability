# Level 1 — Beginners: AgentGateway Standalone

## Objectives

1. Install agentgateway binary locally
2. Choose an LLM provider (OpenAI / Anthropic / LM Studio)
3. Configure `config.yaml`
4. Run the gateway and access the Admin UI
5. Verify LLM access and explore Backends and Policy features

## Prerequisites

- `curl`, `bash`
- An LLM provider (see below)

---

## LLM Providers

| Command | Provider | Requires | Port |
|---------|----------|----------|------|
| `make run` | OpenAI | `OPENAI_API_KEY` | 4000 |
| `make run-multi` | OpenAI + Anthropic | `OPENAI_API_KEY` + `ANTHROPIC_API_KEY` | 3000 |
| `make run-lmstudio` | LM Studio (local) | LM Studio on port 1234 | 3000 |

**LM Studio** is a free alternative — runs models locally, no API key or internet connection needed.
Tested with model `google/gemma-3-4b`. Any model loaded in LM Studio works.

---

## Steps

### 1. Install agentgateway

```bash
make install
# or manually:
curl -sL https://agentgateway.dev/install | bash
```

Verify:
```bash
agentgateway --version
```

### 2. Start the gateway

**OpenAI** (port 4000):
```bash
export OPENAI_API_KEY=sk-...
make run
```

**Anthropic + OpenAI** — multi-provider mode, routing by `x-provider` header (port 3000):
```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
make run-multi
```

**LM Studio** — no API key needed (port 3000):
```bash
# LM Studio must be running on port 1234 before this
make run-lmstudio
```

### 3. Access the Admin UI

| Endpoint | URL |
|----------|-----|
| Admin UI | http://localhost:15000/ui/ |
| Chat API (`run`) | http://localhost:4000/v1/chat/completions |
| Chat API (`run-multi` / `run-lmstudio`) | http://localhost:3000/v1/chat/completions |

### 4. Test

**OpenAI / Anthropic (port 4000):**
```bash
make test

# manually:
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello!"}]}'
```

**LM Studio (port 3000):**
```bash
make test-lmstudio
# Override model: MODEL=google/gemma-3-4b make test-lmstudio

# manually:
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"google/gemma-3-4b","messages":[{"role":"user","content":"Hello!"}]}'
```

**Multi-provider routing via `x-provider` header (port 3000):**
```bash
# Default route → OpenAI:
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello!"}]}'

# Anthropic:
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-provider: anthropic" \
  -d '{"model":"claude-sonnet-4-6","messages":[{"role":"user","content":"Hello!"}]}'
```

---

## Config Files

| File | Provider | Port | Notes |
|------|----------|------|-------|
| `config.yaml` | OpenAI | 4000 | `llm:` mode, single provider |
| `config.anthropic.yaml` | OpenAI + Anthropic | 3000 | `binds:` mode, routes by `x-provider` header |
| `config.lmstudio.yaml` | LM Studio | 3000 | `llm:` mode, `hostOverride: localhost:1234` |

---

## Supported LLM Providers

| Provider | `provider` value | Env var |
|----------|-----------------|---------|
| OpenAI | `openAI` | `OPENAI_API_KEY` |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` |
| Google Gemini | `gemini` | `GEMINI_API_KEY` |
| AWS Bedrock | `bedrock` | AWS credentials |
| Azure OpenAI | `azure` | `AZURE_API_KEY` |
| LM Studio / Ollama (local) | `openAI` + `hostOverride: localhost:1234` | — |

---

## Stop

```bash
make stop
# or: Ctrl+C
```
