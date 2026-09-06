"""Common tool result envelope and stable failure codes."""

from __future__ import annotations

from typing import Any

from st_agent.services.validators import RepairableIssue


def envelope(
    *,
    ok: bool,
    code: str | None = None,
    message: str = "",
    issues: list[RepairableIssue] | None = None,
    artifact_refs: list[str] | None = None,
    revision: int | None = None,
    hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "code": code,
        "message": message,
        "issues": [
            {"code": item.code, "message": item.message, "path": item.path} for item in issues or []
        ],
        "artifact_refs": artifact_refs or [],
        "revision": revision,
        "hashes": hashes or {},
    }
