"""Typed case models for WP-03."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_manifest_has_required_fields() -> None:
    from st_agent.domain.case import (
        CaseManifest,
        Condition,
        DeliveryPreference,
        Phase,
    )

    manifest = CaseManifest(
        case_id="case-1",
        story_name="harbor-watch",
        mode="new",
        phase=Phase.setup,
        condition=Condition.active,
        revision=0,
        operation_id="op-1",
        delivery=DeliveryPreference(),
    )
    dumped = manifest.model_dump()
    assert dumped["schema_version"] == 1
    assert dumped["phase"] == "setup"
    assert dumped["condition"] == "active"
    assert dumped["delivery"]["card"] == "json"
    assert dumped["delivery"]["lorebook"] == "none"
    assert dumped["inputs"] == []
    assert dumped["lineage"] == {}
    assert dumped["blocker"] is None


def test_phase_and_condition_reject_unknown_values() -> None:
    from st_agent.domain.case import CaseManifest, DeliveryPreference

    with pytest.raises(ValidationError):
        CaseManifest(
            case_id="x",
            story_name="x",
            mode="new",
            phase="not-a-phase",
            condition="active",
            revision=0,
            operation_id="op",
            delivery=DeliveryPreference(),
        )


def test_artifact_and_lineage_record_hashes() -> None:
    from st_agent.domain.case import ArtifactRef, Lineage

    ref = ArtifactRef(
        logical_id="story-notes",
        relative_path="01-assets/story.txt",
        sha256="abc",
        kind="text",
    )
    lineage = Lineage(source_hash="abc", artifact_hash="def", stale=False)
    assert ref.kind == "text"
    assert lineage.stale is False
