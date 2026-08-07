"""Finding the source files inside a Takeout tree. SC-011."""

from __future__ import annotations

import pytest

from timemap.places.discovery import discover_sources
from timemap.places.errors import UnrecognizedExportLayout


def test_finds_csv_lists_and_saved_places_json(takeout_min):
    sources = discover_sources(takeout_min)
    assert len(sources.csv_lists) == 2
    assert sources.saved_places_json is not None


def test_csv_lists_are_returned_in_sorted_order(takeout_min):
    names = [p.name for p in discover_sources(takeout_min).csv_lists]
    assert names == sorted(names)


def test_works_when_given_the_takeout_dir_itself(takeout_min):
    # Accept either the parent or the Takeout/ dir -- users unzip both ways.
    sources = discover_sources(takeout_min / "Takeout")
    assert len(sources.csv_lists) == 2


def test_export_with_only_csv_lists_is_valid(takeout_edge):
    sources = discover_sources(takeout_edge)
    assert len(sources.csv_lists) == 4
    assert sources.saved_places_json is None


def test_ignores_unrelated_takeout_products(tmp_path):
    (tmp_path / "Takeout" / "Chrome").mkdir(parents=True)
    (tmp_path / "Takeout" / "Chrome" / "Bookmarks.html").write_text("x", encoding="utf-8")
    (tmp_path / "Takeout" / "Saved").mkdir()
    (tmp_path / "Takeout" / "Saved" / "L.csv").write_text("Title\nX\n", encoding="utf-8")
    sources = discover_sources(tmp_path)
    assert len(sources.csv_lists) == 1


def test_missing_directory_raises_named_error(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(UnrecognizedExportLayout) as exc:
        discover_sources(missing)
    assert str(missing) in str(exc.value)


def test_directory_with_no_known_sources_raises(tmp_path):
    (tmp_path / "random").mkdir()
    with pytest.raises(UnrecognizedExportLayout):
        discover_sources(tmp_path)
