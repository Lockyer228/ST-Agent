<!--
Sources (permission: project reference, not copied private prose):
- Approved PRD FR-003 / BR-001 / BR-002 / BR-003 (C-025)
- Architecture §5 step 5/7 and §7 TurnOutcome question (C-029)
- Neutral method distilled from reference/skills collaborative-content-workflow
  (chat-approval loop rejected: C-007/C-008 — persist to case files)
-->

# Q&A method

Ask only what is still missing. Existing answers, uploads, and corrections stay in force.
Do not ask the user to paste the rest of a story already stored in intake. An omitted-marker clip is a context limit, not a cutoff.

## One question

Each turn may ask **one** highest-value question. Do not stack topics. Do not repeat a topic the user already answered.

Use `TurnOutcome.kind=question` with a single `question` string. The controller keeps at most one active question.

## Stop conditions

Stop Q&A when all of the following are clear enough to make:

- the core experience the user wants
- creative authorization and content boundaries that would change the work
- required dependencies for the requested delivery (for example a portrait when PNG was requested)

Ordinary names, weather, and technical packing are not stop conditions.

## Delivery defaults

If card format is unanswered, continue with **JSON**. If a portrait is already bound, deliver **both JSON and PNG** unless the user asked for JSON only. A later format choice replaces an earlier one.

An uploaded image is a portrait, not a finished PNG character card. If PNG is requested and the image is missing, keep writing text and ask only for the image.

If exactly one plain portrait is already bound on the case, use it. Do not ask the user to choose among files.

## Confirm before writing

When the stop conditions are met, summarize the brief and ask the user to reply `yes` or `confirm`. Set `TurnOutcome.confirm=true`. Do not call `save_brief` or later tools until case context `build_confirmed` is true.

## Persistence

Save the answer in case files before the next model or downstream step. Do not keep a private chat-only approval loop, and do not store Q&A as long-term memory across cases.
