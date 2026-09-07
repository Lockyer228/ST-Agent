"""WP-09 package fixtures: canonical sample used by the representative case."""

from __future__ import annotations

from pathlib import Path

from st_agent.domain.canonical import load_creative_path
from st_agent.domain.case import CardDelivery, LorebookDelivery

CANONICAL = Path(__file__).resolve().parents[1] / "docs" / "spikes" / "wp-09-canonical.md"


def test_wp09_canonical_fixture_roundtrips() -> None:
    doc = load_creative_path(CANONICAL)
    assert doc.character is not None
    assert doc.character.name == "Mara Ellison"
    assert doc.brief.delivery.character is CardDelivery.png
    assert doc.brief.delivery.lorebook is LorebookDelivery.both
    assert doc.brief.delivery.portrait_ref == "01-assets/portraits/wp-09-portrait.png"
    assert doc.lorebook is not None
    assert {entry.entry_id for entry in doc.lorebook.entries} == {"reedwick-jetty", "cinderwake"}
