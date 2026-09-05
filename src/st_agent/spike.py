"""WP-02 runtime spike helpers. Live B-AI is skipped when the API key is absent."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from strands import Agent, tool
from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent
from strands.models.openai import OpenAIModel

from st_agent.config import (
    api_key,
    authorized_model_chain,
    load_local_env,
    load_settings,
)
from st_agent.outcomes import TurnOutcome


@dataclass(frozen=True)
class CredentialStatus:
    available: bool
    provider: str
    base_url: str
    model_id: str


def credential_probe() -> CredentialStatus:
    load_local_env()
    settings = load_settings()
    return CredentialStatus(
        available=api_key() is not None,
        provider=settings.provider,
        base_url=settings.base_url,
        model_id=settings.model_id,
    )


def ping_runtime(note: str) -> str:
    """Return a short acknowledgement so the spike can prove a project-owned tool call."""

    return f"ok:st-agent:{note}"


ping_runtime_tool = tool(ping_runtime)


def bound_turns_hook(max_tool_turns: int):
    """Cancel the agent after the configured number of tool calls."""

    count = 0

    def on_after_tool(event: AfterToolCallEvent) -> None:
        nonlocal count
        count += 1
        if count >= max_tool_turns:
            event.agent.cancel()

    return on_after_tool


def _sanitize_error(exc: Exception) -> str:
    return type(exc).__name__


def _build_model(model_id: str, *, base_url: str, key: str) -> OpenAIModel:
    return OpenAIModel(
        client_args={"api_key": key, "base_url": base_url, "timeout": 60.0},
        model_id=model_id,
    )


def _invoke(
    *,
    model_id: str,
    base_url: str,
    key: str,
    prompt: str,
    system_prompt: str,
    timeout_s: float | None,
    cancel_signal: threading.Event | None,
) -> tuple[object, list[str], float]:
    events: list[str] = []

    def _tool_name(event: BeforeToolCallEvent | AfterToolCallEvent) -> str:
        if isinstance(event.tool_use, dict):
            return str(event.tool_use.get("name", "unknown"))
        return "unknown"

    def before_tool(event: BeforeToolCallEvent) -> None:
        events.append(f"tool-start:{_tool_name(event)}")

    def after_tool(event: AfterToolCallEvent) -> None:
        events.append(f"tool-end:{_tool_name(event)}")

    signal = cancel_signal or threading.Event()
    timer: threading.Timer | None = None
    if timeout_s and timeout_s > 0:
        timer = threading.Timer(timeout_s, signal.set)
        timer.daemon = True
        timer.start()
    agent = Agent(
        model=_build_model(model_id, base_url=base_url, key=key),
        tools=[ping_runtime_tool],
        system_prompt=system_prompt,
        structured_output_model=TurnOutcome,
        hooks=[before_tool, after_tool, bound_turns_hook(max_tool_turns=2)],
        callback_handler=None,
    )
    started = time.perf_counter()
    try:
        result = agent(
            prompt,
            structured_output_model=TurnOutcome,
            limits={"turns": 4},
            cancel_signal=signal,
        )
    finally:
        if timer is not None:
            timer.cancel()
    return result, events, time.perf_counter() - started


def run_strands_spike(
    *,
    timeout_s: float | None = 90.0,
    cancel_signal: threading.Event | None = None,
) -> dict[str, str | bool | None | float]:
    """Attempt one B-AI-backed invocation. Missing key is an explicit blocker."""

    probe = credential_probe()
    key = api_key()
    if not probe.available or key is None:
        return {
            "status": "blocked",
            "code": "b-ai-credentials-missing",
            "message": "No ST_AGENT_API_KEY in this environment.",
            "provider": probe.provider,
            "base_url": probe.base_url,
            "model_id": probe.model_id,
        }

    system_prompt = (
        "You are the ST-Agent runtime spike. Call ping_runtime once with note=spike, "
        "then return kind=blocked with message describing the tool result. "
        "Do not claim delivery."
    )
    prompt = "Prove the custom tool and return a TurnOutcome."
    tried: list[str] = []
    last_error = "unavailable"
    for model_id in authorized_model_chain(probe.model_id):
        tried.append(model_id)
        try:
            result, events, elapsed_s = _invoke(
                model_id=model_id,
                base_url=probe.base_url,
                key=key,
                prompt=prompt,
                system_prompt=system_prompt,
                timeout_s=timeout_s,
                cancel_signal=cancel_signal,
            )
        except Exception as exc:
            last_error = _sanitize_error(exc)
            continue
        outcome = result.structured_output
        usage = getattr(getattr(result, "metrics", None), "accumulated_usage", None) or {}
        return {
            "status": "pass",
            "stop_reason": str(result.stop_reason),
            "events": ",".join(events),
            "kind": getattr(outcome, "kind", None),
            "message": getattr(outcome, "message", None),
            "provider": probe.provider,
            "base_url": probe.base_url,
            "model_id": model_id,
            "fallback_tried": ",".join(tried),
            "elapsed_s": round(elapsed_s, 3),
            "input_tokens": usage.get("inputTokens"),
            "output_tokens": usage.get("outputTokens"),
        }
    return {
        "status": "blocked",
        "code": "b-ai-models-unavailable",
        "message": last_error,
        "provider": probe.provider,
        "base_url": probe.base_url,
        "model_id": probe.model_id,
        "fallback_tried": ",".join(tried),
    }


def run_model_measurement() -> dict[str, str | bool | None | float]:
    """S-04: one representative English case on the authorized B-AI model chain."""

    probe = credential_probe()
    key = api_key()
    if not probe.available or key is None:
        return {
            "status": "blocked",
            "code": "b-ai-credentials-missing",
            "message": "No ST_AGENT_API_KEY in this environment.",
            "provider": probe.provider,
            "model_id": probe.model_id,
        }

    system_prompt = (
        "You are measuring ST-Agent demo quality. Call ping_runtime once with "
        "note=s04, then return kind=blocked. Message must be natural American English "
        "describing a tavern-keeper NPC in two short sentences. Do not claim delivery."
    )
    prompt = (
        "Story idea: a weary tavern keeper in a rain-soaked port who keeps a ledger of "
        "ships that never returned. Call the tool, then return the TurnOutcome."
    )
    tried: list[str] = []
    last_error = "unavailable"
    for model_id in authorized_model_chain(probe.model_id):
        tried.append(model_id)
        try:
            result, events, elapsed_s = _invoke(
                model_id=model_id,
                base_url=probe.base_url,
                key=key,
                prompt=prompt,
                system_prompt=system_prompt,
                timeout_s=180.0,
                cancel_signal=None,
            )
        except Exception as exc:
            last_error = _sanitize_error(exc)
            continue
        outcome = result.structured_output
        usage = getattr(getattr(result, "metrics", None), "accumulated_usage", None) or {}
        message = getattr(outcome, "message", None) or ""
        return {
            "status": "pass",
            "stop_reason": str(result.stop_reason),
            "events": ",".join(events),
            "kind": getattr(outcome, "kind", None),
            "message": message,
            "english": message.isascii() if message else False,
            "provider": probe.provider,
            "model_id": model_id,
            "fallback_tried": ",".join(tried),
            "elapsed_s": round(elapsed_s, 3),
            "within_3min": elapsed_s <= 180,
            "input_tokens": usage.get("inputTokens"),
            "output_tokens": usage.get("outputTokens"),
            "tool_ok": "tool-end:ping_runtime" in events or "tool-end:ping_runtime_tool" in events,
        }
    return {
        "status": "blocked",
        "code": "b-ai-models-unavailable",
        "message": last_error,
        "provider": probe.provider,
        "model_id": probe.model_id,
        "fallback_tried": ",".join(tried),
    }
