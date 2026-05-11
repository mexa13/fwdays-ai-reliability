# Level 1 — Beginners: AgentGateway Standalone

## Objectives

1. Install agentgateway binary locally
2. Choose an LLM provider (OpenAI / Anthropic)
3. Configure `config.yaml`
4. Run the gateway and access the Admin UI
5. Verify LLM access and explore Backends and Policy features

## Prerequisites

- `curl`, `bash`
- LLM API key: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`

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

### 2. Configuration

`config.yaml` is pre-configured for OpenAI via an environment variable:

```yaml
llm:
  models:
    - name: "*"          # wildcard — passes through any OpenAI model name
      provider: openAI
      params:
        apiKey: "$OPENAI_API_KEY"
```

For multi-provider routing (OpenAI + Anthropic), use `config.anthropic.yaml`.

### 3. Start the gateway

```bash
export OPENAI_API_KEY=sk-...
make run
```

Multi-provider:
```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
make run-multi
```

### 4. Access the UI

| Endpoint | URL |
|----------|-----|
| Admin UI | http://localhost:15000/ui/ |
| Chat API | http://localhost:4000/v1/chat/completions |

### 5. Test

```bash
make test

# or manually:
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello!"}]}'
```

Multi-provider routing via `x-provider` header (port 3000):
```bash
# Default (OpenAI):
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello!"}]}'

# Anthropic:
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-provider: anthropic" \
  -d '{"model":"claude-sonnet-4-6","messages":[{"role":"user","content":"Hello!"}]}'
```

## Supported LLM Providers

| Provider | `provider` value | Env var |
|----------|-----------------|---------|
| OpenAI | `openAI` | `OPENAI_API_KEY` |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` |
| Google Gemini | `gemini` | `GEMINI_API_KEY` |
| AWS Bedrock | `bedrock` | AWS credentials |
| Azure OpenAI | `azure` | `AZURE_API_KEY` |
| Ollama (local) | `openAI` + `hostOverride: localhost:11434` | — |

## Stop

```bash
make stop
# or:
Ctrl+C
```
