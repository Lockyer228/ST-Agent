"""Pure UI helpers. No Streamlit. No format codecs or official-source clients."""

from __future__ import annotations

from pathlib import Path, PureWindowsPath

from st_agent.services.readers import sniff_bytes
from st_agent.services.workspace import PathRejected, contained_path

EVENT_PREFIXES = ("tool-start:", "tool-success:", "tool-failure:", "invocation-complete")

_BLOCKER_HELP = {
    "b-ai-credentials-missing": (
        "B-AI credentials are missing. Set ST_AGENT_API_KEY in the environment and retry."
    ),
    "b-ai-models-unavailable": "The model provider is unavailable. Wait a moment and retry.",
    "ungated-delivery": "Delivery was not accepted. Continue until finish_case passes the gate.",
    "case-closed": "This case is closed. Start a new case or open a modification.",
    "case-locked": "This case is busy. Wait and retry.",
    "revision-mismatch": "The case changed. Refresh and retry your message.",
    "invalid-phase": "That step is not allowed now. Follow the current phase shown above.",
    "invalid-outcome": "The model reply was not usable. Retry the turn.",
    "provider": "The model provider failed. Retry the turn.",
    "cleanup_pending": "Cleanup did not finish. Resume this case to retry cleanup.",
}


def preview_upload(name: str, data: bytes) -> str:
    return sniff_bytes(data).value


def sanitize_events(events: list[str]) -> list[str]:
    kept: list[str] = []
    for item in events:
        if item == "idempotent" or item.startswith(EVENT_PREFIXES):
            kept.append(item)
    return kept


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


def write_upload(folder: Path, name: str, data: bytes) -> Path:
    safe = PureWindowsPath(name).name
    if safe in {"", ".", ".."}:
        safe = "upload.bin"
    path = folder / safe
    path.write_bytes(data)
    return path
