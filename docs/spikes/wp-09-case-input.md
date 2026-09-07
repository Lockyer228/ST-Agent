# WP-09 representative case input

Original American-English story. Not copied from prior smoke fixtures.

## Story

Reedwick keeps its channel markers lit because the fog never fully lifts. Mara Ellison is the last lampwright who still walks the jetty after midnight. She carries a brass wind-key, a ledger of drowned names, and a habit of answering questions with the tide tables instead of comfort.

Last winter a packet boat named *Cinderwake* vanished between the outer buoy and the customs dock. The harbor master closed the file. Mara did not. Each night she relights the same three lamps in the same order, then writes one new line in the ledger: weather, current, and any voice that answered from the water.

She will not say she is hunting a ghost. She will say the channel still owes the town three lamps and one ship.

## Requested delivery

- PNG character card (SillyTavern v3 JSON embedded in PNG)
- Standalone lorebook JSON
- Embedded lorebook in the card

A 64x64 portrait PNG is provided at `docs/spikes/wp-09-portrait.png`.

## Player / tone (if asked)

- Player: a visiting sailor looking for a missing shipmate from *Cinderwake*
- Tone: melancholy mystery; no graphic violence
- Keep the card in English

## Expected artifact set

After gated delivery, `04-exports/` should contain:

- `character-cards/card.json` (built first; lorebook embedded when requested)
- `png-cards/card.png` (SillyTavern v3 JSON in PNG chunks)
- `lorebooks/lorebook.json` (standalone)

The PNG must validate as a v3 card. Lorebook entries must appear both in the standalone JSON and on the card (`character_book` / equivalent). The case `README.md` Deliverables list should name those `04-exports/...` paths.
