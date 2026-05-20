# Level-3 — Max: agentgateway → Phoenix + Agent Sandbox SDK

You will:

1. Configure **agentgateway** to export frontend traces (every LLM call that goes through the proxy) as **OTLP/gRPC** into the OTel Collector deployed in level-2 — which forwards them to Phoenix.
2. Run a **Code Interpreter ADK agent** that uses the Agent Sandbox **Python SDK** to spin up a fresh sandbox per tool invocation, execute Python in it, and tear it down — all under the NetworkPolicy guardrails from level-1.

End-to-end, traces from three layers (gateway frontend, ADK agent, MCP server) converge in one Phoenix project so you can correlate a user request → gateway → LLM call → tool call.

## Prerequisites

- Lab-1 level-3 is running (`make l3-run` or one of the variants) — provides the `agentgateway-proxy` Gateway in `ns/agentgateway-system` that the AgentgatewayPolicy below targets.
- Lab-5 level-2 is deployed — provides `phoenix.phoenix` and `otel-collector.phoenix`.
- Lab-5 level-1 is deployed — provides the `python-sandbox-template` and `sandbox-router` the SDK demo relies on.

## Step 1 — Wire agentgateway tracing

```bash
cd lab-5/level-3
make deploy-tracing
```

[`manifests/agentgateway-tracing.yaml`](./manifests/agentgateway-tracing.yaml):

```yaml
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayPolicy
metadata: { name: tracing-to-phoenix, namespace: agentgateway-system }
spec:
  targetRefs:
    - { kind: Gateway, name: agentgateway-proxy, group: gateway.networking.k8s.io }
  frontend:
    tracing:
      backendRef: { name: otel-collector, namespace: phoenix, port: 4317 }
      protocol: GRPC
      randomSampling: "true"
```

Generate a trace:

```bash
make port-forward-agentgateway  # in another terminal — forwards :3000
make test-trace                 # sends a chat completion through the gateway
```

Refresh Phoenix (`make -C ../level-2 port-forward-phoenix` → `http://localhost:6006`). Expect a new project with spans named after the agentgateway frontend (route + backend = your OpenAI/Anthropic provider). Sampling is set to `randomSampling: "true"` (every request) — drop to a fraction in production.

## Step 2 — SDK-managed Code Interpreter

The agent lives in [`sdk-demo/code_interpreter_agent.py`](./sdk-demo/code_interpreter_agent.py). It follows the upstream [code-interpreter-agent-on-adk example](https://agent-sandbox.sigs.k8s.io/docs/use-cases/examples/code-interpreter-agent-on-adk/):

```python
from k8s_agent_sandbox import SandboxClient

_client = SandboxClient()

def execute_python(code: str) -> str:
    sandbox = _client.create_sandbox(
        template="python-sandbox-template",
        namespace="default",
    )
    try:
        sandbox.files.write("run.py", code)
        result = sandbox.commands.run("python3 run.py")
        return result.stdout
    finally:
        sandbox.terminate()

root_agent = Agent(
    model="gemini-2.5-flash",
    name="coding_agent",
    description="Writes Python code and executes it in a sandbox.",
    instruction=(
        "You are a helpful assistant that can write Python code and execute "
        "it in the sandbox. Use the 'execute_python' tool for this purpose."
    ),
    tools=[execute_python],
)
```

Run it from your laptop (uses your current kubeconfig context `kind-abox`):

```bash
# Phoenix port-forward so the agent can reach it on localhost:
kubectl --context kind-abox -n phoenix port-forward svc/phoenix 6006:6006 &

make install-local
export GOOGLE_API_KEY=...      # gemini key
make run-local
```

The agent will produce Python, dispatch it to a freshly minted sandbox, capture stdout, and return the answer. Each call creates and destroys a sandbox — `kubectl get sandboxes -n default -w` in a side terminal shows the lifecycle.

In Phoenix's `lab-5-code-interpreter` project, look for:

- a parent span from the `google-genai` instrumentation (the Gemini call),
- a child span from the `execute_python` tool with the `code` argument captured,
- and — if you also have level-2's MCP server running and called from this agent — its nested MCP tool spans linked by trace ID.

## Combined level-3 deploy

```bash
make deploy                     # just the AgentgatewayPolicy
make install-local && make run-local
```

## Verification table

| Step | Command | Expect |
|---|---|---|
| Policy applied | `kubectl get agentgatewaypolicy -A` | `tracing-to-phoenix` in `agentgateway-system` |
| Gateway trace | `make test-trace`, refresh Phoenix | new project with spans for the chat request |
| Sandbox lifecycle | `kubectl -n default get sandboxes -w` during `make run-local` | sandbox appears and is deleted per tool call |
| ADK span | Phoenix `lab-5-code-interpreter` project | spans for Gemini call + `execute_python` tool |
| Sandbox stdout | terminal output of `make run-local` | the agent's final answer (e.g. "2870") |

## Gotchas

- **AgentgatewayPolicy targetRefs.** The example targets the Gateway from lab-1 level-3. If you only ran level-2 (no Gateway API), apply the policy on the `agentgateway-proxy` Service via the appropriate alternate `targetRefs` from the upstream tutorial.
- **SDK install is from `main`.** `pip install ... agent-sandbox.git@main#subdirectory=clients/python/agentic-sandbox-client` — pin to a release tag once one is published.
- **Sandbox namespace vs NetworkPolicy.** The default `SANDBOX_NAMESPACE=default` puts the sandboxes outside the deny-all NetworkPolicy from level-1. Set `SANDBOX_NAMESPACE=a5-sandbox` to keep them inside it — note the sandbox will need a NetworkPolicy carve-out for the egress your code requires (e.g. PyPI mirror).
- **Phoenix project routing.** `phoenix.otel.register(project_name=...)` is what splits the UI tabs — the agent uses `lab-5-code-interpreter`, the MCP server uses `lab-5-mcp`, agentgateway uses its default service name. Search/filter by project on the Phoenix sidebar.
