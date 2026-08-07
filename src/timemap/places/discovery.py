"""Locating the source files inside a Takeout export.

Users unzip exports inconsistently, so the given directory may be the one
*containing* `Takeout/` or `Takeout/` itself, and the two saved-places products
("Saved" custom lists, "Maps (your places)" starred places) arrive in separate
exports and may not both be present.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

from .errors import UnrecognizedExportLayout

_SAVED_DIR_NAMES = ("saved",)
_PLACES_JSON_NAMES = ("saved places.json",)


@dataclass(frozen=True, slots=True)
class Sources:
    csv_lists: tuple[pathlib.Path, ...]
    saved_places_json: pathlib.Path | None


def discover_sources(root: pathlib.Path) -> Sources:
    root = pathlib.Path(root)
    if not root.is_dir():
        raise UnrecognizedExportLayout(root, "not a directory")

    csv_lists: list[pathlib.Path] = []
    places_json: pathlib.Path | None = None

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".csv" and _in_saved_dir(path):
            csv_lists.append(path)
        elif path.name.lower() in _PLACES_JSON_NAMES:
            places_json = path

    if not csv_lists and places_json is None:
        raise UnrecognizedExportLayout(
            root,
            "no saved-places sources found; expected a Saved/*.csv list or a "
            "'Maps (your places)/Saved Places.json'",
        )
    return Sources(csv_lists=tuple(csv_lists), saved_places_json=places_json)


def _in_saved_dir(path: pathlib.Path) -> bool:
    """Only treat CSVs under a Saved/ directory as lists.

    Takeout archives bundle unrelated products, and a Chrome or Fit export can
    contain CSVs that are emphatically not saved places.
    """
    return any(parent.name.lower() in _SAVED_DIR_NAMES for parent in path.parents)
