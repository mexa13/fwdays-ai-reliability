"""Coordinator A2A agent — receives a high-level request, decomposes it into
sub-questions, fans them out to the worker agent over A2A, and aggregates the
replies into a single answer (lab-4 level-2).

The whole point of this file is the three lines inside `_ask_worker()` — that is
all the application code needed to drive a peer A2A agent's task lifecycle.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import uuid

import httpx
import uvicorn
from a2a.client import ClientConfig, ClientFactory, create_client
from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Message,
    Part,
    Role,
    SendMessageRequest,
    TaskState,
)
from a2a.utils.constants import (
    AGENT_CARD_WELL_KNOWN_PATH,
    DEFAULT_RPC_URL,
    PROTOCOL_VERSION_CURRENT,
    TransportProtocol,
)
from starlette.applications import Starlette

logger = logging.getLogger("coordinator-agent")

WORKER_URL = os.getenv("WORKER_URL", "http://localhost:9001")


# ---------------------------------------------------------------------------
# A2A peer call — driving the worker's task lifecycle from inside our task.
# ---------------------------------------------------------------------------


async def _ask_worker(question: str) -> str:
    """Send one question to the worker agent, return its answer text.

    Demonstrates the minimum a2a-sdk client flow:
      1. `create_client(worker_url)` — fetches the worker's Agent Card and picks
         a compatible transport based on the card's `supportedInterfaces`.
      2. `send_message(req)` — yields `StreamResponse` items. With a non-streaming
         server the SDK auto-aggregates updates into one final `Task` payload.
      3. Read the final `Task.status.message.parts[0].text`.
    """
    client = await create_client(
        WORKER_URL,
        ClientConfig(streaming=False, polling=False),
    )
    try:
        req = SendMessageRequest(
            message=Message(
                message_id=str(uuid.uuid4()),
                role=Role.ROLE_USER,
                parts=[Part(text=question)],
            )
        )
        final_task = None
        async for resp in client.send_message(req):
            if resp.HasField("task"):
                final_task = resp.task
        if final_task is None or final_task.status.state != TaskState.TASK_STATE_COMPLETED:
            state = TaskState.Name(final_task.status.state) if final_task else "no-task"
            return f"(worker did not complete: {state})"

        parts = final_task.status.message.parts if final_task.status.HasField("message") else []
        for p in parts:
            if p.HasField("text"):
                return p.text
        return "(worker completed with no text)"
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Decomposition — turn one user message into N sub-questions for the worker.
# Deterministic so the wire behavior is the focus, not LLM-driven planning.
# ---------------------------------------------------------------------------


_TOPIC_TRIGGERS: list[tuple[str, str]] = [
    ("error budget", "What is an error budget?"),
    ("postmortem",   "How do I run a blameless postmortem?"),
    ("canary",       "When should I use canary releases?"),
    ("retry",        "Best practices for retries and backoff?"),
    ("sev",          "How do I pick incident severities?"),
    ("slo",          "Explain SLI vs SLO vs SLA."),
    ("slo",          "Explain SLI vs SLO vs SLA."),
]


def _decompose(user_text: str) -> list[str]:
    lowered = user_text.lower()
    matches: list[str] = []
    for trigger, expanded in _TOPIC_TRIGGERS:
        if trigger in lowered and expanded not in matches:
            matches.append(expanded)
    return matches or [user_text]


# ---------------------------------------------------------------------------
# Executor — our task delegates to the worker and rolls up the answers.
# ---------------------------------------------------------------------------


class CoordinatorAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.current_task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)
            context.current_task = task

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.start_work()

        question = (context.get_user_input() or "").strip()
        if not question:
            await updater.failed(
                message=updater.new_agent_message([Part(text="empty user input")])
            )
            return

        sub_questions = _decompose(question)
        logger.info("decomposed %r into %d sub-question(s)", question, len(sub_questions))

        # Fan out — could be sequential or asyncio.gather; sequential keeps the demo
        # log readable and avoids overwhelming the in-memory worker queue.
        answers: list[tuple[str, str]] = []
        for q in sub_questions:
            try:
                a = await _ask_worker(q)
            except Exception as e:
                a = f"(worker call failed: {type(e).__name__}: {e})"
            answers.append((q, a))

        rollup = "\n\n".join(f"Q: {q}\nA: {a}" for q, a in answers)
        await updater.complete(
            message=updater.new_agent_message(
                [Part(text=f"Routed {len(answers)} sub-question(s) to {WORKER_URL}\n\n{rollup}")]
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await TaskUpdater(event_queue, context.task_id, context.context_id).update_status(
            TaskState.TASK_STATE_CANCELED
        )


# ---------------------------------------------------------------------------
# Card + app wiring
# ---------------------------------------------------------------------------


def build_agent_card(public_url: str) -> AgentCard:
    url = public_url.rstrip("/") + DEFAULT_RPC_URL
    return AgentCard(
        name="reliability-coordinator-agent",
        description=(
            "Decomposes a high-level reliability request and delegates the parts to "
            "downstream A2A agents (level-2 worker, level-3 kagent agents)."
        ),
        version="0.2.0",
        supported_interfaces=[
            AgentInterface(
                url=url,
                protocol_binding=TransportProtocol.JSONRPC.value,
                protocol_version=PROTOCOL_VERSION_CURRENT,
            ),
        ],
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="reliability_brief",
                name="Reliability Brief",
                description=(
                    "Take a broad reliability question, ask the worker agent the right "
                    "sub-questions over A2A, and return the rolled-up answer."
                ),
                tags=["reliability", "coordinator", "a2a"],
                examples=[
                    "Brief me on error budgets and canaries",
                    "What should I know about retries and severities?",
                ],
                input_modes=["text/plain"],
                output_modes=["text/plain"],
            )
        ],
    )


def build_app(public_url: str) -> Starlette:
    card = build_agent_card(public_url)
    handler = DefaultRequestHandler(
        agent_executor=CoordinatorAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = create_agent_card_routes(card, card_url=AGENT_CARD_WELL_KNOWN_PATH)
    routes += create_jsonrpc_routes(handler, rpc_url=DEFAULT_RPC_URL, enable_v0_3_compat=True)
    return Starlette(routes=routes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "9002")))
    parser.add_argument(
        "--public-url",
        default=os.getenv("PUBLIC_URL", "http://localhost:9002"),
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("coordinator starting on %s (worker=%s)", args.public_url, WORKER_URL)
    uvicorn.run(build_app(args.public_url), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
