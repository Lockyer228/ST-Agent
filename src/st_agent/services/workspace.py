"""File-backed case workspace. User originals are never overwritten."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from st_agent.domain.case import (
    CaseManifest,
    CaseMode,
    Condition,
    DeliveryPreference,
    Phase,
    apply_input_change,
)
from st_agent.paths import source_root as package_source_root

WORK_DIR = "00-work"
ASSETS_DIR = "01-assets"
DRAFTS_DIR = "02-drafts"
FINAL_DIR = "03-final-text"
EXPORTS_DIR = "04-exports"
LAYOUT = (
    WORK_DIR,
    f"{WORK_DIR}/build",
    ASSETS_DIR,
    f"{ASSETS_DIR}/portraits",
    DRAFTS_DIR,
    FINAL_DIR,
    EXPORTS_DIR,
    f"{EXPORTS_DIR}/character-cards",
    f"{EXPORTS_DIR}/lorebooks",
    f"{EXPORTS_DIR}/png-cards",
)
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_FILES = 10
MAX_TOTAL_BYTES = 50 * 1024 * 1024
REJECTED_SUFFIXES = {
    ".gif",
    ".tiff",
    ".tif",
    ".heic",
    ".svg",
    ".doc",
    ".docx",
    ".pdf",
    ".zip",
    ".7z",
    ".rar",
}


class WorkspaceError(ValueError):
    """Workspace operation failed."""


class PathRejected(WorkspaceError):
    """Path is outside the case root or inside application source."""


class LimitExceeded(WorkspaceError):
    """An input count, size, or pixel limit was exceeded."""


class UnsupportedInput(WorkspaceError):
    """The file type is not accepted."""


class CaseLocked(WorkspaceError):
    """Another writer holds the case lock."""


class ClosedCaseError(WorkspaceError):
    """The case is closed or abandoned; Q&A cannot be restored."""


@dataclass(frozen=True)
class ResumePlan:
    phase: Phase
    reason: str


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "story"


def canonicalize_root(path: Path) -> Path:
    return path.expanduser().resolve()


def contained_path(root: Path, *parts: str) -> Path:
    root = canonicalize_root(root)
    candidate = Path(root, *parts).resolve()
    if not candidate.is_relative_to(root):
        raise PathRejected("path escapes the workspace")
    return candidate


def _assert_not_inside_source(root: Path, source: Path) -> None:
    resolved = canonicalize_root(root)
    origin = canonicalize_root(source)
    if resolved == origin or resolved.is_relative_to(origin):
        raise PathRejected("workspace must not be inside application source")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, data: str | bytes, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(data, str):
        tmp.write_text(data, encoding=encoding)
    else:
        tmp.write_bytes(data)
    with tmp.open("r+b") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    if path.exists() and path.name == "case.json":
        bak = path.with_name(path.name + ".bak")
        bak.write_bytes(path.read_bytes())
        with bak.open("r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
    tmp.replace(path)


def _recover_temps(case_root: Path) -> None:
    work = case_root / WORK_DIR
    if not work.is_dir():
        return
    for tmp in work.rglob("*.tmp"):
        tmp.unlink(missing_ok=True)


@contextmanager
def case_lock(case_root: Path):
    lock_path = canonicalize_root(case_root) / "case.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    try:
        if os.name == "nt":
            import msvcrt

            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise CaseLocked("case is locked") from exc
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise CaseLocked("case is locked") from exc
        yield
    finally:
        handle.close()


def _status_md(manifest: CaseManifest) -> str:
    blocker = manifest.blocker.message if manifest.blocker else "none"
    question = manifest.pending_question or "none"
    files = "\n".join(f"  - {item.relative_path}" for item in manifest.inputs) or "  - none"
    return (
        f"# Case status\n\n"
        f"- Story: {manifest.story_name}\n"
        f"- Phase: {manifest.phase}\n"
        f"- Condition: {manifest.condition}\n"
        f"- Revision: {manifest.revision}\n"
        f"- Blocker: {blocker}\n"
        f"- Unresolved: {question}\n"
        f"- Next step: resume {manifest.phase}\n"
        f"- Files:\n{files}\n"
    )


def _readme(story_name: str, state: str = "active") -> str:
    return (
        f"# {story_name}\n\n"
        f"Case state: {state}.\n\n"
        "Deliverables will be listed here after export.\n"
    )


def create_case(
    workspace_root: Path,
    story_name: str,
    *,
    source_root: Path | None = None,
    mode: CaseMode | str = CaseMode.new,
) -> Path:
    _assert_not_inside_source(workspace_root, source_root or package_source_root())
    parent = canonicalize_root(workspace_root)
    parent.mkdir(parents=True, exist_ok=True)
    case_root = parent / slugify(story_name)
    _assert_not_inside_source(case_root, source_root or package_source_root())
    if (case_root / WORK_DIR / "case.json").is_file():
        raise WorkspaceError("an active case already exists in this folder")
    for rel in LAYOUT:
        (case_root / rel).mkdir(parents=True, exist_ok=True)
    manifest = CaseManifest(
        case_id=uuid.uuid4().hex,
        story_name=slugify(story_name),
        mode=CaseMode(mode),
        phase=Phase.setup,
        condition=Condition.active,
        revision=0,
        operation_id=uuid.uuid4().hex,
        delivery=DeliveryPreference(),
    )
    atomic_write(case_root / "README.md", _readme(story_name))
    atomic_write(
        contained_path(case_root, WORK_DIR, "case.json"),
        manifest.model_dump_json(indent=2),
    )
    atomic_write(contained_path(case_root, WORK_DIR, "status.md"), _status_md(manifest))
    atomic_write(contained_path(case_root, WORK_DIR, "intake.md"), "")
    return case_root


def _parse_manifest_text(text: str) -> CaseManifest:
    try:
        return CaseManifest.model_validate_json(text)
    except ValueError:
        data, _end = json.JSONDecoder().raw_decode(text.lstrip())
        return CaseManifest.model_validate(data)


def _read_manifest_file(path: Path) -> tuple[CaseManifest, bool]:
    text = path.read_text(encoding="utf-8")
    try:
        return CaseManifest.model_validate_json(text), False
    except (UnicodeDecodeError, ValueError):
        try:
            return _parse_manifest_text(text), True
        except (UnicodeDecodeError, ValueError, TypeError):
            bak = path.with_name(path.name + ".bak")
            if bak.is_file():
                return _parse_manifest_text(bak.read_text(encoding="utf-8")), True
            raise


def load_manifest(case_root: Path) -> CaseManifest:
    path = case_root / WORK_DIR / "case.json"
    if not path.is_file():
        readme = case_root / "README.md"
        if readme.is_file():
            try:
                text = readme.read_text(encoding="utf-8").lower()
            except UnicodeDecodeError as exc:
                raise WorkspaceError("case manifest is unreadable") from exc
            if "closed" in text or "abandoned" in text:
                raise ClosedCaseError("closed case cannot restore Q&A")
        raise ClosedCaseError("no active case manifest")
    try:
        manifest, dirty = _read_manifest_file(path)
    except (UnicodeDecodeError, ValueError, TypeError, OSError) as exc:
        raise WorkspaceError("case manifest is unreadable") from exc
    if dirty:
        atomic_write(path, manifest.model_dump_json(indent=2))
    return manifest


def save_manifest(
    case_root: Path,
    manifest: CaseManifest,
    *,
    operation_id: str | None = None,
) -> CaseManifest:
    path = contained_path(case_root, WORK_DIR, "case.json")
    current, _dirty = _read_manifest_file(path)
    if operation_id and current.operation_id == operation_id:
        return current
    updated = manifest.model_copy(
        update={
            "operation_id": operation_id or uuid.uuid4().hex,
            "revision": current.revision + 1,
        }
    )
    atomic_write(path, updated.model_dump_json(indent=2))
    atomic_write(contained_path(case_root, WORK_DIR, "status.md"), _status_md(updated))
    return updated


def _kind_for(path: Path) -> str:
    from st_agent.services.readers import InputKind, sniff_path

    suffix = path.suffix.lower()
    if suffix in REJECTED_SUFFIXES:
        raise UnsupportedInput(f"unsupported file type: {suffix}")
    kind = sniff_path(path)
    if kind in {InputKind.image, InputKind.png_card}:
        return "image"
    return kind.value


def _asset_dir(kind: str) -> str:
    if kind == "image":
        return f"{ASSETS_DIR}/portraits"
    return ASSETS_DIR


def _manifest_totals(case_root: Path, refs: Sequence) -> tuple[int, int]:
    total = 0
    for item in refs:
        path = case_root / item.relative_path
        if path.is_file():
            total += path.stat().st_size
    return len(refs), total


def _check_limits(path: Path, kind: str, *, existing_count: int, existing_bytes: int) -> None:
    size = path.stat().st_size
    if existing_count >= MAX_FILES:
        raise LimitExceeded(f"{path.name} exceeds the 10-file case limit")
    if existing_bytes + size > MAX_TOTAL_BYTES:
        raise LimitExceeded(f"{path.name} exceeds the 50 MiB case limit")
    if kind in {"text", "json"} and size > MAX_TEXT_BYTES:
        raise LimitExceeded(f"{path.name} exceeds the 2 MiB text/JSON limit")
    if kind == "image":
        if size > MAX_IMAGE_BYTES:
            raise LimitExceeded(f"{path.name} exceeds the 20 MiB image limit")
        try:
            with Image.open(path) as image:
                width, height = image.size
        except UnidentifiedImageError:
            raise UnsupportedInput(
                "the file is not a readable PNG, JPEG, WebP, or BMP image"
            ) from None
        except OSError:
            raise UnsupportedInput("the image file is damaged and cannot be read") from None
        if width * height > MAX_PIXELS:
            raise LimitExceeded(f"{path.name} exceeds the 16 megapixel limit")


def save_user_inputs(case_root: Path, sources: Sequence[Path]) -> list:
    from st_agent.domain.case import ArtifactRef

    manifest = load_manifest(case_root)
    refs = list(manifest.inputs)
    count, total = _manifest_totals(case_root, refs)
    for source in sources:
        origin = source.resolve()
        kind = _kind_for(origin)
        _check_limits(origin, kind, existing_count=count, existing_bytes=total)
        dest_dir = contained_path(case_root, *_asset_dir(kind).split("/"))
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / origin.name
        if dest.exists():
            dest = dest_dir / f"{dest.stem}-{uuid.uuid4().hex[:8]}{dest.suffix}"
        dest.write_bytes(origin.read_bytes())
        if dest.resolve() == origin:
            raise WorkspaceError("refusing to write over the user original")
        count += 1
        total += dest.stat().st_size
        rel = dest.relative_to(canonicalize_root(case_root)).as_posix()
        refs.append(
            ArtifactRef(
                logical_id=dest.stem,
                relative_path=rel,
                sha256=file_sha256(dest),
                kind=kind,
            )
        )
    names = "\n".join(f"- {item.relative_path}" for item in refs)
    atomic_write(contained_path(case_root, WORK_DIR, "inputs.md"), f"Accepted inputs:\n{names}\n")
    manifest.inputs = refs
    save_manifest(case_root, apply_input_change(manifest) if refs else manifest)
    return refs


def append_intake(case_root: Path, text: str) -> None:
    path = contained_path(case_root, WORK_DIR, "intake.md")
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    addition = text if text.endswith("\n") else f"{text}\n"
    atomic_write(path, current + addition)


def compact_context(case_root: Path, max_chars: int = 800) -> dict[str, object]:
    manifest = load_manifest(case_root)
    work = case_root / WORK_DIR

    def _snippet(name: str) -> str:
        path = work / name
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")[:max_chars]

    files = []
    for path in sorted(case_root.rglob("*")):
        if not path.is_file() or path.suffix == ".tmp" or path.name == "case.lock":
            continue
        rel = path.relative_to(case_root).as_posix()
        files.append({"path": rel, "sha256": file_sha256(path)})
    return {
        "phase": str(manifest.phase),
        "condition": str(manifest.condition),
        "intake": _snippet("intake.md"),
        "brief": _snippet("brief.md"),
        "files": files,
    }


def resume_case(case_root: Path) -> ResumePlan:
    _recover_temps(case_root)
    if not (case_root / WORK_DIR / "case.json").is_file():
        raise ClosedCaseError("closed case cannot restore Q&A")
    manifest = load_manifest(case_root)
    if manifest.condition == Condition.cleanup_pending:
        close_case(case_root)
        return ResumePlan(phase=Phase.cleanup, reason="cleanup_only")
    if manifest.lineage:
        stale = False
        lineage = {}
        for key, item in manifest.lineage.items():
            source = case_root / item.source_path
            digest = file_sha256(source) if source.is_file() else ""
            if item.source_hash != digest:
                lineage[key] = item.model_copy(update={"stale": True})
                stale = True
            else:
                lineage[key] = item
        if stale:
            updated = apply_input_change(manifest.model_copy(update={"lineage": lineage}))
            save_manifest(case_root, updated)
            return ResumePlan(phase=Phase.intake, reason="stale_lineage")
    return ResumePlan(phase=manifest.phase, reason="unfinished")


def _remove_work(work: Path) -> None:
    if work.is_symlink() or work.is_junction():
        work.unlink()
        return
    if not work.is_dir():
        return
    for child in list(work.iterdir()):
        if child.is_symlink() or child.is_junction():
            child.unlink()
        elif child.is_file():
            child.unlink()
        elif child.is_dir():
            _remove_work(child)
    work.rmdir()


def close_case(
    case_root: Path, *, state: str = "closed", deliverables: Sequence[str] | None = None
) -> None:
    story = case_root.name
    if (case_root / WORK_DIR / "case.json").is_file():
        story = load_manifest(case_root).story_name
    if deliverables:
        lines = [f"# {story}", "", f"Case state: {state}.", "", "Deliverables:"]
        lines.extend(f"- {item}" for item in deliverables)
        atomic_write(case_root / "README.md", "\n".join(lines) + "\n")
    else:
        atomic_write(case_root / "README.md", _readme(story, state=state))
    try:
        _remove_work(case_root / WORK_DIR)
    except OSError:
        if (case_root / WORK_DIR / "case.json").is_file():
            pending = load_manifest(case_root).model_copy(
                update={"phase": Phase.cleanup, "condition": Condition.cleanup_pending}
            )
            save_manifest(case_root, pending)


def abandon_case(case_root: Path) -> None:
    close_case(case_root, state="abandoned")
