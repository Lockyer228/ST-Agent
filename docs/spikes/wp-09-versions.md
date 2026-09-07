# WP-09 supported versions and generated-file layout

Recorded for the release-candidate package. Fill run timing in `wp-09-run-log.json` after the live case.

## Runtime

| Item | Value |
| --- | --- |
| Language | Python `==3.12.*` (`requires-python = ">=3.12,<3.13"`) |
| Lock | `uv.lock` (exact pins) |
| `strands-agents` | 1.54.0 (`openai` extra) |
| `streamlit` | 1.63.0 |
| `pydantic` | 2.13.5 |
| `pillow` | 12.3.0 |
| `httpx` | 0.28.1 |
| `pytest` | 9.1.1 |
| `ruff` | 0.16.6 |

## Model configuration

| Item | Value |
| --- | --- |
| Provider | B-AI |
| Base URL | `https://api.b.ai/v1` |
| Preferred model | `hy3` (`ST_AGENT_MODEL_ID`) |
| Authorized fallback chain | `hy3` → `mimo-v2.5` → `glm-5.3-flash` → `qwen3.8-flash` |
| Live turn bound | `LIVE_TIMEOUT_S = 90` per `submit_turn`; provider retries = 1 |

API keys stay in the environment. They are not recorded here.

## Case layout

```text
<workspace>/<story>/
  README.md
  00-work/case.json          recoverable state
  00-work/status.md          generated from the manifest
  00-work/intake.md
  00-work/brief.md
  00-work/build/             failed builds stay here until validators pass
  01-assets/portraits/
  02-drafts/
  03-final-text/canonical.md
  04-exports/character-cards/card.json
  04-exports/png-cards/card.png
  04-exports/lorebooks/lorebook.json
```

Closed README `Deliverables:` entries are the only download paths the UI serves.

## Known limitations

See README Limitations. Optional leftovers O-a / O-b and the redundant `UnicodeDecodeError` except in `load_manifest` stay registered, not fixed, in this package.
