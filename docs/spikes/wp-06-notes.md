# WP-06 start notes

Recorded 2026-09-06. Spike `reasoningContent` warnings and `stop_reason=tool_use` are not the runtime contract.

## Wiring decisions

- **WP-03 A**: upload budget uses `manifest.inputs`, not directory rglob.
- **WP-03 B**: `00-work/inputs.md` lists files; `intake.md` is the Q&A log (`append_intake`).
- **WP-03 D**: `status.md` lists manifest file paths.
- **WP-03 E**: `apply_input_change` lives in `domain.case`; workspace does not import `application`.
- **WP-03 F**: `Lineage.source_path` is the direct upstream; resume hashes that file.
- **WP-04 A / WP-05 6c**: heading-style field lines render as `\## Title` and round-trip. Unescaped headings stay a repairable error.
- **WP-05 6a**: `optional_activation` cannot set `position`.
- **WP-05 6b**: overlay extraction drops `data.character_book`; lorebook comes from canonical entries only.
- **WP-02 follow-up**: model-lock expansion stays an explicit todo. Live invoke uses the authorized chain with a 90s wall budget. `isascii` is not a runtime gate. Live invalid TurnOutcome falls through to the next authorized model; same-model repair is covered by the fake-model suite.
- **Duplicate submit**: `last-operation.json` at the case root, keyed by operation ID.
- **Imported prompts**: user text is wrapped in `<untrusted-user-content>` and cannot add tools.
