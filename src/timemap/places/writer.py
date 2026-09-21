"""Writing the output files.

Writes are atomic (temp file then replace) so a crash cannot leave a half-written
GeoJSON that the frontend would happily try to parse. Output is byte-stable
across runs -- sorted keys, fixed separators, trailing newline -- which is what
makes the files diffable in git and lets tests assert determinism.
"""

from __future__ import annotations

import json
import os
import pathlib
import tempfile

from .errors import OutputWriteError
from .models import SavedPlace

LOCATED_NAME = "places.geojson"
UNRESOLVED_NAME = "places.unresolved.geojson"
REPORT_NAME = "places.report.json"


def write_outputs(
    out_dir: pathlib.Path,
    located: list[SavedPlace],
    unresolved: list[SavedPlace],
    report: dict,
) -> list[pathlib.Path]:
    out_dir = pathlib.Path(out_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputWriteError(out_dir, f"could not create output directory: {exc}") from exc

    return [
        _write_json(out_dir / LOCATED_NAME, _collection(located)),
        _write_json(out_dir / UNRESOLVED_NAME, _collection(unresolved)),
        _write_json(out_dir / REPORT_NAME, report),
    ]


def _collection(places: list[SavedPlace]) -> dict:
    return {"type": "FeatureCollection", "features": [p.to_feature() for p in places]}


def _write_json(path: pathlib.Path, payload: dict) -> pathlib.Path:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        # Same directory as the target so os.replace is atomic (no cross-device move).
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            handle.write(text)
            temp_path = pathlib.Path(handle.name)
        os.replace(temp_path, path)
    except OSError as exc:
        raise OutputWriteError(path, f"could not be written: {exc}") from exc
    return path
