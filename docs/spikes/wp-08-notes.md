# WP-08 start notes

Recorded 2026-09-08.

## Carried constraints

- Failure policy stays in the controller and workspace (architecture section 13). This package adds tests and evidence, not a second retry machine.
- Path checks stay on canonicalize + resolve (architecture section 12). Tools still take logical refs only.
- PNG is a card delivery option inside `build`, not a separate `Phase`. The interruption matrix covers `qa` through `cleanup` plus setup/intake.
- Frozen golden fixtures in `tests/fixtures/golden` are the project-level ST acceptance suite. Ordinary user cases do not import into SillyTavern.
- G-07 (fresh Windows install, representative packaged case) is WP-09. Recorded as an explicit pending-condition, not a pass.
- NFR-003 timing/cost measurement stays WP-09.

## WP-07 observations

- O1 accepted as-is (no extra UI debounce).
- O2 hardened: `sanitize_events` keeps exact `invocation-complete` / `idempotent` and `tool-*:` names with a non-empty suffix.
- O3 hardened: non-UTF-8 README yields no download list instead of raising.
- O4 multi-session `ui-{n}` collision stays a WP-08-out-of-scope plan item; duplicate-operation tests stay single-session.

## Self-contained runtime

`load_local_env()` may read `project/Collaboration/b-ai-development-provider.env` when that sibling file exists. The package still runs from env vars and `.env` alone. No control-plane Python imports.
