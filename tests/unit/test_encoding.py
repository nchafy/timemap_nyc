"""SC-008: encoding robustness.

The real export is UTF-8 without a BOM, but this machine has produced a UTF-16LE
file before (README.md), so the reader must tolerate what it is actually handed.
"""

from __future__ import annotations

import pytest

from timemap.places.encoding import read_text
from timemap.places.errors import SourceFileUnreadable


def test_decodes_plain_utf8(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("Title,URL\nCafé,x\n", encoding="utf-8")
    assert read_text(p) == "Title,URL\nCafé,x\n"


def test_strips_utf8_bom_so_first_header_key_is_clean(tmp_path):
    # An unstripped BOM turns "Title" into "﻿Title" and the Title column
    # silently disappears from every row.
    p = tmp_path / "b.csv"
    p.write_bytes(b"\xef\xbb\xbfTitle,URL\nx,y\n")
    assert read_text(p).startswith("Title")
    assert "﻿" not in read_text(p)


def test_decodes_utf16le_with_bom(tmp_path):
    p = tmp_path / "c.csv"
    p.write_bytes(b"\xff\xfe" + "Title,URL\nx,y\n".encode("utf-16-le"))
    assert read_text(p) == "Title,URL\nx,y\n"


def test_decodes_utf16le_without_bom_via_nul_heuristic(tmp_path):
    p = tmp_path / "d.csv"
    p.write_bytes("Title,URL\nx,y\n".encode("utf-16-le"))
    assert read_text(p) == "Title,URL\nx,y\n"


def test_normalises_crlf_to_lf(tmp_path):
    p = tmp_path / "e.csv"
    p.write_bytes(b"Title,URL\r\nx,y\r\n")
    assert "\r" not in read_text(p)


def test_preserves_emoji_and_cjk(tmp_path):
    p = tmp_path / "f.csv"
    p.write_text("Title\n法拉盛 ☕\n", encoding="utf-8")
    assert "法拉盛 ☕" in read_text(p)


def test_raises_named_error_on_undecodable_bytes(tmp_path):
    p = tmp_path / "g.csv"
    p.write_bytes(b"\xc3\x28\xa0\xa1invalid")
    with pytest.raises(SourceFileUnreadable) as exc:
        read_text(p)
    assert str(p) in str(exc.value)
