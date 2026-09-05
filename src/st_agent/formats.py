"""Frozen format profiles and modification merge (unknown fields preserved)."""

from __future__ import annotations

import copy
import json
from importlib.resources import files
from typing import Any


def load_format_profile(name: str) -> dict[str, Any]:
    path = files("st_agent.resources.formats").joinpath(f"{name}.json")
    return json.loads(path.read_text(encoding="utf-8"))


def apply_card_modification(source: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(source)
    _deep_merge(merged, updates)
    return merged


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> None:
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
