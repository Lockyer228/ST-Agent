"""Single-page Streamlit product flow. Case files are the authority."""

from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path

import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

from st_agent import __version__
from st_agent.application.case_controller import submit_turn
from st_agent.config import RuntimeSettings
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
    AGENT_WORKING,
    INITIAL_ACTIVITY,
    SEND_BUTTON_LABEL,
    WORKING_SPINNER,
    activity_label,
    activity_outcome_label,
    empty_turn_error,
    list_readme_deliverables,
    next_operation_id,
    preview_upload,
    read_deliverable,
    sanitize_events,
    session_config_error,
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
    st.session_state.setdefault("activity_lines", [])
    st.session_state.setdefault("cfg_provider", "")
    st.session_state.setdefault("cfg_base_url", "")
    st.session_state.setdefault("cfg_model_id", "")
    st.session_state.setdefault("cfg_api_key", "")
    st.session_state.setdefault("turn_form_n", 0)
    st.session_state.setdefault("turn_busy", False)
    st.session_state.setdefault("pending_turn", None)


def _open_case(path: Path) -> None:
    st.session_state.screen = "case"
    st.session_state.case_root = str(path)
    st.session_state.events = []
    st.session_state.outcome_kind = ""
    st.session_state.outcome_message = ""
    st.session_state.outcome_blocker = ""
    st.session_state.idempotent = False
    st.session_state.error = ""
    st.session_state.activity_lines = []
    st.session_state.turn_form_n = int(st.session_state.get("turn_form_n", 0)) + 1
    st.session_state.turn_busy = False
    st.session_state.pending_turn = None


def _connection_sidebar() -> None:
    with st.sidebar:
        st.subheader("OpenAI-compatible connection")
        st.text_input("Provider", key="cfg_provider")
        st.text_input("OpenAI Base URL", key="cfg_base_url")
        st.text_input("Model", key="cfg_model_id")
        st.text_input("API key", key="cfg_api_key", type="password")
        st.caption(
            "OpenAI-compatible Chat Completions only. Do not use an Anthropic URL."
        )
        st.caption(
            "These values stay in this process and are discarded when the app stops."
        )


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
            st.error(str(exc))


def _case_page(case_root: Path) -> None:
    closed = False
    manifest = None
    try:
        manifest = load_manifest(case_root)
    except ClosedCaseError:
        closed = True
    except WorkspaceError as exc:
        st.error(str(exc))
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

    if st.session_state.activity_lines:
        st.subheader("Package progress")
        for line in st.session_state.activity_lines:
            st.write(line)

    events = sanitize_events(list(st.session_state.events))
    if events:
        with st.expander("Technical activity"):
            st.text("\n".join(events))

    busy = bool(st.session_state.turn_busy)
    if busy:
        st.info(AGENT_WORKING)

    if not closed:
        with st.form(f"turn-{st.session_state.turn_form_n}"):
            message = st.text_area("Message", disabled=busy)
            uploads = st.file_uploader(
                "Supported uploads", accept_multiple_files=True, disabled=busy
            )
            sent = st.form_submit_button(SEND_BUTTON_LABEL, disabled=busy)
        if sent and not busy:
            files = list(uploads or [])
            blocked = empty_turn_error(message, len(files))
            if blocked:
                st.session_state.error = blocked
            else:
                cfg_err = session_config_error(
                    st.session_state.cfg_provider,
                    st.session_state.cfg_base_url,
                    st.session_state.cfg_model_id,
                    st.session_state.cfg_api_key,
                )
                if cfg_err:
                    st.session_state.error = cfg_err
                else:
                    st.session_state.pending_turn = {
                        "message": message,
                        "uploads": [(item.name, item.getvalue()) for item in files],
                    }
                    st.session_state.turn_busy = True
            st.rerun()

        pending = st.session_state.pending_turn
        if busy and pending is not None:
            st.session_state.pending_turn = None
            packed = [_Upload(name, data) for name, data in pending["uploads"]]
            try:
                _submit(case_root, pending["message"], packed)
            finally:
                st.session_state.turn_busy = False
            if not st.session_state.error:
                st.session_state.turn_form_n += 1
            st.rerun()

    cols = st.columns(3)
    if cols[0].button("Resume", disabled=busy):
        try:
            plan = resume_case(case_root)
            st.session_state.outcome_kind = ""
            st.session_state.outcome_message = f"Resume: {plan.reason} at phase {plan.phase}."
            st.rerun()
        except (OSError, WorkspaceError) as exc:
            st.session_state.error = str(exc)
            st.rerun()
    if cols[1].button("Abandon", disabled=busy) and not closed:
        try:
            abandon_case(case_root)
            st.rerun()
        except (OSError, WorkspaceError) as exc:
            st.session_state.error = str(exc)
            st.rerun()
    if cols[2].button("New modification", disabled=busy):
        st.session_state.screen = "home"
        st.session_state.error = (
            "Create a modification case, then send the source character card "
            "with your first message."
        )
        st.rerun()

    _downloads(case_root, closed=closed)


class _Upload:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def _submit(case_root: Path, message: str, uploads) -> None:
    st.session_state.error = ""
    blocked = empty_turn_error(message, len(uploads))
    if blocked:
        st.session_state.error = blocked
        return
    cfg_err = session_config_error(
        st.session_state.cfg_provider,
        st.session_state.cfg_base_url,
        st.session_state.cfg_model_id,
        st.session_state.cfg_api_key,
    )
    if cfg_err:
        st.session_state.error = cfg_err
        return
    tmp: Path | None = None
    try:
        manifest = load_manifest(case_root)
        saved: list[Path] = []
        tmp = Path(tempfile.mkdtemp(prefix="st-agent-upload-"))
        for item in uploads:
            data = item.getvalue()
            preview_upload(item.name, data)
            saved.append(write_upload(tmp, item.name, data))
        op_id = next_operation_id(st.session_state)
        started: set[str] = set()
        activity = [INITIAL_ACTIVITY]
        st.session_state.activity_lines = list(activity)
        script_ctx = get_script_run_ctx()

        def sink(event: str) -> None:
            line = activity_label(event, started)
            if not line:
                return
            activity.append(line)
            if script_ctx is not None:
                add_script_run_ctx(threading.current_thread(), script_ctx)
            status.write(line)

        with st.status(INITIAL_ACTIVITY, expanded=True) as status:
            with st.spinner(WORKING_SPINNER):
                outcome, events = submit_turn(
                    case_root,
                    message,
                    uploads=saved,
                    operation_id=op_id,
                    expected_revision=manifest.revision,
                    event_sink=sink,
                    live_settings=RuntimeSettings(
                        provider=st.session_state.cfg_provider.strip(),
                        base_url=st.session_state.cfg_base_url.strip(),
                        model_id=st.session_state.cfg_model_id.strip(),
                    ),
                    live_key=st.session_state.cfg_api_key,
                )
            if len(activity) == 1:
                for event in events:
                    line = activity_label(event, started)
                    if line:
                        activity.append(line)
                        status.write(line)
            final = activity_outcome_label(outcome.kind)
            activity.append(final)
            st.session_state.activity_lines = list(activity)
            status.update(
                label=final,
                state="complete" if outcome.kind in {"delivered", "question"} else "error",
            )
    except (OSError, WorkspaceError) as exc:
        st.session_state.error = str(exc)
        return
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
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
    refs = list_readme_deliverables(readme)
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
    st.set_page_config(page_title="ST-Agent", layout="centered")
    _ensure_state()
    _connection_sidebar()
    provider = str(st.session_state.cfg_provider).strip()
    model_id = str(st.session_state.cfg_model_id).strip()
    st.title("ST-Agent")
    if provider and model_id:
        st.caption(f"Version {__version__} · Provider {provider} · Model {model_id}")
    else:
        st.caption(f"Version {__version__} · Model connection is not configured")
    st.write(
        "This app sends your English story material to a configured model provider "
        "to draft a SillyTavern character card. Treat uploaded files and chat text "
        "as untrusted story content."
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
