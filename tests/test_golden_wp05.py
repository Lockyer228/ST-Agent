"""WP-05 golden delivery combinations."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from st_agent.domain.case import CardDelivery, LorebookDelivery
from st_agent.domain.content import (
    CharacterContent,
    DeliveryPreferences,
    LorebookContent,
    LorebookEntry,
    SourceOverlay,
)
from st_agent.formats import apply_card_modification, load_format_profile
from st_agent.png_card import PngCardCodec
from st_agent.services.serializers import (
    serialize_character,
    serialize_embedded_lorebook,
    serialize_standalone_lorebook,
)
from st_agent.services.validators import (
    promote_exports,
    validate_card,
    validate_lorebook,
    validate_png,
    validate_requested_output,
)
from st_agent.services.workspace import create_case

FIXTURES = Path(__file__).parent / "fixtures" / "golden"


def _character() -> CharacterContent:
    return CharacterContent(
        name="Mira Vale",
        description="A night-market cartomancer who reads weather in spilled tea.",
        personality="Dry humor, precise, quietly kind.",
        scenario="Rainy harbor boardwalk after the last ferry.",
        first_message="The lanterns hiss. I keep a chair empty in case you actually sit.",
        example_dialogue="{{user}}: Hello.\n{{char}}: Sit. The tea is already loud.",
        system_prompt="Stay in character as Mira Vale.",
        creator_notes="Spike fixture. Not a shipping character.",
        alternate_greetings=["The tide turned. You still came."],
        tags=["original", "harbor"],
    )


def _book() -> LorebookContent:
    return LorebookContent(
        name="Harbor Notes",
        entries=[
            LorebookEntry(
                entry_id="0",
                title="Last ferry",
                content="The last ferry leaves a wet rope of light across the water.",
                keys=["harbor", "ferry"],
                position="after_char",
            )
        ],
    )


def test_new_card_from_canonical_matches_profile() -> None:
    card = serialize_character(_character())
    profile = load_format_profile("character-card-v3")
    assert card["spec"] == profile["spec"]
    golden = json.loads((FIXTURES / "new-card.json").read_text(encoding="utf-8"))
    assert card["data"]["name"] == golden["data"]["name"]
    assert validate_card(card).ok


def test_modify_unknown_field_preservation() -> None:
    source = json.loads((FIXTURES / "modified-card.json").read_text(encoding="utf-8"))
    overlay = SourceOverlay(original_spec="chara_card_v3", source_hash="src", unknown_fields=source)
    merged = overlay.merge(serialize_character(_character()))
    assert merged["unspecified_top_level"] == "preserve-me"
    assert merged["data"]["extensions"]["vendor_x"] == {"keep": 1}


def test_standalone_and_embedded_and_both() -> None:
    book = _book()
    embedded = serialize_embedded_lorebook(book)
    standalone = serialize_standalone_lorebook(book)
    card = serialize_character(_character(), lorebook=book)
    assert validate_lorebook(embedded, embedded=True).ok
    assert validate_lorebook(standalone, embedded=False).ok
    assert card["data"]["character_book"]["entries"][0]["content"] == (
        standalone["entries"]["0"]["content"]
    )
    embedded_path = FIXTURES / "embedded-character-book.json"
    standalone_path = FIXTURES / "standalone-lorebook.json"
    golden_embedded = json.loads(embedded_path.read_text(encoding="utf-8"))
    golden_standalone = json.loads(standalone_path.read_text(encoding="utf-8"))
    assert embedded["entries"][0]["content"] == golden_embedded["entries"][0]["content"]
    assert standalone["entries"]["0"]["content"] == golden_standalone["entries"]["0"]["content"]


def test_json_only_png_only_and_json_plus_png(tmp_path: Path) -> None:
    card = serialize_character(_character())
    png = PngCardCodec().write(Image.new("RGB", (8, 8), "navy"), card)
    json_only = validate_requested_output(
        DeliveryPreferences(character=CardDelivery.json), {"card.json": b"{}"}
    )
    png_only = validate_requested_output(
        DeliveryPreferences(character=CardDelivery.png), {"card.png": png}
    )
    both = validate_requested_output(
        DeliveryPreferences(character=CardDelivery.both),
        {"card.json": b"{}", "card.png": png},
    )
    assert json_only.ok and png_only.ok and both.ok
    assert validate_png(png, card).ok
    case_root = create_case(tmp_path, "harbor-watch")
    exported = promote_exports(case_root, {"card.json": b"{}", "card.png": png}, both)
    assert len(exported) == 2
    assert (case_root / "04-exports" / "character-cards" / "card.json").is_file()
    assert (case_root / "04-exports" / "png-cards" / "card.png").is_file()


def test_story_named_exports_and_lorebook_folder(tmp_path: Path) -> None:
    png = PngCardCodec().write(Image.new("RGB", (8, 8), "navy"), serialize_character(_character()))
    case_root = create_case(tmp_path, "Dead Air On County Road 17")
    stem = "dead-air-on-county-road-17"
    staged = {
        f"{stem}.json": b"{}",
        f"{stem}.png": png,
        f"{stem}-lorebook.json": b"{}",
    }
    both = validate_requested_output(
        DeliveryPreferences(character=CardDelivery.both, lorebook=LorebookDelivery.standalone),
        staged,
    )
    assert both.ok
    exported = promote_exports(case_root, staged, both)
    assert len(exported) == 3
    assert (case_root / "04-exports" / "character-cards" / f"{stem}.json").is_file()
    assert (case_root / "04-exports" / "png-cards" / f"{stem}.png").is_file()
    assert (case_root / "04-exports" / "lorebooks" / f"{stem}-lorebook.json").is_file()


def test_non_card_png_rejection_and_semantic_readback() -> None:
    card = serialize_character(_character())
    codec = PngCardCodec()
    png = codec.write(Image.new("RGB", (8, 8), "navy"), card)
    extracted = codec.read(png)
    assert extracted["data"]["name"] == card["data"]["name"]
    assert extracted["data"]["first_mes"] == card["data"]["first_mes"]
    plain = Path(__file__).parent / "fixtures" / "golden"
    # non-card PNG is a portrait without chunks
    from io import BytesIO

    raw = BytesIO()
    Image.new("RGB", (4, 4), "navy").save(raw, format="PNG")
    assert not validate_png(raw.getvalue(), card).ok
    assert plain.is_dir()
    merged = apply_card_modification(
        json.loads((FIXTURES / "modified-card.json").read_text(encoding="utf-8")),
        {"data": {"name": "Revised Mira"}},
    )
    assert merged["data"]["name"] == "Revised Mira"
