"""Q&A confirm-before-build and sole plain-image portrait binding."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from st_agent.application.case_controller import submit_turn
from st_agent.application.lifecycle import is_confirm_reply, mark_waiting
from st_agent.application.tools import ToolContext, bind_tools
from st_agent.domain.case import CaseManifest, Condition, DeliveryPreference, Phase
from st_agent.outcomes import TurnOutcome
from st_agent.services.workspace import (
    authorize_build,
    create_case,
    load_manifest,
    save_user_inputs,
)
from tests.fakes import ScriptedModel
from tests.test_wp06_integration import BRIEF_ARGS, _happy_script, _source_service


def _manifest() -> CaseManifest:
    return CaseManifest(
        case_id="c1",
        story_name="harbor-watch",
        mode="new",
        phase=Phase.qa,
        condition=Condition.active,
        revision=1,
        operation_id="op-1",
        delivery=DeliveryPreference(),
    )


def test_is_confirm_reply_accepts_short_yes() -> None:
    assert is_confirm_reply("yes")
    assert is_confirm_reply("Yes.")
    assert is_confirm_reply("confirm")
    assert is_confirm_reply("yes\u3002")
    assert is_confirm_reply("yes\uFF01")
    assert not is_confirm_reply("yes, and also add a dragon")
    assert not is_confirm_reply("Make a JSON card.")


def test_mark_waiting_can_flag_confirm() -> None:
    waiting = mark_waiting(_manifest(), "Reply yes to write the card.", confirm=True)
    assert waiting.pending_confirm is True
    assert waiting.condition == Condition.waiting_for_user


def test_save_brief_requires_confirmation(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    ctx = ToolContext(case_root=case_root, invocation_id="inv-1", operation_id="op-1")
    save_brief = next(item for item in bind_tools(ctx) if item.tool_name == "save_brief")._tool_func
    result = save_brief(**BRIEF_ARGS)
    assert result["ok"] is False
    assert result["code"] == "confirm-required"
    assert not (case_root / "00-work" / "brief.md").is_file()


def test_save_brief_runs_after_authorize_build(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    authorize_build(case_root)
    ctx = ToolContext(case_root=case_root, invocation_id="inv-1", operation_id="op-1")
    save_brief = next(item for item in bind_tools(ctx) if item.tool_name == "save_brief")._tool_func
    assert save_brief(**BRIEF_ARGS)["ok"] is True
    assert (case_root / "00-work" / "brief.md").is_file()


def test_yes_after_confirm_question_allows_delivery(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    first, _ = submit_turn(
        case_root,
        "A tavern keeper named Mara.",
        operation_id="op-ask",
        model=ScriptedModel(
            [
                {
                    "outcome": {
                        "kind": "question",
                        "message": "Brief: Mara keeps a tavern. Reply yes to write the card.",
                        "question": "Reply yes to write the card.",
                        "confirm": True,
                    }
                }
            ]
        ),
    )
    assert first.kind == "question"
    waiting = load_manifest(case_root)
    assert waiting.pending_confirm is True
    assert waiting.build_confirmed is False
    second, _ = submit_turn(
        case_root,
        "yes",
        operation_id="op-yes",
        model=ScriptedModel(_happy_script()),
        source_service=_source_service(),
    )
    assert second.kind == "delivered"


def test_one_plain_image_with_notes_becomes_portrait(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    face = tmp_path / "face.png"
    Image.new("RGB", (4, 4), "navy").save(face)
    notes = tmp_path / "notes.txt"
    notes.write_text("A rain-soaked port.", encoding="utf-8")
    save_user_inputs(case_root, [face, notes])
    manifest = load_manifest(case_root)
    assert manifest.portrait_ref == "01-assets/portraits/face.png"


def test_two_plain_images_do_not_choose_portrait(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    one = tmp_path / "a.png"
    two = tmp_path / "b.png"
    Image.new("RGB", (4, 4), "navy").save(one)
    Image.new("RGB", (4, 4), "teal").save(two)
    save_user_inputs(case_root, [one, two])
    assert load_manifest(case_root).portrait_ref is None


def test_png_card_is_not_a_plain_portrait(tmp_path: Path) -> None:
    from st_agent.png_card import PngCardCodec

    case_root = create_case(tmp_path, "harbor-watch")
    card = tmp_path / "card.png"
    png = PngCardCodec().write(Image.new("RGB", (4, 4), "navy"), {"spec": "chara_card_v3"})
    card.write_bytes(png)
    refs = save_user_inputs(case_root, [card])
    assert refs[0].kind == "png_card"
    assert load_manifest(case_root).portrait_ref is None


def test_save_brief_uses_bound_portrait_ref(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    face = tmp_path / "face.png"
    Image.new("RGB", (4, 4), "navy").save(face)
    save_user_inputs(case_root, [face])
    authorize_build(case_root)
    ctx = ToolContext(case_root=case_root, invocation_id="inv-p", operation_id="op-p")
    save_brief = next(item for item in bind_tools(ctx) if item.tool_name == "save_brief")._tool_func
    assert save_brief(**BRIEF_ARGS)["ok"] is True
    text = (case_root / "00-work" / "brief.md").read_text(encoding="utf-8")
    assert "01-assets/portraits/face.png" in text
    assert "character: both" in text


def test_save_brief_png_in_intake_sets_both_without_portrait(tmp_path: Path) -> None:
    from st_agent.services.workspace import append_intake

    case_root = create_case(tmp_path, "harbor-watch")
    append_intake(case_root, "User: Make a PNG card for Mara.")
    authorize_build(case_root)
    ctx = ToolContext(case_root=case_root, invocation_id="inv-png", operation_id="op-png")
    save_brief = next(item for item in bind_tools(ctx) if item.tool_name == "save_brief")._tool_func
    assert save_brief(**BRIEF_ARGS)["ok"] is True
    text = (case_root / "00-work" / "brief.md").read_text(encoding="utf-8")
    assert "character: both" in text


def test_save_brief_json_only_keeps_json_with_portrait(tmp_path: Path) -> None:
    from st_agent.services.workspace import append_intake

    case_root = create_case(tmp_path, "harbor-watch")
    face = tmp_path / "face.png"
    Image.new("RGB", (4, 4), "navy").save(face)
    save_user_inputs(case_root, [face])
    append_intake(case_root, "User: JSON only please.")
    authorize_build(case_root)
    ctx = ToolContext(case_root=case_root, invocation_id="inv-j", operation_id="op-j")
    save_brief = next(item for item in bind_tools(ctx) if item.tool_name == "save_brief")._tool_func
    assert save_brief(**BRIEF_ARGS)["ok"] is True
    text = (case_root / "00-work" / "brief.md").read_text(encoding="utf-8")
    assert "character: json" in text


def test_save_brief_later_json_intent_overrides_png(tmp_path: Path) -> None:
    from st_agent.services.workspace import append_intake

    case_root = create_case(tmp_path, "harbor-watch")
    append_intake(case_root, "User: I want a PNG card.")
    append_intake(case_root, "User: Use JSON instead.")
    authorize_build(case_root)
    ctx = ToolContext(case_root=case_root, invocation_id="inv-later", operation_id="op-later")
    save_brief = next(item for item in bind_tools(ctx) if item.tool_name == "save_brief")._tool_func
    assert save_brief(**BRIEF_ARGS)["ok"] is True
    text = (case_root / "00-work" / "brief.md").read_text(encoding="utf-8")
    assert "character: json" in text


def test_save_brief_png_filename_is_not_a_format_request(tmp_path: Path) -> None:
    from st_agent.services.workspace import append_intake

    case_root = create_case(tmp_path, "harbor-watch")
    append_intake(case_root, "User: Use Demo.png as the face.")
    authorize_build(case_root)
    ctx = ToolContext(case_root=case_root, invocation_id="inv-fn", operation_id="op-fn")
    save_brief = next(item for item in bind_tools(ctx) if item.tool_name == "save_brief")._tool_func
    assert save_brief(**BRIEF_ARGS)["ok"] is True
    text = (case_root / "00-work" / "brief.md").read_text(encoding="utf-8")
    assert "character: json" in text


def test_confirm_flag_roundtrips_on_outcome() -> None:
    outcome = TurnOutcome(
        kind="question",
        message="Ready?",
        question="Reply yes to write the card.",
        confirm=True,
    )
    assert outcome.confirm is True
