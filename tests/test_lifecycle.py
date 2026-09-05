"""Case phase and condition transitions."""

from __future__ import annotations

import pytest

from st_agent.application.lifecycle import (
    InvalidTransition,
    advance_phase,
    apply_input_change,
    clear_wait,
    mark_blocked,
    mark_cleanup_pending,
)
from st_agent.domain.case import CaseManifest, Condition, DeliveryPreference, Phase


def _manifest(phase: Phase = Phase.setup, condition: Condition = Condition.active) -> CaseManifest:
    return CaseManifest(
        case_id="c1",
        story_name="harbor-watch",
        mode="new",
        phase=phase,
        condition=condition,
        revision=1,
        operation_id="op-1",
        delivery=DeliveryPreference(),
    )


def test_setup_advances_to_intake() -> None:
    next_m = advance_phase(_manifest(), Phase.intake)
    assert next_m.phase == Phase.intake
    assert next_m.condition == Condition.active


def test_content_phase_may_return_to_qa() -> None:
    next_m = advance_phase(_manifest(Phase.draft), Phase.qa)
    assert next_m.phase == Phase.qa


def test_cannot_skip_from_setup_to_delivery() -> None:
    with pytest.raises(InvalidTransition):
        advance_phase(_manifest(Phase.setup), Phase.delivery)


def test_block_stays_on_same_phase() -> None:
    blocked = mark_blocked(_manifest(Phase.build), code="provider", message="timeout")
    assert blocked.phase == Phase.build
    assert blocked.condition == Condition.blocked
    assert blocked.blocker is not None
    assert blocked.blocker.code == "provider"


def test_user_answer_clears_waiting() -> None:
    waiting = _manifest(Phase.qa, Condition.waiting_for_user)
    waiting.pending_question = "Need a portrait."
    cleared = clear_wait(waiting)
    assert cleared.condition == Condition.active
    assert cleared.phase == Phase.qa
    assert cleared.pending_question is None


def test_input_change_returns_to_intake_and_marks_lineage_stale() -> None:
    from st_agent.domain.case import Lineage

    manifest = _manifest(Phase.build)
    manifest.lineage["character"] = Lineage(source_hash="old", artifact_hash="out")
    updated = apply_input_change(manifest)
    assert updated.phase == Phase.intake
    assert updated.lineage["character"].stale is True


def test_cleanup_pending_sets_cleanup_phase() -> None:
    pending = mark_cleanup_pending(_manifest(Phase.delivery))
    assert pending.phase == Phase.cleanup
    assert pending.condition == Condition.cleanup_pending
