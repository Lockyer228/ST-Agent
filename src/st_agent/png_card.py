"""PNG character-card codec matching current SillyTavern release write/read."""

from __future__ import annotations

import base64
import io
import json
import zlib
from typing import Any

from PIL import Image

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _crc(chunk_type: bytes, payload: bytes) -> int:
    return zlib.crc32(chunk_type + payload) & 0xFFFFFFFF


def _parse_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    if data[:8] != PNG_SIG:
        raise ValueError("not a PNG")
    chunks: list[tuple[bytes, bytes]] = []
    pos = 8
    while pos + 12 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        chunk_type = data[pos + 4 : pos + 8]
        start = pos + 8
        payload = data[start : start + length]
        crc_got = int.from_bytes(data[start + length : start + length + 4], "big")
        if crc_got != _crc(chunk_type, payload):
            raise ValueError("PNG chunk CRC mismatch")
        chunks.append((chunk_type, payload))
        pos = start + length + 4
        if chunk_type == b"IEND":
            break
    return chunks


def _encode_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    return (
        len(payload).to_bytes(4, "big")
        + chunk_type
        + payload
        + _crc(chunk_type, payload).to_bytes(4, "big")
    )


def _text_payload(keyword: str, text: str) -> bytes:
    return keyword.encode("latin-1") + b"\x00" + text.encode("latin-1")


def _decode_text(payload: bytes) -> tuple[str, str]:
    keyword, _, rest = payload.partition(b"\x00")
    return keyword.decode("latin-1"), rest.decode("latin-1")


class PngCardCodec:
    """Insert and extract `chara` + `ccv3` tEXt chunks. Read prefers `ccv3`."""

    def write(self, portrait: Image.Image, card: dict[str, Any]) -> bytes:
        raw = io.BytesIO()
        portrait.convert("RGB").save(raw, format="PNG")
        chunks = [
            (ctype, payload)
            for ctype, payload in _parse_chunks(raw.getvalue())
            if not (ctype == b"tEXt" and _decode_text(payload)[0].lower() in {"chara", "ccv3"})
        ]
        payload = json.dumps(card, ensure_ascii=False, separators=(",", ":"))
        v3 = dict(card)
        v3["spec"] = "chara_card_v3"
        v3["spec_version"] = "3.0"
        v3_payload = json.dumps(v3, ensure_ascii=False, separators=(",", ":"))
        chara = _text_payload("chara", base64.b64encode(payload.encode("utf-8")).decode("ascii"))
        ccv3 = _text_payload("ccv3", base64.b64encode(v3_payload.encode("utf-8")).decode("ascii"))
        iend = next(i for i, (ctype, _) in enumerate(chunks) if ctype == b"IEND")
        chunks[iend:iend] = [(b"tEXt", chara), (b"tEXt", ccv3)]
        return PNG_SIG + b"".join(_encode_chunk(ctype, payload) for ctype, payload in chunks)

    def list_text_chunks(self, png: bytes) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for ctype, payload in _parse_chunks(png):
            if ctype == b"tEXt":
                result.append(_decode_text(payload))
        return result

    def read(self, png: bytes) -> dict[str, Any]:
        texts = {name.lower(): text for name, text in self.list_text_chunks(png)}
        encoded = texts.get("ccv3") or texts.get("chara")
        if not encoded:
            raise ValueError("PNG metadata does not contain character data")
        return json.loads(base64.b64decode(encoded).decode("utf-8"))
