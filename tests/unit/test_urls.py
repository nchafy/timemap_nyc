"""Google Maps URL parsing.

Measuring the real export established that NO url carries coordinates (0 of 768):
they are `/maps/place/<Name>/data=!4m2!3m1!1s0x…:0x…`, where the hex pair is a
feature id. So this module extracts the *name* and *feature id*, and explicitly
proves coordinates are not invented from a url.
"""

from __future__ import annotations

import pytest

from timemap.places.urls import (
    extract_feature_id,
    extract_place_name,
    is_google_maps_place_url,
)

PLACE_URL = (
    "https://www.google.com/maps/place/Nostrand+Avenue+Pub/"
    "data=!4m2!3m1!1s0x89c25b9c843094b5:0x97e7ef230b9352d"
)


def test_recognises_a_maps_place_url():
    assert is_google_maps_place_url(PLACE_URL) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/an-article",
        "https://www.verywellhealth.com/something",
        "",
    ],
)
def test_rejects_non_place_urls(url):
    assert is_google_maps_place_url(url) is False


def test_extracts_name_from_path():
    assert extract_place_name(PLACE_URL) == "Nostrand Avenue Pub"


def test_decodes_percent_and_plus_encoding_in_name():
    url = "https://www.google.com/maps/place/BARZAKH%E2%80%A2+CAF%C3%89/data=!4m2!3m1!1s0x1:0x2"
    assert extract_place_name(url) == "BARZAKH• CAFÉ"


def test_extracts_feature_id():
    assert extract_feature_id(PLACE_URL) == "0x89c25b9c843094b5:0x97e7ef230b9352d"


def test_feature_id_absent_returns_none():
    assert extract_feature_id("https://www.google.com/maps/place/X/data=nothing") is None


def test_extracts_ftid_style_identifier():
    url = "http://maps.google.com/?q=7+Unknown+St&ftid=0x7777777777777777:0x8888888888888888"
    assert extract_feature_id(url) == "0x7777777777777777:0x8888888888888888"


def test_extracts_cid_style_identifier():
    assert extract_feature_id("http://maps.google.com/?cid=1234567890123456789") == (
        "cid:1234567890123456789"
    )


def test_name_is_none_when_path_has_no_place_segment():
    assert extract_place_name("http://maps.google.com/?cid=123") is None
