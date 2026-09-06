"""Allowlisted official-source retrieval with pass / unavailable results."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any

import httpx

MAX_BYTES = 1_000_000
TIMEOUT_S = 10.0
ATTEMPTS = 3


@dataclass(frozen=True)
class SourceCheck:
    source_id: str
    url: str
    status: str
    fingerprint: str | None
    agrees_with_local_profile: bool
    detail: str
    retrieved_at: str | None = None
    title: str | None = None
    authority_class: str = ""


def load_source_manifest() -> dict[str, Any]:
    path = files("st_agent.resources.formats").joinpath("source-manifest.json")
    return json.loads(path.read_text(encoding="utf-8"))


def production_sources(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in manifest["sources"] if item.get("role") != "unavailable-fixture"]


def _allowlisted_hosts(manifest: dict[str, Any]) -> set[str]:
    hosts: set[str] = set()
    for item in manifest["sources"]:
        hosts.add(httpx.URL(item["url"]).host)
        documented = item.get("documented_url")
        if documented:
            hosts.add(httpx.URL(documented).host)
    return hosts


def _title(body: str) -> str | None:
    heading = re.search(r"^#\s+(.+)$", body, re.M)
    if heading:
        return heading.group(1).strip()
    html = re.search(r"<title>([^<]+)</title>", body, re.I)
    if html:
        return html.group(1).strip()
    return None


def _result(
    source_id: str,
    url: str,
    status: str,
    fingerprint: str | None,
    agrees: bool,
    detail: str,
    *,
    title: str | None = None,
    authority_class: str = "",
) -> SourceCheck:
    return SourceCheck(
        source_id,
        url,
        status,
        fingerprint,
        agrees,
        detail,
        retrieved_at=datetime.now(UTC).isoformat(),
        title=title,
        authority_class=authority_class,
    )


class OfficialSourceService:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._manifest = load_source_manifest()
        self._hosts = _allowlisted_hosts(self._manifest)
        self._owned_client = client is None
        self._client = client or httpx.Client(
            timeout=TIMEOUT_S,
            follow_redirects=False,
        )

    def close(self) -> None:
        if self._owned_client:
            self._client.close()

    def check(self, source_id: str) -> SourceCheck:
        item = next(src for src in self._manifest["sources"] if src["id"] == source_id)
        url = item["url"]
        authority = item.get("authority_class", "")

        def fail(
            status: str,
            detail: str,
            fingerprint: str | None = None,
            agrees: bool = False,
        ) -> SourceCheck:
            return _result(
                source_id,
                url,
                status,
                fingerprint,
                agrees,
                detail,
                authority_class=authority,
            )

        if httpx.URL(url).host not in self._hosts:
            return fail("unavailable", "url not allowlisted")
        response = None
        error = ""
        for _ in range(ATTEMPTS):
            try:
                response = self._client.get(url)
                error = ""
                break
            except httpx.HTTPError as exc:
                error = type(exc).__name__
        if response is None:
            return fail("unavailable", error)
        location = response.headers.get("location")
        if response.has_redirect_location and location:
            target = httpx.URL(location)
            if target.host not in self._hosts:
                return fail("unavailable", "redirect off allowlist")
        if response.status_code != 200:
            return fail("unavailable", f"http {response.status_code}")
        content = response.content[: MAX_BYTES + 1]
        if len(content) > MAX_BYTES:
            return fail("unavailable", "response too large")
        body = content.decode("utf-8", errors="replace").replace("\r\n", "\n")
        if not body.strip():
            return fail("inconclusive", "empty body")
        fingerprint = hashlib.sha256(body.encode("utf-8")).hexdigest()
        markers = item.get("expected_markers") or []
        agrees = bool(markers) and all(marker in body for marker in markers)
        expected = item.get("verified_fingerprint")
        if expected and expected != fingerprint:
            agrees = False
        if not markers and not expected:
            status, detail, agrees = "inconclusive", "no baseline markers", False
        elif agrees:
            status, detail = "pass", "ok"
        else:
            status, detail = "changed", "markers or fingerprint mismatch"
        return _result(
            source_id,
            url,
            status,
            fingerprint,
            agrees,
            detail,
            title=_title(body),
            authority_class=authority,
        )
