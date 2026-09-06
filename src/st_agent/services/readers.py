"""Content-sniffing readers. File extensions are not trusted."""

from __future__ import annotations

import io
import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from st_agent.png_card import PNG_SIG, PngCardCodec
from st_agent.services.workspace import UnsupportedInput


class InputKind(StrEnum):
    text = "text"
    json = "json"
    image = "image"
    png_card = "png_card"


def open_image(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        return image
    except UnidentifiedImageError:
        raise UnsupportedInput(
            "the file is not a readable PNG, JPEG, WebP, or BMP image"
        ) from None
    except OSError:
        raise UnsupportedInput("the image file is damaged and cannot be read") from None


def sniff_bytes(data: bytes) -> InputKind:
    if data.startswith((b"GIF87a", b"GIF89a")):
        raise UnsupportedInput("GIF is not supported")
    if data.startswith(b"%PDF"):
        raise UnsupportedInput("PDF is not supported")
    if data.startswith((b"II*\x00", b"MM\x00*")):
        raise UnsupportedInput("TIFF is not supported")
    if data.startswith(b"PK\x03\x04"):
        raise UnsupportedInput("archives and Office documents are not supported")
    if data.startswith(PNG_SIG):
        try:
            names = {name.lower() for name, _ in PngCardCodec().list_text_chunks(data)}
        except ValueError:
            raise UnsupportedInput("the image file is damaged and cannot be read") from None
        if "chara" in names or "ccv3" in names:
            return InputKind.png_card
        return InputKind.image
    if data.startswith(b"\xff\xd8") or data.startswith(b"BM"):
        return InputKind.image
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return InputKind.image
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise UnsupportedInput("the file type is not supported") from None
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            json.loads(text)
        except ValueError:
            raise UnsupportedInput("the JSON file is damaged and cannot be read") from None
        return InputKind.json
    return InputKind.text


def sniff_path(path: Path) -> InputKind:
    return sniff_bytes(path.read_bytes())


def read_input(path: Path) -> tuple[InputKind, Any]:
    data = path.read_bytes()
    kind = sniff_bytes(data)
    if kind is InputKind.json:
        return kind, json.loads(data.decode("utf-8"))
    if kind is InputKind.text:
        return kind, data.decode("utf-8")
    if kind is InputKind.png_card:
        try:
            return kind, PngCardCodec().read(data)
        except ValueError:
            raise UnsupportedInput(
                "the PNG card payload is damaged and cannot be read"
            ) from None
    open_image(data)
    return kind, data
