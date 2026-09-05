"""Allowlisted official-source retrieval with pass / unavailable results."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

import httpx

MAX_BYTES = 1_000_000
TIMEOUT_S = 10.0


@dataclass(frozen=True)
class SourceCheck:
    source_id: str
    url: str
    status: str
    fingerprint: str | None
    agrees_with_local_profile: bool
    detail: str


def load_source_manifest() -> dict[str, Any]:
    path = files("st_agent.resources.formats").joinpath("source-manifest.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _allowlisted_hosts(manifest: dict[str, Any]) -> set[str]:
    hosts: set[str] = set()
    for item in manifest["sources"]:
        hosts.add(httpx.URL(item["url"]).host)
        documented = item.get("documented_url")
        if documented:
            hosts.add(httpx.URL(documented).host)
    return hosts


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
        if httpx.URL(url).host not in self._hosts:
            return SourceCheck(
                source_id, url, "unavailable", None, False, "url not allowlisted"
            )
        try:
            response = self._client.get(url)
        except httpx.HTTPError as exc:
            return SourceCheck(source_id, url, "unavailable", None, False, type(exc).__name__)
        location = response.headers.get("location")
        if response.has_redirect_location and location:
            target = httpx.URL(location)
            if target.host not in self._hosts:
                return SourceCheck(
                    source_id,
                    url,
                    "unavailable",
                    None,
                    False,
                    "redirect off allowlist",
                )
        if response.status_code != 200:
            return SourceCheck(
                source_id,
                url,
                "unavailable",
                None,
                False,
                f"http {response.status_code}",
            )
        content = response.content[: MAX_BYTES + 1]
        if len(content) > MAX_BYTES:
            return SourceCheck(
                source_id, url, "unavailable", None, False, "response too large"
            )
        body = content.decode("utf-8", errors="replace").replace("\r\n", "\n")
        fingerprint = hashlib.sha256(body.encode("utf-8")).hexdigest()
        markers = item.get("expected_markers") or []
        agrees = all(marker in body for marker in markers)
        status = "pass" if agrees else "changed"
        detail = "ok" if agrees else "markers missing"
        return SourceCheck(source_id, url, status, fingerprint, agrees, detail)
