"""WP-02 runtime spike helpers. Live Bedrock is skipped when credentials are absent."""

from __future__ import annotations

from dataclasses import dataclass

import boto3
from strands import tool

from st_agent.config import load_settings


@dataclass(frozen=True)
class CredentialStatus:
    available: bool
    region_source: str
    region: str | None
    model_id: str


def credential_probe() -> CredentialStatus:
    settings = load_settings()
    session = boto3.Session()
    creds = session.get_credentials()
    if settings.aws_region:
        region_source = "env"
        region = settings.aws_region
    elif session.region_name:
        region_source = "session"
        region = session.region_name
    else:
        region_source = "unset"
        region = None
    return CredentialStatus(
        available=creds is not None,
        region_source=region_source,
        region=region,
        model_id=settings.model_id,
    )


def ping_runtime(note: str) -> str:
    """Return a short acknowledgement so the spike can prove a project-owned tool call."""

    return f"ok:st-agent:{note}"


ping_runtime_tool = tool(ping_runtime)


def bound_turns_hook(max_tool_turns: int):
    """Cancel the agent after the configured number of tool calls."""

    count = 0

    def on_after_tool(event) -> None:
        nonlocal count
        count += 1
        if count >= max_tool_turns:
            event.agent.cancel()

    return on_after_tool


def run_strands_spike() -> dict[str, str | bool | None]:
    """Attempt one Bedrock-backed invocation. Missing credentials is an explicit blocker."""

    probe = credential_probe()
    if not probe.available:
        return {
            "status": "blocked",
            "code": "bedrock-credentials-missing",
            "message": "Standard AWS credential chain has no credentials in this environment.",
            "region_source": probe.region_source,
            "region": probe.region,
            "model_id": probe.model_id,
        }
    from strands import Agent
    from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent
    from strands.models import BedrockModel

    from st_agent.outcomes import TurnOutcome

    events: list[str] = []

    def before_tool(event: BeforeToolCallEvent) -> None:
        events.append(f"tool-start:{event.tool_use.get('name', 'unknown')}")

    def after_tool(event: AfterToolCallEvent) -> None:
        events.append(f"tool-end:{event.tool_use.get('name', 'unknown')}")

    model = BedrockModel(model_id=probe.model_id, region_name=probe.region)
    agent = Agent(
        model=model,
        tools=[ping_runtime_tool],
        system_prompt=(
            "You are the ST-Agent runtime spike. Call ping_runtime once with note=spike, "
            "then return kind=blocked with message describing the tool result. "
            "Do not claim delivery."
        ),
        structured_output_model=TurnOutcome,
        hooks=[before_tool, after_tool, bound_turns_hook(max_tool_turns=2)],
        callback_handler=None,
    )
    result = agent(
        "Prove the custom tool and return a TurnOutcome.",
        structured_output_model=TurnOutcome,
    )
    outcome = result.structured_output
    return {
        "status": "pass",
        "stop_reason": str(result.stop_reason),
        "events": ",".join(events),
        "kind": getattr(outcome, "kind", None),
        "message": getattr(outcome, "message", None),
        "model_id": probe.model_id,
        "region": probe.region,
    }
