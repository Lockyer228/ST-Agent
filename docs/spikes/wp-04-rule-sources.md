# WP-04 rule source map

Recorded 2026-09-06. Private prose, paths, and preferences were not copied
into runtime resources.

| Runtime rule | Informed by | Not copied |
| --- | --- | --- |
| `qa-method.md` one-question stop conditions | PRD FR-003; architecture TurnOutcome | Chat-only approval loop from collaborative-content-workflow |
| `creation-workflow.md` brief → draft → canonical | Architecture §8; PRD FR-004; C-007/C-008 | House review cadence; long-term Q&A archive |
| `st-content-mapping.md` card layers | st-character-card-engineering; CCv3 audit | “No tags / no alternate greetings” as a product default |
| Scene-card multi-NPC dispatch | st-scene-card-engineering; PRD scene-card note | Topic-specific academy/company templates |
| Lorebook keyword vs constant | st-world-info; CARD-SPEC-AUDIT-2026-09 | Unverified 90% context claims; numeric position as creative truth |
| Trigger scope / frequency | worldbook-entry-architecture (neutralized) | Oppression-topic examples; percentage guarantees |
| File ops / PNG | st-character-card-file-operations(-ops/-png) | Deferred to WP-05 serializers |
| JSON from structured entries | st-worldbook-json-creation | JSON as the authoring source (forbidden here) |

Migration checks from `concept/90-INBOX/SKILL-SOURCES.md`:

1. Duplicate file-ops skills and conflicting lorebook field types were not merged; canonical text uses CCv3 string `position`, ST numeric mapping stays in WP-05.
2. Personal taste and local paths were left out of `resources/methods/`.
3. Keyword, context-budget, and lock claims were not turned into product guarantees.
4. Sources are listed in HTML comments on each method file plus this map; lookup is not a publish license for private examples.
5. Runtime reads only `resources/methods/`; reference skills stay outside the product Git tree.
