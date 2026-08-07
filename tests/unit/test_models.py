"""The two place shapes and their GeoJSON rendering."""

from __future__ import annotations

import dataclasses

import pytest

from timemap.places.models import RawEntry, SavedPlace


def saved(**kw) -> SavedPlace:
    base = {
        "identity_key": "k",
        "name": "A Place",
        "lat": 40.75,
        "lon": -73.98,
        "address": "1 Nowhere St",
        "lists": ("L",),
        "source_files": ("L.csv",),
        "feature_id": "0x1:0x2",
        "url": "https://example.com/a",
        "note": "",
        "needs_geocoding": False,
        "geocode_reason": None,
        "outside_region": False,
    }
    base.update(kw)
    return SavedPlace(**base)


def test_raw_entry_is_immutable():
    entry = RawEntry(
        name="X",
        note="",
        url="",
        list_name="L",
        feature_id=None,
        lat=None,
        lon=None,
        address=None,
        source_file="L.csv",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.name = "Y"


def test_located_place_renders_a_point_in_lon_lat_order():
    feature = saved().to_feature()
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    # GeoJSON is [lon, lat]. Swapping puts Manhattan in Antarctica.
    assert feature["geometry"]["coordinates"] == [-73.98, 40.75]


def test_unlocated_place_renders_null_geometry():
    # RFC 7946 permits a null geometry, so unlocated places can still travel
    # in a FeatureCollection.
    feature = saved(lat=None, lon=None, needs_geocoding=True, geocode_reason="no_coordinates")
    feature = feature.to_feature()
    assert feature["geometry"] is None
    assert feature["properties"]["needs_geocoding"] is True


def test_feature_properties_carry_provenance():
    props = saved(lists=("A", "B"), source_files=("a.csv", "b.csv")).to_feature()["properties"]
    assert props["lists"] == ["A", "B"]
    assert props["source_files"] == ["a.csv", "b.csv"]
    assert props["feature_id"] == "0x1:0x2"


def test_tuples_render_as_json_arrays():
    props = saved().to_feature()["properties"]
    assert isinstance(props["lists"], list)
