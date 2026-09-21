"""Parsing `Saved Places.json` (the starred/labelled places export).

Two details matter. GeoJSON coordinates are `[lon, lat]`; swapping them puts
Manhattan in Antarctica. And the real export writes `[0, 0]` for places it could
not resolve -- taking that literally drops pins in the Gulf of Guinea, so it is
treated as absent.
"""

from __future__ import annotations

import json
import pathlib
import urllib.parse as up

from .encoding import read_text
from .errors import SourceFileMalformed
from .models import RawEntry
from .urls import extract_feature_id, extract_place_name

LIST_NAME = "Saved Places"


def parse_saved_places(path: pathlib.Path) -> list[RawEntry]:
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise SourceFileMalformed(path, f"not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or "features" not in data:
        raise SourceFileMalformed(path, "not a GeoJSON FeatureCollection")

    entries: list[RawEntry] = []
    for feature in data.get("features") or []:
        entry = _entry_from_feature(feature, path.name)
        if entry is not None:
            entries.append(entry)
    return entries


def _entry_from_feature(feature: dict, source_file: str) -> RawEntry | None:
    props = feature.get("properties") or {}
    location = props.get("location") or {}
    url = (props.get("google_maps_url") or "").strip()

    name = (location.get("name") or "").strip() or _name_from_url(url)
    if not name:
        return None

    lat, lon = _coordinates(feature)
    return RawEntry(
        name=name,
        note=(props.get("Comment") or "").strip(),
        url=url,
        list_name=LIST_NAME,
        feature_id=extract_feature_id(url),
        lat=lat,
        lon=lon,
        address=(location.get("address") or None),
        source_file=source_file,
    )


def _coordinates(feature: dict) -> tuple[float | None, float | None]:
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates")
    if not isinstance(coords, list) or len(coords) != 2:
        return None, None
    lon, lat = coords
    if not isinstance(lat, int | float) or not isinstance(lon, int | float):
        return None, None
    if lat == 0 and lon == 0:
        return None, None  # the export's "unresolved" sentinel
    return float(lat), float(lon)


def _name_from_url(url: str) -> str:
    """Entries with no `location` block still carry an address in `q=`."""
    if not url:
        return ""
    from_path = extract_place_name(url)
    if from_path:
        return from_path
    query = up.parse_qs(up.urlparse(url).query)
    return (query.get("q") or [""])[0].strip()
