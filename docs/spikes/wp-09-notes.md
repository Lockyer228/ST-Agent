# WP-09 notes

## Scope

Release-candidate packaging: representative original case, live B-AI evidence, English README, architecture diagram aligned to the implemented system, G-07 install record, and AgentCore go/no-go materials. No product-behavior change is required.

## README gaps before this package

The WP-01 README covered purpose, setup, and test commands. It did not name the target creator, summarize architecture, list supported inputs, state limitations, or document generated-file locations and the representative New/Send/Q&A/download path.

## Architecture gap

`docs/TECHNICAL-ARCHITECTURE.md` §2 still described an older module map (`ui/streamlit_app.py`, `agent/runtime.py`). Live code is `st_agent.ui.app`, `st_agent.ui.view`, `st_agent.application.case_controller`, eight tools in `st_agent.application.tools`, plus file-based recovery and hygiene.

## Optional leftovers (register, do not implement)

- O-a: hygiene scan still uses a 220-character window.
- O-b: `sanitize_events` still does not collapse multiline event text.
- Redundant `except UnicodeDecodeError` under `except ValueError` in `load_manifest` (CPython `UnicodeDecodeError` is a `ValueError` subclass).

## Live-run method

## Live-run method

The representative case is driven by `docs/spikes/wp-09-run-case.py` against a temp workspace outside the source tree (the app rejects workspaces inside application source). That uses the same `create_case` / `submit_turn` path as Streamlit Send. Live B-AI delivery of PNG + both lorebooks did not complete; timed attempts and tool events are in `wp-09-case-run.md`. G-07 records a fresh `uv sync --group dev` and Streamlit HTTP 200 on the Windows host.
