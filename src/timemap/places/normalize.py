"""Canonicalising raw entries into deduplicated places.

Conservation is the invariant that matters: every input entry ends up in exactly
one of the two output sets, so nothing is ever silently dropped. Places are
merged on a feature id where one exists -- that identifies the exact venue saved,
which a name cannot, since chains repeat names across boroughs.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from .models import RawEntry, SavedPlace
from .urls import is_google_maps_place_url

# Reasons a place has no usable coordinates. A closed set, asserted by the
# contract tests, so the frontend and any later geocoder can switch on it.
REASON_NO_COORDINATES = "no_coordinates"
REASON_NOT_A_PLACE = "not_a_place"
REASON_NO_URL = "no_url"

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def normalize(
    entries: list[RawEntry], *, region_bbox: tuple[float, float, float, float]
) -> tuple[list[SavedPlace], list[SavedPlace]]:
    """Merge duplicates and split into (located, unresolved), each sorted stably."""
    merged: dict[str, RawEntry] = {}
    lists: dict[str, list[str]] = {}
    files: dict[str, list[str]] = {}

    for entry in entries:
        key = identity_key(entry)
        lists.setdefault(key, [])
        files.setdefault(key, [])
        if entry.list_name not in lists[key]:
            lists[key].append(entry.list_name)
        if entry.source_file not in files[key]:
            files[key].append(entry.source_file)
        merged[key] = _prefer(merged.get(key), entry)

    located: list[SavedPlace] = []
    unresolved: list[SavedPlace] = []
    for key, entry in merged.items():
        place = _to_place(key, entry, tuple(lists[key]), tuple(files[key]), region_bbox)
        (located if place.lat is not None else unresolved).append(place)

    located.sort(key=lambda p: (p.name.casefold(), p.identity_key))
    unresolved.sort(key=lambda p: (p.name.casefold(), p.identity_key))
    return located, unresolved


def identity_key(entry: RawEntry) -> str:
    """A stable key for one real-world place.

    Prefers the Google feature id, which is exact. Falls back to a normalised
    name, which is all the CSV lists give for places lacking an id.
    """
    if entry.feature_id:
        return f"fid:{entry.feature_id}"
    return f"name:{hashlib.sha1(_normalise_name(entry.name).encode()).hexdigest()[:16]}"


def _normalise_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    collapsed = _WHITESPACE.sub(" ", _PUNCTUATION.sub(" ", stripped))
    return collapsed.strip().casefold()


def _prefer(existing: RawEntry | None, candidate: RawEntry) -> RawEntry:
    """Keep the richer of two records for the same place."""
    if existing is None:
        return candidate
    if existing.lat is None and candidate.lat is not None:
        return candidate
    if existing.lat is not None and candidate.lat is None:
        return existing
    # Both located or both not: prefer the one carrying more provenance.
    if not existing.address and candidate.address:
        return candidate
    if not existing.note and candidate.note:
        return candidate
    return existing


def _to_place(
    key: str,
    entry: RawEntry,
    lists: tuple[str, ...],
    files: tuple[str, ...],
    region_bbox: tuple[float, float, float, float],
) -> SavedPlace:
    reason = None if entry.lat is not None else _reason(entry)
    return SavedPlace(
        identity_key=key,
        name=entry.name,
        lat=entry.lat,
        lon=entry.lon,
        address=entry.address,
        lists=lists,
        source_files=files,
        feature_id=entry.feature_id,
        url=entry.url,
        note=entry.note,
        needs_geocoding=entry.lat is None,
        geocode_reason=reason,
        outside_region=_outside(entry, region_bbox),
    )


def _reason(entry: RawEntry) -> str:
    if not entry.url:
        return REASON_NO_URL
    if not is_google_maps_place_url(entry.url):
        return REASON_NOT_A_PLACE
    return REASON_NO_COORDINATES


def _outside(entry: RawEntry, bbox: tuple[float, float, float, float]) -> bool:
    """Flag rather than reject: lists mix cities, and a vacation save is still a save."""
    if entry.lat is None or entry.lon is None:
        return False
    lon_min, lat_min, lon_max, lat_max = bbox
    return not (lat_min <= entry.lat <= lat_max and lon_min <= entry.lon <= lon_max)
