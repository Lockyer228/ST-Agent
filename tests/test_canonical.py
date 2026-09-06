"""Canonical Markdown is the creative source, not JSON."""

from __future__ import annotations

from pathlib import Path

import pytest

from st_agent.domain.canonical import (
    CanonicalDocument,
    CanonicalError,
    load_creative_path,
    parse_canonical,
    render_canonical,
    roundtrip,
)
from st_agent.domain.content import (
    CaseBrief,
    CharacterContent,
    DeliveryPreferences,
    LorebookContent,
    LorebookEntry,
)


def _brief(**overrides: str) -> CaseBrief:
    data = {
        "experience_goal": "Play a returning sailor.",
        "player_role": "A tired navigator.",
        "characters": "Mara keeps the tavern.",
        "world": "A rain-soaked port.",
        "tone_and_boundaries": "Melancholy; no graphic violence.",
        "mechanics": "Track missing ships.",
        "information_reveals": "The ledger is shown only if asked.",
        "opening": "Rain hits the windows at dusk.",
        "creative_authorization": "Ordinary tavern details may be invented.",
    }
    data.update(overrides)
    return CaseBrief(**data, delivery=DeliveryPreferences())


def _character() -> CharacterContent:
    return CharacterContent(
        name="Mara",
        description="A tavern keeper who records lost ships.",
        personality="Quiet and exact.",
        scenario="The Salt Lantern after a storm.",
        first_message="Mara wipes a mug and does not look up.",
        example_dialogue="{{user}}: Any news?\n{{char}}: Only the names that did not return.",
        system_prompt="Stay in Mara's voice.",
        creator_notes="Keep the ledger mundane.",
        alternate_greetings=["The door bell is still wet."],
        tags=["tavern", "port"],
        lorebook_relationship="Uses the harbor ledger entries.",
    )


def test_character_roundtrip_is_semantic() -> None:
    doc = CanonicalDocument(brief=_brief(), character=_character())
    restored = roundtrip(doc)
    assert restored.model_dump() == doc.model_dump()
    text = render_canonical(doc)
    assert text.startswith("# Brief")
    assert "## Name" in text
    assert "{" not in text.split("## Description", 1)[1][:80]


def test_lorebook_roundtrip_keeps_one_entry_set() -> None:
    book = LorebookContent(
        name="Harbor notes",
        entries=[
            LorebookEntry(
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
        ],
    )
    doc = CanonicalDocument(brief=_brief(), lorebook=book)
    restored = roundtrip(doc)
    assert restored.lorebook is not None
    assert restored.lorebook.entries[0].entry_id == "harbor-ledger"
    assert restored.lorebook.model_dump() == book.model_dump()


def test_json_is_rejected_as_creative_source(tmp_path: Path) -> None:
    path = tmp_path / "card.json"
    path.write_text('{"name": "Mara"}', encoding="utf-8")
    with pytest.raises(CanonicalError):
        load_creative_path(path)


def test_parse_matches_render() -> None:
    doc = CanonicalDocument(brief=_brief(), character=_character())
    parsed = parse_canonical(render_canonical(doc))
    assert parsed.character is not None
    assert parsed.character.name == "Mara"
    assert parsed.brief.delivery.character == "json"
