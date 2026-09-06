"""One-turn case controller: persist input, run a fresh agent, validate outcomes."""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError
from strands import Agent
from strands.models import Model
from strands.models.openai import OpenAIModel

from st_agent.application.assembly import assemble_prompt
from st_agent.application.hooks import SanitizedHooks
from st_agent.application.lifecycle import clear_wait, mark_blocked, mark_waiting
from st_agent.application.tools import ToolContext, bind_tools
from st_agent.config import api_key, authorized_model_chain, load_local_env, load_settings
from st_agent.domain.case import Condition
from st_agent.official_sources import OfficialSourceService
from st_agent.outcomes import TurnOutcome
from st_agent.services.workspace import (
    ClosedCaseError,
    append_intake,
    canonicalize_root,
    load_manifest,
    save_manifest,
    save_user_inputs,
)

MAX_TURNS = 12
PROVIDER_RETRIES = 1
OUTCOME_REPAIRS = 1
LIVE_TIMEOUT_S = 90.0
OPERATION_FILE = "last-operation.json"


def _operation_path(case_root: Path) -> Path:
    return canonicalize_root(case_root) / OPERATION_FILE


def _load_cached(case_root: Path, operation_id: str) -> TurnOutcome | None:
    path = _operation_path(case_root)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("operation_id") != operation_id:
        return None
    return TurnOutcome.model_validate(data["outcome"])


def _store_cached(case_root: Path, operation_id: str, outcome: TurnOutcome) -> None:
    _operation_path(case_root).write_text(
        json.dumps({"operation_id": operation_id, "outcome": outcome.model_dump()}, indent=2),
        encoding="utf-8",
    )


def _live_model(model_id: str, *, base_url: str, key: str) -> OpenAIModel:
    return OpenAIModel(
        client_args={"api_key": key, "base_url": base_url, "timeout": 60.0},
        model_id=model_id,
    )


def submit_turn(
    case_root: Path,
    message: str,
    *,
    uploads: Sequence[Path] = (),
    operation_id: str,
    expected_revision: int | None = None,
    model: Model | None = None,
    source_service: OfficialSourceService | None = None,
) -> tuple[TurnOutcome, list[str]]:
    case_root = canonicalize_root(case_root)
    cached = _load_cached(case_root, operation_id)
    if cached is not None:
        return cached, ["idempotent"]

    if uploads:
        save_user_inputs(case_root, uploads)
    append_intake(case_root, f"User: {message}")

    try:
        manifest = load_manifest(case_root)
    except ClosedCaseError:
        outcome = TurnOutcome(kind="blocked", message="The case is closed.", blocker="case-closed")
        _store_cached(case_root, operation_id, outcome)
        return outcome, []

    if expected_revision is not None and manifest.revision != expected_revision:
        outcome = TurnOutcome(
            kind="blocked",
            message="The case changed; refresh and retry.",
            blocker="revision-mismatch",
        )
        return outcome, []

    if manifest.condition == Condition.waiting_for_user:
        save_manifest(case_root, clear_wait(manifest))
        manifest = load_manifest(case_root)

    ctx = ToolContext(
        case_root=case_root,
        invocation_id=uuid.uuid4().hex,
        operation_id=operation_id,
        source_service=source_service,
    )
    hooks = SanitizedHooks()
    system_prompt, user_prompt = assemble_prompt(case_root, message)
    tools = bind_tools(ctx)

    def _invoke(active_model: Model, prompt: str, *, timeout_s: float | None = None) -> TurnOutcome:
        signal = threading.Event()
        timer: threading.Timer | None = None
        if timeout_s and timeout_s > 0:
            timer = threading.Timer(timeout_s, signal.set)
            timer.daemon = True
            timer.start()
        agent = Agent(
            model=active_model,
            tools=tools,
            system_prompt=system_prompt,
            structured_output_model=TurnOutcome,
            hooks=hooks.as_list(),
            callback_handler=None,
        )
        try:
            result = agent(
                prompt,
                structured_output_model=TurnOutcome,
                limits={"turns": MAX_TURNS},
                cancel_signal=signal,
            )
        finally:
            if timer is not None:
                timer.cancel()
        outcome = result.structured_output
        if outcome is None:
            raise ValueError("TurnOutcome is missing")
        if isinstance(outcome, TurnOutcome):
            return outcome
        return TurnOutcome.model_validate(outcome)

    if model is None:
        load_local_env()
        settings = load_settings()
        key = api_key()
        if key is None:
            outcome = TurnOutcome(
                kind="blocked",
                message="No ST_AGENT_API_KEY in this environment.",
                blocker="b-ai-credentials-missing",
            )
            _store_cached(case_root, operation_id, outcome)
            return outcome, hooks.events
        last_error = "unavailable"
        outcome = None
        deadline = time.perf_counter() + LIVE_TIMEOUT_S
        for model_id in authorized_model_chain(settings.model_id):
            remaining = deadline - time.perf_counter()
            if remaining <= 1:
                last_error = "timeout"
                break
            try:
                outcome = _invoke(
                    _live_model(model_id, base_url=settings.base_url, key=key),
                    user_prompt,
                    timeout_s=remaining,
                )
                last_error = ""
                break
            except Exception as exc:
                last_error = type(exc).__name__
                continue
        if outcome is None:
            outcome = TurnOutcome(
                kind="blocked",
                message=last_error,
                blocker="b-ai-models-unavailable",
            )
            _store_cached(case_root, operation_id, outcome)
            return outcome, hooks.events
    else:
        prompt = user_prompt
        last_exc: Exception | None = None
        outcome = None
        for attempt in range(PROVIDER_RETRIES + 1 + OUTCOME_REPAIRS):
            try:
                outcome = _invoke(model, prompt)
                last_exc = None
                break
            except (ValidationError, ValueError, TypeError) as exc:
                last_exc = exc
                prompt = f"Previous outcome was invalid: {exc}. Return a valid TurnOutcome."
            except Exception as exc:
                last_exc = exc
                if attempt >= PROVIDER_RETRIES:
                    break
        if outcome is None:
            outcome = TurnOutcome(
                kind="blocked",
                message=type(last_exc).__name__ if last_exc else "invalid outcome",
                blocker="invalid-outcome",
            )

    outcome = _accept_outcome(case_root, ctx, outcome)
    _store_cached(case_root, operation_id, outcome)
    return outcome, hooks.events


def _accept_outcome(case_root: Path, ctx: ToolContext, outcome: TurnOutcome) -> TurnOutcome:
    if outcome.kind == "delivered" and not ctx.finish_ok:
        outcome = TurnOutcome(
            kind="blocked",
            message="Delivery is only accepted after finish_case passes the gate.",
            blocker="ungated-delivery",
            artifact_refs=outcome.artifact_refs,
        )
    try:
        manifest = load_manifest(case_root)
    except ClosedCaseError:
        return outcome
    if outcome.kind == "question":
        question = (outcome.question or outcome.message).strip()
        save_manifest(case_root, mark_waiting(manifest, question))
    elif outcome.kind == "blocked":
        save_manifest(
            case_root,
            mark_blocked(manifest, code=outcome.blocker or "blocked", message=outcome.message),
        )
    return outcome
