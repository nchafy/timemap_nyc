"""Parsing one saved-list CSV.

Every list in the owner's export has the header `Title,Note,URL,Tags,Comment`
and is UTF-8 without a BOM, but header matching is case- and
whitespace-insensitive and tolerates extra or reordered columns, because a single
malformed header would otherwise silently drop a whole list.
"""

from __future__ import annotations

import csv
import io
import pathlib

from .encoding import read_text
from .errors import SourceFileMalformed
from .models import RawEntry
from .urls import extract_feature_id, extract_place_name

_TITLE_KEYS = ("title", "name")
_URL_KEYS = ("url", "link")
_NOTE_KEYS = ("note", "notes")


def parse_csv_list(path: pathlib.Path) -> list[RawEntry]:
    """Read one list file. The list name is the filename stem."""
    text = read_text(path)
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []

    header = {_canonical(name): name for name in reader.fieldnames if name is not None}
    title_col = _first_present(header, _TITLE_KEYS)
    url_col = _first_present(header, _URL_KEYS)
    if title_col is None and url_col is None:
        raise SourceFileMalformed(
            path, f"no Title or URL column found in header {reader.fieldnames!r}"
        )

    note_col = _first_present(header, _NOTE_KEYS)
    list_name = path.stem
    entries: list[RawEntry] = []

    for row in reader:
        url = _value(row, url_col)
        name = _value(row, title_col) or extract_place_name(url) or ""
        if not name and not url:
            continue  # 2 of the owner's 35 lists end with a fully blank row
        entries.append(
            RawEntry(
                name=name,
                note=_value(row, note_col),
                url=url,
                list_name=list_name,
                feature_id=extract_feature_id(url),
                lat=None,  # no CSV url in the real export carries coordinates
                lon=None,
                address=None,
                source_file=path.name,
            )
        )
    return entries


def _canonical(name: str) -> str:
    return name.strip().lstrip("﻿").lower()


def _first_present(header: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    for key in candidates:
        if key in header:
            return header[key]
    return None


def _value(row: dict[str, str | None], column: str | None) -> str:
    if column is None:
        return ""
    return (row.get(column) or "").strip()
