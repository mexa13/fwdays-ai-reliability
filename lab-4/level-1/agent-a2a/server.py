"""Reliability Knowledge Agent — minimal A2A agent (lab-4 level-1).

Publishes an Agent Card at /.well-known/agent-card.json (the path A2A discovery
clients hit) and handles `message/send` + `tasks/get` via JSON-RPC at /.

Spec: https://a2a-protocol.org/latest/specification/
SDK:  https://github.com/a2aproject/a2a-python  (a2a-sdk >= 1.0)

The agent has one skill — `reliability_qa` — that takes a free-text question and
returns a deterministic, opinionated answer from a hand-curated SRE FAQ.
There is intentionally **no LLM**: level-1 is about the A2A wire, not modelling.
"""

from __future__ import annotations

import argparse
import logging
import os
import re

import uvicorn
from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Part,
    TaskState,
)
from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.utils.constants import (
    AGENT_CARD_WELL_KNOWN_PATH,
    DEFAULT_RPC_URL,
    PROTOCOL_VERSION_CURRENT,
    TransportProtocol,
)
from starlette.applications import Starlette

logger = logging.getLogger("reliability-agent")

# ---------------------------------------------------------------------------
# Hand-curated SRE FAQ — the "skill" of this agent.
# ---------------------------------------------------------------------------

_FAQ: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\berror budget\b", re.I),
        "Error budget = (1 - SLO) × window. For a 99.9% target over 30 days that's "
        "~43.2 minutes of permitted unavailability. Spend it on planned risk, not surprises.",
    ),
    (
        re.compile(r"\b(sev|severity)\b", re.I),
        "Severities map user impact to response: SEV1 (broad outage, page now), "
        "SEV2 (degraded for many users), SEV3 (minor or contained), SEV4 (cosmetic/info).",
    ),
    (
        re.compile(r"\bslo\b|\bslis?\b", re.I),
        "SLIs are measurements (latency p95, error rate, availability). SLOs are targets on "
        "those SLIs. SLAs are contracts with consequences. Pick 1–3 SLIs per user journey.",
    ),
    (
        re.compile(r"\bpostmortem|post-?mortem\b", re.I),
        "A blameless postmortem captures: timeline, impact, root cause, contributing factors, "
        "what went well, what went poorly, and concrete action items with owners.",
    ),
    (
        re.compile(r"\bcanary|progressive (delivery|rollout)\b", re.I),
        "Canary releases route a small % of traffic to a new version, watch error/latency SLIs, "
        "and either ramp up or roll back. Pair with automated abort criteria.",
    ),
    (
        re.compile(r"\b(rate ?limit|throttl)\b", re.I),
        "Rate limits protect a service from itself. Apply at the edge (per-user, per-IP) and "
        "between internal tiers. Always return 429 with a Retry-After hint.",
    ),
    (
        re.compile(r"\bretry|backoff\b", re.I),
        "Exponential backoff with jitter, on idempotent operations only. Cap total attempts; "
        "wrap with a circuit breaker so a downstream outage doesn't amplify into a thundering herd.",
    ),
]


def _answer(question: str) -> str:
    for pat, ans in _FAQ:
        if pat.search(question):
            return ans
    return (
        "I don't have a canned answer for that. Topics I cover: error budget, severities, "
        "SLI/SLO/SLA, postmortems, canary releases, rate limiting, retries/backoff."
    )


# ---------------------------------------------------------------------------
# AgentExecutor — the only place we touch the A2A task lifecycle.
# ---------------------------------------------------------------------------


class ReliabilityAgentExecutor(AgentExecutor):
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

        answer_text = _answer(question)
        logger.info("Q: %s  →  A: %s", question, answer_text[:80])
        await updater.complete(
            message=updater.new_agent_message([Part(text=answer_text)])
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.update_status(TaskState.TASK_STATE_CANCELED)


# ---------------------------------------------------------------------------
# Agent Card — what discovery returns at /.well-known/agent-card.json
# ---------------------------------------------------------------------------


def build_agent_card(public_url: str) -> AgentCard:
    url = public_url.rstrip("/") + DEFAULT_RPC_URL
    return AgentCard(
        name="reliability-knowledge-agent",
        description=(
            "Deterministic SRE FAQ agent. Demonstrates A2A discovery + task "
            "lifecycle without bringing an LLM into the loop."
        ),
        version="0.1.0",
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
                id="reliability_qa",
                name="Reliability Q&A",
                description=(
                    "Answer concise questions about SLI/SLO, error budgets, severities, "
                    "postmortems, canary releases, rate limiting, retries."
                ),
                tags=["reliability", "sre", "knowledge"],
                examples=[
                    "What is an error budget?",
                    "How do I pick severities?",
                    "Explain SLI vs SLO vs SLA",
                    "Best practices for retries",
                ],
                input_modes=["text/plain"],
                output_modes=["text/plain"],
            )
        ],
    )


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------


def build_app(public_url: str) -> Starlette:
    card = build_agent_card(public_url)
    handler = DefaultRequestHandler(
        agent_executor=ReliabilityAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = []
    routes += create_agent_card_routes(card, card_url=AGENT_CARD_WELL_KNOWN_PATH)
    routes += create_jsonrpc_routes(handler, rpc_url=DEFAULT_RPC_URL, enable_v0_3_compat=True)
    return Starlette(routes=routes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "9000")))
    parser.add_argument(
        "--public-url",
        default=os.getenv("PUBLIC_URL", "http://localhost:9000"),
        help="URL peers will use to reach this agent (goes into Agent Card .url).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info(
        "starting reliability-agent at %s (public_url=%s)",
        f"{args.host}:{args.port}",
        args.public_url,
    )
    uvicorn.run(build_app(args.public_url), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
