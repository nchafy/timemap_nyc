"""Parsing one saved-list CSV. SC-001, SC-007, SC-008, SC-011."""

from __future__ import annotations

import pytest

from timemap.places.csv_source import parse_csv_list
from timemap.places.errors import SourceFileMalformed


def test_parses_the_real_header_shape(tmp_path):
    p = tmp_path / "My List.csv"
    p.write_text(
        "Title,Note,URL,Tags,Comment\n"
        "A Place,a note,https://www.google.com/maps/place/A+Place/data=!4m2!3m1!1s0x1:0x2,t,\n",
        encoding="utf-8",
    )
    entries = parse_csv_list(p)
    assert len(entries) == 1
    e = entries[0]
    assert e.name == "A Place"
    assert e.note == "a note"
    assert e.list_name == "My List"
    assert e.feature_id == "0x1:0x2"


def test_list_name_comes_from_the_filename_stem(tmp_path):
    p = tmp_path / "Food NYC.csv"
    p.write_text("Title,Note,URL,Tags,Comment\nX,,https://example.com/a,,\n", encoding="utf-8")
    assert parse_csv_list(p)[0].list_name == "Food NYC"


def test_tolerates_header_case_and_whitespace_variation(tmp_path):
    p = tmp_path / "L.csv"
    p.write_text(" title , note , url , tags , comment \nX,,,,\n", encoding="utf-8")
    assert parse_csv_list(p)[0].name == "X"


def test_tolerates_reordered_and_extra_columns(tmp_path):
    p = tmp_path / "L.csv"
    p.write_text("URL,Extra,Title\nhttps://example.com/a,junk,X\n", encoding="utf-8")
    e = parse_csv_list(p)[0]
    assert e.name == "X"
    assert e.url == "https://example.com/a"


def test_header_only_file_yields_no_entries(tmp_path):
    p = tmp_path / "Empty.csv"
    p.write_text("Title,Note,URL,Tags,Comment\n", encoding="utf-8")
    assert parse_csv_list(p) == []


def test_skips_trailing_blank_row(tmp_path):
    # 2 of the owner's 35 real lists end with a fully blank row.
    p = tmp_path / "L.csv"
    p.write_text(
        "Title,Note,URL,Tags,Comment\nX,,https://example.com/a,,\n,,,,\n", encoding="utf-8"
    )
    assert len(parse_csv_list(p)) == 1


def test_row_with_no_url_is_kept_and_flagged(tmp_path):
    p = tmp_path / "L.csv"
    p.write_text("Title,Note,URL,Tags,Comment\nNo Url Place,,,,\n", encoding="utf-8")
    e = parse_csv_list(p)[0]
    assert e.name == "No Url Place"
    assert e.url == ""


def test_row_with_blank_title_falls_back_to_url_name(tmp_path):
    p = tmp_path / "L.csv"
    p.write_text(
        "Title,Note,URL,Tags,Comment\n"
        ",,https://www.google.com/maps/place/Blank+Title/data=!4m2!3m1!1s0x1:0x2,,\n",
        encoding="utf-8",
    )
    assert parse_csv_list(p)[0].name == "Blank Title"


def test_row_with_neither_title_nor_url_is_dropped_not_errored(tmp_path):
    p = tmp_path / "L.csv"
    p.write_text("Title,Note,URL,Tags,Comment\n,,,,\n", encoding="utf-8")
    assert parse_csv_list(p) == []


def test_file_with_no_recognisable_header_raises_named_error(tmp_path):
    p = tmp_path / "Bad.csv"
    p.write_text("this,is,not,a,saved,list\n1,2,3,4,5,6\n", encoding="utf-8")
    with pytest.raises(SourceFileMalformed) as exc:
        parse_csv_list(p)
    assert str(p) in str(exc.value)


def test_parses_bom_and_crlf_fixture(takeout_edge):
    p = takeout_edge / "Takeout" / "Saved" / "Bom List.csv"
    entries = parse_csv_list(p)
    assert len(entries) == 1
    assert entries[0].name == "Café Fictif ☕"


def test_parses_utf16_fixture(takeout_edge):
    p = takeout_edge / "Takeout" / "Saved" / "Utf16 List.csv"
    assert parse_csv_list(p)[0].name == "Café Fictif ☕"
