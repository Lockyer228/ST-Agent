"""One-turn case controller: persist input, run a fresh agent, validate outcomes."""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path

import httpx
from pydantic import ValidationError
from strands import Agent
from strands.models import Model
from strands.models.openai import OpenAIModel

from st_agent.application.assembly import assemble_prompt
from st_agent.application.hooks import SanitizedHooks
from st_agent.application.lifecycle import (
    clear_wait,
    is_confirm_reply,
    mark_blocked,
    mark_waiting,
)
from st_agent.application.tools import ToolContext, bind_tools
from st_agent.config import (
    RuntimeSettings,
    api_key,
    authorized_model_chain,
    load_local_env,
    load_settings,
)
from st_agent.domain.case import Condition
from st_agent.official_sources import OfficialSourceService
from st_agent.outcomes import TurnOutcome
from st_agent.services.workspace import (
    CaseLocked,
    ClosedCaseError,
    append_intake,
    atomic_write,
    authorize_build,
    canonicalize_root,
    case_lock,
    load_manifest,
    save_manifest,
    save_user_inputs,
)

MAX_TURNS = 12
PROVIDER_RETRIES = 1
OUTCOME_REPAIRS = 1
CONNECT_TIMEOUT_S = 15.0
WRITE_TIMEOUT_S = 60.0
POOL_TIMEOUT_S = 15.0
OPERATION_FILE = "last-operation.json"


def try_live_model_chain(
    model_ids: Sequence[str],
    invoke,
) -> tuple[TurnOutcome | None, str]:
    """Try each authorized model. No shared wall-clock budget."""

    last_error = "unavailable"
    for model_id in model_ids:
        try:
            return invoke(model_id), ""
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"[:240]
    return None, last_error


def _http_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=CONNECT_TIMEOUT_S,
        read=None,
        write=WRITE_TIMEOUT_S,
        pool=POOL_TIMEOUT_S,
    )


def _operation_path(case_root: Path) -> Path:
    return canonicalize_root(case_root) / OPERATION_FILE


def _load_cached(case_root: Path, operation_id: str) -> TurnOutcome | None:
    path = _operation_path(case_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("operation_id") != operation_id:
            return None
        return TurnOutcome.model_validate(data["outcome"])
    except (OSError, ValueError, ValidationError, TypeError, KeyError):
        return None


def _store_cached(case_root: Path, operation_id: str, outcome: TurnOutcome) -> None:
    atomic_write(
        _operation_path(case_root),
        json.dumps({"operation_id": operation_id, "outcome": outcome.model_dump()}, indent=2),
    )


def _live_model(model_id: str, *, base_url: str, key: str) -> OpenAIModel:
    return OpenAIModel(
        client_args={"api_key": key, "base_url": base_url, "timeout": _http_timeout()},
        model_id=model_id,
        params={"extra_body": {"enable_thinking": False}},
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
    event_sink: Callable[[str], None] | None = None,
    live_settings: RuntimeSettings | None = None,
    live_key: str | None = None,
) -> tuple[TurnOutcome, list[str]]:
    case_root = canonicalize_root(case_root)
    try:
        with case_lock(case_root):
            return _submit_locked(
                case_root,
                message,
                uploads=uploads,
                operation_id=operation_id,
                expected_revision=expected_revision,
                model=model,
                source_service=source_service,
                event_sink=event_sink,
                live_settings=live_settings,
                live_key=live_key,
            )
    except CaseLocked:
        return (
            TurnOutcome(kind="blocked", message="The case is locked.", blocker="case-locked"),
            [],
        )


def _submit_locked(
    case_root: Path,
    message: str,
    *,
    uploads: Sequence[Path],
    operation_id: str,
    expected_revision: int | None,
    model: Model | None,
    source_service: OfficialSourceService | None,
    event_sink: Callable[[str], None] | None = None,
    live_settings: RuntimeSettings | None = None,
    live_key: str | None = None,
) -> tuple[TurnOutcome, list[str]]:
    cached = _load_cached(case_root, operation_id)
    if cached is not None:
        return cached, ["idempotent"]

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

    if uploads:
        save_user_inputs(case_root, uploads)
    append_intake(case_root, f"User: {message}")

    waiting = manifest.condition == Condition.waiting_for_user
    pending_confirm = manifest.pending_confirm
    if pending_confirm and is_confirm_reply(message):
        authorize_build(case_root)
    elif waiting:
        save_manifest(case_root, clear_wait(load_manifest(case_root)))

    ctx = ToolContext(
        case_root=case_root,
        invocation_id=uuid.uuid4().hex,
        operation_id=operation_id,
        source_service=source_service,
    )
    hooks = SanitizedHooks(event_sink)
    system_prompt, user_prompt = assemble_prompt(case_root, message)
    tools = bind_tools(ctx)

    def _invoke(
        active_model: Model,
        prompt: str,
        *,
        timeout_s: float | None = None,
        turn_limit: int = MAX_TURNS,
    ) -> TurnOutcome:
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
                limits={"turns": turn_limit},
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
        if live_settings is not None:
            settings = live_settings
            key = (live_key or "").strip() or None
            model_ids: Sequence[str] = (settings.model_id,)
        else:
            load_local_env()
            settings = load_settings()
            key = api_key()
            model_ids = authorized_model_chain(settings.model_id)
        if key is None:
            outcome = TurnOutcome(
                kind="blocked",
                message="No ST_AGENT_API_KEY in this environment.",
                blocker="provider-credentials-missing",
            )
        else:
            def _live_invoke(model_id: str) -> TurnOutcome:
                return _invoke(
                    _live_model(
                        model_id,
                        base_url=settings.base_url,
                        key=key,
                    ),
                    user_prompt,
                )

            outcome, last_error = try_live_model_chain(model_ids, _live_invoke)
            if outcome is None:
                if "TurnOutcome is missing" in last_error:
                    outcome = TurnOutcome(
                        kind="blocked",
                        message=(
                            "The model stopped responding. "
                            "Saved files are kept; send again to continue."
                        ),
                        blocker="live-timeout",
                    )
                else:
                    outcome = TurnOutcome(
                        kind="blocked",
                        message=last_error,
                        blocker="provider-models-unavailable",
                    )
    else:
        prompt = user_prompt
        last_exc: Exception | None = None
        outcome = None
        for attempt in range(PROVIDER_RETRIES + 1 + OUTCOME_REPAIRS):
            budget = MAX_TURNS if attempt == 0 else 2
            try:
                outcome = _invoke(model, prompt, turn_limit=budget)
                last_exc = None
                break
            except (ValidationError, ValueError, TypeError) as exc:
                last_exc = exc
                prompt = (
                    f"{user_prompt}\n\nPrevious outcome was invalid: {exc}. "
                    "Return a valid TurnOutcome."
                )
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


def _export_refs(case_root: Path) -> list[str]:
    exports = case_root / "04-exports"
    if not exports.is_dir():
        return []
    return sorted(
        path.relative_to(case_root).as_posix()
        for path in exports.rglob("*")
        if path.is_file()
    )


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
        if ctx.finish_ok:
            refs = outcome.artifact_refs or _export_refs(case_root)
            return TurnOutcome(
                kind="delivered",
                message=outcome.message or "Deliverables are ready.",
                artifact_refs=refs,
            )
        return outcome
    if outcome.kind == "question":
        question = (outcome.question or outcome.message).strip()
        save_manifest(case_root, mark_waiting(manifest, question, confirm=outcome.confirm))
    elif outcome.kind == "blocked":
        save_manifest(
            case_root,
            mark_blocked(manifest, code=outcome.blocker or "blocked", message=outcome.message),
        )
    return outcome
