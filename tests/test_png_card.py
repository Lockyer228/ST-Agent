"""Golden PNG chunk round-trip for the frozen SillyTavern profile."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from st_agent.png_card import PngCardCodec

FIXTURES = Path(__file__).parent / "fixtures" / "golden"


def _blank_portrait() -> Image.Image:
    return Image.new("RGB", (8, 8), color=(40, 80, 120))


def test_new_card_png_writes_chara_and_ccv3_and_prefers_ccv3() -> None:
    card = json.loads((FIXTURES / "new-card.json").read_text(encoding="utf-8"))
    codec = PngCardCodec()
    png = codec.write(_blank_portrait(), card)
    chunks = codec.list_text_chunks(png)
    names = [name.lower() for name, _ in chunks]
    assert "chara" in names
    assert "ccv3" in names
    extracted = codec.read(png)
    assert extracted["spec"] == "chara_card_v3"
    assert extracted["data"]["name"] == card["data"]["name"]
    assert extracted["data"]["first_mes"] == card["data"]["first_mes"]


def test_png_crc_is_verified() -> None:
    card = json.loads((FIXTURES / "new-card.json").read_text(encoding="utf-8"))
    codec = PngCardCodec()
    png = bytearray(codec.write(_blank_portrait(), card))
    marker = png.find(b"tEXt")
    assert marker != -1
    png[marker + 8] ^= 0xFF
    try:
        codec.read(bytes(png))
    except ValueError as exc:
        assert "crc" in str(exc).lower()
    else:
        raise AssertionError("corrupt PNG must not round-trip")
