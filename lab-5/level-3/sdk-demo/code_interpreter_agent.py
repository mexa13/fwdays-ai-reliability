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
- Local laptop: `kubectl -n phoenix port-forward svc/phoenix-svc 6006:6006` and
  run this file directly; SandboxClient picks up your current kubeconfig.
"""

from __future__ import annotations

import os
import subprocess
import tempfile

from google.adk.agents import Agent
from phoenix.otel import register


def _ensure_kube_context(context: str = "kind-abox") -> None:
    """Materialize a single-context kubeconfig for the SDK.

    SandboxClient calls `config.load_kube_config()` without arguments and uses
    `current-context`. If the user's `~/.kube/config` has a stale current
    context (common when they jump between projects), the SDK crashes before
    it tries to do anything useful. We sidestep that by exporting a fresh,
    minified config file pinned to the lab cluster, and pointing KUBECONFIG
    at it for the rest of this process.
    """
    if os.environ.get("LAB5_SKIP_KUBE_CONFIG_REWRITE") == "1":
        return
    try:
        result = subprocess.run(
            ["kubectl", f"--context={context}", "config", "view", "--minify", "--flatten"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            f"Failed to materialize kubeconfig for context {context!r}: {exc}. "
            f"Run `kubectl config get-contexts` and pass --context yourself, or "
            f"set LAB5_SKIP_KUBE_CONFIG_REWRITE=1 to bypass."
        )
    tmp = tempfile.NamedTemporaryFile(prefix="lab5-kubeconfig-", suffix=".yaml", delete=False, mode="w")
    tmp.write(result.stdout)
    tmp.close()
    os.environ["KUBECONFIG"] = tmp.name


_ensure_kube_context(os.environ.get("KUBE_CONTEXT", "kind-abox"))

# Import SandboxClient AFTER KUBECONFIG is set so its module-level loader sees
# the sanitized file.
from k8s_agent_sandbox import SandboxClient  # noqa: E402

PHOENIX_ENDPOINT = os.environ.get(
    "PHOENIX_COLLECTOR_ENDPOINT",
    "http://phoenix-svc.phoenix.svc.cluster.local:6006/v1/traces",
)
SANDBOX_TEMPLATE = os.environ.get("SANDBOX_TEMPLATE", "python-sandbox-template")
SANDBOX_NAMESPACE = os.environ.get("SANDBOX_NAMESPACE", "default")

register(
    project_name="lab-5-code-interpreter",
    endpoint=PHOENIX_ENDPOINT,
    protocol="http/protobuf",
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
    from google.genai import types

    APP = "lab-5-code-interpreter"
    runner = InMemoryRunner(agent=root_agent, app_name=APP)
    session = runner.session_service.create_session_sync(app_name=APP, user_id="dev")

    # ADK 1.19+ expects google.genai.types.Content here, not a bare string —
    # otherwise runner.run() crashes with 'str' object has no attribute 'role'.
    prompt = types.Content(
        role="user",
        parts=[types.Part.from_text(text="What is the sum of squares from 1 to 20?")],
    )

    print(f"\n>>> prompt: {prompt.parts[0].text}\n")
    for event in runner.run(user_id="dev", session_id=session.id, new_message=prompt):
        if event.is_final_response() and event.content and event.content.parts:
            print(f"<<< answer: {event.content.parts[0].text}")
