# WP-05 start notes

Recorded 2026-09-06. Private reference prose was not copied.

## Reuse from WP-02

- `formats.py` profile loader + `_deep_merge` for modifications.
- `png_card.PngCardCodec` (`chara` + `ccv3`, CRC, read prefers `ccv3`).
- `official_sources.OfficialSourceService` allowlist fetch.
- Golden JSON under `tests/fixtures/golden/`.
- `format-rules.md` and `source-manifest.json` reviewed in this package.

## Carried constraints

- C: damaged images become `UnsupportedInput` English text, never a bare PIL error.
- D: lorebook `position` only `before_char` / `after_char`; ST numeric map is 0 / 1.
- E: `optional_activation` is overlay/serializer-only; canonical Markdown does not grow an activation block.
- F: overlay merge uses the same deep merge as card modification.
- A: this package does not add heading-escape to canonical Markdown (left for WP-06 if needed).
- `ccv3-spec-missing` stays in the manifest as an unavailable-path fixture (`role=unavailable-fixture`); production checks skip it. `st-worldinfo` remains the target-application source.
