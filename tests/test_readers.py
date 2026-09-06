"""Content-sniffing readers reject unsupported and damaged files in English."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, UnidentifiedImageError

from st_agent.services.readers import InputKind, read_input, sniff_path
from st_agent.services.workspace import UnsupportedInput, create_case, save_user_inputs


def test_sniff_dispatches_by_content_not_suffix(tmp_path: Path) -> None:
    text = tmp_path / "notes.bin"
    text.write_text("# Harbor\nRain.", encoding="utf-8")
    data = tmp_path / "card.txt"
    data.write_text('{"spec": "chara_card_v3"}', encoding="utf-8")
    png = tmp_path / "shot.jpg"
    Image.new("RGB", (4, 4), "navy").save(png, format="PNG")
    assert sniff_path(text) == InputKind.text
    assert sniff_path(data) == InputKind.json
    assert sniff_path(png) == InputKind.image


def test_png_card_is_distinct_from_plain_png(tmp_path: Path) -> None:
    from st_agent.png_card import PngCardCodec

    plain = tmp_path / "plain.png"
    Image.new("RGB", (4, 4), "navy").save(plain)
    card = tmp_path / "card.png"
    png = PngCardCodec().write(
        Image.new("RGB", (4, 4), "navy"),
        {"spec": "chara_card_v3", "data": {"name": "Mira"}},
    )
    card.write_bytes(png)
    assert sniff_path(plain) == InputKind.image
    assert sniff_path(card) == InputKind.png_card
    kind, payload = read_input(card)
    assert kind == InputKind.png_card
    assert payload["data"]["name"] == "Mira"


def test_gif_and_pdf_are_rejected(tmp_path: Path) -> None:
    gif = tmp_path / "x.png"
    gif.write_bytes(b"GIF89a" + b"\x00" * 8)
    pdf = tmp_path / "doc.md"
    pdf.write_bytes(b"%PDF-1.4\n")
    with pytest.raises(UnsupportedInput, match="GIF"):
        sniff_path(gif)
    with pytest.raises(UnsupportedInput, match="PDF"):
        sniff_path(pdf)


def test_damaged_image_is_english_rejection_not_pil(tmp_path: Path) -> None:
    damaged = tmp_path / "bad.png"
    damaged.write_bytes(b"\x89PNG\r\n\x1a\n" + b"truncated")
    with pytest.raises(UnsupportedInput, match="damaged|not a readable") as err:
        read_input(damaged)
    assert "UnidentifiedImageError" not in str(err.value)
    assert err.value.__cause__ is None


def test_save_user_inputs_maps_damaged_image(tmp_path: Path) -> None:
    case_root = create_case(tmp_path, "harbor-watch")
    damaged = tmp_path / "bad.png"
    damaged.write_bytes(b"\x89PNG\r\n\x1a\n" + b"truncated")
    with pytest.raises(UnsupportedInput) as err:
        save_user_inputs(case_root, [damaged])
    assert not isinstance(err.value, UnidentifiedImageError)
    assert "UnidentifiedImageError" not in str(err.value)
    assert not any(path.is_file() for path in (case_root / "01-assets").rglob("*"))


def test_truncated_json_is_english_rejection(tmp_path: Path) -> None:
    damaged = tmp_path / "card.json"
    damaged.write_text('{"spec": "chara_card_v3"', encoding="utf-8")
    with pytest.raises(UnsupportedInput, match="JSON file is damaged") as err:
        read_input(damaged)
    assert err.value.__cause__ is None


def test_png_card_with_garbage_payload_is_english_rejection(tmp_path: Path) -> None:
    import base64
    import io

    from st_agent.png_card import PNG_SIG, _encode_chunk, _parse_chunks, _text_payload

    raw = io.BytesIO()
    Image.new("RGB", (4, 4), "navy").save(raw, format="PNG")
    chunks = list(_parse_chunks(raw.getvalue()))
    junk = base64.b64encode(b"not-json").decode("ascii")
    iend = next(i for i, (ctype, _) in enumerate(chunks) if ctype == b"IEND")
    chunks[iend:iend] = [(b"tEXt", _text_payload("ccv3", junk))]
    png = PNG_SIG + b"".join(_encode_chunk(ctype, payload) for ctype, payload in chunks)
    path = tmp_path / "card.png"
    path.write_bytes(png)
    with pytest.raises(UnsupportedInput, match="card payload") as err:
        read_input(path)
    assert err.value.__cause__ is None
