# WP-02 Spike Decision Notes

Recorded 2026-09-06 on Windows from `impl/cursor`. Credentials, keys, and
absolute machine paths are omitted.

## S-01 Strands + Bedrock

**Result: explicit blocker** `bedrock-credentials-missing`

Evidence:

- `boto3.Session().get_credentials()` is `None` (no env keys, no `AWS_PROFILE`,
  no `%USERPROFILE%\.aws`).
- `run_strands_spike()` returns status `blocked` without calling Bedrock.
- SDK path proven in code (not live): `Agent(..., structured_output_model=TurnOutcome)`,
  project-owned `ping_runtime` tool, `BeforeToolCallEvent`/`AfterToolCallEvent`
  hooks, `bound_turns_hook` calling `agent.cancel()`, invocation
  `cancel_signal=threading.Event` documented on Strands 1.54 `Agent.__call__`.
- Default SDK region if unset is `us-west-2` (`BedrockModel.DEFAULT_BEDROCK_REGION`).
  No region is locked until credentials exist.

Bounded replacement: none. A fake model would not satisfy "Bedrock-backed".
Do not expand into WP-06 agent product work.

## S-02 ST format and PNG

**Result: pass** (source + fixture freeze; no local SillyTavern install)

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

**Result: pass** (unit pass + live fetch recorded below)

Allowlist in `source-manifest.json`. Timeouts, size cap, no off-allowlist
redirects. 404 is `unavailable`, not pass.

Live Windows fetch (httpx, no secrets):

| id | status | notes |
| --- | --- | --- |
| `ccv3-spec` | pass | fingerprint `3c472a16eeda…`; markers matched |
| `ccv3-spec-missing` | unavailable | HTTP 404 (not treated as pass) |
| `st-worldinfo` | pass | fingerprint `0e8be0c0c18e…`; markers matched |

## S-04 Demo model

**Result: explicit blocker** same credential gap as S-01.

Candidate remains architecture starting point
`global.anthropic.claude-sonnet-4-6`. Region not selected. Quality, latency,
and demo cost were not measured.

## WP-01 review A/B/C

- A/B: README commit `76a2e4b`.
- C: author `ST-Agent Development <development@st-agent.local>` via process
  env; git config not modified.
