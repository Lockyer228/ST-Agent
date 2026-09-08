# WP-09 PRD / gate evidence

Recorded 2026-09-08. Live artifact set exists. Three-minute target met on Alibaba-Token.

| Requirement | Result | Evidence |
| --- | --- | --- |
| NFR-001 English | pass | README and spike notes are American English; hygiene scan |
| NFR-002 Reliability | pass | WP-08 matrix; `load_manifest` recovers trailing bytes / `.bak`; per-model live timeout |
| NFR-003 Time and cost | pass | Alibaba-Token `deepseek-v4-flash-0731` delivered in 83.5s (`wp-09-run-deepseek-nfr.json`) |
| NFR-004 Data and security | pass (prior) | WP-08; live logs omit keys |
| NFR-005 Visible autonomy | pass | Live `build_*` / `check_official_sources` / `validate_deliverables` / `finish_case` in `wp-09-run-retry.json` |
| G-07 README | pass | Product README: purpose, target creator, architecture, setup, credentials, inputs, data, limits, run, test |
| G-07 architecture diagram | pass | `docs/TECHNICAL-ARCHITECTURE.md` §2 mermaid + eight-tool list + M-01/M-02 names |
| G-07 fresh Windows install | pass | New venv via `UV_PROJECT_ENVIRONMENT`; `uv sync --group dev` (uv 0.12.5, Python 3.12.14, 79 packages); `import st_agent` 0.1.0; Streamlit `:8510` HTTP 200 |
| G-07 representative artifacts | pass | Live PNG + standalone lorebook + embedded lorebook + closed-case README; copies in `wp-09-export-*` |

## Registered, not fixed

- O-a, O-b, redundant `UnicodeDecodeError` except (from WP-08).
- Chat Completions `reasoningContent` warnings on tool loops (Strands strips the field; log-level; not fatal).
- `enable_thinking: false` is wired on the live OpenAI client. The 83.5s NFR-003 run happened before that extra; it is unit-tested only.
