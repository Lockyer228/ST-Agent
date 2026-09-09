"""Live provider smoke case. Skipped when ST_AGENT_API_KEY is absent."""

from __future__ import annotations

import pytest

from st_agent.application.case_controller import submit_turn
from st_agent.config import api_key, load_local_env
from st_agent.services.workspace import create_case


def test_bai_smoke_emits_real_tool_events(tmp_path) -> None:
    load_local_env()
    if api_key() is None:
        pytest.skip("ST_AGENT_API_KEY is not available")
    case_root = create_case(tmp_path, "harbor-watch")
    outcome, events = submit_turn(
        case_root,
        "Create a JSON-only tavern-keeper character card. Do not request PNG. "
        "Ask one question if a required intent field is missing; otherwise use the tools "
        "and finish_case. Never claim delivery yourself.",
        operation_id="op-smoke",
    )
    assert outcome.kind in {"question", "delivered", "blocked"}
    assert "ST_AGENT_API_KEY" not in (outcome.message or "")
    assert any(item.startswith("tool-start:") for item in events) or outcome.kind == "blocked"
