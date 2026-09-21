"""SC-005, SC-007: the output files conform to their published schemas.

Schemas are the contract the MapLibre frontend and any later API will code
against, so they are asserted independently of how the pipeline happens to work.
"""

from __future__ import annotations

import json
import pathlib

import jsonschema
import pytest

from timemap.places.cli import main

SCHEMAS = pathlib.Path(__file__).parent / "schemas"


@pytest.fixture(scope="module")
def outputs(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("out")
    fixtures = pathlib.Path(__file__).parent.parent / "fixtures" / "takeout_min"
    exit_code = main(["--takeout-dir", str(fixtures), "--out-dir", str(out), "--quiet"])
    assert exit_code == 0
    return {
        "located": json.loads((out / "places.geojson").read_text(encoding="utf-8")),
        "unresolved": json.loads((out / "places.unresolved.geojson").read_text(encoding="utf-8")),
        "report": json.loads((out / "places.report.json").read_text(encoding="utf-8")),
    }


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_located_output_matches_schema(outputs):
    jsonschema.validate(outputs["located"], load_schema("places.schema.json"))


def test_unresolved_output_matches_schema(outputs):
    jsonschema.validate(outputs["unresolved"], load_schema("places_unresolved.schema.json"))


def test_report_matches_schema(outputs):
    jsonschema.validate(outputs["report"], load_schema("report.schema.json"))


def test_located_features_are_rfc7946_points(outputs):
    assert outputs["located"]["type"] == "FeatureCollection"
    for feat in outputs["located"]["features"]:
        assert feat["geometry"]["type"] == "Point"
        coords = feat["geometry"]["coordinates"]
        assert len(coords) == 2
        lon, lat = coords
        assert -180 <= lon <= 180
        assert -90 <= lat <= 90


def test_no_located_feature_sits_at_null_island(outputs):
    for feat in outputs["located"]["features"]:
        assert feat["geometry"]["coordinates"] != [0, 0]


def test_unresolved_features_have_null_geometry_and_the_flag(outputs):
    for feat in outputs["unresolved"]["features"]:
        assert feat["geometry"] is None
        assert feat["properties"]["needs_geocoding"] is True
        assert feat["properties"]["geocode_reason"]


def test_every_feature_carries_the_required_properties(outputs):
    required = {"name", "lists", "needs_geocoding"}
    for coll in ("located", "unresolved"):
        for feat in outputs[coll]["features"]:
            assert required <= set(feat["properties"])


def test_reason_codes_come_from_a_closed_set(outputs):
    allowed = {"no_coordinates", "not_a_place", "no_url", "zero_coordinates"}
    for feat in outputs["unresolved"]["features"]:
        assert feat["properties"]["geocode_reason"] in allowed
