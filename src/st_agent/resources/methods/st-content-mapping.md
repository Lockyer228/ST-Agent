<!--
Sources (permission: project reference, not copied private prose):
- Approved PRD FR-003 scene-card note; FR-004 content layers (C-025)
- Architecture §8 canonical models (C-029)
- Character Card V3 specification (kwaroran) via reference/official/CARD-SPEC-AUDIT-2026-09.md
- SillyTavern World Info behavior (docs.sillytavern.app) via the same audit
- Neutral mapping distilled from reference/skills:
  st-character-card-engineering, st-scene-card-engineering, st-world-info,
  seraphina-profile_worldbook-entry-architecture, st-worldbook-json-creation
Excluded: private Seraphina preferences, local paths, topic-specific oppression
defaults, unverified context percentages, and “absolute lock” guarantees.
-->

# ST content mapping

Map story meaning onto card and lorebook **roles**. Do not copy a house style, a fixed identity relationship, or a stock opening.

## Character card layers

| Layer | Holds |
| --- | --- |
| Description | Overview of the character or scene |
| Personality / system prompt | Behavior the model should keep |
| Scenario | Where play starts |
| First message | The opening the player sees |
| Example dialogue | Only when a specific speech pattern is required |
| Creator notes | Production notes, not secret plot |
| Alternate greetings / tags | Optional; omit rather than invent a house default |
| Lorebook relationship | How entries attach to this card |

A **scene card** may present several NPCs in one card. Dispatch them by name or a clear address, not by a hidden job title.

## Lorebook

Entries are a dynamic dictionary. Content must be self-contained; titles and keys are not injected as prose.

- **Keyword (selective)** entries load when keys match. Keep trigger scope narrow.
- **Constant** entries stay available. Use them for facts the scene always needs.
- Organize by relevance and how often the fact is needed. Do not promise token percentages.
- Hidden information stays out of constant context until the user asks.

One canonical entry list feeds both standalone and embedded files. Serializers
map canonical `before_char` / `after_char` to SillyTavern numeric `0` / `1`.
Any other position is rejected.

Optional activation settings (probability, scan depth, recursion flags, and
similar vendor fields) are **not** canonical Markdown. They live on the
serializer/overlay: new cases omit them; modify cases keep unknown source
fields through `SourceOverlay`.

## What not to bake in

Do not set default kinks, factions, local disk paths, or unverified format claims. Format envelopes and PNG chunks belong to format profiles, not to this mapping.
