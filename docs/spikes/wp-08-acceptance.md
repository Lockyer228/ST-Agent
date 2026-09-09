# WP-08 PRD acceptance evidence

Recorded 2026-09-08. Rows are product-source tests unless noted.

| Requirement | Result | Evidence |
| --- | --- | --- |
| FR-001 Input files | pass | `tests/test_readers.py`, `tests/test_workspace.py` limits, `tests/test_wp07_ui.py` GIF/path |
| FR-002 Workspace and recovery | pass | `tests/test_recovery_matrix.py`, `tests/test_workspace.py` resume/lock/tmp |
| FR-003 Q&A and defaults | pass | `tests/test_wp06_integration.py` question then resume; WP-07 AppTest |
| FR-004 Creation method | pass | `tests/test_content_fixtures.py`, `tests/test_canonical.py` |
| FR-005 Rule assets | pass | `tests/test_rule_resources.py`; English methods under `src/st_agent/resources/methods/` |
| FR-006 Card and lorebook | pass | `tests/test_golden_wp05.py`, serializers/validators |
| FR-007 PNG | pass | `tests/test_png_card.py`, golden PNG path in WP-05 |
| FR-008 Official check | pass | `tests/test_official_sources.py` pass/unavailable/inconclusive; WP-06 official-fail stays in build |
| FR-009 Streamlit | pass | `tests/test_wp07_ui.py` AppTest + live Send evidence in WP-07 notes |
| FR-010 Lifecycle | pass | WP-06 finish/abandon/cleanup_pending; `tests/test_wp06_review.py` |
| NFR-001 English | pass | hygiene scan in `tests/test_wp08_gate.py`; product files have no Han |
| NFR-002 Reliability | pass | atomic write, op-id idempotent, lineage stale; clean-install is G-07/WP-09 |
| NFR-003 Time and cost | pending-condition | WP-09 representative timed run |
| NFR-004 Data and security | pass | path/symlink tests, wrap_user_content, log/hygiene scan |
| NFR-005 Visible autonomy | pass | WP-06/WP-07 tool events |
| BR-001 Intent gate | pass | finish_case delivery checks |
| BR-002 No repeated Q&A | pass | WP-04/WP-06 fixtures |
| BR-003 JSON default | pass | brief/delivery defaults |
| BR-004 Lorebook selection | pass | golden none/standalone/embedded/both |
| BR-005 Agent autonomy | pass | fake-model happy path without extra approval tools |
| BR-006 Delivery boundary | pass | close_case after gated finish |
| BR-007 No cross-case memory | pass | close drops Q&A; new case empty intake |
| BR-008 Imported prompt safety | pass | `wrap_user_content` in WP-06; `tests/test_wp08_gate.py` |
| BR-009 Project-level ST tests | pass | frozen golden suite; not run per user case |
| BR-010 American English | pass | hygiene scan; release README polish is WP-09 |
| G-01 Runtime | pass (prior) | WP-02 provider S-01/S-04; smoke skips without key |
| G-02 Format | pass (prior) | WP-02/WP-05 profiles |
| G-03 Source | pass | official-source pass and unavailable |
| G-04 Domain | pass | domain/workspace/canonical tests |
| G-05 Agent | pass | fake-model + live smoke when key present |
| G-06 Product | pass | this package: matrix + security + hygiene |
| G-07 Release | pending-condition | WP-09 clean Windows install and representative packaged case |
