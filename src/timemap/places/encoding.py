"""Reading source files whose encoding cannot be trusted.

The owner's real export is UTF-8 without a BOM, but this machine has produced a
BOM-less UTF-16LE file before (README.md), and a stray BOM silently corrupts the
first CSV header key -- which loses the Title column without raising anything.
"""

from __future__ import annotations

import pathlib

from .errors import SourceFileUnreadable

_UTF8_BOM = b"\xef\xbb\xbf"
_UTF16_LE_BOM = b"\xff\xfe"
_UTF16_BE_BOM = b"\xfe\xff"


def read_text(path: pathlib.Path) -> str:
    """Decode `path` to text, sniffing the encoding, and normalise line endings."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SourceFileUnreadable(path, f"could not be read: {exc}") from exc

    text = _decode(path, raw)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _decode(path: pathlib.Path, raw: bytes) -> str:
    if raw.startswith(_UTF8_BOM):
        return raw[len(_UTF8_BOM) :].decode("utf-8")
    if raw.startswith(_UTF16_LE_BOM):
        return raw[len(_UTF16_LE_BOM) :].decode("utf-16-le")
    if raw.startswith(_UTF16_BE_BOM):
        return raw[len(_UTF16_BE_BOM) :].decode("utf-16-be")

    # No BOM. UTF-16 text that is mostly ASCII is riddled with NUL bytes, which
    # never appear in valid UTF-8, so their position identifies the byte order.
    if b"\x00" in raw[:64]:
        for codec in ("utf-16-le", "utf-16-be"):
            try:
                return raw.decode(codec)
            except UnicodeDecodeError:
                continue

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceFileUnreadable(
            path, f"not valid UTF-8, UTF-16, or BOM-prefixed text ({exc.reason})"
        ) from exc
