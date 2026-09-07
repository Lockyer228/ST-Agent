"""WP-07 UI view-model tests. Streamlit is not required here."""

from __future__ import annotations

from pathlib import Path

import pytest

from st_agent.application.case_controller import submit_turn
from st_agent.domain.case import CaseMode
from st_agent.services.readers import UnsupportedInput
from st_agent.services.workspace import PathRejected, create_case, load_manifest
from st_agent.ui.view import (
    EVENT_PREFIXES,
    empty_turn_error,
    next_operation_id,
    parse_deliverables,
    preview_upload,
    read_deliverable,
    sanitize_events,
    status_guidance,
    write_upload,
)
from tests.fakes import ScriptedModel


def test_default_create_case_is_new(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    assert load_manifest(case_root).mode == CaseMode.new


def test_create_case_can_record_modify_mode(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch", mode=CaseMode.modify)
    assert load_manifest(case_root).mode == CaseMode.modify


def test_preview_upload_rejects_gif() -> None:
    with pytest.raises(UnsupportedInput, match="GIF"):
        preview_upload("clip.gif", b"GIF89a" + b"\x00" * 8)


def test_preview_upload_accepts_utf8_text() -> None:
    assert preview_upload("notes.txt", b"A rain-soaked port.\n") == "text"


def test_sanitize_events_keeps_only_safe_names() -> None:
    kept = sanitize_events(
        [
            "tool-start:save_brief",
            "tool-success:save_brief",
            "prompt:secret",
            "reasoning:hidden",
            "invocation-complete",
            "idempotent",
            "tool-failure:finish_case",
        ]
    )
    assert kept == [
        "tool-start:save_brief",
        "tool-success:save_brief",
        "invocation-complete",
        "idempotent",
        "tool-failure:finish_case",
    ]
    assert all(item.startswith(EVENT_PREFIXES) or item == "idempotent" for item in kept)


def test_parse_deliverables_ignores_escape() -> None:
    text = (
        "# harbor-watch\n\nCase state: closed.\n\nDeliverables:\n"
        "- 04-exports/character-cards/card.json\n"
        "- ../../secret.txt\n"
        "- 00-work/brief.md\n"
    )
    assert parse_deliverables(text) == ["04-exports/character-cards/card.json"]


def test_read_deliverable_returns_exact_bytes(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    dest = case_root / "04-exports" / "character-cards"
    dest.mkdir(parents=True, exist_ok=True)
    payload = b'{"spec":"chara_card_v3"}'
    (dest / "card.json").write_bytes(payload)
    assert read_deliverable(case_root, "04-exports/character-cards/card.json") == payload


def test_read_deliverable_rejects_work_dir(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    with pytest.raises(PathRejected):
        read_deliverable(case_root, "00-work/case.json")
    with pytest.raises(PathRejected):
        read_deliverable(case_root, "04-exports/../00-work/case.json")


def test_empty_turn_error_blocks_blank_message_without_uploads() -> None:
    assert empty_turn_error("", 0) == "Message is empty."
    assert empty_turn_error("   ", 0) == "Message is empty."
    assert empty_turn_error("A tavern keeper.", 0) is None
    assert empty_turn_error("", 1) is None


def test_write_upload_keeps_basename_only(tmp_path: Path) -> None:
    dest = write_upload(tmp_path, r"..\secret.txt", b"plain")
    assert dest == tmp_path / "secret.txt"
    assert dest.read_bytes() == b"plain"
    slash = write_upload(tmp_path, "../notes.txt", b"slash")
    assert slash == tmp_path / "notes.txt"
    fallback = write_upload(tmp_path, "..", b"dots")
    assert fallback == tmp_path / "upload.bin"
    assert fallback.read_bytes() == b"dots"


def test_status_guidance_is_english_and_actionable() -> None:
    text = status_guidance("blocked", "b-ai-credentials-missing", None)
    assert "ST_AGENT_API_KEY" in text
    assert "retry" in text.lower()
    waiting = status_guidance("waiting_for_user", None, "Please upload a portrait.")
    assert "Please upload a portrait." in waiting
    mismatch = status_guidance("blocked", "revision-mismatch", None)
    assert "refresh" in mismatch.lower()
    cleanup = status_guidance("cleanup_pending", None, None)
    assert "Resume" in cleanup


def test_next_operation_id_is_stable_per_submit() -> None:
    store: dict[str, int] = {}
    first = next_operation_id(store)
    second = next_operation_id(store)
    assert first != second
    assert first.startswith("ui-")
    assert second.startswith("ui-")


def test_question_envelope_feeds_status_guidance(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    outcome, events = submit_turn(
        case_root,
        "I want a PNG card.",
        operation_id=next_operation_id({}),
        model=ScriptedModel(
            [
                {
                    "outcome": {
                        "kind": "question",
                        "message": "Need a portrait file.",
                        "question": "Please upload a portrait.",
                    }
                }
            ]
        ),
    )
    assert outcome.kind == "question"
    manifest = load_manifest(case_root)
    assert "Please upload a portrait." in status_guidance(
        manifest.condition, None, manifest.pending_question
    )
    kept = sanitize_events(events)
    assert all(item.startswith(EVENT_PREFIXES) or item == "idempotent" for item in kept)
    assert not any(item.startswith(("prompt:", "reasoning:")) for item in kept)


def test_product_page_creates_and_resumes_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from st_agent.outcomes import TurnOutcome

    monkeypatch.setattr("st_agent.ui.app.load_local_env", lambda: None)
    monkeypatch.setattr(
        "st_agent.ui.app.submit_turn",
        lambda *args, **kwargs: (
            TurnOutcome(
                kind="question",
                message="Need a portrait file.",
                question="Please upload a portrait.",
            ),
            ["tool-start:save_brief", "invocation-complete"],
        ),
    )
    from streamlit.testing.v1 import AppTest

    def click(app: AppTest, label: str) -> None:
        next(item for item in app.button if item.label == label).click().run()

    script = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(script), default_timeout=20)
    at.run()
    assert not at.exception
    labels = [item.value for item in at.subheader]
    assert "New project" in labels
    assert "Resume project" in labels
    at.text_input[0].input(str(tmp_path))
    at.text_input[1].input("harbor-watch")
    click(at, "Create case")
    assert not at.exception
    page = "\n".join(str(item.value) for item in [*at.markdown, *at.caption, *at.text])
    assert "setup" in page
    at.text_area[0].input("Make a JSON card.")
    click(at, "Send")
    assert not at.exception
    page = "\n".join(str(item.value) for item in [*at.markdown, *at.text, *at.warning, *at.info])
    assert "Need a portrait file." in page or "Please upload a portrait." in page
    assert "tool-start:save_brief" in page
    click(at, "Back to start")
    at.text_input[2].input(str(tmp_path / "harbor-watch"))
    click(at, "Resume case")
    assert not at.exception
    page = "\n".join(
        str(item.value) for item in [*at.markdown, *at.caption, *at.text, *at.info]
    )
    assert "setup" in page
    assert "Resume:" in page


def test_product_page_rejects_empty_send(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from st_agent.outcomes import TurnOutcome

    calls: list[int] = []

    def fake_submit(*args, **kwargs):
        calls.append(1)
        return TurnOutcome(kind="question", message="should not run"), []

    monkeypatch.setattr("st_agent.ui.app.load_local_env", lambda: None)
    monkeypatch.setattr("st_agent.ui.app.submit_turn", fake_submit)
    from streamlit.testing.v1 import AppTest

    script = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(script), default_timeout=20)
    at.run()
    at.text_input[0].input(str(tmp_path))
    at.text_input[1].input("harbor-watch")
    next(item for item in at.button if item.label == "Create case").click().run()
    next(item for item in at.button if item.label == "Send").click().run()
    assert not at.exception
    assert calls == []
    page = "\n".join(str(item.value) for item in [*at.error, *at.markdown, *at.text])
    assert "Message is empty." in page
