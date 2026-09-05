# Frozen format rules (WP-02 / S-02)

Inspected 2026-09-06 against Character Card V3 `SPEC_V3.md` and SillyTavern
`release` `src/character-card-parser.js`. Local SillyTavern was not installed;
source inspection plus JSON/PNG round-trip is the freeze. Runtime cases will
not repeat a SillyTavern import.

## PNG chunks

- Write both `chara` and `ccv3` tEXt chunks (base64 of UTF-8 JSON).
- Read prefers `ccv3`, then `chara`.
- Verify per-chunk CRC32. Do not treat a CRC failure as a valid card.
- The stale comment in ST's parser ("ccv3 is not supported") does not match
  the current `write()` body, which does emit `ccv3`.

## Character card JSON

- New cards: `spec=chara_card_v3`, `spec_version=3.0`, CCv3 `data` fields.
- Modifications: deep-merge updates; preserve unknown top-level keys and
  `data.extensions` values. Do not blend unknown fields into authored prose.

## Lorebooks

- Embedded character book: CCv3 `Lorebook` with `entries` as an **array**.
- Standalone SillyTavern World Info: `entries` as a **uid-keyed object** with
  ST fields (`key`, `order`, `constant`, ...).
- Serializers must use these two profiles. One blended schema is rejected.
