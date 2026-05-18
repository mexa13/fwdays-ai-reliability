"""
Reliability MCP Server — Sampling + Elicitation edition (lab-3 level-3).

Demonstrates two MCP capabilities (spec 2025-06-18):

  1. **Elicitation** — server asks the human user for structured input via the
     client (e.g. "what severity is this incident?"). Used to fill in fields
     the LLM cannot reliably infer.

  2. **Sampling** — server asks the host's LLM to generate text on its behalf
     (e.g. "draft a stakeholder update"). Lets the server stay model-agnostic
     and use the user's existing LLM seat.

Concrete case: end-to-end incident triage.

Tools exposed:
  - confirm_runbook_step  — Elicitation-only: human gate for destructive ops
  - explain_anomaly       — Sampling-only:    host LLM writes a stakeholder paragraph
  - triage_incident       — Elicitation + Sampling combined

Each capability degrades gracefully when the client does not support it
(e.g. when invoked from a headless kagent Agent): tools fall back to
deterministic defaults rather than failing the call.
"""

import asyncio
import datetime
from dataclasses import dataclass
from typing import Literal, Optional

from fastmcp import FastMCP, Context

# These imports differ slightly between FastMCP minor versions; import lazily.
try:
    from fastmcp.exceptions import ToolError  # type: ignore
except Exception:  # pragma: no cover
    class ToolError(Exception):
        pass

try:
    from fastmcp.server.elicitation import (
        AcceptedElicitation,
        DeclinedElicitation,
        CancelledElicitation,
    )
    _HAS_ELICITATION_TYPES = True
except Exception:  # pragma: no cover
    _HAS_ELICITATION_TYPES = False

mcp = FastMCP("reliability-tools-sampling-elicitation")


# ---------------------------------------------------------------------------
# Helpers — safe wrappers that degrade to defaults if the client lacks support
# ---------------------------------------------------------------------------

async def safe_elicit(ctx: Context, message: str, response_type, default):
    """Call ctx.elicit(); if client cannot elicit (kagent headless, etc.),
    return `default` and surface that we fell back."""
    try:
        result = await ctx.elicit(message, response_type=response_type)
    except Exception as e:
        return default, f"elicitation unavailable ({type(e).__name__}); using defaults"

    if not _HAS_ELICITATION_TYPES:
        # Older FastMCP returns the raw value
        return result, None
    if isinstance(result, AcceptedElicitation):
        return result.data, None
    if isinstance(result, DeclinedElicitation):
        return default, "user declined; using defaults"
    if isinstance(result, CancelledElicitation):
        return default, "user cancelled; using defaults"
    return default, "unexpected elicitation result; using defaults"


async def safe_sample(
    ctx: Context,
    messages,
    *,
    system_prompt: Optional[str] = None,
    max_tokens: int = 600,
    temperature: float = 0.3,
):
    """Call ctx.sample(); on failure return a templated string with a note so
    the tool result is still useful when the client has no LLM to route to."""
    try:
        result = await ctx.sample(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception as e:
        return None, f"sampling unavailable ({type(e).__name__}); returning template"

    # FastMCP returns an object with .text and .content; older may return str
    text = getattr(result, "text", None)
    if text is None and hasattr(result, "content"):
        try:
            text = result.content[0].text
        except Exception:
            text = None
    if text is None:
        text = str(result)
    return text, None


# ---------------------------------------------------------------------------
# Tool 1 — Elicitation only: human gate for a destructive runbook step
# ---------------------------------------------------------------------------

@mcp.tool()
async def confirm_runbook_step(step_description: str, ctx: Context) -> dict:
    """Ask the human user to confirm a destructive operation before proceeding.

    Args:
        step_description: short description of the action, e.g. "restart pods
            in checkout-api namespace" or "rotate the prod database password"

    Returns:
        dict with `approved` (bool), `note` (str), and `fallback` (bool) so the
        calling agent can decide whether to proceed.
    """
    @dataclass
    class Confirm:
        approve: bool
        reason: str = ""

    message = (
        f"⚠️  Confirm runbook step:\n\n"
        f"    {step_description}\n\n"
        f"This action may be destructive. Approve only if you have verified the impact."
    )
    data, note = await safe_elicit(
        ctx, message, response_type=Confirm,
        default=Confirm(approve=False, reason="no human in the loop — denied by default"),
    )
    return {
        "approved": bool(getattr(data, "approve", False)),
        "reason": getattr(data, "reason", "") or "",
        "fallback": note is not None,
        "note": note,
        "step": step_description,
    }


# ---------------------------------------------------------------------------
# Tool 2 — Sampling only: stakeholder explanation of a metric anomaly
# ---------------------------------------------------------------------------

@mcp.tool()
async def explain_anomaly(
    metric: str,
    before: float,
    after: float,
    unit: str,
    ctx: Context,
    audience: Literal["engineer", "exec", "customer"] = "engineer",
) -> dict:
    """Use the host LLM to draft a stakeholder-ready explanation of a
    sudden change in a metric.

    Args:
        metric: name of the metric, e.g. "p95 latency"
        before: baseline value
        after: current value
        unit: unit string, e.g. "ms" or "%"
        audience: tone — engineer (technical), exec (one paragraph, plain
            English, no jargon), or customer (apologetic, no internals)
    """
    delta_pct = None
    if before:
        delta_pct = round((after - before) / before * 100, 1)

    system = {
        "engineer": "You are an SRE writing a Slack incident channel post. Be precise, terse, and mention likely failure modes.",
        "exec":     "You are writing one paragraph for non-technical executives. Plain English. No internal jargon. State business impact.",
        "customer": "You are writing a customer-facing status note. Apologetic, factual, no internal details. End with the next update time.",
    }[audience]

    user_msg = (
        f"Metric: {metric}\n"
        f"Before: {before}{unit}\n"
        f"After:  {after}{unit}\n"
        f"Change: {delta_pct}%\n\n"
        "Write a 2-4 sentence explanation appropriate for the audience above. "
        "Do not invent root causes you cannot infer from the numbers; flag uncertainty."
    )

    text, note = await safe_sample(
        ctx,
        messages=user_msg,
        system_prompt=system,
        max_tokens=300,
        temperature=0.4,
    )

    if text is None:
        # Deterministic fallback
        text = (
            f"{metric} moved from {before}{unit} to {after}{unit} "
            f"({delta_pct:+.1f}%). [LLM unavailable — template fallback.]"
        )

    return {
        "metric": metric,
        "before": before,
        "after": after,
        "unit": unit,
        "delta_pct": delta_pct,
        "audience": audience,
        "explanation": text,
        "fallback": note is not None,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Tool 3 — Elicitation + Sampling combined: full triage flow
# ---------------------------------------------------------------------------

@mcp.tool()
async def triage_incident(service: str, ctx: Context) -> dict:
    """Triage an incident end-to-end.

    Flow:
      1. **Elicit** severity, affected users, and start time from the user.
      2. **Sample** the host LLM to draft a stakeholder update + postmortem
         skeleton from the elicited facts.
      3. Return everything plus next-step recommendations.

    Args:
        service: the impacted service name (e.g. "checkout-api")
    """
    @dataclass
    class TriageInput:
        severity: Literal["SEV1", "SEV2", "SEV3", "SEV4"]
        affected_users: int
        started_at: str  # ISO 8601 ideally; free text accepted
        symptoms: str = ""

    default = TriageInput(
        severity="SEV3",
        affected_users=0,
        started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        symptoms="(no symptoms provided)",
    )

    data, elicit_note = await safe_elicit(
        ctx,
        f"Triage for **{service}** — please provide severity, user impact, "
        f"approximate start time, and visible symptoms.",
        response_type=TriageInput,
        default=default,
    )

    severity = getattr(data, "severity", default.severity)
    affected_users = getattr(data, "affected_users", default.affected_users)
    started_at = getattr(data, "started_at", default.started_at)
    symptoms = getattr(data, "symptoms", default.symptoms)

    # Stakeholder update — sampled
    stakeholder_prompt = (
        f"Draft a stakeholder Slack update for an active incident.\n\n"
        f"Service: {service}\n"
        f"Severity: {severity}\n"
        f"Affected users: ~{affected_users}\n"
        f"Started: {started_at}\n"
        f"Symptoms: {symptoms}\n\n"
        "Write 3-5 sentences. Include current status, scope, what's being "
        "investigated, and time of next update. Be honest about uncertainty."
    )
    stakeholder_update, samp_note_a = await safe_sample(
        ctx,
        messages=stakeholder_prompt,
        system_prompt="You are a senior SRE incident commander. Terse, accurate, no speculation.",
        max_tokens=350,
        temperature=0.3,
    )

    # Postmortem skeleton — sampled
    postmortem_prompt = (
        f"Outline a blameless postmortem for the incident described below. "
        f"Use these sections: Summary, Impact, Timeline (UTC), Root Cause "
        f"(mark as TBD if unknown), Contributing Factors, Action Items.\n\n"
        f"Incident facts:\n"
        f"  service: {service}\n"
        f"  severity: {severity}\n"
        f"  affected_users: {affected_users}\n"
        f"  started_at: {started_at}\n"
        f"  symptoms: {symptoms}\n\n"
        "Fill each section with placeholder bullets the on-call engineer can "
        "complete during the postmortem meeting. Mark unknowns as TBD."
    )
    postmortem, samp_note_b = await safe_sample(
        ctx,
        messages=postmortem_prompt,
        system_prompt="You are a postmortem facilitator. Produce a complete skeleton, never invent facts.",
        max_tokens=700,
        temperature=0.3,
    )

    # Deterministic fallbacks
    if stakeholder_update is None:
        stakeholder_update = (
            f"[Template] Active {severity} incident on {service}. "
            f"~{affected_users} users affected since {started_at}. "
            f"Symptoms: {symptoms}. Investigating; next update in 30 min."
        )
    if postmortem is None:
        postmortem = (
            f"# Postmortem — {service} ({severity})\n\n"
            f"## Summary\n- TBD\n\n## Impact\n- ~{affected_users} users since {started_at}\n\n"
            "## Timeline (UTC)\n- TBD\n\n## Root Cause\n- TBD\n\n"
            "## Contributing Factors\n- TBD\n\n## Action Items\n- TBD"
        )

    next_steps = []
    if severity in ("SEV1", "SEV2"):
        next_steps.append("Page the on-call engineer immediately.")
        next_steps.append("Open an incident channel and post the stakeholder update.")
    next_steps.append("Identify a single Incident Commander (IC).")
    next_steps.append("Set the next status update for T+30 min.")
    if severity == "SEV1":
        next_steps.append("Notify customer success for proactive customer comms.")

    notes = [n for n in [elicit_note, samp_note_a, samp_note_b] if n]

    return {
        "service": service,
        "elicited": {
            "severity": severity,
            "affected_users": affected_users,
            "started_at": started_at,
            "symptoms": symptoms,
        },
        "stakeholder_update": stakeholder_update,
        "postmortem_skeleton": postmortem,
        "next_steps": next_steps,
        "fallback": bool(notes),
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--transport",
        default="streamableHttp",
        choices=["streamableHttp", "sse", "stdio"],
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=args.port)
