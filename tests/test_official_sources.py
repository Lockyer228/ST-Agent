"""Allowlisted official-source retrieval: pass and unavailable paths."""

from __future__ import annotations

import httpx

from st_agent.official_sources import OfficialSourceService, load_source_manifest


def test_pass_records_fingerprint_and_agrees_with_local_profile() -> None:
    spec_body = "# Character Card V3\nspec: 'chara_card_v3'\nPNG tEXt chunk named ccv3\n"
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("https://raw.githubusercontent.com/")
        return httpx.Response(200, text=spec_body)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    service = OfficialSourceService(client=client)
    result = service.check("ccv3-spec")
    assert result.status == "pass"
    assert result.url.endswith("SPEC_V3.md")
    assert result.fingerprint
    assert result.agrees_with_local_profile is True


def test_unavailable_is_not_a_false_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="missing")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = OfficialSourceService(client=client)
    result = service.check("ccv3-spec-missing")
    assert result.status == "unavailable"
    assert result.agrees_with_local_profile is False


def test_redirect_off_allowlist_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "raw.githubusercontent.com":
            return httpx.Response(302, headers={"location": "https://evil.example/spec"})
        raise AssertionError("must not follow off-allowlist redirect")

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    service = OfficialSourceService(client=client)
    result = service.check("ccv3-spec")
    assert result.status == "unavailable"


def test_manifest_lists_both_authority_classes() -> None:
    manifest = load_source_manifest()
    classes = {item["authority_class"] for item in manifest["sources"]}
    assert "format-specification" in classes
    assert "target-application" in classes
