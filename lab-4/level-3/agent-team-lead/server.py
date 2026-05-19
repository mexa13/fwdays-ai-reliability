"""Team-Lead A2A agent — fans one composite incident-triage task across a team
of A2A peers and aggregates their replies (lab-4 level-3).

Peers may be your own a2a-sdk agents (lab-4 level-2 worker) or **kagent Agents**
whose `a2aConfig` makes them speak A2A natively. The team-lead does not care —
it discovers each peer through its Agent Card and drives the task lifecycle the
same way.

Peer wiring is data, not code. Set `PEERS_CONFIG` (or `PEERS_FILE`) to a JSON
document like:

  [
    {"role": "knowledge", "url": "http://reliability-worker.a2a-lab:9001",
     "ask": "Summarize the relevant runbooks for this incident."},
    {"role": "probe",     "url": "http://reliability-agent.kagent:8080",
     "ask": "Check whether https://checkout.example.com is reachable."},
    {"role": "triage",    "url": "http://reliability-agent-sampling.kagent:8080",
     "ask": "Given 2.1% error rate, p95 1800ms, 800 users affected — classify severity."}
  ]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
import uvicorn
from a2a.client import ClientConfig, create_client
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

logger = logging.getLogger("team-lead")


# ---------------------------------------------------------------------------
# Peer configuration
# ---------------------------------------------------------------------------


@dataclass
class Peer:
    role: str
    url: str
    ask: str  # the sub-prompt sent to this peer for every incident


def _load_peers() -> list[Peer]:
    raw = os.getenv("PEERS_CONFIG")
    if not raw:
        path = os.getenv("PEERS_FILE", "peers.json")
        p = Path(path)
        if p.exists():
            raw = p.read_text()
    if not raw:
        logger.warning("no PEERS_CONFIG / peers.json found — running with empty team")
        return []
    return [Peer(**item) for item in json.loads(raw)]


# ---------------------------------------------------------------------------
# A2A peer call
# ---------------------------------------------------------------------------


async def _ask_peer(peer: Peer, prompt: str) -> tuple[str, str]:
    """Call one peer; return (role, answer_text). Never raises — failures are
    reported as the answer text so partial team results are still useful."""
    # kagent peers are LLM-backed and routinely take 20-40s. The default
    # httpx.AsyncClient timeout is 5s, which trips A2AClientTimeoutError before
    # the peer can answer. Build a per-call httpx client with a generous
    # timeout and hand it to the SDK via ClientConfig.
    http = httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0))
    try:
        client = await create_client(
            peer.url,
            ClientConfig(streaming=False, polling=False, httpx_client=http),
        )
    except Exception as e:
        await http.aclose()
        return peer.role, f"(could not resolve Agent Card at {peer.url}: {type(e).__name__}: {e})"

    try:
        req = SendMessageRequest(
            message=Message(
                message_id=str(uuid.uuid4()),
                role=Role.ROLE_USER,
                parts=[Part(text=prompt)],
            )
        )
        final_task = None
        async for resp in client.send_message(req):
            if resp.HasField("task"):
                final_task = resp.task
        if final_task is None:
            return peer.role, "(no task returned)"
        if final_task.status.state != TaskState.TASK_STATE_COMPLETED:
            return peer.role, f"(state={TaskState.Name(final_task.status.state)})"
        # Some frameworks (a2a-sdk) put the answer in status.message; others
        # (kagent) emit it as a Task artifact. Check both, falling back from
        # the agreed status.message convention to artifacts[].parts[].
        texts: list[str] = []
        if final_task.status.HasField("message"):
            for p in final_task.status.message.parts:
                if p.HasField("text") and p.text:
                    texts.append(p.text)
        if not texts:
            for art in final_task.artifacts:
                for p in art.parts:
                    if p.HasField("text") and p.text:
                        texts.append(p.text)
        if texts:
            return peer.role, "\n".join(texts)
        return peer.role, "(completed, no text)"
    except Exception as e:
        return peer.role, f"(peer call raised: {type(e).__name__}: {e})"
    finally:
        try:
            await client.close()
        except Exception:
            pass
        try:
            await http.aclose()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Executor — receives the incident; fans out concurrently to all peers.
# ---------------------------------------------------------------------------


class TeamLeadExecutor(AgentExecutor):
    def __init__(self, peers: list[Peer]):
        self._peers = peers

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.current_task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)
            context.current_task = task

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.start_work()

        incident = (context.get_user_input() or "").strip() or "Unspecified incident."

        if not self._peers:
            await updater.complete(
                message=updater.new_agent_message(
                    [Part(text="No peers configured — set PEERS_CONFIG / PEERS_FILE.")]
                )
            )
            return

        # Fan out concurrently. Each peer gets its pre-configured `ask` prompt with the
        # current incident appended; partial failures don't break the rollup.
        prompts = [(peer, f"{peer.ask}\n\nIncident context:\n{incident}") for peer in self._peers]
        replies = await asyncio.gather(*[_ask_peer(p, q) for p, q in prompts])

        rollup_lines = [f"Incident: {incident}", "", f"Team ({len(replies)} peers):"]
        for role, ans in replies:
            rollup_lines.append(f"\n— [{role}]\n{ans}")

        await updater.complete(
            message=updater.new_agent_message([Part(text="\n".join(rollup_lines))])
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await TaskUpdater(event_queue, context.task_id, context.context_id).update_status(
            TaskState.TASK_STATE_CANCELED
        )


# ---------------------------------------------------------------------------
# Card + app wiring
# ---------------------------------------------------------------------------


def build_agent_card(public_url: str, peers: list[Peer]) -> AgentCard:
    url = public_url.rstrip("/") + DEFAULT_RPC_URL
    return AgentCard(
        name="reliability-team-lead",
        description=(
            "Coordinates a heterogeneous A2A team — own a2a-sdk agents and "
            "kagent Agents — to triage one incident in parallel."
        ),
        version="0.3.0",
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
                id="incident_triage",
                name="Incident Triage (team)",
                description=(
                    f"Fan one incident across {len(peers)} A2A peers "
                    f"({', '.join(p.role for p in peers) or 'none configured'}); "
                    "return per-role replies aggregated by the team-lead."
                ),
                tags=["reliability", "incident", "team", "a2a"],
                examples=[
                    "Investigate 2.1% error rate on checkout-api, p95 1800ms, 800 users affected",
                    "Triage: payments service degraded, SEV2 declared at 10:14 UTC",
                ],
                input_modes=["text/plain"],
                output_modes=["text/plain"],
            )
        ],
    )


def build_app(public_url: str) -> Starlette:
    peers = _load_peers()
    card = build_agent_card(public_url, peers)
    handler = DefaultRequestHandler(
        agent_executor=TeamLeadExecutor(peers),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = create_agent_card_routes(card, card_url=AGENT_CARD_WELL_KNOWN_PATH)
    routes += create_jsonrpc_routes(handler, rpc_url=DEFAULT_RPC_URL, enable_v0_3_compat=True)
    return Starlette(routes=routes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "9100")))
    parser.add_argument(
        "--public-url",
        default=os.getenv("PUBLIC_URL", "http://localhost:9100"),
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("team-lead starting on %s", args.public_url)
    uvicorn.run(build_app(args.public_url), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
