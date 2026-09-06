<!--
Sources (permission: project reference, not copied private prose):
- Approved PRD FR-004 / BR-001 / BR-005 (C-025)
- Architecture §8 content pipeline (C-029)
- Decisions C-007 / C-008 (no inherited review cadence; no long-term Q&A archive)
- Neutral workflow distilled from reference/skills st-character-card-engineering
  and seraphina-creative_collaborative-content-workflow (file-first, not chat-first)
-->

# Creation workflow

Creative work is autonomous after intent is clear. Do not inherit an old review cadence that waits for chat approval before writing files.

## Pipeline

1. Save intake in the case workspace.
2. Write a `CaseBrief` covering experience, player role, people, world, tone, mechanics, reveals, opening, authorization, and delivery.
3. Write draft Markdown the user can read.
4. Render **canonical final Markdown** from typed content, parse it back, and only then allow JSON or PNG serialization.
5. Keep one lorebook entry set for standalone and embedded outputs.

JSON is a serializer input, not the creative source.

## When to return to Q&A

Return only for a material gap: intent, authorization, or a required dependency. Ordinary prose, packing fields, and format details are agent work (BR-005).

## Modification

Treat modification as a new case. Update canonical text first. Preserve unrelated unknown source fields in `SourceOverlay`; do not rewrite them as new story prose.

## Unsupported requests

If the user asks for a live mechanism this product does not run (for example a full tabletop combat engine), record the gap in the brief and continue the story. Do not fake the missing system.
