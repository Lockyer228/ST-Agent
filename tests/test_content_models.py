"""Canonical content models."""

from __future__ import annotations

from st_agent.domain.content import (
    CaseBrief,
    CharacterContent,
    DeliveryPreferences,
    LorebookContent,
    LorebookEntry,
    SourceOverlay,
)


def test_case_brief_holds_intent_fields() -> None:
    brief = CaseBrief(
        experience_goal="Play a returning sailor in a rain-soaked port.",
        player_role="A tired navigator seeking one lost ship.",
        characters="Mara keeps the Salt Lantern tavern.",
        world="A North Atlantic port after a winter storm.",
        tone_and_boundaries="Melancholy; no graphic violence.",
        mechanics="Track which ships are still missing.",
        information_reveals="The ledger is shown only if asked.",
        opening="Rain hits the tavern windows at dusk.",
        creative_authorization="Ordinary tavern details may be invented.",
        delivery=DeliveryPreferences(),
    )
    assert brief.delivery.character == "json"
    assert brief.delivery.lorebook == "none"


def test_character_and_lorebook_models() -> None:
    character = CharacterContent(
        name="Mara",
        description="A tavern keeper who records lost ships.",
        personality="Quiet, exact, unwilling to offer false hope.",
        scenario="The Salt Lantern after a three-day storm.",
        first_message="Mara wipes a mug and does not look up.",
        example_dialogue="{{user}}: Any news?\n{{char}}: Only the names that did not return.",
        system_prompt="Stay in Mara's voice. Do not invent rescued ships.",
        creator_notes="Keep the ledger mundane.",
        alternate_greetings=["The door bell is still wet."],
        tags=["tavern", "port"],
        lorebook_relationship="Uses the harbor ledger entries.",
    )
    entry = LorebookEntry(
        entry_id="harbor-ledger",
        title="Harbor ledger",
        content="A dog-eared book of ships that never returned.",
        keys=["ledger", "ships"],
        secondary_keys=["names"],
        constant=False,
        selective=True,
        insertion_order=10,
        position="after_char",
        enabled=True,
    )
    book = LorebookContent(name="Harbor notes", entries=[entry])
    assert character.name == "Mara"
    assert book.entries[0].constant is False
    assert len(book.entries) == 1


def test_source_overlay_keeps_unknown_fields() -> None:
    overlay = SourceOverlay(
        original_spec="chara_card_v3",
        source_hash="abc123",
        unknown_fields={"extensions": {"foo": 1}, "mystery": "keep"},
        merge_policy="preserve_unknown",
    )
    merged = overlay.merge({"name": "Mara", "description": "new"})
    assert merged["mystery"] == "keep"
    assert merged["extensions"] == {"foo": 1}
    assert merged["name"] == "Mara"
    assert "mystery" not in (overlay.as_creative_text())
