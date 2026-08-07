"""End-to-end over the committed fixture. Always runs in CI.

SC-001 conservation, SC-003 zero network, SC-004 determinism, SC-006 dedupe,
SC-011 failure legibility.
"""

from __future__ import annotations

import json
import socket

import pytest

from timemap.places.cli import main


def run(takeout, out, *extra) -> int:
    return main(["--takeout-dir", str(takeout), "--out-dir", str(out), "--quiet", *extra])


def read(out, name):
    return json.loads((out / name).read_text(encoding="utf-8"))


def test_writes_three_output_files(takeout_min, tmp_path):
    assert run(takeout_min, tmp_path) == 0
    assert (tmp_path / "places.geojson").is_file()
    assert (tmp_path / "places.unresolved.geojson").is_file()
    assert (tmp_path / "places.report.json").is_file()


def test_conservation_located_plus_unresolved_equals_total(takeout_min, tmp_path):
    run(takeout_min, tmp_path)
    located = read(tmp_path, "places.geojson")["features"]
    unresolved = read(tmp_path, "places.unresolved.geojson")["features"]
    report = read(tmp_path, "places.report.json")
    assert len(located) + len(unresolved) == report["total_places"]


def test_no_place_is_dropped_or_duplicated(takeout_min, tmp_path):
    run(takeout_min, tmp_path)
    keys = [
        f["properties"]["identity_key"]
        for coll in ("places.geojson", "places.unresolved.geojson")
        for f in read(tmp_path, coll)["features"]
    ]
    assert len(keys) == len(set(keys))


def test_place_saved_in_two_lists_appears_once_with_both(takeout_min, tmp_path):
    run(takeout_min, tmp_path)
    feats = read(tmp_path, "places.geojson")["features"]
    feats += read(tmp_path, "places.unresolved.geojson")["features"]
    diner = [f for f in feats if f["properties"]["name"] == "Fictional Diner"]
    assert len(diner) == 1
    assert set(diner[0]["properties"]["lists"]) == {"Test Diner List", "Test Favourites"}


def test_second_run_is_byte_identical(takeout_min, tmp_path):
    run(takeout_min, tmp_path)
    first = {n: (tmp_path / n).read_bytes() for n in ("places.geojson", "places.unresolved.geojson")}
    run(takeout_min, tmp_path)
    for name, data in first.items():
        assert (tmp_path / name).read_bytes() == data


def test_makes_no_network_connections(takeout_min, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("ingest attempted a network connection")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert run(takeout_min, tmp_path) == 0


def test_non_place_url_is_reported_not_mapped(takeout_min, tmp_path):
    run(takeout_min, tmp_path)
    unresolved = read(tmp_path, "places.unresolved.geojson")["features"]
    reasons = {f["properties"]["name"]: f["properties"]["geocode_reason"] for f in unresolved}
    assert reasons.get("Some Article") == "not_a_place"


def test_missing_takeout_dir_exits_nonzero_and_writes_nothing(tmp_path):
    out = tmp_path / "out"
    code = main(["--takeout-dir", str(tmp_path / "absent"), "--out-dir", str(out), "--quiet"])
    assert code != 0
    assert not (out / "places.geojson").exists()


def test_unrecognised_layout_names_the_path(tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    code = main(["--takeout-dir", str(empty), "--out-dir", str(tmp_path / "o")])
    assert code != 0
    assert str(empty) in capsys.readouterr().err


def test_edge_fixture_ingests_without_error(takeout_edge, tmp_path):
    assert run(takeout_edge, tmp_path) == 0
    total = read(tmp_path, "places.report.json")["total_places"]
    assert total >= 3


@pytest.mark.parametrize("name", ["places.geojson", "places.unresolved.geojson"])
def test_output_ends_with_a_newline(takeout_min, tmp_path, name):
    # Keeps the files diffable and POSIX-clean.
    run(takeout_min, tmp_path)
    assert (tmp_path / name).read_bytes().endswith(b"\n")
