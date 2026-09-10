"""WP-06 review findings 1–12."""

from __future__ import annotations

from pathlib import Path

import pytest

from st_agent.application.case_controller import (
    MAX_TURNS,
    OUTCOME_REPAIRS,
    PROVIDER_RETRIES,
    submit_turn,
)
from st_agent.application.tools import ToolContext, bind_tools
from st_agent.domain.canonical import CanonicalError, parse_canonical, render_canonical
from st_agent.domain.case import Condition, Phase
from st_agent.services.workspace import (
    CaseLocked,
    case_lock,
    close_case,
    create_case,
    file_sha256,
    load_manifest,
)
from tests.fakes import ScriptedModel
from tests.test_wp06_integration import (
    BRIEF_ARGS,
    _authorized_case,
    _canonical_markdown,
    _happy_script,
    _source_service,
)


def _ctx(case_root: Path) -> ToolContext:
    return ToolContext(case_root=case_root, invocation_id="inv-1", operation_id="op-review")


def _fn(ctx: ToolContext, name: str):
    return next(item for item in bind_tools(ctx) if item.tool_name == name)._tool_func


def test_portrait_ref_rejects_relative_and_absolute_escape(tmp_path: Path) -> None:
    case_root = _authorized_case(tmp_path)
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"not-a-real-png")
    save_brief = _fn(_ctx(case_root), "save_brief")
    relative = save_brief(**BRIEF_ARGS, portrait_ref="../../outside.png")
    assert relative["ok"] is False
    assert relative["code"] == "path-rejected"
    assert not (case_root / "00-work" / "brief.md").is_file()
    absolute = save_brief(**BRIEF_ARGS, portrait_ref=str(outside.resolve()))
    assert absolute["ok"] is False
    assert absolute["code"] == "path-rejected"
    assert not (case_root / "00-work" / "brief.md").is_file()


def test_canonical_portrait_line_rejects_escape() -> None:
    text = render_canonical(parse_canonical(_canonical_markdown()))
    escaped = text.replace("portrait: ", "portrait: ../../outside.png", 1)
    with pytest.raises(CanonicalError, match="portrait"):
        parse_canonical(escaped)
    absolute = text.replace("portrait: ", "portrait: /tmp/outside.png", 1)
    with pytest.raises(CanonicalError, match="portrait"):
        parse_canonical(absolute)


def test_save_brief_invalid_phase_does_not_write(tmp_path: Path) -> None:
    case_root = _authorized_case(tmp_path)
    ctx = _ctx(case_root)
    assert _fn(ctx, "save_brief")(**BRIEF_ARGS)["ok"] is True
    assert _fn(ctx, "save_content_document")(kind="canonical", markdown=_canonical_markdown())[
        "ok"
    ]
    brief = case_root / "00-work" / "brief.md"
    before = brief.read_text(encoding="utf-8")
    again = _fn(ctx, "save_brief")(**{**BRIEF_ARGS, "experience_goal": "Changed later."})
    assert again["ok"] is False
    assert again["code"] == "invalid-phase"
    assert brief.read_text(encoding="utf-8") == before


def test_repair_loop_after_official_check_rewrites_lineage(tmp_path: Path) -> None:
    case_root = _authorized_case(tmp_path)
    repaired = _canonical_markdown().replace("Mara wipes a mug", "Mara sets a mug down")
    outcome, _ = submit_turn(
        case_root,
        "Repair after official check.",
        operation_id="op-repair-loop",
        model=ScriptedModel(
            [
                {"tools": [{"name": "save_brief", "input": BRIEF_ARGS}]},
                {
                    "tools": [
                        {
                            "name": "save_content_document",
                            "input": {"kind": "canonical", "markdown": _canonical_markdown()},
                        }
                    ]
                },
                {"tools": [{"name": "build_character_card", "input": {}}]},
                {"tools": [{"name": "check_official_sources", "input": {}}]},
                {"tools": [{"name": "validate_deliverables", "input": {}}]},
                {
                    "tools": [
                        {
                            "name": "save_content_document",
                            "input": {"kind": "canonical", "markdown": repaired},
                        }
                    ]
                },
                {"tools": [{"name": "validate_deliverables", "input": {}}]},
                {"tools": [{"name": "build_character_card", "input": {}}]},
                {"tools": [{"name": "check_official_sources", "input": {}}]},
                {"tools": [{"name": "validate_deliverables", "input": {}}]},
                {"tools": [{"name": "finish_case", "input": {}}]},
                {"outcome": {"kind": "delivered", "message": "Repaired card is ready."}},
            ]
        ),
        source_service=_source_service(),
    )
    assert outcome.kind == "delivered"
    card = case_root / "04-exports" / "character-cards" / "harbor-watch.json"
    assert "Mara sets a mug down" in card.read_text(encoding="utf-8")
    readme = (case_root / "README.md").read_text(encoding="utf-8")
    assert "04-exports/character-cards/harbor-watch.json" in readme


def test_closed_readme_lists_deliverables(tmp_path: Path) -> None:
    case_root = _authorized_case(tmp_path)
    outcome, _ = submit_turn(
        case_root,
        "Make a JSON card.",
        operation_id="op-readme",
        model=ScriptedModel(_happy_script()),
        source_service=_source_service(),
    )
    assert outcome.kind == "delivered"
    text = (case_root / "README.md").read_text(encoding="utf-8")
    assert "04-exports/character-cards/harbor-watch.json" in text
    assert "will be listed here" not in text


def test_missing_api_key_marks_manifest_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("st_agent.application.case_controller.load_local_env", lambda: None)
    monkeypatch.setattr("st_agent.application.case_controller.api_key", lambda: None)
    case_root = create_case(tmp_path, "harbor-watch")
    outcome, _ = submit_turn(case_root, "Hello.", operation_id="op-nokey")
    assert outcome.blocker == "provider-credentials-missing"
    assert load_manifest(case_root).condition == Condition.blocked


def test_revision_mismatch_does_not_persist_input(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    upload = tmp_path / "note.txt"
    upload.write_text("hello", encoding="utf-8")
    outcome, _ = submit_turn(
        case_root,
        "First message.",
        uploads=[upload],
        operation_id="op-stale-rev",
        expected_revision=99,
        model=ScriptedModel([{"outcome": {"kind": "blocked", "message": "x", "blocker": "x"}}]),
    )
    assert outcome.blocker == "revision-mismatch"
    intake = (case_root / "00-work" / "intake.md").read_text(encoding="utf-8")
    assert "First message" not in intake
    assert not any(case_root.joinpath("01-assets").rglob("note.txt"))


def test_corrupt_operation_cache_is_ignored(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    (case_root / "last-operation.json").write_text("{truncated", encoding="utf-8")
    outcome, events = submit_turn(
        case_root,
        "Continue.",
        operation_id="op-after-corrupt",
        model=ScriptedModel(
            [{"outcome": {"kind": "blocked", "message": "stopped", "blocker": "provider"}}]
        ),
    )
    assert "idempotent" not in events
    assert outcome.kind == "blocked"
    assert outcome.blocker == "provider"


def test_tool_saves_use_per_call_operation_ids(tmp_path: Path) -> None:
    case_root = _authorized_case(tmp_path)
    ctx = _ctx(case_root)
    first = _fn(ctx, "save_brief")(**BRIEF_ARGS)
    second = _fn(ctx, "save_brief")(**{**BRIEF_ARGS, "experience_goal": "A tighter goal."})
    assert first["ok"] is True
    assert second["ok"] is True
    assert second["revision"] > first["revision"]


def test_finish_case_reports_invalid_phase(tmp_path: Path) -> None:
    case_root = _authorized_case(tmp_path)
    ctx = _ctx(case_root)
    _fn(ctx, "save_brief")(**BRIEF_ARGS)
    result = _fn(ctx, "finish_case")()
    assert result["ok"] is False
    assert result["code"] in {"delivery-gate", "invalid-phase"}
    assert (case_root / "00-work").is_dir()


def test_official_source_failure_does_not_advance(tmp_path: Path) -> None:
    case_root = _authorized_case(tmp_path)
    ctx = ToolContext(
        case_root=case_root,
        invocation_id="inv-src",
        operation_id="op-src",
        source_service=_source_service(),
    )
    _fn(ctx, "save_brief")(**BRIEF_ARGS)
    _fn(ctx, "save_content_document")(kind="canonical", markdown=_canonical_markdown())
    built = _fn(ctx, "build_character_card")()
    assert built["ok"] is True
    assert built["revision"] is not None
    import httpx

    from st_agent.official_sources import OfficialSourceService

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="unrelated page")

    ctx.source_service = OfficialSourceService(
        client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    )
    checked = _fn(ctx, "check_official_sources")()
    assert checked["ok"] is False
    assert load_manifest(case_root).phase == Phase.build


def test_cleanup_failure_leaves_cleanup_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from st_agent.services import workspace

    def boom(_path: Path) -> None:
        raise OSError("busy")

    monkeypatch.setattr(workspace, "_remove_work", boom)
    case_root = create_case(tmp_path, "harbor-watch")
    close_case(case_root, deliverables=["04-exports/character-cards/harbor-watch.json"])
    manifest = load_manifest(case_root)
    assert manifest.condition == Condition.cleanup_pending
    assert "04-exports/character-cards/harbor-watch.json" in (case_root / "README.md").read_text(
        encoding="utf-8"
    )


def test_submit_turn_blocked_when_locked(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    with case_lock(case_root):
        with pytest.raises(CaseLocked):
            with case_lock(case_root):
                pass
        outcome, _ = submit_turn(
            case_root,
            "Hello.",
            operation_id="op-locked",
            model=ScriptedModel(
                [{"outcome": {"kind": "blocked", "message": "x", "blocker": "x"}}]
            ),
        )
    assert outcome.blocker == "case-locked"


def test_repair_retries_do_not_multiply_turn_budget(tmp_path: Path) -> None:
    case_root = _authorized_case(tmp_path)
    steps = [{"tools": [{"name": "save_brief", "input": BRIEF_ARGS}]} for _ in range(20)]
    outcome, events = submit_turn(
        case_root,
        "Loop.",
        operation_id="op-turns",
        model=ScriptedModel(steps),
    )
    assert events.count("tool-start:save_brief") <= MAX_TURNS + 2 * (
        PROVIDER_RETRIES + OUTCOME_REPAIRS
    )
    assert outcome.kind == "blocked"


def test_lineage_hash_matches_export_after_rebuild(tmp_path: Path) -> None:
    case_root = _authorized_case(tmp_path)
    ctx = ToolContext(
        case_root=case_root,
        invocation_id="inv-1",
        operation_id="op-review",
        source_service=_source_service(),
    )
    _fn(ctx, "save_brief")(**BRIEF_ARGS)
    _fn(ctx, "save_content_document")(kind="canonical", markdown=_canonical_markdown())
    _fn(ctx, "build_character_card")()
    _fn(ctx, "check_official_sources")()
    _fn(ctx, "save_content_document")(kind="canonical", markdown=_canonical_markdown())
    _fn(ctx, "build_character_card")()
    manifest = load_manifest(case_root)
    card = case_root / "04-exports" / "character-cards" / "harbor-watch.json"
    assert manifest.lineage["character"].stale is False
    assert manifest.lineage["character"].artifact_hash == file_sha256(card)
