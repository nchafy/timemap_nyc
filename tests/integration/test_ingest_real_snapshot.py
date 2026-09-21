"""End-to-end over the owner's private export. Skipped unless TIMEMAP_TAKEOUT_DIR is set.

These are the tests that would have caught the wrong assumptions in the original
plan, because only real data shows that no url carries coordinates.
"""

from __future__ import annotations

import json
import subprocess
import time

import pytest

from timemap.places.cli import main

pytestmark = pytest.mark.real_snapshot


@pytest.fixture(scope="module")
def ingested(real_takeout_dir, tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("real")
    started = time.monotonic()
    code = main(["--takeout-dir", str(real_takeout_dir), "--out-dir", str(out), "--quiet"])
    elapsed = time.monotonic() - started
    assert code == 0
    return {
        "out": out,
        "elapsed": elapsed,
        "located": json.loads((out / "places.geojson").read_text(encoding="utf-8")),
        "unresolved": json.loads((out / "places.unresolved.geojson").read_text(encoding="utf-8")),
        "report": json.loads((out / "places.report.json").read_text(encoding="utf-8")),
    }


def test_ingests_the_real_export(ingested):
    assert ingested["report"]["total_places"] > 0


def test_conservation_invariant_holds_on_real_data(ingested):
    located = len(ingested["located"]["features"])
    unresolved = len(ingested["unresolved"]["features"])
    assert located + unresolved == ingested["report"]["total_places"]


def test_all_located_coordinates_are_valid(ingested):
    for feat in ingested["located"]["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        assert -180 <= lon <= 180
        assert -90 <= lat <= 90
        assert (lon, lat) != (0, 0)


def test_no_duplicate_identity_keys(ingested):
    keys = [
        f["properties"]["identity_key"]
        for coll in ("located", "unresolved")
        for f in ingested[coll]["features"]
    ]
    assert len(keys) == len(set(keys))


def test_every_unresolved_entry_has_provenance_and_a_reason(ingested):
    for entry in ingested["report"]["unresolved"]:
        assert entry["name"]
        assert entry["lists"]
        assert entry["reason"]


def test_completes_quickly(ingested):
    assert ingested["elapsed"] < 5.0


def test_ingesting_real_data_adds_nothing_to_git(real_takeout_dir, ingested):
    """SC-010: no personal data becomes committable.

    Asserts that nothing under data/ is visible to git, rather than that the
    whole tree is clean -- a developer with work in progress would trip that,
    which would make the test noise rather than a signal.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
        check=True,
    )
    offending = [
        line for line in result.stdout.splitlines() if "data/" in line or "places.geojson" in line
    ]
    assert offending == []


def test_writes_nothing_outside_the_out_dir(ingested):
    names = sorted(p.name for p in ingested["out"].iterdir())
    assert names == ["places.geojson", "places.report.json", "places.unresolved.geojson"]
