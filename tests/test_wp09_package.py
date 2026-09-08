"""WP-09 package fixtures and live-retry helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from st_agent.application.assembly import SYSTEM_PROMPT
from st_agent.application.case_controller import (
    _live_model,
    submit_turn,
    try_live_model_chain,
)
from st_agent.application.hooks import _envelope_code
from st_agent.application.tools import ToolContext, bind_tools
from st_agent.config import RuntimeSettings
from st_agent.domain.canonical import load_creative_path
from st_agent.domain.case import CardDelivery, LorebookDelivery
from st_agent.outcomes import TurnOutcome
from st_agent.services.workspace import create_case
from tests.fakes import ScriptedModel
from tests.test_wp06_integration import BRIEF_ARGS, _authorized_case, _happy_script, _source_service

CANONICAL = Path(__file__).resolve().parents[1] / "docs" / "spikes" / "wp-09-canonical.md"


def test_wp09_canonical_fixture_roundtrips() -> None:
    doc = load_creative_path(CANONICAL)
    assert doc.character is not None
    assert doc.character.name == "Mara Ellison"
    assert doc.brief.delivery.character is CardDelivery.png
    assert doc.brief.delivery.lorebook is LorebookDelivery.both
    assert doc.brief.delivery.portrait_ref == "01-assets/portraits/wp-09-portrait.png"
    assert doc.lorebook is not None
    assert {entry.entry_id for entry in doc.lorebook.entries} == {"reedwick-jetty", "cinderwake"}


def test_live_chain_tries_next_model_after_failure() -> None:
    seen: list[str] = []

    def invoke(model_id: str) -> TurnOutcome:
        seen.append(model_id)
        if model_id == "hy3":
            raise TimeoutError("connect")
        return TurnOutcome(kind="blocked", message="fallback ran", blocker="probe")

    outcome, err = try_live_model_chain(("hy3", "glm-5.3-flash"), invoke)
    assert seen == ["hy3", "glm-5.3-flash"]
    assert err == ""
    assert outcome is not None
    assert outcome.message == "fallback ran"


def test_live_http_timeout_fails_connect_not_long_reads() -> None:
    model = _live_model(
        "deepseek-v4-flash-0731",
        base_url="https://example.invalid/v1",
        key="k",
    )
    timeout = model.client_args["timeout"]
    assert timeout.connect == 15.0
    assert timeout.read is None
    assert timeout.write == 60.0
    assert model.config["params"]["extra_body"]["enable_thinking"] is False


def test_system_prompt_requires_canonical_roundtrip() -> None:
    assert "canonical-invalid" in SYSTEM_PROMPT
    assert "# Brief" in SYSTEM_PROMPT or "Brief" in SYSTEM_PROMPT
    assert "round-trip" in SYSTEM_PROMPT
    assert "save_brief" in SYSTEM_PROMPT
    assert "build_character_card" in SYSTEM_PROMPT
    assert "check_official_sources" in SYSTEM_PROMPT
    assert "validate_deliverables" in SYSTEM_PROMPT
    assert "finish_case" in SYSTEM_PROMPT
    assert "build_confirmed" in SYSTEM_PROMPT
    assert "confirm" in SYSTEM_PROMPT


def test_save_brief_writes_importable_canonical(tmp_path: Path) -> None:
    from st_agent.services.serializers import serialize_character
    from st_agent.services.validators import validate_card

    case_root = _authorized_case(tmp_path)
    ctx = ToolContext(case_root=case_root, invocation_id="inv-brief", operation_id="op-brief")
    tools = {item.tool_name: item._tool_func for item in bind_tools(ctx)}
    args = {**BRIEF_ARGS, "lorebook_output": "both"}
    assert tools["save_brief"](**args)["ok"] is True
    doc = load_creative_path(case_root / "03-final-text" / "canonical.md")
    assert doc.character is not None
    assert doc.character.name.strip()
    assert doc.lorebook is not None
    assert doc.lorebook.entries
    card = serialize_character(doc.character, lorebook=doc.lorebook)
    assert validate_card(card).ok
    built = tools["build_character_card"]()
    assert built["ok"] is True
    payload = json.loads((case_root / "04-exports" / "character-cards" / "card.json").read_text())
    assert payload["data"]["name"].strip()


def test_brief_then_builds_can_finish(tmp_path: Path) -> None:
    case_root = _authorized_case(tmp_path)
    ctx = ToolContext(
        case_root=case_root,
        invocation_id="inv-finish",
        operation_id="op-finish",
        source_service=_source_service(),
    )
    tools = {item.tool_name: item._tool_func for item in bind_tools(ctx)}
    args = {**BRIEF_ARGS, "lorebook_output": "both"}
    assert tools["save_brief"](**args)["ok"] is True
    assert tools["build_character_card"]()["ok"] is True
    lore = tools["build_lorebook"]()
    assert lore["ok"] is True
    assert tools["check_official_sources"]()["ok"] is True
    assert tools["validate_deliverables"]()["ok"] is True
    done = tools["finish_case"]()
    assert done["ok"] is True


def test_invalid_canonical_save_keeps_auto_file(tmp_path: Path) -> None:
    case_root = _authorized_case(tmp_path)
    ctx = ToolContext(case_root=case_root, invocation_id="inv-keep", operation_id="op-keep")
    tools = {item.tool_name: item._tool_func for item in bind_tools(ctx)}
    assert tools["save_brief"](**BRIEF_ARGS)["ok"] is True
    path = case_root / "03-final-text" / "canonical.md"
    before = path.read_text(encoding="utf-8")
    result = tools["save_content_document"](kind="canonical", markdown="# Notes\nNot canonical.\n")
    assert result["ok"] is False
    assert result["code"] == "canonical-invalid"
    assert path.read_text(encoding="utf-8") == before


def test_canonical_save_stops_after_three_invalid(tmp_path: Path) -> None:
    case_root = _authorized_case(tmp_path)
    ctx = ToolContext(case_root=case_root, invocation_id="inv-bound", operation_id="op-bound")
    tools = {item.tool_name: item._tool_func for item in bind_tools(ctx)}
    assert tools["save_brief"](**BRIEF_ARGS)["ok"] is True
    bad = "# Notes\nThis is not a canonical document.\n"
    save = tools["save_content_document"]
    codes = [save(kind="canonical", markdown=bad)["code"] for _ in range(4)]
    assert codes[:3] == ["canonical-invalid", "canonical-invalid", "canonical-invalid"]
    assert codes[3] == "canonical-retry-limit"


def test_envelope_code_reads_wrapped_payload() -> None:
    payload = '{"ok": false, "code": "canonical-invalid"}'
    wrapped = {"status": "success", "content": [{"text": payload}], "toolUseId": "1"}
    assert _envelope_code(wrapped) == "canonical-invalid"
    assert _envelope_code({"ok": True, "code": None}) is None


def test_live_missing_outcome_is_timeout_not_provider_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("st_agent.application.case_controller.load_local_env", lambda: None)
    monkeypatch.setattr("st_agent.application.case_controller.api_key", lambda: "k")
    monkeypatch.setattr(
        "st_agent.application.case_controller.load_settings",
        lambda: RuntimeSettings(
            provider="Alibaba-Token",
            base_url="https://example.invalid/v1",
            model_id="deepseek-v4-flash-0731",
        ),
    )
    monkeypatch.setattr(
        "st_agent.application.case_controller._live_model",
        lambda *args, **kwargs: object(),
    )

    class _Result:
        structured_output = None
        stop_reason = "cancelled"

    class _Agent:
        def __init__(self, **kwargs) -> None:
            pass

        def __call__(self, *args, **kwargs):
            return _Result()

    monkeypatch.setattr("st_agent.application.case_controller.Agent", _Agent)
    case_root = create_case(tmp_path, "harbor-watch")
    outcome, _ = submit_turn(case_root, "Hello.", operation_id="op-live-timeout")
    assert outcome.kind == "blocked"
    assert outcome.blocker == "live-timeout"
    assert "stopped responding" in (outcome.message or "").lower() or "unreachable" in (
        outcome.message or ""
    ).lower()


def test_submit_turn_uses_explicit_live_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, str] = {}

    def fake_env() -> None:
        raise AssertionError("must not load env files")

    monkeypatch.setattr("st_agent.application.case_controller.load_local_env", fake_env)

    def fake_live(model_id: str, *, base_url: str, key: str):
        seen["model_id"] = model_id
        seen["base_url"] = base_url
        seen["key"] = key
        return object()

    monkeypatch.setattr("st_agent.application.case_controller._live_model", fake_live)

    class _Result:
        structured_output = TurnOutcome(
            kind="question", message="Need a portrait.", question="Upload?"
        )

    class _Agent:
        def __init__(self, **kwargs) -> None:
            pass

        def __call__(self, *args, **kwargs):
            return _Result()

    monkeypatch.setattr("st_agent.application.case_controller.Agent", _Agent)
    case_root = create_case(tmp_path, "harbor-watch")
    outcome, _ = submit_turn(
        case_root,
        "Hello.",
        operation_id="op-live-cfg",
        live_settings=RuntimeSettings(
            provider="Alibaba-Token",
            base_url="https://example.invalid/v1",
            model_id="page-model",
        ),
        live_key="session-key",
    )
    assert outcome.kind == "question"
    assert seen == {
        "model_id": "page-model",
        "base_url": "https://example.invalid/v1",
        "key": "session-key",
    }


def test_finish_ok_reports_delivered_if_model_says_blocked(tmp_path: Path) -> None:
    script = _happy_script()
    script[-1] = {
        "outcome": {
            "kind": "blocked",
            "message": "The case looks closed.",
            "blocker": "case-state: closed",
        }
    }
    case_root = _authorized_case(tmp_path)
    outcome, _ = submit_turn(
        case_root,
        "Make a JSON card.",
        operation_id="op-closed-delivered",
        model=ScriptedModel(script),
        source_service=_source_service(),
    )
    assert outcome.kind == "delivered"
    assert (case_root / "04-exports" / "character-cards" / "card.json").is_file()
