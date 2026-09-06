"""Decode supported portraits and write a clean PNG without resizing."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import ImageOps

from st_agent.services.readers import open_image


def portrait_to_png(path: Path) -> bytes:
    image = open_image(path.read_bytes())
    transposed = ImageOps.exif_transpose(image)
    if transposed is not None:
        image = transposed
    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGB")
    raw = io.BytesIO()
    image.save(raw, format="PNG")
    return raw.getvalue()
