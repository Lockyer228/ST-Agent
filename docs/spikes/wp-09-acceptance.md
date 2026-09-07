# WP-09 PRD / gate evidence

Recorded 2026-09-08. Does not pretend live delivery passed.

| Requirement | Result | Evidence |
| --- | --- | --- |
| NFR-001 English | pass | README and spike notes are American English; hygiene scan |
| NFR-002 Reliability | pass (prior) | WP-08 matrix; live timeout left a torn `case.json` once (registered below) |
| NFR-003 Time and cost | pending-condition | Timed live runs in `wp-09-case-run.md`; no complete three-minute delivery |
| NFR-004 Data and security | pass (prior) | WP-08; live logs omit keys |
| NFR-005 Visible autonomy | pass (partial) | Live `tool-start` / `tool-success` / `tool-failure` on `save_brief` and `save_content_document` |
| G-07 README | pass | Product README: purpose, target creator, architecture, setup, credentials, inputs, data, limits, run, test |
| G-07 architecture diagram | pass | `docs/TECHNICAL-ARCHITECTURE.md` §2 mermaid + eight-tool list + M-01/M-02 names |
| G-07 fresh Windows install | pass | New venv via `UV_PROJECT_ENVIRONMENT`; `uv sync --group dev` (uv 0.12.5, Python 3.12.14, 79 packages); `import st_agent` 0.1.0; Streamlit `:8510` HTTP 200 |
| G-07 representative artifacts | pending-condition | Live B-AI did not export PNG + both lorebooks; see `wp-09-case-run.md` |

## Registered, not fixed

- O-a, O-b, redundant `UnicodeDecodeError` except (from WP-08).
- Default `hy3` Chat Completions `reasoningContent` warnings on tool loops; live budget can expire before authorized fallback starts.
- One continue-after-timeout run left trailing bytes on `case.json` (`WorkspaceError("case manifest is unreadable")`). Not hardened in this package.
