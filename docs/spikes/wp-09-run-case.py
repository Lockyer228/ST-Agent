"""Drive the WP-09 representative case through create_case / submit_turn.

Uses the same controller path as Streamlit Send. Does not print secrets.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from st_agent.application import case_controller as _case_controller
from st_agent.application.case_controller import LIVE_TIMEOUT_S, submit_turn
from st_agent.config import api_key, load_local_env, load_settings
from st_agent.services.workspace import create_case
from st_agent.ui.view import sanitize_events

STORY_PATH = Path(__file__).with_name("wp-09-case-input.md")
PORTRAIT = Path(__file__).with_name("wp-09-portrait.png")
CANONICAL = Path(__file__).with_name("wp-09-canonical.md")
LOG_PATH = Path(os.environ.get("ST_AGENT_WP09_LOG") or Path(__file__).with_name("wp-09-run-log.json"))
WORKSPACE = Path(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp") / "st-agent-wp09-rc"
MAX_TURNS = 8
_TIMEOUT_OVERRIDE = os.environ.get("ST_AGENT_LIVE_TIMEOUT_S")
WORKING_TIMEOUT_S = float(_TIMEOUT_OVERRIDE) if _TIMEOUT_OVERRIDE else LIVE_TIMEOUT_S
FIRST_TURN_TIMEOUT_S = float(os.environ.get("ST_AGENT_FIRST_TURN_S") or 25)
if _TIMEOUT_OVERRIDE:
    _case_controller.LIVE_TIMEOUT_S = WORKING_TIMEOUT_S
HARD_BLOCKERS = {
    "b-ai-credentials-missing",
    "b-ai-models-unavailable",
    "case-closed",
    "case-locked",
}

FIRST_MESSAGE = """Create a SillyTavern character from this original English story.

Reedwick keeps its channel markers lit because the fog never fully lifts. Mara Ellison is the last lampwright who still walks the jetty after midnight. She carries a brass wind-key, a ledger of drowned names, and a habit of answering questions with the tide tables instead of comfort.

Last winter a packet boat named Cinderwake vanished between the outer buoy and the customs dock. The harbor master closed the file. Mara did not. Each night she relights the same three lamps in the same order, then writes one new line in the ledger: weather, current, and any voice that answered from the water.

She will not say she is hunting a ghost. She will say the channel still owes the town three lamps and one ship.

The player is a visiting sailor looking for a missing shipmate from Cinderwake.

I need a PNG character card plus both a standalone lorebook and an embedded lorebook. A portrait PNG is uploaded with this message. Call save_brief as the first tool. Do not write a plan. Ask one question only if a required intent field is missing. Never claim delivery yourself.
"""

CONTINUE_HINT = (
    "Save the following as save_content_document kind=canonical. "
    "Use portrait_ref 01-assets/portraits/wp-09-portrait.png. "
    "Then call build_character_card, build_lorebook, build_png_card, "
    "check_official_sources, validate_deliverables, and finish_case.\n\n"
)


def _continue_message() -> str:
    return CONTINUE_HINT + CANONICAL.read_text(encoding="utf-8")


def _redact(text: str, secret: str | None) -> str:
    if not secret or not text:
        return text
    return text.replace(secret, "[redacted]")


def _exports(case_root: Path) -> list[str]:
    exports = case_root / "04-exports"
    if not exports.is_dir():
        return []
    return sorted(
        path.relative_to(case_root).as_posix()
        for path in exports.rglob("*")
        if path.is_file()
    )


def main() -> int:
    load_local_env()
    settings = load_settings()
    key = api_key()
    started = time.perf_counter()
    record: dict[str, object] = {
        "provider": settings.provider,
        "base_url": settings.base_url,
        "preferred_model": settings.model_id,
        "key_present": key is not None,
        "live_timeout_s": WORKING_TIMEOUT_S,
        "first_turn_timeout_s": FIRST_TURN_TIMEOUT_S,
        "turns": [],
        "elapsed_s": 0.0,
        "result": "not-started",
        "exports": [],
        "events": [],
    }
    if key is None:
        record["result"] = "pending-condition"
        record["blocker"] = "b-ai-credentials-missing"
        LOG_PATH.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print("pending-condition: ST_AGENT_API_KEY is missing")
        return 2

    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True)
    case_root = create_case(WORKSPACE, "reedwick-lampwright")
    portrait = PORTRAIT if PORTRAIT.is_file() else None
    all_events: list[str] = []
    message = FIRST_MESSAGE
    uploads = [portrait] if portrait is not None else []
    final_kind = "blocked"

    for turn in range(1, MAX_TURNS + 1):
        _case_controller.LIVE_TIMEOUT_S = (
            FIRST_TURN_TIMEOUT_S if turn == 1 else WORKING_TIMEOUT_S
        )
        outcome, events = submit_turn(
            case_root,
            message,
            uploads=uploads,
            operation_id=f"wp09-{turn}",
        )
        events = sanitize_events(list(events))
        all_events.extend(events)
        turn_row = {
            "n": turn,
            "kind": outcome.kind,
            "blocker": outcome.blocker,
            "required_input": outcome.required_input,
            "question": _redact(outcome.question or "", key),
            "message": _redact(outcome.message or "", key)[:500],
            "artifact_refs": outcome.artifact_refs,
            "events": events,
        }
        record["turns"].append(turn_row)
        print(f"turn {turn}: {outcome.kind} blocker={outcome.blocker}")
        if outcome.kind == "delivered":
            final_kind = "delivered"
            break
        if outcome.kind == "blocked" and outcome.blocker in HARD_BLOCKERS:
            final_kind = "blocked"
            record["blocker"] = outcome.blocker
            break
        uploads = []
        message = _continue_message()
    else:
        final_kind = "blocked"
        record["blocker"] = "turn-limit"

    record["elapsed_s"] = round(time.perf_counter() - started, 1)
    record["result"] = final_kind
    record["exports"] = _exports(case_root)
    record["events"] = all_events
    record["story"] = STORY_PATH.name
    LOG_PATH.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"result={final_kind} elapsed_s={record['elapsed_s']} exports={record['exports']}")
    return 0 if final_kind == "delivered" else 1


if __name__ == "__main__":
    raise SystemExit(main())
