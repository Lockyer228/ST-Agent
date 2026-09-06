"""Eight bounded tools bound to the active case by the application."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from PIL import Image
from strands import tool

from st_agent.application.envelope import envelope
from st_agent.application.lifecycle import InvalidTransition, advance_phase
from st_agent.domain.canonical import (
    CanonicalDocument,
    CanonicalError,
    parse_canonical,
    render_canonical,
    roundtrip,
)
from st_agent.domain.case import (
    CardDelivery,
    CaseManifest,
    DeliveryPreference,
    Lineage,
    LorebookDelivery,
    Phase,
)
from st_agent.domain.content import CaseBrief, DeliveryPreferences
from st_agent.formats import extract_source_overlay
from st_agent.official_sources import (
    OfficialSourceService,
    load_source_manifest,
    production_sources,
)
from st_agent.png_card import PngCardCodec
from st_agent.services.serializers import (
    FormatError,
    serialize_character,
    serialize_standalone_lorebook,
)
from st_agent.services.validators import (
    RepairableIssue,
    ValidationResult,
    promote_exports,
    validate_card,
    validate_lineage,
    validate_lorebook,
    validate_png,
    validate_requested_output,
)
from st_agent.services.workspace import (
    FINAL_DIR,
    WORK_DIR,
    atomic_write,
    close_case,
    contained_path,
    file_sha256,
    load_manifest,
    save_manifest,
)

MAX_FIELD = 8000
MAX_MARKDOWN = 200_000
MAX_FORMAT_REPAIRS = 2
TOOL_NAMES = (
    "save_brief",
    "save_content_document",
    "build_character_card",
    "build_lorebook",
    "build_png_card",
    "check_official_sources",
    "validate_deliverables",
    "finish_case",
)


@dataclass
class ToolContext:
    case_root: Path
    invocation_id: str
    operation_id: str
    format_repairs: int = 0
    finish_ok: bool = False
    source_service: OfficialSourceService | None = None


def _too_long(value: str, limit: int = MAX_FIELD) -> bool:
    return len(value) > limit


def _advance(case_root: Path, *targets: Phase) -> tuple[CaseManifest | None, dict[str, Any] | None]:
    manifest = load_manifest(case_root)
    for target in targets:
        if manifest.phase == target:
            continue
        try:
            manifest = advance_phase(manifest, target)
        except InvalidTransition:
            return None, envelope(
                ok=False,
                code="invalid-phase",
                message=f"cannot advance from {manifest.phase} to {target}",
            )
    return save_manifest(case_root, manifest), None


def _canonical_path(case_root: Path) -> Path:
    return contained_path(case_root, FINAL_DIR, "canonical.md")


def _load_canonical(case_root: Path) -> CanonicalDocument | dict[str, Any]:
    path = _canonical_path(case_root)
    if not path.is_file():
        return envelope(ok=False, code="missing-canonical", message="canonical Markdown is missing")
    try:
        return roundtrip(parse_canonical(path.read_text(encoding="utf-8")))
    except CanonicalError as exc:
        return envelope(ok=False, code="canonical-invalid", message=str(exc))


def _overlay_from_inputs(case_root: Path, manifest: CaseManifest):
    for item in manifest.inputs:
        path = case_root / item.relative_path
        if item.kind != "json" or not path.is_file():
            continue
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(card, dict) and card.get("spec") == "chara_card_v3":
            return extract_source_overlay(card, source_hash=item.sha256)
    return None


def _rel(case_root: Path, path: Path) -> str:
    return path.relative_to(case_root).as_posix()


def _record_lineage(case_root: Path, key: str, source: Path, artifact: Path) -> CaseManifest:
    manifest = load_manifest(case_root)
    lineage = dict(manifest.lineage)
    lineage[key] = Lineage(
        source_hash=file_sha256(source),
        artifact_hash=file_sha256(artifact),
        stale=False,
        source_path=_rel(case_root, source),
    )
    return save_manifest(case_root, manifest.model_copy(update={"lineage": lineage}))


def bind_tools(ctx: ToolContext) -> list[Any]:
    case_root = ctx.case_root

    @tool
    def save_brief(
        experience_goal: str,
        player_role: str,
        characters: str,
        world: str,
        tone_and_boundaries: str,
        mechanics: str,
        information_reveals: str,
        opening: str,
        creative_authorization: str,
        character_output: Literal["json", "png", "both"] = "json",
        lorebook_output: Literal["none", "standalone", "embedded", "both"] = "none",
        portrait_ref: str = "",
    ) -> dict[str, Any]:
        fields = (
            experience_goal,
            player_role,
            characters,
            world,
            tone_and_boundaries,
            mechanics,
            information_reveals,
            opening,
            creative_authorization,
        )
        if any(_too_long(item) for item in fields):
            return envelope(
                ok=False, code="field-too-long", message="a brief field exceeds the size limit"
            )
        brief = CaseBrief(
            experience_goal=experience_goal,
            player_role=player_role,
            characters=characters,
            world=world,
            tone_and_boundaries=tone_and_boundaries,
            mechanics=mechanics,
            information_reveals=information_reveals,
            opening=opening,
            creative_authorization=creative_authorization,
            delivery=DeliveryPreferences(
                character=CardDelivery(character_output),
                lorebook=LorebookDelivery(lorebook_output),
                portrait_ref=portrait_ref or None,
            ),
        )
        path = contained_path(case_root, WORK_DIR, "brief.md")
        atomic_write(path, _brief_markdown(brief))
        manifest, err = _advance(case_root, Phase.intake, Phase.draft)
        if err:
            return err
        assert manifest is not None
        manifest = save_manifest(
            case_root,
            manifest.model_copy(
                update={
                    "delivery": DeliveryPreference(
                        card=CardDelivery(character_output),
                        lorebook=LorebookDelivery(lorebook_output),
                    )
                }
            ),
        )
        return envelope(
            ok=True,
            artifact_refs=["00-work/brief.md"],
            revision=manifest.revision,
            hashes={"brief": file_sha256(path)},
        )

    @tool
    def save_content_document(
        kind: Literal["draft", "canonical"],
        markdown: str,
    ) -> dict[str, Any]:
        if _too_long(markdown, MAX_MARKDOWN):
            return envelope(
                ok=False, code="field-too-long", message="document exceeds the size limit"
            )
        if kind == "draft":
            path = contained_path(case_root, "02-drafts", "story.md")
            atomic_write(path, markdown)
            return envelope(
                ok=True, artifact_refs=[_rel(case_root, path)], hashes={"draft": file_sha256(path)}
            )
        try:
            text = roundtrip(parse_canonical(markdown))
            rendered = render_canonical(text)
        except CanonicalError as exc:
            return envelope(
                ok=False,
                code="canonical-invalid",
                message=str(exc)
                + "; escape heading-style lines with a backslash, for example \\## Title",
            )
        path = _canonical_path(case_root)
        atomic_write(path, rendered)
        manifest, err = _advance(case_root, Phase.final_text)
        if err:
            return err
        assert manifest is not None
        return envelope(
            ok=True,
            artifact_refs=[_rel(case_root, path)],
            revision=manifest.revision,
            hashes={"canonical": file_sha256(path)},
        )

    @tool
    def build_character_card() -> dict[str, Any]:
        loaded = _load_canonical(case_root)
        if isinstance(loaded, dict):
            return loaded
        if loaded.character is None:
            return envelope(
                ok=False, code="missing-character", message="canonical character is missing"
            )
        manifest = load_manifest(case_root)
        lorebook = (
            loaded.lorebook
            if manifest.delivery.lorebook in {LorebookDelivery.embedded, LorebookDelivery.both}
            else None
        )
        overlay = _overlay_from_inputs(case_root, manifest)
        try:
            card = serialize_character(loaded.character, lorebook=lorebook, overlay=overlay)
        except FormatError as exc:
            return envelope(ok=False, code="format-error", message=str(exc))
        payload = json.dumps(card, ensure_ascii=False, indent=2).encode("utf-8")
        staged = {"card.json": payload}
        result = validate_card(card)
        exported = promote_exports(case_root, staged, result)
        if not result.ok:
            ctx.format_repairs += 1
            return envelope(ok=False, code="validation-failed", issues=result.issues)
        manifest, err = _advance(case_root, Phase.build)
        if err:
            return err
        artifact = exported[0]
        _record_lineage(case_root, "character", _canonical_path(case_root), artifact)
        return envelope(
            ok=True,
            artifact_refs=[_rel(case_root, artifact)],
            hashes={"card": file_sha256(artifact)},
        )

    @tool
    def build_lorebook() -> dict[str, Any]:
        loaded = _load_canonical(case_root)
        if isinstance(loaded, dict):
            return loaded
        manifest = load_manifest(case_root)
        if manifest.delivery.lorebook in {LorebookDelivery.none, LorebookDelivery.embedded}:
            return envelope(ok=True, message="no standalone lorebook requested")
        if loaded.lorebook is None:
            return envelope(
                ok=False, code="missing-lorebook", message="canonical lorebook is missing"
            )
        try:
            book = serialize_standalone_lorebook(loaded.lorebook)
        except FormatError as exc:
            return envelope(ok=False, code="format-error", message=str(exc))
        payload = json.dumps(book, ensure_ascii=False, indent=2).encode("utf-8")
        result = validate_lorebook(book, embedded=False)
        exported = promote_exports(case_root, {"lorebook.json": payload}, result)
        if not result.ok:
            ctx.format_repairs += 1
            return envelope(ok=False, code="validation-failed", issues=result.issues)
        artifact = exported[0]
        _record_lineage(case_root, "lorebook", _canonical_path(case_root), artifact)
        _advance(case_root, Phase.build)
        return envelope(
            ok=True,
            artifact_refs=[_rel(case_root, artifact)],
            hashes={"lorebook": file_sha256(artifact)},
        )

    @tool
    def build_png_card() -> dict[str, Any]:
        loaded = _load_canonical(case_root)
        if isinstance(loaded, dict):
            return loaded
        manifest = load_manifest(case_root)
        if manifest.delivery.card not in {CardDelivery.png, CardDelivery.both}:
            return envelope(ok=True, message="no PNG card requested")
        card_path = case_root / "04-exports" / "character-cards" / "card.json"
        if not card_path.is_file():
            return envelope(ok=False, code="missing-card", message="JSON card must be built first")
        card = json.loads(card_path.read_text(encoding="utf-8"))
        portrait = _portrait_path(case_root, loaded)
        if portrait is None:
            return envelope(
                ok=False, code="missing-portrait", message="a portrait is required for PNG delivery"
            )
        png = PngCardCodec().write(Image.open(portrait), card)
        result = validate_png(png, card)
        exported = promote_exports(case_root, {"card.png": png}, result)
        if not result.ok:
            ctx.format_repairs += 1
            return envelope(ok=False, code="validation-failed", issues=result.issues)
        artifact = exported[0]
        _record_lineage(case_root, "png", _canonical_path(case_root), artifact)
        _advance(case_root, Phase.build)
        return envelope(
            ok=True,
            artifact_refs=[_rel(case_root, artifact)],
            hashes={"png": file_sha256(artifact)},
        )

    @tool
    def check_official_sources() -> dict[str, Any]:
        service = ctx.source_service or OfficialSourceService()
        owned = ctx.source_service is None
        checks = []
        try:
            for item in production_sources(load_source_manifest()):
                result = service.check(item["id"])
                checks.append(
                    {
                        "source_id": result.source_id,
                        "status": result.status,
                        "url": result.url,
                        "agrees_with_local_profile": result.agrees_with_local_profile,
                    }
                )
        finally:
            if owned:
                service.close()
        path = contained_path(case_root, WORK_DIR, "official-evidence.json")
        atomic_write(path, json.dumps(checks, indent=2))
        manifest, err = _advance(case_root, Phase.official_check)
        if err:
            return err
        ok = bool(checks) and all(item["status"] == "pass" for item in checks)
        return envelope(
            ok=ok,
            code=None if ok else "source-changed",
            artifact_refs=[_rel(case_root, path)],
            revision=None if manifest is None else manifest.revision,
        )

    @tool
    def validate_deliverables() -> dict[str, Any]:
        result = run_delivery_checks(case_root)
        if not result.ok:
            ctx.format_repairs += 1
            if ctx.format_repairs > MAX_FORMAT_REPAIRS:
                return envelope(ok=False, code="repair-exhausted", issues=result.issues)
            return envelope(ok=False, code="validation-failed", issues=result.issues)
        manifest, err = _advance(case_root, Phase.validate)
        if err:
            return err
        return envelope(ok=True, revision=None if manifest is None else manifest.revision)

    @tool
    def finish_case() -> dict[str, Any]:
        result = run_delivery_checks(case_root)
        if not result.ok:
            return envelope(ok=False, code="delivery-gate", issues=result.issues)
        _advance(case_root, Phase.delivery)
        exported = sorted((case_root / "04-exports").rglob("*"))
        refs = [_rel(case_root, path) for path in exported if path.is_file()]
        story = load_manifest(case_root).story_name
        lines = [f"# {story}", "", "Case state: closed.", "", "Deliverables:"]
        lines.extend(f"- {ref}" for ref in refs)
        atomic_write(case_root / "README.md", "\n".join(lines) + "\n")
        close_case(case_root)
        ctx.finish_ok = True
        return envelope(ok=True, artifact_refs=refs)

    return [
        save_brief,
        save_content_document,
        build_character_card,
        build_lorebook,
        build_png_card,
        check_official_sources,
        validate_deliverables,
        finish_case,
    ]


def _brief_markdown(brief: CaseBrief) -> str:
    from st_agent.domain.canonical import render_canonical

    return render_canonical(CanonicalDocument(brief=brief))


def _portrait_path(case_root: Path, doc: CanonicalDocument) -> Path | None:
    ref = doc.brief.delivery.portrait_ref
    if ref:
        candidate = case_root / ref
        if candidate.is_file():
            return candidate
    manifest = load_manifest(case_root)
    for item in manifest.inputs:
        if item.kind == "image":
            path = case_root / item.relative_path
            if path.is_file():
                return path
    portraits = case_root / "01-assets" / "portraits"
    if portraits.is_dir():
        for path in portraits.iterdir():
            if path.is_file():
                return path
    return None


def _export_bytes(case_root: Path) -> dict[str, bytes]:
    artifacts: dict[str, bytes] = {}
    exports = case_root / "04-exports"
    mapping = {
        "character-cards/card.json": "card.json",
        "png-cards/card.png": "card.png",
        "lorebooks/lorebook.json": "lorebook.json",
    }
    for rel, name in mapping.items():
        path = exports / rel
        if path.is_file():
            artifacts[name] = path.read_bytes()
    return artifacts


def run_delivery_checks(case_root: Path) -> ValidationResult:
    manifest = load_manifest(case_root)
    prefs = DeliveryPreferences(
        character=manifest.delivery.card, lorebook=manifest.delivery.lorebook
    )
    artifacts = _export_bytes(case_root)
    issues = []
    issues.extend(validate_requested_output(prefs, artifacts).issues)
    issues.extend(validate_lineage(manifest.lineage).issues)
    evidence = case_root / WORK_DIR / "official-evidence.json"
    if not evidence.is_file():
        issues.append(RepairableIssue("source-evidence", "official source evidence is missing"))
    else:
        rows = json.loads(evidence.read_text(encoding="utf-8"))
        if not rows or any(item.get("status") != "pass" for item in rows):
            issues.append(
                RepairableIssue("source-evidence", "official source evidence is not current")
            )
    card_path = case_root / "04-exports" / "character-cards" / "card.json"
    if card_path.is_file():
        issues.extend(validate_card(json.loads(card_path.read_text(encoding="utf-8"))).issues)
    lore_path = case_root / "04-exports" / "lorebooks" / "lorebook.json"
    if lore_path.is_file():
        issues.extend(
            validate_lorebook(
                json.loads(lore_path.read_text(encoding="utf-8")), embedded=False
            ).issues
        )
    png_path = case_root / "04-exports" / "png-cards" / "card.png"
    if png_path.is_file() and card_path.is_file():
        issues.extend(
            validate_png(
                png_path.read_bytes(), json.loads(card_path.read_text(encoding="utf-8"))
            ).issues
        )
    return ValidationResult(issues=issues)
