# WP-07 start notes

Recorded 2026-09-07.

## Wiring

- UI calls `create_case`, `resume_case`, `abandon_case`, and `submit_turn` only. No serializers, validators, or official-source clients.
- Phase/condition come from `case.json`. The page does not advance phases.
- Each Send click uses `ui-{n}` as `operation_id`. `idempotent` renders as already processed.
- Chat always goes through `submit_turn` (persist first). Uploads are sniffed with WP-05 readers, then copied by the controller.
- Hook events shown: tool-start/success/failure, invocation-complete, idempotent. No prompts or reasoning.
- Downloads read `04-exports/...` paths listed in the closed README. `read_deliverable` rejects `..` and any path outside `04-exports`.
- `create_case(..., mode=modify)` stores `CaseMode.modify`. The first user turn still uploads the source card; overlay merge stays in WP-06 tools.
- Page flow: Streamlit `AppTest` covers New / Send (injected `TurnOutcome`) / Resume without a live provider call. Live Send is a browser check.

## Registered, not implemented

- Claude leftover observations 1–3 as new behavior.
- WP-02 model-lock expansion; `isascii` as a gate.
- Unique-naming / unknown-fields modification policy (WP-08+).
- WP-08 Recovery/Security/Release Gate and WP-09 release packaging.
