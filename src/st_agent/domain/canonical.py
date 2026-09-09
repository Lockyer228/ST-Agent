"""Render and parse canonical Markdown. JSON is not the creative source."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from st_agent.domain.case import CardDelivery, LorebookDelivery
from st_agent.domain.content import (
    CaseBrief,
    CharacterContent,
    DeliveryPreferences,
    LorebookContent,
    LorebookEntry,
)

BRIEF_FIELDS = (
    ("Experience Goal", "experience_goal"),
    ("Player Role", "player_role"),
    ("Characters", "characters"),
    ("World", "world"),
    ("Tone and Boundaries", "tone_and_boundaries"),
    ("Mechanics", "mechanics"),
    ("Information Reveals", "information_reveals"),
    ("Opening", "opening"),
    ("Creative Authorization", "creative_authorization"),
)
CHARACTER_FIELDS = (
    ("Name", "name"),
    ("Description", "description"),
    ("Personality", "personality"),
    ("Scenario", "scenario"),
    ("First Message", "first_message"),
    ("Example Dialogue", "example_dialogue"),
    ("System Prompt", "system_prompt"),
    ("Creator Notes", "creator_notes"),
    ("Lorebook Relationship", "lorebook_relationship"),
)
ENTRY_FIELDS = (
    ("Id", "entry_id"),
    ("Title", "title"),
    ("Content", "content"),
    ("Keys", "keys"),
    ("Secondary Keys", "secondary_keys"),
    ("Constant", "constant"),
    ("Selective", "selective"),
    ("Insertion Order", "insertion_order"),
    ("Position", "position"),
    ("Enabled", "enabled"),
)
H1_ALLOWED = frozenset({"Brief", "Character", "Lorebook"})
BRIEF_ALLOWED = frozenset(heading for heading, _ in BRIEF_FIELDS) | {"Delivery"}
CHARACTER_ALLOWED = frozenset(heading for heading, _ in CHARACTER_FIELDS) | {
    "Alternate Greetings",
    "Tags",
}
LOREBOOK_ALLOWED = frozenset({"Name", "Entry"})
ENTRY_ALLOWED = frozenset(heading for heading, _ in ENTRY_FIELDS)
HEADING = re.compile(r"^(#{1,3}) (.+)$")


class CanonicalError(ValueError):
    """Canonical Markdown is missing, mismatched, or replaced by JSON."""


class CanonicalDocument(BaseModel):
    brief: CaseBrief
    character: CharacterContent | None = None
    lorebook: LorebookContent | None = None


def _h_blocks(
    text: str,
    level: int,
    allowed: frozenset[str],
    nested: frozenset[int] = frozenset(),
) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    current: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            hashes = len(match.group(1))
            title = match.group(2).strip()
            if hashes == level:
                if title not in allowed:
                    raise CanonicalError(f"unknown heading: {title}")
                if current is not None:
                    blocks.append((current, "\n".join(buf).strip()))
                current = title
                buf = []
                continue
            if hashes not in nested:
                raise CanonicalError("heading markup is not allowed in field text")
        buf.append(line)
    if current is not None:
        blocks.append((current, "\n".join(buf).strip()))
    return blocks


def _reject_rule(heading: str, body: str) -> None:
    if heading == "Alternate Greetings":
        return
    for line in body.splitlines():
        if line.strip() == "---":
            raise CanonicalError("horizontal rule is only allowed between alternate greetings")


def _fields(
    text: str,
    level: int,
    allowed: frozenset[str],
    nested: frozenset[int] = frozenset(),
) -> dict[str, str]:
    out: dict[str, str] = {}
    for heading, body in _h_blocks(text, level, allowed, nested):
        _reject_rule(heading, body)
        out[heading] = _unescape_field(body)
    return out


def _list(value: str) -> list[str]:
    if not value.strip():
        return []
    items = [line.strip() for line in value.splitlines() if line.strip()]
    if any("," in item for item in items):
        raise CanonicalError("list fields cannot contain commas")
    return items


def _bool(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "1"}


def _delivery_text(prefs: DeliveryPreferences) -> str:
    return (
        f"character: {prefs.character}\n"
        f"lorebook: {prefs.lorebook}\n"
        f"portrait: {prefs.portrait_ref or ''}\n"
        f"environment: {prefs.environment_constraints or ''}"
    )


def _parse_delivery(text: str) -> DeliveryPreferences:
    data = {"character": "json", "lorebook": "none", "portrait": "", "environment": ""}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip().lower()] = value.strip()
    if _portrait_escapes(data["portrait"]):
        raise CanonicalError("portrait path must stay inside the case")
    return DeliveryPreferences(
        character=CardDelivery(data["character"] or "json"),
        lorebook=LorebookDelivery(data["lorebook"] or "none"),
        portrait_ref=data["portrait"] or None,
        environment_constraints=data["environment"] or None,
    )


def _portrait_escapes(ref: str) -> bool:
    if not ref:
        return False
    path = Path(ref)
    posix = path.as_posix()
    if path.is_absolute() or posix.startswith("/") or posix.startswith("~"):
        return True
    return ".." in path.parts


def _unescape_field(value: str) -> str:
    return "\n".join(
        line[1:] if line.startswith("\\") and HEADING.match(line[1:]) else line
        for line in value.splitlines()
    )


def _escape_field(value: str) -> str:
    return "\n".join("\\" + line if HEADING.match(line) else line for line in value.splitlines())


def render_canonical(doc: CanonicalDocument) -> str:
    parts = ["# Brief"]
    for heading, field in BRIEF_FIELDS:
        parts.append(f"## {heading}\n{_escape_field(getattr(doc.brief, field))}")
    parts.append(f"## Delivery\n{_delivery_text(doc.brief.delivery)}")
    if doc.character is not None:
        parts.append("# Character")
        for heading, field in CHARACTER_FIELDS:
            parts.append(f"## {heading}\n{_escape_field(getattr(doc.character, field))}")
        greetings = "\n---\n".join(
            _escape_field(item) for item in doc.character.alternate_greetings
        )
        parts.append(f"## Alternate Greetings\n{greetings}")
        parts.append("## Tags\n" + "\n".join(_escape_field(tag) for tag in doc.character.tags))
    if doc.lorebook is not None:
        parts.append("# Lorebook")
        parts.append(f"## Name\n{_escape_field(doc.lorebook.name)}")
        for entry in doc.lorebook.entries:
            parts.append("## Entry")
            for heading, field in ENTRY_FIELDS:
                value = getattr(entry, field)
                if isinstance(value, list):
                    value = "\n".join(_escape_field(str(item)) for item in value)
                else:
                    value = _escape_field(str(value))
                parts.append(f"### {heading}\n{value}")
    return "\n\n".join(parts) + "\n"


def _parse_brief(text: str) -> CaseBrief:
    fields = _fields(text, 2, BRIEF_ALLOWED)
    values = {attr: fields.get(heading, "") for heading, attr in BRIEF_FIELDS}
    return CaseBrief(
        **values,
        delivery=_parse_delivery(fields.get("Delivery", "")),
    )


def _parse_character(text: str) -> CharacterContent:
    fields = _fields(text, 2, CHARACTER_ALLOWED)
    greetings = fields.get("Alternate Greetings", "")
    alts = [item.strip() for item in greetings.split("\n---\n") if item.strip()]
    return CharacterContent(
        **{attr: fields.get(heading, "") for heading, attr in CHARACTER_FIELDS},
        alternate_greetings=alts,
        tags=_list(fields.get("Tags", "")),
    )


def _parse_entry(text: str) -> LorebookEntry:
    fields = _fields(text, 3, ENTRY_ALLOWED)
    return LorebookEntry(
        entry_id=fields.get("Id", ""),
        title=fields.get("Title", ""),
        content=fields.get("Content", ""),
        keys=_list(fields.get("Keys", "")),
        secondary_keys=_list(fields.get("Secondary Keys", "")),
        constant=_bool(fields.get("Constant", "")),
        selective=_bool(fields.get("Selective", "")),
        insertion_order=int(fields.get("Insertion Order", "100") or "100"),
        position=fields.get("Position", "after_char") or "after_char",
        enabled=_bool(fields.get("Enabled", "true") or "true"),
    )


def _parse_lorebook(text: str) -> LorebookContent:
    name = ""
    entries: list[LorebookEntry] = []
    for heading, body in _h_blocks(text, 2, LOREBOOK_ALLOWED, nested=frozenset({3})):
        _reject_rule(heading, body)
        if heading == "Name":
            name = _unescape_field(body)
        elif heading == "Entry":
            entries.append(_parse_entry(body))
    return LorebookContent(name=name, entries=entries)


def parse_canonical(text: str) -> CanonicalDocument:
    blocks = dict(_h_blocks(text, 1, H1_ALLOWED, nested=frozenset({2, 3})))
    if "Brief" not in blocks:
        raise CanonicalError("canonical Markdown requires a Brief section")
    return CanonicalDocument(
        brief=_parse_brief(blocks["Brief"]),
        character=_parse_character(blocks["Character"]) if "Character" in blocks else None,
        lorebook=_parse_lorebook(blocks["Lorebook"]) if "Lorebook" in blocks else None,
    )


def roundtrip(doc: CanonicalDocument) -> CanonicalDocument:
    restored = parse_canonical(render_canonical(doc))
    if restored.model_dump() == doc.model_dump():
        return restored
    raise CanonicalError("canonical Markdown round-trip changed the content")


def load_creative_path(path: Path) -> CanonicalDocument:
    if path.suffix.lower() == ".json":
        raise CanonicalError("JSON is not the creative source")
    return roundtrip(parse_canonical(path.read_text(encoding="utf-8")))


def _slug(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:48] or fallback


def _name_from_characters(characters: str) -> str:
    text = (characters or "").strip()
    if not text:
        return "Character"
    line = text.splitlines()[0].strip()
    for sep in ("\uFF1A", ":"):
        if sep in line:
            left, right = (part.strip() for part in line.split(sep, 1))
            line = right if len(left) <= 4 else left
            break
    clause = re.split("[.\u3002;\uFF1B!\uFF01?\uFF1F]", line, maxsplit=1)[0]
    clause = re.split("[,\uFF0C]", clause, maxsplit=1)[0].strip()
    taken: list[str] = []
    for word in clause.split():
        token = word.strip("\"'")
        if token and token[:1].isupper():
            taken.append(token)
        else:
            break
    name = " ".join(taken) if taken else clause
    return name[:80].strip() or "Character"


def _keys(text: str, fallback: str) -> list[str]:
    cleaned = text.replace(",", " ").replace("\uFF0C", " ")
    keys: list[str] = []
    for word in cleaned.split():
        token = word.strip(".,;:\u3002")[:40]
        if len(token) < 2 or "," in token or token in keys:
            continue
        keys.append(token)
        if len(keys) >= 3:
            break
    if keys:
        return keys
    token = (cleaned.strip()[:20] or fallback).replace(",", " ").strip()
    return [token or fallback]


def _brief_entry(text: str, fallback_id: str, title: str) -> LorebookEntry | None:
    content = (text or "").strip()
    if not content:
        return None
    return LorebookEntry(
        entry_id=_slug(title, fallback_id),
        title=title,
        content=content,
        keys=_keys(content, fallback_id),
        selective=True,
        enabled=True,
    )


def document_from_brief(brief: CaseBrief) -> CanonicalDocument:
    character = CharacterContent(
        name=_name_from_characters(brief.characters),
        description=brief.characters,
        personality=brief.tone_and_boundaries,
        scenario="\n".join(part for part in (brief.player_role, brief.world) if part.strip()),
        first_message=brief.opening,
    )
    lorebook = None
    if brief.delivery.lorebook is not LorebookDelivery.none:
        entries = [
            item
            for item in (
                _brief_entry(brief.world, "world", "World"),
                _brief_entry(brief.information_reveals, "reveal", "Reveal"),
            )
            if item is not None
        ]
        if not entries:
            fallback = _brief_entry(brief.experience_goal, "world", "World")
            entries = [fallback] if fallback is not None else []
        seen: set[str] = set()
        for entry in entries:
            if entry.entry_id in seen:
                entry.entry_id = f"{entry.entry_id}-2"
            seen.add(entry.entry_id)
        lorebook = LorebookContent(
            name=(brief.world.strip().splitlines()[0][:60] if brief.world.strip() else "Lorebook"),
            entries=entries,
        )
    return CanonicalDocument(brief=brief, character=character, lorebook=lorebook)
