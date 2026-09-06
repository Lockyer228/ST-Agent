"""Character card and lorebook serializers. JSON is an output, not the source."""

from __future__ import annotations

import zlib
from typing import Any

from st_agent.domain.content import CharacterContent, LorebookContent, LorebookEntry, SourceOverlay

SUPPORTED_POSITIONS = {"before_char", "after_char"}
ST_POSITION = {"before_char": 0, "after_char": 1}


class FormatError(ValueError):
    """Serialized ST/CCv3 output would be invalid."""


def _position(entry: LorebookEntry) -> str:
    if entry.position not in SUPPORTED_POSITIONS:
        raise FormatError(f"unsupported lorebook position: {entry.position}")
    return entry.position


def _activation(entry: LorebookEntry) -> dict[str, Any]:
    return {key: value for key, value in entry.optional_activation.items() if key != "position"}


def _uid(entry: LorebookEntry, seen: set[int]) -> int:
    if entry.entry_id.isdigit():
        uid = int(entry.entry_id)
    else:
        uid = zlib.crc32(entry.entry_id.encode("utf-8")) & 0x7FFFFFFF
    if uid in seen:
        raise FormatError(f"duplicate lorebook uid: {uid}")
    seen.add(uid)
    return uid


def serialize_embedded_lorebook(book: LorebookContent) -> dict[str, Any]:
    entries = []
    seen: set[int] = set()
    for entry in book.entries:
        position = _position(entry)
        item = {
            "id": _uid(entry, seen),
            "keys": list(entry.keys),
            "content": entry.content,
            "extensions": {},
            "enabled": entry.enabled,
            "insertion_order": entry.insertion_order,
            "case_sensitive": False,
            "use_regex": False,
            "constant": entry.constant,
            "name": entry.title,
            "comment": entry.title,
            "selective": entry.selective,
            "secondary_keys": list(entry.secondary_keys),
            "position": position,
        }
        if entry.optional_activation:
            activation = _activation(entry)
            if activation:
                item["extensions"]["optional_activation"] = activation
        entries.append(item)
    return {
        "name": book.name,
        "description": "",
        "scan_depth": 4,
        "token_budget": 512,
        "recursive_scanning": False,
        "extensions": {},
        "entries": entries,
    }


def serialize_standalone_lorebook(book: LorebookContent) -> dict[str, Any]:
    entries: dict[str, Any] = {}
    seen: set[int] = set()
    for entry in book.entries:
        position = _position(entry)
        uid = _uid(entry, seen)
        item = {
            "uid": uid,
            "key": list(entry.keys),
            "keysecondary": list(entry.secondary_keys),
            "comment": entry.title,
            "content": entry.content,
            "constant": entry.constant,
            "vectorized": False,
            "selective": entry.selective,
            "selectiveLogic": 0,
            "addMemo": True,
            "order": entry.insertion_order,
            "position": ST_POSITION[position],
            "disable": not entry.enabled,
            "excludeRecursion": False,
            "preventRecursion": False,
            "delayUntilRecursion": False,
            "probability": 100,
            "useProbability": True,
            "depth": 4,
            "group": "",
            "groupOverride": False,
            "groupWeight": 100,
            "scanDepth": None,
            "caseSensitive": False,
            "matchWholeWords": None,
            "useGroupScoring": None,
            "automationId": "",
            "role": 0,
            "sticky": 0,
            "cooldown": 0,
            "delay": 0,
            "displayIndex": uid,
        }
        if entry.optional_activation:
            item.update(_activation(entry))
        entries[str(uid)] = item
    return {"entries": entries}


def serialize_character(
    character: CharacterContent,
    *,
    lorebook: LorebookContent | None = None,
    overlay: SourceOverlay | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": character.name,
        "description": character.description,
        "personality": character.personality,
        "scenario": character.scenario,
        "first_mes": character.first_message,
        "mes_example": character.example_dialogue,
        "system_prompt": character.system_prompt,
        "post_history_instructions": "",
        "tags": list(character.tags),
        "creator": "",
        "character_version": "1",
        "extensions": {},
        "alternate_greetings": list(character.alternate_greetings),
        "group_only_greetings": [],
        "creator_notes": character.creator_notes,
    }
    if lorebook is not None:
        data["character_book"] = serialize_embedded_lorebook(lorebook)
    card: dict[str, Any] = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": data,
    }
    if overlay is not None:
        return overlay.merge(card)
    return card
