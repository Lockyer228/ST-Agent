"""Pure UI helpers. No Streamlit. No format codecs or official-source clients."""

from __future__ import annotations

from pathlib import Path, PureWindowsPath

from st_agent.services.readers import sniff_bytes
from st_agent.services.workspace import PathRejected, contained_path

EVENT_PREFIXES = ("tool-start:", "tool-success:", "tool-failure:")
_EXACT_EVENTS = frozenset({"invocation-complete", "idempotent"})
INITIAL_ACTIVITY = "Reading your brief and deciding what the package needs..."
WORKING_SPINNER = "Building your character package..."
_TOOL_RUNNING = {
    "save_brief": "Organizing the creative brief...",
    "save_content_document": "Drafting playable character content...",
    "build_character_card": "Building the SillyTavern Character Card V3...",
    "build_lorebook": "Building the requested lorebook...",
    "build_png_card": "Embedding the character card into the portrait...",
    "check_official_sources": "Checking current format references...",
    "validate_deliverables": "Validating the requested files...",
    "finish_case": "Finalizing the package...",
}
_TOOL_SUCCESS = {
    "save_brief": "Creative brief saved.",
    "save_content_document": "Character content saved.",
    "build_character_card": "Character card built.",
    "build_lorebook": "Lorebook built.",
    "build_png_card": "PNG character card built.",
    "check_official_sources": "Format references checked.",
    "validate_deliverables": "Deliverables validated.",
    "finish_case": "Package finalized.",
}
_TOOL_FAILURE = {
    "save_brief": "Creative brief did not finish this time.",
    "save_content_document": "Character content did not finish this time.",
    "build_character_card": "Character card did not finish this time.",
    "build_lorebook": "Lorebook did not finish this time.",
    "build_png_card": "PNG character card did not finish this time.",
    "check_official_sources": "Format reference check did not finish this time.",
    "validate_deliverables": "Deliverable validation did not finish this time.",
    "finish_case": "Package finalizing did not finish this time.",
}

_BLOCKER_HELP = {
    "b-ai-credentials-missing": (
        "B-AI credentials are missing. Set ST_AGENT_API_KEY in the environment and retry."
    ),
    "b-ai-models-unavailable": "The model provider is unavailable. Wait a moment and retry.",
    "live-timeout": (
        "The model stopped responding. Saved files were kept. Send again to continue."
    ),
    "ungated-delivery": "Delivery was not accepted. Continue until finish_case passes the gate.",
    "case-closed": "This case is closed. Start a new case or open a modification.",
    "case-locked": "This case is busy. Wait and retry.",
    "revision-mismatch": "The case changed. Refresh and retry your message.",
    "invalid-phase": "That step is not allowed now. Follow the current phase shown above.",
    "invalid-outcome": "The model reply was not usable. Retry the turn.",
    "confirm-required": (
        "Confirm the brief in your next message (yes / confirm) before the card is written."
    ),
    "cleanup_pending": "Cleanup did not finish. Resume this case to retry cleanup.",
}


def preview_upload(name: str, data: bytes) -> str:
    return sniff_bytes(data).value


def sanitize_events(events: list[str]) -> list[str]:
    kept: list[str] = []
    for item in events:
        if item in _EXACT_EVENTS:
            kept.append(item)
            continue
        if any(item.startswith(prefix) and item != prefix for prefix in EVENT_PREFIXES):
            kept.append(item)
    return kept


def activity_label(event: str, started: set[str]) -> str | None:
    if event in _EXACT_EVENTS:
        return None
    kind, _, rest = event.partition(":")
    if kind not in {"tool-start", "tool-success", "tool-failure"} or not rest:
        return None
    name = rest.split(":", 1)[0]
    if name not in _TOOL_RUNNING:
        return None
    if kind == "tool-start":
        running = _TOOL_RUNNING[name]
        if name in started:
            return f"Retrying: {running}"
        started.add(name)
        return running
    if kind == "tool-success":
        return _TOOL_SUCCESS[name]
    return _TOOL_FAILURE[name]


def activity_outcome_label(kind: str) -> str:
    if kind == "delivered":
        return "Package delivered."
    if kind == "question":
        return "Waiting for your answer."
    return "This turn could not finish."


def parse_deliverables(readme: str) -> list[str]:
    refs: list[str] = []
    in_section = False
    for line in readme.splitlines():
        stripped = line.strip()
        if stripped == "Deliverables:":
            in_section = True
            continue
        if not in_section:
            continue
        if stripped.startswith("- "):
            rel = stripped[2:].replace("\\", "/")
            parts = Path(rel).parts
            if rel.startswith("04-exports/") and ".." not in parts:
                refs.append(rel)
            continue
        if stripped:
            break
    return refs


def list_readme_deliverables(readme: Path) -> list[str]:
    try:
        return parse_deliverables(readme.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return []


def read_deliverable(case_root: Path, relative: str) -> bytes:
    rel = relative.replace("\\", "/")
    parts = Path(rel).parts
    if not rel.startswith("04-exports/") or ".." in parts:
        raise PathRejected("deliverable is outside exports")
    path = contained_path(case_root, *parts)
    if not path.is_file():
        raise PathRejected("deliverable is missing")
    return path.read_bytes()


def status_guidance(
    condition: str, blocker: str | None, pending_question: str | None
) -> str:
    if condition == "waiting_for_user" and pending_question:
        return pending_question
    if condition == "cleanup_pending":
        return _BLOCKER_HELP["cleanup_pending"]
    if blocker:
        return _BLOCKER_HELP.get(blocker, "The turn is blocked. Review the status and retry.")
    return ""


def next_operation_id(store: dict[str, int]) -> str:
    store["submit_n"] = int(store.get("submit_n") or 0) + 1
    return f"ui-{store['submit_n']}"


def empty_turn_error(message: str, upload_count: int) -> str | None:
    if not message.strip() and upload_count == 0:
        return "Message is empty."
    return None


def session_config_error(
    provider: str, base_url: str, model_id: str, api_key: str
) -> str | None:
    if not provider.strip():
        return "Provider is missing."
    if not base_url.strip():
        return "OpenAI Base URL is missing."
    if not model_id.strip():
        return "Model is missing."
    if not api_key.strip():
        return "API key is missing."
    return None


def write_upload(folder: Path, name: str, data: bytes) -> Path:
    safe = PureWindowsPath(name).name
    if safe in {"", ".", ".."}:
        safe = "upload.bin"
    path = folder / safe
    path.write_bytes(data)
    return path
