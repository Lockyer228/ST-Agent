"""Frozen ST / CCv3 format profiles and unknown-field preservation."""

from __future__ import annotations

import json
from pathlib import Path

from st_agent.formats import apply_card_modification, load_format_profile

FIXTURES = Path(__file__).parent / "fixtures" / "golden"


def test_new_card_matches_ccv3_profile() -> None:
    card = json.loads((FIXTURES / "new-card.json").read_text(encoding="utf-8"))
    profile = load_format_profile("character-card-v3")
    assert card["spec"] == profile["spec"]
    assert card["spec_version"] == profile["spec_version"]
    for field in profile["required_data_fields"]:
        assert field in card["data"]


def test_modified_card_preserves_unknown_fields() -> None:
    source = json.loads((FIXTURES / "modified-card.json").read_text(encoding="utf-8"))
    updates = {"data": {"name": "Revised Mira", "description": "Updated description."}}
    merged = apply_card_modification(source, updates)
    assert merged["data"]["name"] == "Revised Mira"
    assert merged["data"]["extensions"]["vendor_x"] == {"keep": 1}
    assert merged["data"]["extensions"]["st_agent_unknown_probe"] is True
    assert merged["unspecified_top_level"] == "preserve-me"


def test_embedded_and_standalone_lorebook_profiles_differ() -> None:
    embedded = json.loads((FIXTURES / "embedded-character-book.json").read_text(encoding="utf-8"))
    standalone = json.loads((FIXTURES / "standalone-lorebook.json").read_text(encoding="utf-8"))
    ccv3 = load_format_profile("st-character-book")
    st_wi = load_format_profile("st-lorebook")
    assert isinstance(embedded["entries"], list)
    assert ccv3["entries_shape"] == "array"
    assert isinstance(standalone["entries"], dict)
    assert st_wi["entries_shape"] == "uid-map"
    assert embedded["entries"][0]["content"] == standalone["entries"]["0"]["content"]
