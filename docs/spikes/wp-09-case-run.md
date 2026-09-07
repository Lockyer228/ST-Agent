# WP-09 representative case run

Recorded 2026-09-08 on the Windows implementation host. No API keys.

## Input

- Story: `docs/spikes/wp-09-case-input.md`
- Canonical continue sample: `docs/spikes/wp-09-canonical.md` (round-trip tested)
- Portrait: `docs/spikes/wp-09-portrait.png` (64x64 PNG)
- Driver: `docs/spikes/wp-09-run-case.py` (`create_case` / `submit_turn`, same path as Streamlit Send)
- Workspace: process temp dir (not inside application source)

## Expected artifacts

- `04-exports/character-cards/card.json`
- `04-exports/png-cards/card.png`
- `04-exports/lorebooks/lorebook.json`
- Embedded lorebook on the card
- Case README Deliverables list

## Live attempts

| Attempt | Model | Wall clock | Result | Tool events |
| --- | --- | --- | --- | --- |
| A | `hy3` (default) | 91.4s | blocked `b-ai-models-unavailable` (timeout) | `save_brief`, `save_content_document` start/success/failure |
| B | `glm-5.3-flash` | 90.6s | blocked timeout | `invocation-complete` only |
| C | `hy3`, `LIVE_TIMEOUT_S=180` trial | 180.6s | blocked timeout | brief saved; repeated canonical `save_content_document` failures; Chat Completions `reasoningContent` warnings |
| D | `hy3` plus canonical-continue | 367s | runner crash | turn 1 timeout; turn 2 `load_manifest` `WorkspaceError("case manifest is unreadable")` from trailing bytes on `case.json` |

JSON logs: `wp-09-run-hy3.json`, `wp-09-run-glm.json`, `wp-09-run-hy3-180.json`.

## NFR-003

Timed live invocations exist. None produced the expected export set inside three minutes. A complete PNG + both-lorebook delivery on default `hy3` did not finish before the 90s live budget. This row is **pending-condition**, not a pass.

## NFR-005

Attempt A and C show real Strands tool-start/success/failure events (`save_brief`, `save_content_document`). That visibility is recorded. Downstream `build_*` / `finish_case` did not run on the live path.

## Streamlit

`uv run streamlit run app.py --server.headless true --server.port 8510` returned HTTP 200. The multi-minute live Send path was not walked in the browser; the driver uses the same controller as Send.

## Honest gap

Expected PNG + lorebook files were **not** produced by a live B-AI run. Format/PNG/lorebook construction remains covered by frozen golden tests and fake-model integration, not by this packaged live case.
