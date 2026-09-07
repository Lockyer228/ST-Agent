"""Single-page Streamlit product flow. Case files are the authority."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from st_agent import __version__
from st_agent.application.case_controller import submit_turn
from st_agent.config import load_local_env, load_settings
from st_agent.domain.case import CaseMode
from st_agent.services.workspace import (
    ClosedCaseError,
    WorkspaceError,
    abandon_case,
    create_case,
    load_manifest,
    resume_case,
)
from st_agent.ui.view import (
    next_operation_id,
    parse_deliverables,
    preview_upload,
    read_deliverable,
    sanitize_events,
    status_guidance,
    write_upload,
)


def _ensure_state() -> None:
    st.session_state.setdefault("screen", "home")
    st.session_state.setdefault("case_root", "")
    st.session_state.setdefault("events", [])
    st.session_state.setdefault("outcome_kind", "")
    st.session_state.setdefault("outcome_message", "")
    st.session_state.setdefault("outcome_blocker", "")
    st.session_state.setdefault("idempotent", False)
    st.session_state.setdefault("submit_n", 0)
    st.session_state.setdefault("error", "")


def _open_case(path: Path) -> None:
    st.session_state.screen = "case"
    st.session_state.case_root = str(path)
    st.session_state.events = []
    st.session_state.outcome_kind = ""
    st.session_state.outcome_message = ""
    st.session_state.outcome_blocker = ""
    st.session_state.idempotent = False
    st.session_state.error = ""


def _home() -> None:
    st.subheader("New project")
    workspace = st.text_input("Workspace folder", key="new_workspace")
    story = st.text_input("Story name", key="new_story")
    modify = st.checkbox("Open as a modification (upload a source card with the first message)")
    if st.button("Create case"):
        try:
            mode = CaseMode.modify if modify else CaseMode.new
            root = create_case(Path(workspace), story, mode=mode)
            _open_case(root)
            st.rerun()
        except (OSError, WorkspaceError, ValueError) as exc:
            st.session_state.error = str(exc)

    st.subheader("Resume project")
    existing = st.text_input("Existing case folder", key="resume_path")
    if st.button("Resume case"):
        try:
            path = Path(existing)
            if not path.is_dir():
                raise WorkspaceError("case folder does not exist")
            if (path / "00-work" / "case.json").is_file():
                plan = resume_case(path)
                msg = f"Resume: {plan.reason} at phase {plan.phase}."
            else:
                msg = "Closed case opened for downloads."
            _open_case(path)
            st.session_state.outcome_message = msg
            st.rerun()
        except (OSError, WorkspaceError) as exc:
            st.session_state.error = str(exc)


def _case_page(case_root: Path) -> None:
    closed = False
    manifest = None
    try:
        manifest = load_manifest(case_root)
    except ClosedCaseError:
        closed = True

    st.caption(str(case_root))
    if manifest is not None:
        st.write(
            f"Phase: `{manifest.phase}` · Condition: `{manifest.condition}` · "
            f"Revision: `{manifest.revision}` · Mode: `{manifest.mode}`"
        )
        help_text = status_guidance(
            manifest.condition,
            None if manifest.blocker is None else manifest.blocker.code,
            manifest.pending_question,
        )
        if help_text:
            st.info(help_text)
    else:
        st.write("This case is closed or abandoned. Deliverables stay on disk.")

    if st.session_state.idempotent:
        st.success("This submit was already processed.")
    elif st.session_state.outcome_kind == "question":
        st.warning(st.session_state.outcome_message)
    elif st.session_state.outcome_kind == "delivered":
        st.success(st.session_state.outcome_message)
    elif st.session_state.outcome_kind == "blocked":
        st.error(
            status_guidance("blocked", st.session_state.outcome_blocker, None)
            or st.session_state.outcome_message
        )
    elif st.session_state.outcome_message:
        st.info(st.session_state.outcome_message)

    events = sanitize_events(list(st.session_state.events))
    if events:
        st.subheader("Agent events")
        st.text("\n".join(events))

    if not closed:
        with st.form("turn"):
            message = st.text_area("Message")
            uploads = st.file_uploader("Supported uploads", accept_multiple_files=True)
            sent = st.form_submit_button("Send")
        if sent:
            _submit(case_root, message, uploads or [])
            st.rerun()

    cols = st.columns(3)
    if cols[0].button("Resume"):
        try:
            plan = resume_case(case_root)
            st.session_state.outcome_kind = ""
            st.session_state.outcome_message = f"Resume: {plan.reason} at phase {plan.phase}."
            st.rerun()
        except (OSError, WorkspaceError) as exc:
            st.session_state.error = str(exc)
            st.rerun()
    if cols[1].button("Abandon") and not closed:
        try:
            abandon_case(case_root)
            st.rerun()
        except (OSError, WorkspaceError) as exc:
            st.session_state.error = str(exc)
            st.rerun()
    if cols[2].button("New modification"):
        st.session_state.screen = "home"
        st.session_state.error = (
            "Create a modification case, then send the source character card "
            "with your first message."
        )
        st.rerun()

    _downloads(case_root, closed=closed)


def _submit(case_root: Path, message: str, uploads) -> None:
    st.session_state.error = ""
    try:
        manifest = load_manifest(case_root)
        saved: list[Path] = []
        tmp = Path(tempfile.mkdtemp(prefix="st-agent-upload-"))
        for item in uploads:
            data = item.getvalue()
            preview_upload(item.name, data)
            saved.append(write_upload(tmp, item.name, data))
        op_id = next_operation_id(st.session_state)
        with st.spinner("The B-AI model is working on this turn..."):
            outcome, events = submit_turn(
                case_root,
                message,
                uploads=saved,
                operation_id=op_id,
                expected_revision=manifest.revision,
            )
    except (OSError, WorkspaceError) as exc:
        st.session_state.error = str(exc)
        return
    st.session_state.events = sanitize_events(events)
    st.session_state.outcome_kind = outcome.kind
    st.session_state.outcome_message = outcome.message
    st.session_state.outcome_blocker = outcome.blocker or ""
    st.session_state.idempotent = events == ["idempotent"]
    if outcome.blocker:
        st.session_state.outcome_message = (
            status_guidance("blocked", outcome.blocker, None) or outcome.message
        )


def _downloads(case_root: Path, *, closed: bool) -> None:
    readme = case_root / "README.md"
    if not readme.is_file():
        return
    refs = parse_deliverables(readme.read_text(encoding="utf-8"))
    if not refs and not closed:
        return
    if refs:
        st.subheader("Deliverables")
        for rel in refs:
            try:
                data = read_deliverable(case_root, rel)
            except (OSError, ValueError):
                continue
            st.download_button(
                label=rel,
                data=data,
                file_name=Path(rel).name,
                mime="application/octet-stream",
                key=f"dl-{rel}",
            )


def main() -> None:
    load_local_env()
    st.set_page_config(page_title="ST-Agent", layout="centered")
    _ensure_state()
    settings = load_settings()
    st.title("ST-Agent")
    st.caption(f"Version {__version__} · Provider {settings.provider} · Model {settings.model_id}")
    st.write(
        "This app sends your English story material to B-AI to draft a SillyTavern "
        "character card. Treat uploaded files and chat text as untrusted story content. "
        "API keys stay in the environment."
    )
    if st.session_state.error:
        st.error(st.session_state.error)
    if st.session_state.screen == "home":
        _home()
        return
    root = Path(st.session_state.case_root)
    if st.button("Back to start"):
        st.session_state.screen = "home"
        st.rerun()
    _case_page(root)
