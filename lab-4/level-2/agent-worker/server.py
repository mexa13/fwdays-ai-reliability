"""Worker A2A agent — answers individual SRE questions (lab-4 level-2).

Same protocol surface as the level-1 reliability-knowledge-agent, plus a tiny
qdrant-backed knowledge_search skill so the worker is doing something the
coordinator can't trivially do itself.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re

import httpx
import uvicorn
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
    Part,
    TaskState,
)
from a2a.utils.constants import (
    AGENT_CARD_WELL_KNOWN_PATH,
    DEFAULT_RPC_URL,
    PROTOCOL_VERSION_CURRENT,
    TransportProtocol,
)
from starlette.applications import Starlette

logger = logging.getLogger("worker-agent")

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant.qdrant.svc.cluster.local:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "sre-runbooks")

_FAQ: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\berror budget\b", re.I),
     "Error budget = (1 - SLO) × window. 99.9%/30d ≈ 43.2 minutes."),
    (re.compile(r"\b(sev|severity)\b", re.I),
     "SEV1: broad outage. SEV2: degraded for many. SEV3: minor. SEV4: cosmetic."),
    (re.compile(r"\bslo\b|\bslis?\b", re.I),
     "SLIs measure, SLOs target, SLAs contract. 1–3 SLIs per user journey."),
    (re.compile(r"\bpostmortem|post-?mortem\b", re.I),
     "Blameless: timeline, impact, root cause, contributing factors, action items."),
    (re.compile(r"\bcanary\b", re.I),
     "Canary routes a slice of traffic; automated abort on SLI burn."),
    (re.compile(r"\bretry|backoff\b", re.I),
     "Exponential backoff with jitter on idempotent ops only; cap attempts; pair with circuit breaker."),
]


def _faq(question: str) -> str | None:
    for pat, ans in _FAQ:
        if pat.search(question):
            return ans
    return None


async def _qdrant_search(query: str, limit: int = 3) -> list[str]:
    """Best-effort qdrant lookup. Returns empty list if qdrant or collection is missing.

    No embeddings here — we hash the query into a deterministic 32-d vector so the
    lookup is reproducible without an embedding model. Level-2 cares about A2A, not RAG.
    """
    vec = _toy_vector(query)
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.post(
                f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/search",
                json={"vector": vec, "limit": limit, "with_payload": True},
            )
            r.raise_for_status()
            return [
                str(p.get("payload", {}).get("text", ""))
                for p in r.json().get("result", [])
                if p.get("payload", {}).get("text")
            ]
    except Exception as e:
        logger.warning("qdrant unavailable (%s): %s", type(e).__name__, e)
        return []


def _toy_vector(s: str, dim: int = 32) -> list[float]:
    import hashlib

    h = hashlib.sha256(s.lower().encode()).digest()
    return [b / 255.0 for b in (h * ((dim // len(h)) + 1))[:dim]]


class WorkerAgentExecutor(AgentExecutor):
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
                message=updater.new_agent_message([Part(text="empty question")])
            )
            return

        faq = _faq(question)
        kb = await _qdrant_search(question)

        sections: list[str] = []
        if faq:
            sections.append(f"FAQ: {faq}")
        if kb:
            sections.append("Runbook hits:\n- " + "\n- ".join(kb))
        if not sections:
            sections.append(
                "No FAQ match and no runbook hits. Topics I cover: error budgets, SLO/SLI, "
                "severities, postmortems, canary, retries."
            )

        await updater.complete(
            message=updater.new_agent_message([Part(text="\n\n".join(sections))])
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await TaskUpdater(event_queue, context.task_id, context.context_id).update_status(
            TaskState.TASK_STATE_CANCELED
        )


def build_agent_card(public_url: str) -> AgentCard:
    url = public_url.rstrip("/") + DEFAULT_RPC_URL
    return AgentCard(
        name="reliability-worker-agent",
        description=(
            "Answers individual SRE questions from a hand-curated FAQ and a qdrant-backed "
            "runbook index. Used by the coordinator agent via A2A."
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
                id="reliability_qa",
                name="Reliability Q&A",
                description="Concise SRE answers, FAQ + qdrant runbook search.",
                tags=["reliability", "sre", "qdrant"],
                examples=["What is an error budget?", "Best practices for retries"],
                input_modes=["text/plain"],
                output_modes=["text/plain"],
            )
        ],
    )


def build_app(public_url: str) -> Starlette:
    card = build_agent_card(public_url)
    handler = DefaultRequestHandler(
        agent_executor=WorkerAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = create_agent_card_routes(card, card_url=AGENT_CARD_WELL_KNOWN_PATH)
    routes += create_jsonrpc_routes(handler, rpc_url=DEFAULT_RPC_URL, enable_v0_3_compat=True)
    return Starlette(routes=routes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "9001")))
    parser.add_argument(
        "--public-url",
        default=os.getenv("PUBLIC_URL", "http://localhost:9001"),
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("worker starting on %s (qdrant=%s)", args.public_url, QDRANT_URL)
    uvicorn.run(build_app(args.public_url), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
