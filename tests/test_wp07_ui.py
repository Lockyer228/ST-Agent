"""WP-07 UI view-model tests. Streamlit is not required here."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from st_agent.application.case_controller import submit_turn
from st_agent.config import RuntimeSettings
from st_agent.domain.case import CaseMode
from st_agent.services.readers import UnsupportedInput
from st_agent.services.workspace import PathRejected, create_case, load_manifest
from st_agent.ui.view import (
    AGENT_WORKING,
    EVENT_PREFIXES,
    SEND_BUTTON_LABEL,
    activity_label,
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
    assert all(
        item.startswith(("tool-start:", "tool-success:", "tool-failure:"))
        or item in {"idempotent", "invocation-complete"}
        for item in kept
    )


def test_sanitize_events_rejects_prefix_extension() -> None:
    kept = sanitize_events(
        [
            "invocation-complete-and-prompt",
            "tool-start:",
            "tool-start:save_brief",
            "tool-success",
        ]
    )
    assert kept == ["tool-start:save_brief"]


def test_activity_label_covers_tools_and_hides_internals() -> None:
    started: set[str] = set()
    assert activity_label("tool-start:save_brief", started) == "Organizing the creative brief..."
    assert activity_label("tool-success:save_brief", started) == "Creative brief saved."
    assert (
        activity_label("tool-failure:validate_deliverables:validation-failed", started)
        == "Deliverable validation did not finish this time."
    )
    assert activity_label("tool-start:save_brief", started) == (
        "Retrying: Organizing the creative brief..."
    )
    assert activity_label("tool-start:TurnOutcome", started) is None
    assert activity_label("invocation-complete", started) is None
    assert activity_label("idempotent", started) is None
    assert activity_label("tool-start:not-a-tool", started) is None
    assert activity_label("prompt:secret", started) is None
    assert "save_brief" not in (activity_label("tool-start:build_lorebook", started) or "")
    for name in (
        "save_content_document",
        "build_character_card",
        "build_lorebook",
        "build_png_card",
        "check_official_sources",
        "validate_deliverables",
        "finish_case",
    ):
        line = activity_label(f"tool-start:{name}", started)
        assert line
        assert name not in line


def test_event_sink_receives_tools_before_return(tmp_path: Path) -> None:
    from tests.test_wp06_integration import _authorized_case, _happy_script, _source_service

    case_root = _authorized_case(tmp_path)
    seen: list[str] = []
    finished = {"done": False}

    def sink(event: str) -> None:
        assert finished["done"] is False
        seen.append(event)

    outcome, events = submit_turn(
        case_root,
        "Make a JSON card for Mara.",
        operation_id="op-sink",
        model=ScriptedModel(_happy_script()),
        source_service=_source_service(),
        event_sink=sink,
    )
    finished["done"] = True
    assert outcome.kind == "delivered"
    assert seen == events
    assert any(item.startswith("tool-start:save_brief") for item in seen)
    assert any(item.startswith("tool-success:finish_case") for item in seen)
    assert "invocation-complete" in seen
    assert not any("prompt:" in item or "reasoning:" in item for item in seen)
    assert not any("ST_AGENT_API_KEY" in item for item in seen)


def test_submit_turn_without_sink_stays_compatible(tmp_path: Path) -> None:
    from tests.test_wp06_integration import _authorized_case, _happy_script, _source_service

    case_root = _authorized_case(tmp_path)
    outcome, events = submit_turn(
        case_root,
        "Make a JSON card for Mara.",
        operation_id="op-nosink",
        model=ScriptedModel(_happy_script()),
        source_service=_source_service(),
    )
    assert outcome.kind == "delivered"
    assert any(item.startswith("tool-start:save_brief") for item in events)


def test_event_sink_exception_does_not_fail_turn(tmp_path: Path) -> None:
    from tests.test_wp06_integration import _authorized_case, _happy_script, _source_service

    case_root = _authorized_case(tmp_path)

    def sink(_event: str) -> None:
        raise RuntimeError("NoSessionContext")

    outcome, events = submit_turn(
        case_root,
        "Make a JSON card for Mara.",
        operation_id="op-sink-err",
        model=ScriptedModel(_happy_script()),
        source_service=_source_service(),
        event_sink=sink,
    )
    assert outcome.kind == "delivered"
    assert any(item.startswith("tool-start:save_brief") for item in events)


def test_parse_deliverables_ignores_escape() -> None:
    text = (
        "# harbor-watch\n\nCase state: closed.\n\nDeliverables:\n"
        "- 04-exports/character-cards/card.json\n"
        "- ../../secret.txt\n"
        "- 00-work/brief.md\n"
    )
    assert parse_deliverables(text) == ["04-exports/character-cards/card.json"]


def test_list_readme_deliverables_ignores_non_utf8(tmp_path: Path) -> None:
    from st_agent.ui.view import list_readme_deliverables

    readme = tmp_path / "README.md"
    readme.write_bytes(b"\xff\xfe Deliverables:\n- 04-exports/card.json\n")
    assert list_readme_deliverables(readme) == []


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


def test_session_config_error_requires_connection_fields() -> None:
    from st_agent.ui.view import session_config_error

    url = "https://example.invalid/v1"
    assert session_config_error("", url, "m", "k") == "Provider is missing."
    assert session_config_error("P", "", "m", "k") == "OpenAI Base URL is missing."
    assert session_config_error("P", url, "", "k") == "Model is missing."
    assert session_config_error("P", url, "m", "") == "API key is missing."
    assert session_config_error("P", url, "m", "k") is None


def test_write_upload_keeps_basename_only(tmp_path: Path) -> None:
    dest = write_upload(tmp_path, r"..\secret.txt", b"plain")
    assert dest == tmp_path / "secret.txt"
    assert dest.read_bytes() == b"plain"
    slash = write_upload(tmp_path, "../notes.txt", b"slash")
    assert slash == tmp_path / "notes.txt"
    fallback = write_upload(tmp_path, "..", b"dots")
    assert fallback == tmp_path / "upload.bin"
    assert fallback.read_bytes() == b"dots"


def test_send_is_paused_while_agent_working() -> None:
    assert SEND_BUTTON_LABEL == "Send message"
    assert "working" in AGENT_WORKING.lower()
    assert "sending" in AGENT_WORKING.lower()


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
    assert all(
        item.startswith(EVENT_PREFIXES) or item in {"idempotent", "invocation-complete"}
        for item in kept
    )
    assert not any(item.startswith(("prompt:", "reasoning:")) for item in kept)


def _click(app, label: str) -> None:
    next(item for item in app.button if item.label == label).click().run()


def _input_by_label(app, label: str):
    for group in (app.text_input, app.sidebar.text_input):
        for item in group:
            if item.label == label:
                return item
    raise LookupError(label)


def _fill_connection(
    app,
    *,
    provider: str = "Alibaba-Token",
    base_url: str = "https://example.invalid/v1",
    model: str = "page-model",
    api_key: str = "session-key",
) -> None:
    _input_by_label(app, "Provider").input(provider)
    _input_by_label(app, "OpenAI Base URL").input(base_url)
    _input_by_label(app, "Model").input(model)
    _input_by_label(app, "API key").input(api_key)


def test_product_page_shows_connection_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "st_agent.ui.app.submit_turn",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not submit")),
    )
    from streamlit.testing.v1 import AppTest

    script = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(script), default_timeout=20)
    at.run()
    assert not at.exception
    labels = [item.label for item in [*at.text_input, *at.sidebar.text_input]]
    assert "Provider" in labels
    assert "OpenAI Base URL" in labels
    assert "Model" in labels
    assert "API key" in labels
    page = "\n".join(
        str(item.value)
        for item in [
            *at.markdown,
            *at.caption,
            *at.text,
            *at.sidebar.markdown,
            *at.sidebar.caption,
            *at.sidebar.text,
        ]
    )
    assert "not configured" in page.lower()
    assert "openai-compatible" in page.lower()
    assert "anthropic" in page.lower()
    assert "discarded when the app stops" in page.lower()


def test_product_page_creates_and_resumes_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from st_agent.outcomes import TurnOutcome

    seen: dict[str, object] = {}

    def fake_submit(*args, **kwargs):
        seen.update(kwargs)
        return (
            TurnOutcome(
                kind="question",
                message="Need a portrait file.",
                question="Please upload a portrait.",
            ),
            ["tool-start:save_brief", "invocation-complete"],
        )

    monkeypatch.setattr("st_agent.ui.app.submit_turn", fake_submit)
    from streamlit.testing.v1 import AppTest

    script = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(script), default_timeout=20)
    at.run()
    assert not at.exception
    labels = [item.value for item in at.subheader]
    assert "New project" in labels
    assert "Resume project" in labels
    _input_by_label(at, "Workspace folder").input(str(tmp_path))
    _input_by_label(at, "Story name").input("harbor-watch")
    _fill_connection(at)
    _click(at, "Create case")
    assert not at.exception
    page = "\n".join(str(item.value) for item in [*at.markdown, *at.caption, *at.text])
    assert "setup" in page
    at.text_area[0].input("Make a JSON card.")
    _click(at, SEND_BUTTON_LABEL)
    assert not at.exception
    assert not (at.text_area[0].value or "").strip()
    page = "\n".join(str(item.value) for item in [*at.markdown, *at.text, *at.warning, *at.info])
    assert "Need a portrait file." in page or "Please upload a portrait." in page
    assert "Organizing the creative brief..." in page or "Waiting for your answer." in page
    assert "tool-start:save_brief" in page
    assert "Agent events" not in page
    assert seen["live_key"] == "session-key"
    settings = seen["live_settings"]
    assert isinstance(settings, RuntimeSettings)
    assert settings.provider == "Alibaba-Token"
    assert settings.base_url == "https://example.invalid/v1"
    assert settings.model_id == "page-model"
    _click(at, "Back to start")
    _input_by_label(at, "Existing case folder").input(str(tmp_path / "harbor-watch"))
    _click(at, "Resume case")
    assert not at.exception
    page = "\n".join(
        str(item.value) for item in [*at.markdown, *at.caption, *at.text, *at.info]
    )
    assert "setup" in page
    assert "Resume:" in page


def test_product_page_send_needs_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from st_agent.outcomes import TurnOutcome

    calls: list[int] = []

    def fake_submit(*args, **kwargs):
        calls.append(1)
        return TurnOutcome(kind="question", message="should not run"), []

    monkeypatch.setattr("st_agent.ui.app.submit_turn", fake_submit)
    from streamlit.testing.v1 import AppTest

    script = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(script), default_timeout=20)
    at.run()
    _input_by_label(at, "Workspace folder").input(str(tmp_path))
    _input_by_label(at, "Story name").input("harbor-watch")
    _fill_connection(at, api_key="")
    _click(at, "Create case")
    at.text_area[0].input("Make a JSON card.")
    _click(at, SEND_BUTTON_LABEL)
    assert not at.exception
    assert calls == []
    page = "\n".join(str(item.value) for item in [*at.error, *at.markdown, *at.text])
    assert "API key is missing." in page


def test_product_page_rejects_empty_send(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from st_agent.outcomes import TurnOutcome

    calls: list[int] = []

    def fake_submit(*args, **kwargs):
        calls.append(1)
        return TurnOutcome(kind="question", message="should not run"), []

    monkeypatch.setattr("st_agent.ui.app.submit_turn", fake_submit)
    from streamlit.testing.v1 import AppTest

    script = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(script), default_timeout=20)
    at.run()
    _input_by_label(at, "Workspace folder").input(str(tmp_path))
    _input_by_label(at, "Story name").input("harbor-watch")
    _click(at, "Create case")
    _click(at, SEND_BUTTON_LABEL)
    assert not at.exception
    assert calls == []
    page = "\n".join(str(item.value) for item in [*at.error, *at.markdown, *at.text])
    assert "Message is empty." in page


def test_product_page_disables_send_while_agent_working(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from st_agent.outcomes import TurnOutcome

    calls: list[int] = []

    def fake_submit(*args, **kwargs):
        calls.append(1)
        return TurnOutcome(kind="question", message="should not run"), []

    monkeypatch.setattr("st_agent.ui.app.submit_turn", fake_submit)
    from streamlit.testing.v1 import AppTest

    script = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(script), default_timeout=20)
    at.run()
    _input_by_label(at, "Workspace folder").input(str(tmp_path))
    _input_by_label(at, "Story name").input("harbor-watch")
    _fill_connection(at)
    _click(at, "Create case")
    at.session_state["turn_busy"] = True
    at.run()
    assert not at.exception
    send = next(item for item in at.button if item.label == SEND_BUTTON_LABEL)
    assert send.disabled
    page = "\n".join(str(item.value) for item in [*at.info, *at.markdown, *at.text])
    assert AGENT_WORKING in page
    assert calls == []


def test_product_page_shows_unreadable_manifest(tmp_path: Path) -> None:
    from streamlit.testing.v1 import AppTest

    case_root = create_case(tmp_path, "harbor-watch")
    (case_root / "00-work" / "case.json").write_text("{not-json", encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(script), default_timeout=20)
    at.run()
    _input_by_label(at, "Existing case folder").input(str(case_root))
    _click(at, "Resume case")
    assert not at.exception
    page = "\n".join(str(item.value) for item in [*at.error, *at.markdown, *at.text])
    assert "case manifest is unreadable" in page


def test_product_page_shows_unreadable_closed_readme(tmp_path: Path) -> None:
    from streamlit.testing.v1 import AppTest

    case_root = create_case(tmp_path, "harbor-watch")
    shutil.rmtree(case_root / "00-work")
    (case_root / "README.md").write_bytes(b"\xff\xfe abandoned\n")
    script = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(script), default_timeout=20)
    at.run()
    _input_by_label(at, "Existing case folder").input(str(case_root))
    _click(at, "Resume case")
    assert not at.exception
    page = "\n".join(str(item.value) for item in [*at.error, *at.markdown, *at.text])
    assert "case manifest is unreadable" in page
    assert "Deliverables stay on disk." in page
