"""The ingest report. SC-007."""

from __future__ import annotations

from timemap.places.models import SavedPlace
from timemap.places.report import build_report, format_summary


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
    return place(identity_key=key, lat=None, lon=None, needs_geocoding=True, geocode_reason=reason)


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


def test_summary_leads_with_the_counts():
    r = build_report(
        [place()], [unlocated("b", "no_coordinates")], source_count=2, duplicates_merged=0
    )
    first_line = format_summary(r).splitlines()[0]
    assert "2 places" in first_line
    assert "1 located" in first_line
    assert "1 need coordinates" in first_line


def test_summary_reports_reason_breakdown():
    unresolved = [unlocated("a", "no_coordinates"), unlocated("b", "not_a_place")]
    summary = format_summary(build_report([], unresolved, source_count=2, duplicates_merged=0))
    assert "1 no_coordinates" in summary
    assert "1 not_a_place" in summary


def test_summary_mentions_merges_and_out_of_region_only_when_present():
    quiet = format_summary(build_report([place()], [], source_count=1, duplicates_merged=0))
    assert "merged" not in quiet
    assert "outside the region" not in quiet

    noisy = format_summary(
        build_report(
            [place(identity_key="a", outside_region=True)], [], source_count=3, duplicates_merged=2
        )
    )
    assert "merged 2 duplicate entries" in noisy
    assert "1 outside the region" in noisy
