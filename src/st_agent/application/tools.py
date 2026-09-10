"""Eight bounded tools bound to the active case by the application."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from PIL import Image
from strands import tool

from st_agent.application.envelope import envelope
from st_agent.application.lifecycle import (
    PHASE_ORDER,
    InvalidTransition,
    advance_phase,
    rewind_phase,
)
from st_agent.domain.canonical import (
    CanonicalDocument,
    CanonicalError,
    document_from_brief,
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
    apply_input_change,
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
    PathRejected,
    atomic_write,
    close_case,
    contained_path,
    export_filename,
    export_path,
    export_stem,
    file_sha256,
    load_manifest,
    save_manifest,
)

MAX_FIELD = 8000
MAX_MARKDOWN = 200_000
MAX_FORMAT_REPAIRS = 2
_PNG_TOKEN = re.compile(r"\bpng\b", re.I)
_PNG_FILENAME = re.compile(r"[\w./\\-]+\.png\b", re.I)
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
    seq: int = 0
    canonical_invalid: int = 0

    def next_op(self, tool: str) -> str:
        self.seq += 1
        return f"{self.invocation_id}:{tool}:{self.seq}"


BRIEF_PHASES = {Phase.setup, Phase.intake, Phase.qa, Phase.draft}
CANONICAL_PHASES = {
    Phase.draft,
    Phase.final_text,
    Phase.build,
    Phase.official_check,
    Phase.validate,
}
BUILD_PHASES = {Phase.draft, Phase.final_text, Phase.build, Phase.official_check, Phase.validate}
SOURCE_PHASES = {Phase.build, Phase.official_check}
VALIDATE_PHASES = {Phase.official_check, Phase.validate}


def _too_long(value: str, limit: int = MAX_FIELD) -> bool:
    return len(value) > limit


def _phase_error(current: Phase, target: Phase) -> dict[str, Any]:
    return envelope(
        ok=False,
        code="invalid-phase",
        message=f"cannot advance from {current} to {target}",
    )


def _require_confirm(case_root: Path) -> dict[str, Any] | None:
    if load_manifest(case_root).build_confirmed:
        return None
    return envelope(
        ok=False,
        code="confirm-required",
        message="Confirm the brief before writing the card.",
    )


def _advance(
    case_root: Path, *targets: Phase, operation_id: str | None = None
) -> tuple[CaseManifest | None, dict[str, Any] | None]:
    manifest = load_manifest(case_root)
    for target in targets:
        if manifest.phase == target:
            continue
        if PHASE_ORDER.index(target) < PHASE_ORDER.index(manifest.phase):
            continue
        try:
            manifest = advance_phase(manifest, target)
        except InvalidTransition:
            return None, _phase_error(manifest.phase, target)
    return save_manifest(case_root, manifest, operation_id=operation_id), None


def _stale(manifest: CaseManifest, *keys: str) -> CaseManifest:
    lineage = dict(manifest.lineage)
    for key in keys:
        if key in lineage:
            lineage[key] = lineage[key].model_copy(update={"stale": True})
    return manifest.model_copy(update={"lineage": lineage})


def _check_portrait_ref(case_root: Path, ref: str) -> dict[str, Any] | None:
    if not ref:
        return None
    raw = Path(ref)
    if raw.is_absolute() or ".." in raw.parts:
        return envelope(
            ok=False, code="path-rejected", message="portrait_ref must stay inside the case"
        )
    try:
        contained_path(case_root, *raw.parts)
    except (PathRejected, OSError, ValueError):
        return envelope(
            ok=False, code="path-rejected", message="portrait_ref must stay inside the case"
        )
    return None


def _intake_text(case_root: Path) -> str:
    path = case_root / WORK_DIR / "intake.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _message_requests_png(text: str) -> bool:
    stripped = _PNG_FILENAME.sub(" ", text)
    return _PNG_TOKEN.search(stripped) is not None


def _latest_format_intent(intake: str) -> str | None:
    intent: str | None = None
    for raw in intake.splitlines():
        line = raw.strip()
        if not line.lower().startswith("user:"):
            continue
        body = line.split(":", 1)[-1]
        if _message_requests_png(body):
            intent = "png"
        elif re.search(r"\bjson\b", body, re.I):
            intent = "json"
    return intent


def _resolve_card_output(case_root: Path, character_output: str, portrait_ref: str) -> str:
    intake = _intake_text(case_root)
    intent = _latest_format_intent(intake)
    if intent == "json":
        return "json"
    if character_output in {"png", "both"}:
        return character_output
    if intent == "png":
        return "both"
    has_portrait = bool(portrait_ref.strip() or load_manifest(case_root).portrait_ref)
    if has_portrait:
        return "both"
    return "json"


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


def _record_lineage(
    case_root: Path,
    key: str,
    source: Path,
    artifact: Path,
    *,
    operation_id: str | None = None,
) -> CaseManifest:
    manifest = load_manifest(case_root)
    lineage = dict(manifest.lineage)
    lineage[key] = Lineage(
        source_hash=file_sha256(source),
        artifact_hash=file_sha256(artifact),
        stale=False,
        source_path=_rel(case_root, source),
    )
    return save_manifest(
        case_root, manifest.model_copy(update={"lineage": lineage}), operation_id=operation_id
    )


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
        gated = _require_confirm(case_root)
        if gated:
            return gated
        if not portrait_ref.strip():
            portrait_ref = load_manifest(case_root).portrait_ref or ""
        character_output = _resolve_card_output(case_root, character_output, portrait_ref)
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
        rejected = _check_portrait_ref(case_root, portrait_ref)
        if rejected:
            return rejected
        manifest = load_manifest(case_root)
        if manifest.phase not in BRIEF_PHASES:
            return _phase_error(manifest.phase, Phase.draft)
        if manifest.phase == Phase.draft:
            save_manifest(
                case_root, apply_input_change(manifest), operation_id=ctx.next_op("save_brief")
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
        canonical = _canonical_path(case_root)
        try:
            auto = roundtrip(document_from_brief(brief))
        except CanonicalError as exc:
            return envelope(ok=False, code="canonical-invalid", message=str(exc))
        atomic_write(canonical, render_canonical(auto))
        manifest, err = _advance(
            case_root, Phase.intake, Phase.draft, operation_id=ctx.next_op("save_brief")
        )
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
            operation_id=ctx.next_op("save_brief"),
        )
        return envelope(
            ok=True,
            artifact_refs=["00-work/brief.md", "03-final-text/canonical.md"],
            revision=manifest.revision,
            hashes={"brief": file_sha256(path), "canonical": file_sha256(canonical)},
        )

    @tool
    def save_content_document(
        kind: Literal["draft", "canonical"],
        markdown: str,
    ) -> dict[str, Any]:
        gated = _require_confirm(case_root)
        if gated:
            return gated
        if _too_long(markdown, MAX_MARKDOWN):
            return envelope(
                ok=False, code="field-too-long", message="document exceeds the size limit"
            )
        if kind == "draft":
            path = contained_path(case_root, "02-drafts", "story.md")
            atomic_write(path, markdown)
            return envelope(
                ok=True,
                artifact_refs=[_rel(case_root, path)],
                hashes={"draft": file_sha256(path)},
                revision=load_manifest(case_root).revision,
            )
        if ctx.canonical_invalid >= 3:
            return envelope(
                ok=False,
                code="canonical-retry-limit",
                message="canonical Markdown failed validation three times; stop retrying",
            )
        try:
            text = roundtrip(parse_canonical(markdown))
            rendered = render_canonical(text)
        except CanonicalError as exc:
            ctx.canonical_invalid += 1
            return envelope(
                ok=False,
                code="canonical-invalid",
                message=str(exc)
                + "; escape heading-style lines with a backslash, for example \\## Title",
            )
        rejected = _check_portrait_ref(case_root, text.brief.delivery.portrait_ref or "")
        if rejected:
            return rejected
        manifest = load_manifest(case_root)
        if manifest.phase not in CANONICAL_PHASES:
            return _phase_error(manifest.phase, Phase.final_text)
        path = _canonical_path(case_root)
        atomic_write(path, rendered)
        if manifest.phase in {Phase.build, Phase.official_check, Phase.validate}:
            updated = _stale(manifest, "character", "lorebook", "png")
            updated = rewind_phase(updated, Phase.final_text)
            saved = save_manifest(case_root, updated, operation_id=ctx.next_op("save_content"))
        else:
            saved, err = _advance(
                case_root, Phase.final_text, operation_id=ctx.next_op("save_content")
            )
            if err:
                return err
            assert saved is not None
        return envelope(
            ok=True,
            artifact_refs=[_rel(case_root, path)],
            revision=saved.revision,
            hashes={"canonical": file_sha256(path)},
        )

    @tool
    def build_character_card() -> dict[str, Any]:
        gated = _require_confirm(case_root)
        if gated:
            return gated
        loaded = _load_canonical(case_root)
        if isinstance(loaded, dict):
            return loaded
        if loaded.character is None:
            return envelope(
                ok=False, code="missing-character", message="canonical character is missing"
            )
        manifest = load_manifest(case_root)
        if manifest.phase not in BUILD_PHASES:
            return _phase_error(manifest.phase, Phase.build)
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
        staged = {export_filename("json", export_stem(case_root)): payload}
        result = validate_card(card)
        exported = promote_exports(case_root, staged, result)
        if not result.ok:
            ctx.format_repairs += 1
            return envelope(ok=False, code="validation-failed", issues=result.issues)
        artifact = exported[0]
        _record_lineage(
            case_root,
            "character",
            _canonical_path(case_root),
            artifact,
            operation_id=ctx.next_op("build_character_card"),
        )
        current = load_manifest(case_root)
        if current.phase in {Phase.official_check, Phase.validate}:
            current = rewind_phase(_stale(current, "png"), Phase.build)
            current = save_manifest(
                case_root, current, operation_id=ctx.next_op("build_character_card")
            )
        else:
            current, err = _advance(
                case_root,
                Phase.final_text,
                Phase.build,
                operation_id=ctx.next_op("build_character_card"),
            )
            if err:
                return err
            assert current is not None
        return envelope(
            ok=True,
            artifact_refs=[_rel(case_root, artifact)],
            hashes={"card": file_sha256(artifact)},
            revision=current.revision,
        )

    @tool
    def build_lorebook() -> dict[str, Any]:
        gated = _require_confirm(case_root)
        if gated:
            return gated
        loaded = _load_canonical(case_root)
        if isinstance(loaded, dict):
            return loaded
        manifest = load_manifest(case_root)
        if manifest.delivery.lorebook in {LorebookDelivery.none, LorebookDelivery.embedded}:
            return envelope(
                ok=True,
                message="no standalone lorebook requested",
                revision=manifest.revision,
            )
        if manifest.phase not in BUILD_PHASES:
            return _phase_error(manifest.phase, Phase.build)
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
        exported = promote_exports(
            case_root, {export_filename("lorebook", export_stem(case_root)): payload}, result
        )
        if not result.ok:
            ctx.format_repairs += 1
            return envelope(ok=False, code="validation-failed", issues=result.issues)
        artifact = exported[0]
        _record_lineage(
            case_root,
            "lorebook",
            _canonical_path(case_root),
            artifact,
            operation_id=ctx.next_op("build_lorebook"),
        )
        current = load_manifest(case_root)
        if current.phase in {Phase.official_check, Phase.validate}:
            current = save_manifest(
                case_root,
                rewind_phase(current, Phase.build),
                operation_id=ctx.next_op("build_lorebook"),
            )
        else:
            current, err = _advance(
                case_root, Phase.final_text, Phase.build, operation_id=ctx.next_op("build_lorebook")
            )
            if err:
                return err
            assert current is not None
        return envelope(
            ok=True,
            artifact_refs=[_rel(case_root, artifact)],
            hashes={"lorebook": file_sha256(artifact)},
            revision=current.revision,
        )

    @tool
    def build_png_card() -> dict[str, Any]:
        gated = _require_confirm(case_root)
        if gated:
            return gated
        loaded = _load_canonical(case_root)
        if isinstance(loaded, dict):
            return loaded
        manifest = load_manifest(case_root)
        if manifest.delivery.card not in {CardDelivery.png, CardDelivery.both}:
            return envelope(ok=True, message="no PNG card requested", revision=manifest.revision)
        if manifest.phase not in BUILD_PHASES:
            return _phase_error(manifest.phase, Phase.build)
        card_path = export_path(case_root, "json")
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
        exported = promote_exports(
            case_root, {export_filename("png", export_stem(case_root)): png}, result
        )
        if not result.ok:
            ctx.format_repairs += 1
            return envelope(ok=False, code="validation-failed", issues=result.issues)
        artifact = exported[0]
        _record_lineage(
            case_root,
            "png",
            _canonical_path(case_root),
            artifact,
            operation_id=ctx.next_op("build_png_card"),
        )
        current = load_manifest(case_root)
        if current.phase in {Phase.official_check, Phase.validate}:
            current = save_manifest(
                case_root,
                rewind_phase(current, Phase.build),
                operation_id=ctx.next_op("build_png_card"),
            )
        else:
            current, err = _advance(
                case_root, Phase.final_text, Phase.build, operation_id=ctx.next_op("build_png_card")
            )
            if err:
                return err
            assert current is not None
        return envelope(
            ok=True,
            artifact_refs=[_rel(case_root, artifact)],
            hashes={"png": file_sha256(artifact)},
            revision=current.revision,
        )

    @tool
    def check_official_sources() -> dict[str, Any]:
        gated = _require_confirm(case_root)
        if gated:
            return gated
        manifest = load_manifest(case_root)
        if manifest.phase not in SOURCE_PHASES:
            return _phase_error(manifest.phase, Phase.official_check)
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
        ok = bool(checks) and all(item["status"] == "pass" for item in checks)
        saved = manifest
        if ok:
            saved, err = _advance(
                case_root, Phase.official_check, operation_id=ctx.next_op("check_official_sources")
            )
            if err:
                return err
            assert saved is not None
        return envelope(
            ok=ok,
            code=None if ok else "source-changed",
            artifact_refs=[_rel(case_root, path)],
            revision=saved.revision,
        )

    @tool
    def validate_deliverables() -> dict[str, Any]:
        gated = _require_confirm(case_root)
        if gated:
            return gated
        result = run_delivery_checks(case_root)
        if not result.ok:
            ctx.format_repairs += 1
            if ctx.format_repairs > MAX_FORMAT_REPAIRS:
                return envelope(ok=False, code="repair-exhausted", issues=result.issues)
            return envelope(ok=False, code="validation-failed", issues=result.issues)
        if load_manifest(case_root).phase not in VALIDATE_PHASES:
            return _phase_error(load_manifest(case_root).phase, Phase.validate)
        saved, err = _advance(
            case_root, Phase.validate, operation_id=ctx.next_op("validate_deliverables")
        )
        if err:
            return err
        return envelope(ok=True, revision=None if saved is None else saved.revision)

    @tool
    def finish_case() -> dict[str, Any]:
        gated = _require_confirm(case_root)
        if gated:
            return gated
        result = run_delivery_checks(case_root)
        if not result.ok:
            return envelope(ok=False, code="delivery-gate", issues=result.issues)
        saved, err = _advance(case_root, Phase.delivery, operation_id=ctx.next_op("finish_case"))
        if err:
            return err
        exported = sorted((case_root / "04-exports").rglob("*"))
        refs = [_rel(case_root, path) for path in exported if path.is_file()]
        close_case(case_root, deliverables=refs)
        if (case_root / WORK_DIR / "case.json").is_file():
            return envelope(ok=False, code="cleanup-pending", artifact_refs=refs)
        ctx.finish_ok = True
        return envelope(
            ok=True,
            artifact_refs=refs,
            revision=None if saved is None else saved.revision,
        )

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
        if _check_portrait_ref(case_root, ref):
            return None
        candidate = contained_path(case_root, *Path(ref).parts)
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
    for kind in ("json", "png", "lorebook"):
        path = export_path(case_root, kind)
        if path.is_file():
            artifacts[path.name] = path.read_bytes()
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
    card_path = export_path(case_root, "json")
    if card_path.is_file():
        issues.extend(validate_card(json.loads(card_path.read_text(encoding="utf-8"))).issues)
    lore_path = export_path(case_root, "lorebook")
    if lore_path.is_file():
        issues.extend(
            validate_lorebook(
                json.loads(lore_path.read_text(encoding="utf-8")), embedded=False
            ).issues
        )
    png_path = export_path(case_root, "png")
    if png_path.is_file() and card_path.is_file():
        issues.extend(
            validate_png(
                png_path.read_bytes(), json.loads(card_path.read_text(encoding="utf-8"))
            ).issues
        )
    return ValidationResult(issues=issues)
