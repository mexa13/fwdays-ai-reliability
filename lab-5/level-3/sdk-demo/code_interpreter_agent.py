"""Code Interpreter ADK agent that manages Agent Sandbox via the Python SDK.

Architecture
------------
- One ADK Agent with a single tool `execute_python(code: str) -> str`.
- The tool spins up a fresh sandbox from the `python-sandbox-template`
  applied in lab-5/level-1, runs the code, returns stdout, and terminates
  the sandbox. The sandbox-router (also from level-1) handles the routing.
- Tracing is enabled via `phoenix.otel.register(auto_instrument=True)`,
  which lights up both google-genai (the ADK call to Gemini) and the
  surrounding tool invocation. Set PHOENIX_COLLECTOR_ENDPOINT to point at
  Phoenix (default = the in-cluster Service).

Run modes
---------
- In-cluster: build the image, mount kubeconfig in the Pod, and point the
  SandboxClient at the cluster API.
- Local laptop: `kubectl port-forward svc/phoenix-collector 4317` and run
  this file directly; SandboxClient picks up your current kubeconfig.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from k8s_agent_sandbox import SandboxClient
from phoenix.otel import register

PHOENIX_ENDPOINT = os.environ.get(
    "PHOENIX_COLLECTOR_ENDPOINT",
    "http://phoenix.phoenix.svc.cluster.local:6006",
)
SANDBOX_TEMPLATE = os.environ.get("SANDBOX_TEMPLATE", "python-sandbox-template")
SANDBOX_NAMESPACE = os.environ.get("SANDBOX_NAMESPACE", "default")

register(
    project_name="lab-5-code-interpreter",
    endpoint=PHOENIX_ENDPOINT,
    auto_instrument=True,
)

_client = SandboxClient()


def execute_python(code: str) -> str:
    """Run Python in a fresh Agent Sandbox and return stdout.

    Each invocation gets its own sandbox so the agent cannot accumulate
    state across tool calls (matches the upstream code-interpreter-agent
    example). The deny-by-default NetworkPolicy from level-1 still applies
    when the sandbox is created in the `a5-sandbox` namespace.
    """
    sandbox = _client.create_sandbox(
        template=SANDBOX_TEMPLATE,
        namespace=SANDBOX_NAMESPACE,
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


if __name__ == "__main__":
    # Smoke test — run the agent on a single prompt and print the answer.
    from google.adk.runners import InMemoryRunner

    runner = InMemoryRunner(agent=root_agent, app_name="lab-5-code-interpreter")
    session = runner.session_service.create_session_sync(
        app_name="lab-5-code-interpreter", user_id="dev"
    )
    for event in runner.run(
        user_id="dev",
        session_id=session.id,
        new_message="What is the sum of squares from 1 to 20?",
    ):
        if event.is_final_response():
            print(event.content.parts[0].text)
