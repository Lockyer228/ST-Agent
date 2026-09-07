"""Narrow case lifecycle transitions."""

from __future__ import annotations

from st_agent.domain.case import CaseManifest, Condition, Phase

PHASE_ORDER = (
    Phase.setup,
    Phase.intake,
    Phase.qa,
    Phase.draft,
    Phase.final_text,
    Phase.build,
    Phase.official_check,
    Phase.validate,
    Phase.delivery,
    Phase.cleanup,
)

CONTENT_PHASES = {
    Phase.draft,
    Phase.final_text,
    Phase.build,
    Phase.official_check,
    Phase.validate,
    Phase.delivery,
}


class InvalidTransition(ValueError):
    """The requested phase or condition change is not allowed."""


def _replace(manifest: CaseManifest, **changes: object) -> CaseManifest:
    return manifest.model_copy(update=changes)


def advance_phase(manifest: CaseManifest, target: Phase) -> CaseManifest:
    if target == manifest.phase:
        return manifest
    current_i = PHASE_ORDER.index(manifest.phase)
    target_i = PHASE_ORDER.index(target)
    allowed = False
    if target_i == current_i + 1:
        allowed = True
    elif manifest.phase == Phase.intake and target == Phase.draft:
        allowed = True
    elif manifest.phase in CONTENT_PHASES and target == Phase.qa:
        allowed = True
    if not allowed:
        raise InvalidTransition(f"{manifest.phase} -> {target}")
    return _replace(manifest, phase=target, condition=Condition.active, blocker=None)


REWINDABLE = {
    Phase.draft,
    Phase.final_text,
    Phase.build,
    Phase.official_check,
    Phase.validate,
}


def rewind_phase(manifest: CaseManifest, target: Phase) -> CaseManifest:
    if target == manifest.phase:
        return manifest
    if manifest.phase not in REWINDABLE or target not in REWINDABLE:
        raise InvalidTransition(f"{manifest.phase} -> {target}")
    if PHASE_ORDER.index(target) > PHASE_ORDER.index(manifest.phase):
        raise InvalidTransition(f"{manifest.phase} -> {target}")
    return _replace(manifest, phase=target, condition=Condition.active, blocker=None)


def mark_blocked(manifest: CaseManifest, *, code: str, message: str) -> CaseManifest:
    from st_agent.domain.case import Blocker

    retry = manifest.retry_count + 1
    return _replace(
        manifest,
        condition=Condition.blocked,
        retry_count=retry,
        last_error=message,
        blocker=Blocker(code=code, message=message, retry_count=retry),
    )


def clear_wait(manifest: CaseManifest) -> CaseManifest:
    return _replace(
        manifest,
        condition=Condition.active,
        pending_question=None,
        blocker=None,
    )


def mark_waiting(manifest: CaseManifest, question: str) -> CaseManifest:
    return _replace(
        manifest,
        condition=Condition.waiting_for_user,
        pending_question=question,
        blocker=None,
    )


def mark_cleanup_pending(manifest: CaseManifest) -> CaseManifest:
    return _replace(manifest, phase=Phase.cleanup, condition=Condition.cleanup_pending)
