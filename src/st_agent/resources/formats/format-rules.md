# Reviewed format rules

Reviewed 2026-09-06 against Character Card V3 `SPEC_V3.md` and SillyTavern
`release` `src/character-card-parser.js`. Local SillyTavern was not installed;
source inspection plus JSON/PNG round-trip is the freeze. Runtime cases will
not repeat a SillyTavern import.

## Supported structures

- New cards: `spec=chara_card_v3`, `spec_version=3.0`, CCv3 `data` fields.
- Embedded character book: CCv3 lorebook with `entries` as an **array**.
- Standalone SillyTavern World Info: `entries` as a **uid-keyed object**.
- Serializers use these two profiles. One blended schema is rejected.

## Defaults and identity

- Required CCv3 `data` fields are filled with empty strings, empty lists, or
  `{}` when the canonical model has no value (`post_history_instructions`,
  `group_only_greetings`, `creator`, `extensions`).
- Lorebook entry identity is `entry_id` (numeric ids stay as uid; others hash
  stably). `enabled`, `insertion_order`, keys, and content are required.
- Canonical `position` is `before_char` or `after_char`. Standalone ST numeric
  map is `0` / `1`. Any other position is a repairable serializer error.
- `optional_activation` is overlay/serializer-only. Canonical Markdown has no
  activation block. New cases leave it empty; modify flows keep vendor settings
  in overlay unknown fields / entry `extensions`. `position` is never taken
  from `optional_activation`; canonical `before_char`/`after_char` remains the
  only allowed value.
- Modification overlay extraction copies unknown source fields but **drops**
  `data.character_book`. Lorebook presence comes only from canonical entries.
  Heading-style lines in canonical field text are escaped with a leading
  backslash (`\## Title`) so round-trip stays lossless. Unescaped headings in
  a loaded file remain a repairable error.

## PNG transport

- Write both `chara` and `ccv3` tEXt chunks (base64 of UTF-8 JSON).
- Read prefers `ccv3`, then `chara`.
- Verify per-chunk CRC32. A CRC failure is not a valid card.
- A PNG without those chunks is a portrait, not a character card.
- Portraits: PNG/JPEG/WebP/BMP; apply EXIF orientation; convert non-RGB(A)
  modes; keep pixel size; write PNG.

## Validation

Failed builds stay in `00-work/build/` and are not copied to `04-exports/`.
Validators return repairable English issues for card envelope, lorebook shape,
requested delivery, lineage hashes, and PNG semantic read-back.

## Current source references

- Format specification: Character Card V3 `SPEC_V3.md` (`ccv3-spec`).
- Target application: SillyTavern World Info docs (`st-worldinfo`).
- `ccv3-spec-missing` is an unavailable-path fixture, not a production source.
