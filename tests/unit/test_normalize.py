"""Identity, dedupe, merge, and deterministic ordering. SC-002, SC-004, SC-006."""

from __future__ import annotations

from timemap.places.models import RawEntry
from timemap.places.normalize import identity_key, normalize

NYC_BBOX = (-74.35, 40.45, -73.65, 41.00)


def raw(**kw) -> RawEntry:
    base = {
        "name": "A Place",
        "note": "",
        "url": "",
        "list_name": "L",
        "feature_id": None,
        "lat": None,
        "lon": None,
        "address": None,
        "source_file": "L.csv",
    }
    base.update(kw)
    return RawEntry(**base)


def test_identity_key_prefers_feature_id():
    a = raw(name="One Name", feature_id="0x1:0x2")
    b = raw(name="Different Name", feature_id="0x1:0x2")
    assert identity_key(a) == identity_key(b)


def test_identity_key_falls_back_to_name_when_no_feature_id():
    assert identity_key(raw(name="Same")) == identity_key(raw(name="Same", list_name="Other"))


def test_name_matching_ignores_case_diacritics_and_whitespace():
    assert identity_key(raw(name="Café  Fictif")) == identity_key(raw(name="cafe fictif"))


def test_different_places_get_different_keys():
    assert identity_key(raw(name="A")) != identity_key(raw(name="B"))


def test_place_in_two_lists_is_merged_once_with_both_memberships():
    entries = [
        raw(name="Shared", feature_id="0x1:0x2", list_name="First", source_file="First.csv"),
        raw(name="Shared", feature_id="0x1:0x2", list_name="Second", source_file="Second.csv"),
    ]
    located, unresolved = normalize(entries, region_bbox=NYC_BBOX)
    all_places = located + unresolved
    assert len(all_places) == 1
    assert set(all_places[0].lists) == {"First", "Second"}


def test_located_entry_wins_over_unlocated_for_the_same_place():
    entries = [
        raw(name="Dup", feature_id="0x1:0x2"),
        raw(name="Dup", feature_id="0x1:0x2", lat=40.7, lon=-74.0),
    ]
    located, unresolved = normalize(entries, region_bbox=NYC_BBOX)
    assert len(located) == 1
    assert unresolved == []
    assert located[0].lat == 40.7


def test_located_and_unresolved_are_disjoint_and_conserve_input():
    entries = [
        raw(name="Has Coords", feature_id="0x1:0x1", lat=40.7, lon=-74.0),
        raw(name="No Coords", feature_id="0x2:0x2"),
    ]
    located, unresolved = normalize(entries, region_bbox=NYC_BBOX)
    assert len(located) == 1
    assert len(unresolved) == 1
    assert {p.identity_key for p in located}.isdisjoint({p.identity_key for p in unresolved})


def test_unresolved_entries_carry_a_reason_code():
    located, unresolved = normalize([raw(name="No Coords")], region_bbox=NYC_BBOX)
    assert unresolved[0].needs_geocoding is True
    assert unresolved[0].geocode_reason


def test_out_of_region_place_is_flagged_not_dropped():
    # A Seattle thrift store in an NYC list is still a saved place.
    located, _ = normalize(
        [raw(name="Far Away", lat=47.55, lon=-122.04)], region_bbox=NYC_BBOX
    )
    assert len(located) == 1
    assert located[0].outside_region is True


def test_in_region_place_is_not_flagged():
    located, _ = normalize([raw(name="Nearby", lat=40.7, lon=-74.0)], region_bbox=NYC_BBOX)
    assert located[0].outside_region is False


def test_output_order_is_deterministic_regardless_of_input_order():
    a = raw(name="Alpha", feature_id="0x1:0x1", lat=40.7, lon=-74.0)
    b = raw(name="Beta", feature_id="0x2:0x2", lat=40.8, lon=-73.9)
    first, _ = normalize([a, b], region_bbox=NYC_BBOX)
    second, _ = normalize([b, a], region_bbox=NYC_BBOX)
    assert [p.identity_key for p in first] == [p.identity_key for p in second]


def test_non_place_urls_are_reported_as_such():
    located, unresolved = normalize(
        [raw(name="Some Article", url="https://example.com/an-article")],
        region_bbox=NYC_BBOX,
    )
    assert located == []
    assert unresolved[0].geocode_reason == "not_a_place"
