"""The two shapes a place takes: as read, and as canonicalised."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RawEntry:
    """One row or feature exactly as it appeared in one source file."""

    name: str
    note: str
    url: str
    list_name: str
    feature_id: str | None
    lat: float | None
    lon: float | None
    address: str | None
    source_file: str


@dataclass(frozen=True, slots=True)
class SavedPlace:
    """One deduplicated place, merged across every list it appears in."""

    identity_key: str
    name: str
    lat: float | None
    lon: float | None
    address: str | None
    lists: tuple[str, ...]
    source_files: tuple[str, ...]
    feature_id: str | None
    url: str
    note: str
    needs_geocoding: bool
    geocode_reason: str | None
    outside_region: bool

    def to_feature(self) -> dict:
        """Render as a GeoJSON Feature.

        Unlocated places get `"geometry": null`, which RFC 7946 permits, so they
        can travel in a FeatureCollection alongside the located ones.
        """
        geometry = None
        if self.lat is not None and self.lon is not None:
            geometry = {"type": "Point", "coordinates": [self.lon, self.lat]}
        return {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "identity_key": self.identity_key,
                "name": self.name,
                "address": self.address,
                "lists": list(self.lists),
                "source_files": list(self.source_files),
                "feature_id": self.feature_id,
                "url": self.url,
                "note": self.note,
                "needs_geocoding": self.needs_geocoding,
                "geocode_reason": self.geocode_reason,
                "outside_region": self.outside_region,
            },
        }
