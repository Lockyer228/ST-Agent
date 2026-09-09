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
| A | `hy3` (default) | 91.4s | blocked `provider-models-unavailable` (timeout) | `save_brief`, `save_content_document` start/success/failure |
| B | `glm-5.3-flash` | 90.6s | blocked timeout | `invocation-complete` only |
| C | `hy3`, `LIVE_TIMEOUT_S=180` trial | 180.6s | blocked timeout | brief saved; repeated canonical `save_content_document` failures; Chat Completions `reasoningContent` warnings |
| D | `hy3` plus canonical-continue | 367s | runner crash | turn 1 timeout; turn 2 `load_manifest` `WorkspaceError("case manifest is unreadable")` from trailing bytes on `case.json` |
| E | authorized chain, per-model 90s | 356.1s | artifacts written; driver `blocked` `case-closed` | turn 1 `question` (player_role); turn 2 `save_brief` / canonical / `build_*` / `check_official_sources` / `validate_deliverables` / `finish_case` success, then extra calls after close |
| F | `deepseek-v4-flash-0731` continue | 219.6s | delivered | turn 1 90s no tools; turn 2 builds almost finish; turn 3 `finish_case` |
| G | `deepseek-v4-flash-0731`, first turn 25s | 83.5s | delivered | turn 1 `live-timeout`; turn 2 canned canonical continue through `finish_case` |

JSON logs: `wp-09-run-hy3.json`, `wp-09-run-glm.json`, `wp-09-run-hy3-180.json`, `wp-09-run-retry.json`, `wp-09-run-deepseek-continue.json`, `wp-09-run-deepseek-nfr.json`.
Provider probe: `wp-09-provider-probe.md` (the model provider) and `wp-09-provider-probe-deepseek.json`.

Copied closed-case files (no secrets): `wp-09-export-card.json`, `wp-09-export-lorebook.json`, `wp-09-export-card.png`, `wp-09-export-readme.md`.

Attempt E checks: `validate_card` issues empty; PNG `ccv3` reads Mara Ellison with two embedded lorebook entries; case README lists the three export paths.

## NFR-003

Attempt G delivered the expected export set in **83.5s** (`wp-09-run-deepseek-nfr.json`, recorded at `e96bfb4`): PNG card, standalone lorebook, embedded lorebook, closed-case README. That is a historical measurement, not a structural guarantee. Since `5e7cfe7` a live turn has no total duration cap; HTTP connect/write/pool timeouts (15/60/15s) still cover unreachable providers.

## NFR-005

Attempt E shows the real Strands sequence through `build_character_card`, `build_lorebook`, `build_png_card`, `check_official_sources`, `validate_deliverables`, and `finish_case`.

## Streamlit

`uv run streamlit run app.py --server.headless true --server.port 8510` returned HTTP 200. The multi-minute live Send path was not walked in the browser; the driver uses the same controller as Send.

## Honest gap

Attempt E produced live the model provider artifacts in 356.1s and the driver reported `blocked` because `finish_case` closed the case before TurnOutcome. The controller now treats `finish_ok` on a closed case as `delivered` (unit test). NFR-003 is measured on Attempt G, not Attempt E.

`enable_thinking: false` was added after Attempt G. That extra is unit-tested only.
