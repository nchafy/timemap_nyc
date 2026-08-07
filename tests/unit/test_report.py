"""The ingest report. SC-007."""

from __future__ import annotations

from timemap.places.models import SavedPlace
from timemap.places.report import build_report


def place(**kw) -> SavedPlace:
    base = {
        "identity_key": "k",
        "name": "A Place",
        "lat": 40.7,
        "lon": -74.0,
        "address": None,
        "lists": ("L",),
        "source_files": ("L.csv",),
        "feature_id": None,
        "url": "",
        "note": "",
        "needs_geocoding": False,
        "geocode_reason": None,
        "outside_region": False,
    }
    base.update(kw)
    return SavedPlace(**base)


def unlocated(key: str, reason: str) -> SavedPlace:
    return place(
        identity_key=key, lat=None, lon=None, needs_geocoding=True, geocode_reason=reason
    )


def test_counts_sum_to_the_total():
    located = [place(identity_key="a"), place(identity_key="b")]
    unresolved = [unlocated("c", "no_coordinates")]
    r = build_report(located, unresolved, source_count=3, duplicates_merged=0)
    assert r["located_count"] == 2
    assert r["unresolved_count"] == 1
    assert r["total_places"] == 3


def test_groups_unresolved_by_reason_code():
    unresolved = [
        unlocated("a", "no_coordinates"),
        unlocated("b", "no_coordinates"),
        unlocated("c", "not_a_place"),
    ]
    r = build_report([], unresolved, source_count=3, duplicates_merged=0)
    assert r["unresolved_by_reason"] == {"no_coordinates": 2, "not_a_place": 1}


def test_lists_every_unresolved_place_with_its_provenance():
    unresolved = [unlocated("a", "no_coordinates")]
    r = build_report([], unresolved, source_count=1, duplicates_merged=0)
    entry = r["unresolved"][0]
    assert entry["name"] == "A Place"
    assert entry["lists"] == ["L"]
    assert entry["reason"] == "no_coordinates"


def test_records_duplicates_merged():
    r = build_report([place()], [], source_count=3, duplicates_merged=2)
    assert r["duplicates_merged"] == 2


def test_counts_out_of_region_places():
    located = [place(identity_key="a", outside_region=True), place(identity_key="b")]
    r = build_report(located, [], source_count=2, duplicates_merged=0)
    assert r["outside_region_count"] == 1


def test_report_is_json_serialisable_and_stable():
    import json

    r = build_report([place()], [], source_count=1, duplicates_merged=0)
    assert json.dumps(r, sort_keys=True) == json.dumps(r, sort_keys=True)
