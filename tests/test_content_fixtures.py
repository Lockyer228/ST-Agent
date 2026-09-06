"""WP-04 representative fixtures round-trip through canonical Markdown."""

from __future__ import annotations

from pathlib import Path

from st_agent.domain.canonical import load_creative_path, render_canonical, roundtrip
from tests.fixtures.content.cases import FIXTURES

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "content"
PRIVATE_MARKERS = (
    "seraphina",
    "d:\\",
    "/home/",
    "c:\\st-agent",
)


def test_six_representative_fixtures_exist() -> None:
    assert set(FIXTURES) == {
        "ordinary-character",
        "scene-card",
        "keyword-lorebook",
        "constant-lorebook",
        "hidden-information",
        "unsupported-mechanism",
    }
    for name, doc in FIXTURES.items():
        path = FIXTURE_DIR / f"{name}.md"
        assert path.is_file(), name
        assert path.read_text(encoding="utf-8") == render_canonical(doc)


def test_fixtures_roundtrip_and_stay_neutral() -> None:
    for name, doc in FIXTURES.items():
        restored = roundtrip(doc)
        assert restored.model_dump() == doc.model_dump()
        assert restored.brief.experience_goal
        assert restored.brief.creative_authorization
        loaded = load_creative_path(FIXTURE_DIR / f"{name}.md")
        assert loaded.model_dump() == doc.model_dump()
        blob = render_canonical(doc).lower()
        for marker in PRIVATE_MARKERS:
            assert marker not in blob
        assert "unsupported" not in name or "combat engine" in blob


def test_json_default_does_not_extend_authorization() -> None:
    ordinary = FIXTURES["ordinary-character"]
    assert ordinary.brief.delivery.character == "json"
    assert "approval" not in ordinary.brief.creative_authorization.lower()
    assert ordinary.character is not None
    assert not ordinary.brief.delivery.portrait_ref
