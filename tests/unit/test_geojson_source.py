"""Parsing `Saved Places.json`. SC-001, SC-002."""

from __future__ import annotations

import json

from timemap.places.geojson_source import parse_saved_places


def test_parses_the_fixture_collection(takeout_min):
    p = takeout_min / "Takeout" / "Maps (your places)" / "Saved Places.json"
    entries = parse_saved_places(p)
    assert len(entries) == 3


def test_extracts_name_address_and_coordinates(takeout_min):
    p = takeout_min / "Takeout" / "Maps (your places)" / "Saved Places.json"
    by_name = {e.name: e for e in parse_saved_places(p)}
    e = by_name["Fictional Landmark"]
    assert e.lat == 40.75282
    assert e.lon == -73.9772
    assert e.address.startswith("1 Fictional Plaza")


def test_longitude_latitude_order_is_not_swapped(takeout_min):
    # GeoJSON is [lon, lat]. Swapping puts NYC in Antarctica.
    p = takeout_min / "Takeout" / "Maps (your places)" / "Saved Places.json"
    e = next(e for e in parse_saved_places(p) if e.name == "Fictional Landmark")
    assert 40 < e.lat < 41
    assert -75 < e.lon < -73


def test_zero_zero_coordinates_are_treated_as_absent(takeout_min):
    # The real export uses [0,0] for entries it could not resolve. Taking it
    # literally puts pins in the Gulf of Guinea.
    p = takeout_min / "Takeout" / "Maps (your places)" / "Saved Places.json"
    unlocated = [e for e in parse_saved_places(p) if e.lat is None]
    assert len(unlocated) == 1
    assert unlocated[0].lon is None


def test_entry_without_location_block_still_yields_a_name(takeout_min):
    p = takeout_min / "Takeout" / "Maps (your places)" / "Saved Places.json"
    e = next(e for e in parse_saved_places(p) if e.lat is None)
    assert e.name  # recovered from the q= parameter
    assert e.feature_id == "0x7777777777777777:0x8888888888888888"


def test_foreign_place_is_parsed_not_discarded(takeout_min):
    p = takeout_min / "Takeout" / "Maps (your places)" / "Saved Places.json"
    names = {e.name for e in parse_saved_places(p)}
    assert "Distant Tower" in names


def test_empty_feature_collection_yields_nothing(tmp_path):
    p = tmp_path / "Saved Places.json"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
    assert parse_saved_places(p) == []
