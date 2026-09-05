"""Interruption resume matrix for every case phase."""

from __future__ import annotations

from pathlib import Path

import pytest

from st_agent.application.lifecycle import PHASE_ORDER, mark_cleanup_pending
from st_agent.domain.case import Phase
from st_agent.services.workspace import (
    ClosedCaseError,
    abandon_case,
    atomic_write,
    close_case,
    create_case,
    load_manifest,
    resume_case,
    save_manifest,
    save_user_inputs,
)


@pytest.mark.parametrize("phase", [item for item in PHASE_ORDER if item is not Phase.cleanup])
def test_unfinished_phase_resumes_in_place(tmp_path: Path, phase: Phase) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    manifest = load_manifest(case_root)
    manifest.phase = phase
    save_manifest(case_root, manifest)
    plan = resume_case(case_root)
    assert plan.phase == phase
    assert plan.reason == "unfinished"
    original = tmp_path / "notes.txt"
    original.write_text("original", encoding="utf-8")
    save_user_inputs(case_root, [original])
    assert original.read_text(encoding="utf-8") == "original"


def test_cleanup_pending_resumes_cleanup_only(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    atomic_write(case_root / "00-work" / "intake.md", "secret Q&A")
    atomic_write(case_root / "02-drafts" / "character.md", "keep")
    manifest = mark_cleanup_pending(load_manifest(case_root))
    save_manifest(case_root, manifest)
    plan = resume_case(case_root)
    assert plan.reason == "cleanup_only"
    assert plan.phase == Phase.cleanup
    assert not (case_root / "00-work").exists()
    assert (case_root / "02-drafts" / "character.md").is_file()
    with pytest.raises(ClosedCaseError):
        load_manifest(case_root)


def test_abandon_keeps_drafts_and_drops_qa(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    atomic_write(case_root / "00-work" / "intake.md", "Q&A")
    atomic_write(case_root / "02-drafts" / "character.md", "draft")
    abandon_case(case_root)
    assert not (case_root / "00-work").exists()
    assert (case_root / "02-drafts" / "character.md").is_file()
    readme = (case_root / "README.md").read_text(encoding="utf-8")
    assert "abandoned" in readme.lower()
    with pytest.raises(ClosedCaseError):
        resume_case(case_root)


def test_new_case_does_not_restore_deleted_qa(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    atomic_write(case_root / "00-work" / "intake.md", "old Q&A")
    close_case(case_root)
    with pytest.raises(ClosedCaseError):
        resume_case(case_root)
    new_root = create_case(tmp_path, "harbor-watch")
    intake = (new_root / "00-work" / "intake.md").read_text(encoding="utf-8")
    assert "old Q&A" not in intake
