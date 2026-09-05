# WP-02 Spike Decision Notes

Recorded 2026-09-06 on Windows from `impl/cursor`. Credentials, keys, and
absolute machine paths are omitted.

## Provider decision (2026-09-06)

Development model provider is **B-AI** (OpenAI-compatible
`https://api.b.ai/v1`) via the Strands `OpenAIModel` adapter. Authorized
models, tried in order from the configured start: `hy3`, `mimo-v2.5`,
`glm-5.3-flash`, `qwen3.8-flash`. The former `bedrock-credentials-missing`
blocker is void. API key is read only from `ST_AGENT_API_KEY` (collaboration
env file outside product Git).

## S-01 Strands + B-AI

**Result: pass** on `hy3` (no fallback).

Live invocation (`uv run python`, `run_strands_spike()`):

| Field | Value |
| --- | --- |
| status | `pass` |
| model_id | `hy3` |
| fallback_tried | `hy3` |
| stop_reason | `tool_use` (Strands structured-output tool) |
| events | `tool-start:ping_runtime,tool-end:ping_runtime,tool-start:TurnOutcome,tool-end:TurnOutcome` |
| kind | `blocked` (as instructed; no delivery claimed) |
| elapsed_s | 10.141 |
| tokens | input 1031 / output 167 |
| message | American English; reports `ok:st-agent:spike` |

Cancel / timeout (same helper, no prompt bodies or keys logged):

- `cancel_signal` already set: `stop_reason=cancelled`, elapsed 1.721s, no tool events.
- `timeout_s=0.05` timer setting the same event: `stop_reason=cancelled`, elapsed 2.126s.

Bounded turns: `limits.turns=4` plus `bound_turns_hook(max_tool_turns=2)`.
Streamlit "Run S-01 spike" calls the same `run_strands_spike()`.

Known provider quirk (did not fail the spike): Strands logs
`reasoningContent is not supported in multi-turn conversations with the Chat
Completions API` on the B-AI Chat Completions path.

## S-02 ST format and PNG

**Result: pass** (unchanged by the provider switch).

Inspected:

- CCv3 `SPEC_V3.md` (PNG `ccv3` tEXt, `chara` backfill, lorebook array).
- SillyTavern `release` `src/character-card-parser.js`: write `chara` then
  `ccv3`; read prefers `ccv3`. The file comment claiming ccv3 is unsupported
  is stale relative to the function body.

Frozen profiles:

- `src/st_agent/resources/formats/character-card-v3.json`
- `src/st_agent/resources/formats/st-character-book.json` (entries array)
- `src/st_agent/resources/formats/st-lorebook.json` (uid map)
- `src/st_agent/resources/formats/format-rules.md`

Golden fixtures under `tests/fixtures/golden/`. PNG round-trip and CRC
mismatch tests pass via `PngCardCodec`.

Limitation: fixtures were not imported into a running SillyTavern process.
Architecture allows freezing from current ST source plus round-trip tests;
runtime cases will not repeat ST import.

## S-03 Official sources

**Result: pass** (unchanged by the provider switch).

Allowlist in `source-manifest.json`. Timeouts, size cap, no off-allowlist
redirects. 404 is `unavailable`, not pass.

Live Windows fetch (httpx, no secrets):

| id | status | notes |
| --- | --- | --- |
| `ccv3-spec` | pass | fingerprint `3c472a16eeda…`; markers matched |
| `ccv3-spec-missing` | unavailable | HTTP 404 (not treated as pass) |
| `st-worldinfo` | pass | fingerprint `0e8be0c0c18e…`; markers matched |

## S-04 Demo model

**Result: pass** on `hy3` (no fallback). Representative English case via
`run_model_measurement()`.

| Field | Value |
| --- | --- |
| model_id | `hy3` |
| fallback_tried | `hy3` |
| stop_reason | `tool_use` |
| tool events | `ping_runtime` then `TurnOutcome` |
| kind | `blocked` |
| elapsed_s | 6.126 (within NFR-003 three-minute target) |
| tokens | input 1103 / output 326 |
| english | ASCII / American English tavern-keeper description on-prompt |

Quality: two-sentence NPC sketch stayed on the rain-soaked port / missing-ships
ledger brief; natural American English. Tool reliability: one `ping_runtime`
call and a valid `TurnOutcome`. Latency is acceptable for the local demo.

Estimated demo cost: B-AI public API docs (`docs.b.ai` LLM service API) do not
publish a unit price. Token counts above are the measurable proxy; no key or
account balance was logged.

## WP-01 review A/B/C

- A/B: README commit `76a2e4b`.
- C: author `ST-Agent Development <development@st-agent.local>` via process
  env; git config not modified.
