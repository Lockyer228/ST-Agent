"""Runtime rule resources stay English, reusable, and free of private defaults."""

from __future__ import annotations

import re

from st_agent.paths import package_dir

METHODS = package_dir() / "resources" / "methods"
CJK = re.compile(r"[\u4e00-\u9fff]")
FORBIDDEN = ("seraphina", "d:\\", "/home/", "c:\\users\\", "90%", "绝对")


def _text(name: str) -> str:
    return (METHODS / name).read_text(encoding="utf-8")


def test_method_files_exist() -> None:
    for name in ("qa-method.md", "creation-workflow.md", "st-content-mapping.md"):
        assert (METHODS / name).is_file()


def _body(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def test_methods_are_neutral_english() -> None:
    for name in ("qa-method.md", "creation-workflow.md", "st-content-mapping.md"):
        text = _body(_text(name))
        assert CJK.search(text) is None, name
        lower = text.lower()
        for marker in FORBIDDEN:
            assert marker not in lower, f"{name} contains {marker}"


def test_qa_method_contract() -> None:
    text = _text("qa-method.md").lower()
    assert "one" in text and "question" in text
    assert "json" in text
    assert "turnoutcome" in text
    assert "stop" in text


def test_creation_workflow_uses_canonical_markdown() -> None:
    text = _text("creation-workflow.md").lower()
    assert "canonical" in text
    assert "json is a serializer" in text or "not the creative source" in text
    assert "q&a" in text or "qa" in text


def test_content_mapping_avoids_topic_defaults() -> None:
    text = _body(_text("st-content-mapping.md")).lower()
    assert "keyword" in text
    assert "constant" in text
    assert "scene card" in text
    assert "oppression" not in text
