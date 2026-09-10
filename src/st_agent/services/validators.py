"""Deterministic validators. Failed builds stay out of 04-exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from st_agent.domain.case import CardDelivery, Lineage, LorebookDelivery
from st_agent.domain.content import DeliveryPreferences
from st_agent.formats import load_format_profile
from st_agent.png_card import PngCardCodec
from st_agent.services.serializers import SUPPORTED_POSITIONS
from st_agent.services.workspace import EXPORTS_DIR, WORK_DIR


@dataclass
class RepairableIssue:
    code: str
    message: str
    path: str = ""


@dataclass
class ValidationResult:
    issues: list[RepairableIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def _result(*issues: RepairableIssue) -> ValidationResult:
    return ValidationResult(issues=list(issues))


def validate_card(card: dict[str, Any]) -> ValidationResult:
    profile = load_format_profile("character-card-v3")
    issues: list[RepairableIssue] = []
    if card.get("spec") != profile["spec"]:
        issues.append(RepairableIssue("card-spec", "card spec must be chara_card_v3"))
    if card.get("spec_version") != profile["spec_version"]:
        issues.append(RepairableIssue("card-version", "card spec_version must be 3.0"))
    data = card.get("data")
    if not isinstance(data, dict):
        issues.append(RepairableIssue("card-data", "card data object is missing"))
        return _result(*issues)
    for name in profile["required_data_fields"]:
        if name not in data:
            issues.append(RepairableIssue("card-field", f"missing data.{name}", name))
    name = data.get("name")
    if isinstance(name, str) and not name.strip():
        issues.append(RepairableIssue("card-name", "card name must not be blank", "name"))
    return _result(*issues)


def validate_lorebook(book: dict[str, Any], *, embedded: bool) -> ValidationResult:
    issues: list[RepairableIssue] = []
    profile = load_format_profile("st-character-book" if embedded else "st-lorebook")
    if embedded:
        required = list(profile["required_entry_fields"])
    else:
        required = [
            *profile["entry_key_fields"],
            profile["content_field"],
            profile["constant_field"],
            profile["order_field"],
        ]
    entries = book.get("entries")
    if embedded:
        if not isinstance(entries, list):
            return _result(RepairableIssue("lorebook-shape", "embedded entries must be an array"))
        rows = entries
    else:
        if not isinstance(entries, dict):
            return _result(RepairableIssue("lorebook-shape", "standalone entries must be a map"))
        rows = list(entries.values())
    for row in rows:
        if not isinstance(row, dict):
            issues.append(RepairableIssue("lorebook-entry", "entry is not an object"))
            continue
        for name in required:
            if name not in row:
                issues.append(RepairableIssue("lorebook-field", f"missing {name}", name))
        position = row.get("position")
        if embedded and position not in SUPPORTED_POSITIONS:
            issues.append(RepairableIssue("lorebook-position", f"unsupported position: {position}"))
        if not embedded and position not in {0, 1}:
            issues.append(RepairableIssue("lorebook-position", f"bad ST position: {position}"))
        if not (row.get("content") or "").strip():
            issues.append(RepairableIssue("lorebook-content", "entry content is empty"))
    return _result(*issues)


def _artifact_role(name: str) -> str:
    base = Path(name).name.lower()
    if base.endswith(".png"):
        return "png"
    if "lorebook" in base:
        return "lorebook"
    if base.endswith(".json"):
        return "json"
    return "other"


def validate_requested_output(
    prefs: DeliveryPreferences, artifacts: dict[str, bytes]
) -> ValidationResult:
    issues: list[RepairableIssue] = []
    roles = {_artifact_role(name) for name in artifacts}
    if prefs.character in {CardDelivery.json, CardDelivery.both} and "json" not in roles:
        issues.append(RepairableIssue("output-json", "JSON card was requested but not built"))
    if prefs.character in {CardDelivery.png, CardDelivery.both} and "png" not in roles:
        issues.append(RepairableIssue("output-png", "PNG card was requested but not built"))
    if prefs.lorebook in {LorebookDelivery.standalone, LorebookDelivery.both}:
        if "lorebook" not in roles:
            issues.append(RepairableIssue("output-lorebook", "standalone lorebook was not built"))
    if prefs.lorebook in {LorebookDelivery.embedded, LorebookDelivery.both}:
        if "json" not in roles and "png" not in roles:
            issues.append(RepairableIssue("output-embedded", "embedded lorebook needs a card"))
    return _result(*issues)


def validate_lineage(lineage: dict[str, Lineage]) -> ValidationResult:
    issues: list[RepairableIssue] = []
    for key, item in lineage.items():
        if item.stale:
            issues.append(RepairableIssue("lineage-stale", f"{key} source hash is stale", key))
        if not item.artifact_hash:
            issues.append(RepairableIssue("lineage-artifact", f"{key} missing artifact hash", key))
    return _result(*issues)


def validate_png(png: bytes, card: dict[str, Any]) -> ValidationResult:
    try:
        extracted = PngCardCodec().read(png)
    except ValueError as exc:
        return _result(RepairableIssue("png-read", str(exc)))
    if extracted.get("data") != card.get("data"):
        return _result(RepairableIssue("png-semantic", "PNG read-back does not match source"))
    return _result()


def _export_dir(case_root: Path, name: str) -> Path:
    base = name.lower()
    if base.endswith(".png"):
        folder = "png-cards"
    elif "lorebook" in base:
        folder = "lorebooks"
    else:
        folder = "character-cards"
    dest = case_root / EXPORTS_DIR / folder
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def promote_exports(
    case_root: Path, staged: dict[str, bytes], result: ValidationResult
) -> list[Path]:
    build = case_root / WORK_DIR / "build"
    build.mkdir(parents=True, exist_ok=True)
    for name, data in staged.items():
        (build / name).write_bytes(data)
    if not result.ok:
        return []
    exported: list[Path] = []
    for name, data in staged.items():
        dest = _export_dir(case_root, name) / name
        dest.write_bytes(data)
        exported.append(dest)
    return exported
