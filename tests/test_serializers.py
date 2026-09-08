"""Serializers, overlay merge, portraits, and validators."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from st_agent.domain.case import CardDelivery, Lineage, LorebookDelivery
from st_agent.domain.content import (
    CharacterContent,
    DeliveryPreferences,
    LorebookContent,
    LorebookEntry,
    SourceOverlay,
)
from st_agent.formats import apply_card_modification
from st_agent.png_card import PngCardCodec
from st_agent.services.portraits import portrait_to_png
from st_agent.services.serializers import (
    FormatError,
    serialize_character,
    serialize_embedded_lorebook,
    serialize_standalone_lorebook,
)
from st_agent.services.validators import (
    promote_exports,
    validate_card,
    validate_lineage,
    validate_lorebook,
    validate_png,
    validate_requested_output,
)
from st_agent.services.workspace import create_case


def _character() -> CharacterContent:
    return CharacterContent(
        name="Mira Vale",
        description="A night-market cartomancer.",
        personality="Dry humor.",
        scenario="Rainy harbor boardwalk.",
        first_message="The lanterns hiss.",
        example_dialogue="{{user}}: Hello.\n{{char}}: Sit.",
        system_prompt="Stay in character as Mira Vale.",
        creator_notes="Fixture.",
        alternate_greetings=["The tide turned."],
        tags=["harbor"],
    )


def _book(*, position: str = "after_char") -> LorebookContent:
    return LorebookContent(
        name="Harbor Notes",
        entries=[
            LorebookEntry(
                entry_id="0",
                title="Last ferry",
                content="The last ferry leaves a wet rope of light across the water.",
                keys=["harbor", "ferry"],
                position=position,
                insertion_order=100,
            )
        ],
    )


def test_character_serializer_matches_ccv3_envelope() -> None:
    card = serialize_character(_character())
    assert card["spec"] == "chara_card_v3"
    assert card["spec_version"] == "3.0"
    assert card["data"]["name"] == "Mira Vale"
    assert card["data"]["first_mes"] == "The lanterns hiss."
    assert validate_card(card).ok


def test_validate_card_rejects_blank_name() -> None:
    card = serialize_character(_character())
    card["data"]["name"] = ""
    result = validate_card(card)
    assert not result.ok
    assert any(item.code == "card-name" for item in result.issues)


def test_unsupported_position_is_rejected() -> None:
    with pytest.raises(FormatError, match="position"):
        serialize_embedded_lorebook(_book(position="at_depth"))


def test_standalone_and_embedded_share_one_entry_set() -> None:
    book = _book()
    embedded = serialize_embedded_lorebook(book)
    standalone = serialize_standalone_lorebook(book)
    assert isinstance(embedded["entries"], list)
    assert isinstance(standalone["entries"], dict)
    assert embedded["entries"][0]["content"] == standalone["entries"]["0"]["content"]
    assert embedded["entries"][0]["position"] == "after_char"
    assert standalone["entries"]["0"]["position"] == 1


def test_overlay_nested_overlap_keeps_unknown_subtree() -> None:
    overlay = SourceOverlay(
        original_spec="chara_card_v3",
        source_hash="abc",
        unknown_fields={"data": {"extensions": {"foo": 1}, "name": "Old"}},
    )
    merged = overlay.merge({"data": {"name": "New", "description": "d"}})
    assert merged["data"]["name"] == "New"
    assert merged["data"]["extensions"]["foo"] == 1
    card = serialize_character(_character(), overlay=overlay)
    assert card["data"]["extensions"]["foo"] == 1
    assert card["data"]["name"] == "Mira Vale"


def test_optional_activation_cannot_override_position() -> None:
    book = _book()
    book.entries[0].optional_activation = {"probability": 40, "position": 999}
    embedded = serialize_embedded_lorebook(book)
    assert embedded["entries"][0]["position"] == "after_char"
    assert "position" not in embedded["entries"][0]["extensions"]["optional_activation"]
    standalone = serialize_standalone_lorebook(book)
    assert standalone["entries"]["0"]["position"] == 1


def test_overlay_extract_drops_character_book() -> None:
    from st_agent.formats import extract_source_overlay

    source = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {
            "name": "Old",
            "character_book": {"name": "Keep out", "entries": []},
            "extensions": {"vendor_x": 1},
        },
    }
    overlay = extract_source_overlay(source, source_hash="abc")
    merged = overlay.merge(serialize_character(_character()))
    assert "character_book" not in merged.get("data", {})
    assert merged["data"]["extensions"]["vendor_x"] == 1


def test_modify_preserves_unknown_top_level() -> None:
    source = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "unspecified_top_level": "preserve-me",
        "data": {"name": "Mira", "extensions": {"vendor_x": {"keep": 1}}},
    }
    merged = apply_card_modification(source, {"data": {"name": "Revised Mira"}})
    assert merged["unspecified_top_level"] == "preserve-me"
    assert merged["data"]["extensions"]["vendor_x"] == {"keep": 1}


def test_portrait_keeps_size_and_writes_png(tmp_path: Path) -> None:
    src = tmp_path / "face.bmp"
    Image.new("RGBA", (12, 8), (1, 2, 3, 255)).save(src, format="BMP")
    png = portrait_to_png(src)
    out = Image.open(io.BytesIO(png))
    assert out.format == "PNG"
    assert out.size == (12, 8)


def test_non_card_png_is_rejected() -> None:
    raw = io.BytesIO()
    Image.new("RGB", (4, 4), "navy").save(raw, format="PNG")
    with pytest.raises(ValueError, match="character data"):
        PngCardCodec().read(raw.getvalue())


def test_semantic_png_readback() -> None:
    card = serialize_character(_character())
    png = PngCardCodec().write(Image.new("RGB", (6, 6), "navy"), card)
    assert validate_png(png, card).ok


def test_failed_build_stays_out_of_exports(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    staged = {"card.json": b'{"spec": "nope"}'}
    issues = validate_card({"spec": "nope"})
    promoted = promote_exports(case_root, staged, issues)
    assert promoted == []
    assert list((case_root / "04-exports").rglob("*.json")) == []
    assert (case_root / "00-work" / "build" / "card.json").is_file()


def test_requested_output_and_lineage_validators() -> None:
    prefs = DeliveryPreferences(character=CardDelivery.png, lorebook=LorebookDelivery.standalone)
    artifacts = {"card.json": b"{}"}
    result = validate_requested_output(prefs, artifacts)
    assert not result.ok
    lineage = {"character": Lineage(source_hash="aa", artifact_hash="bb", stale=True)}
    assert not validate_lineage(lineage).ok


def test_png_semantic_rejects_description_mismatch() -> None:
    card = serialize_character(_character())
    png = PngCardCodec().write(Image.new("RGB", (6, 6), "navy"), card)
    tampered = serialize_character(_character())
    tampered["data"]["description"] = "tampered"
    assert not validate_png(png, tampered).ok


def test_lorebook_rejects_missing_required_fields() -> None:
    book = serialize_embedded_lorebook(_book())
    del book["entries"][0]["keys"]
    assert not validate_lorebook(book, embedded=True).ok
    standalone = serialize_standalone_lorebook(_book())
    del standalone["entries"]["0"]["key"]
    assert not validate_lorebook(standalone, embedded=False).ok


def test_numeric_uid_collision_is_rejected() -> None:
    book = LorebookContent(
        name="Harbor Notes",
        entries=[
            LorebookEntry(entry_id="1", title="A", content="one", keys=["a"]),
            LorebookEntry(entry_id="01", title="B", content="two", keys=["b"]),
        ],
    )
    with pytest.raises(FormatError, match="uid"):
        serialize_embedded_lorebook(book)
    with pytest.raises(FormatError, match="uid"):
        serialize_standalone_lorebook(book)
