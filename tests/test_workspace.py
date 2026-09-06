"""Workspace create, paths, inputs, locking, lineage, and close."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from st_agent.domain.case import Condition, Lineage, Phase
from st_agent.services.workspace import (
    CaseLocked,
    ClosedCaseError,
    LimitExceeded,
    PathRejected,
    UnsupportedInput,
    atomic_write,
    case_lock,
    close_case,
    compact_context,
    contained_path,
    create_case,
    load_manifest,
    resume_case,
    save_manifest,
    save_user_inputs,
)


def test_create_case_writes_english_layout(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "Harbor Watch")
    assert case_root.name == "harbor-watch"
    assert (case_root / "README.md").is_file()
    assert (case_root / "00-work" / "case.json").is_file()
    status = (case_root / "00-work" / "status.md").read_text(encoding="utf-8")
    assert "Phase" in status
    assert "setup" in status
    manifest = load_manifest(case_root)
    assert manifest.phase == Phase.setup
    assert manifest.condition == Condition.active


def test_status_md_is_generated_from_manifest(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    manifest = load_manifest(case_root)
    manifest.phase = Phase.intake
    save_manifest(case_root, manifest)
    status = (case_root / "00-work" / "status.md").read_text(encoding="utf-8")
    assert "intake" in status


def test_reject_workspace_inside_source(tmp_path: Path) -> None:
    source = tmp_path / "app-src"
    inside = source / "user-ws"
    inside.mkdir(parents=True)
    with pytest.raises(PathRejected):
        create_case(inside, "story", source_root=source)


def test_contained_path_rejects_escape(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    with pytest.raises(PathRejected):
        contained_path(case_root, "..", "outside.txt")


def test_symlink_escape_rejected(tmp_path: Path) -> None:
    case_root = create_case(tmp_path / "ws", "story")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("no", encoding="utf-8")
    link = case_root / "00-work" / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not permitted")
    with pytest.raises(PathRejected):
        contained_path(case_root, "00-work", "escape", "secret.txt")


def test_save_input_copies_without_overwriting_original(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    original = tmp_path / "notes.txt"
    original.write_text("keep me", encoding="utf-8")
    refs = save_user_inputs(case_root, [original])
    assert original.read_text(encoding="utf-8") == "keep me"
    copied = case_root / refs[0].relative_path
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == "keep me"
    assert copied != original.resolve()


def test_reject_oversize_text(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    huge = tmp_path / "big.txt"
    huge.write_bytes(b"a" * (2 * 1024 * 1024 + 1))
    with pytest.raises(LimitExceeded):
        save_user_inputs(case_root, [huge])


def test_reject_eleventh_file_keeps_accepted(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    files = []
    for i in range(10):
        path = tmp_path / f"n{i}.txt"
        path.write_text("ok", encoding="utf-8")
        files.append(path)
    save_user_inputs(case_root, files)
    extra = tmp_path / "n10.txt"
    extra.write_text("no", encoding="utf-8")
    with pytest.raises(LimitExceeded):
        save_user_inputs(case_root, [extra])
    assert (case_root / "01-assets" / "n0.txt").is_file()
    assert not (case_root / "01-assets" / "n10.txt").exists()


def test_reject_gif(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    gif = tmp_path / "x.gif"
    gif.write_bytes(b"GIF89a")
    with pytest.raises(UnsupportedInput):
        save_user_inputs(case_root, [gif])


def test_reject_oversized_pixels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    portrait = tmp_path / "wide.png"
    Image.new("RGB", (8, 8), "red").save(portrait)

    class _Huge:
        size = (5000, 4000)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def close(self):
            return None

    monkeypatch.setattr("st_agent.services.workspace.Image.open", lambda _path: _Huge())
    with pytest.raises(LimitExceeded):
        save_user_inputs(case_root, [portrait])


def test_atomic_write_leaves_no_tmp(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    atomic_write(path, "one")
    atomic_write(path, "two")
    assert path.read_text(encoding="utf-8") == "two"
    assert list(tmp_path.glob("*.tmp")) == []


def test_stale_tmp_removed_on_resume(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    stale = case_root / "00-work" / "status.md.tmp"
    stale.write_text("partial", encoding="utf-8")
    resume_case(case_root)
    assert not stale.exists()


def test_lock_rejects_second_holder(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    with case_lock(case_root):
        with pytest.raises(CaseLocked):
            with case_lock(case_root):
                pass


def test_idempotent_save_same_operation_id(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    manifest = load_manifest(case_root)
    first = save_manifest(case_root, manifest, operation_id="op-repeat")
    second = save_manifest(case_root, first, operation_id="op-repeat")
    assert second.revision == first.revision
    assert second.operation_id == "op-repeat"


def test_upstream_hash_change_marks_lineage_stale(tmp_path: Path) -> None:
    from st_agent.services.workspace import file_sha256

    case_root = create_case(tmp_path, "harbor-watch")
    brief = case_root / "00-work" / "brief.md"
    atomic_write(brief, "v1")
    manifest = load_manifest(case_root)
    manifest.lineage["character"] = Lineage(
        source_hash=file_sha256(brief),
        artifact_hash="out",
        stale=False,
    )
    save_manifest(case_root, manifest)
    atomic_write(brief, "v2")
    plan = resume_case(case_root)
    loaded = load_manifest(case_root)
    assert loaded.lineage["character"].stale is True
    assert plan.phase == Phase.intake


def test_compact_context_reads_real_files(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    atomic_write(case_root / "00-work" / "intake.md", "User said hello.")
    ctx = compact_context(case_root)
    assert ctx["phase"] == "setup"
    assert "hello" in ctx["intake"]
    assert isinstance(ctx["files"], list)


def test_close_removes_work_keeps_assets(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    original = tmp_path / "notes.txt"
    original.write_text("keep me", encoding="utf-8")
    save_user_inputs(case_root, [original])
    atomic_write(case_root / "02-drafts" / "character.md", "draft")
    close_case(case_root)
    assert not (case_root / "00-work").exists()
    assert (case_root / "01-assets" / "notes.txt").is_file()
    assert (case_root / "02-drafts" / "character.md").is_file()
    assert (case_root / "README.md").is_file()
    readme = (case_root / "README.md").read_text(encoding="utf-8")
    assert "closed" in readme.lower()
    with pytest.raises(ClosedCaseError):
        load_manifest(case_root)
    with pytest.raises(ClosedCaseError):
        resume_case(case_root)
    assert not (case_root / "00-work" / "intake.md").exists()


def _link_directory(link: Path, target: Path) -> str:
    try:
        link.symlink_to(target, target_is_directory=True)
        return "symlink"
    except OSError:
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip(result.stderr.strip() or result.stdout.strip() or "directory link failed")
        return "junction"


def test_close_unlinks_directory_symlink_without_removing_target(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    target = tmp_path / "kept-outside"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("safe", encoding="utf-8")
    link = case_root / "00-work" / "linked-dir"
    _link_directory(link, target)
    close_case(case_root)
    assert not (case_root / "00-work").exists()
    assert not link.exists()
    assert marker.read_text(encoding="utf-8") == "safe"


def test_close_unlinks_work_dir_link_without_removing_target(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    work = case_root / "00-work"
    target = tmp_path / "outside-work"
    work.rename(target)
    _link_directory(work, target)
    marker = target / "intake.md"
    close_case(case_root)
    assert not work.exists()
    assert marker.read_text(encoding="utf-8") == ""


def test_close_unlinks_nested_junction_without_removing_target(tmp_path: Path) -> None:
    if shutil.which("cmd") is None:
        pytest.skip("cmd is not available")
    case_root = create_case(tmp_path, "harbor-watch")
    target = tmp_path / "kept-outside"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("safe", encoding="utf-8")
    link = case_root / "00-work" / "linked-dir"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(result.stderr.strip() or result.stdout.strip() or "mklink /J failed")
    close_case(case_root)
    assert not (case_root / "00-work").exists()
    assert not link.exists()
    assert marker.read_text(encoding="utf-8") == "safe"

