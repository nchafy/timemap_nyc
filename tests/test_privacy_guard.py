"""SC-010: committed fixtures must never contain real saved-place data.

This is the test that keeps the fixtures honest as they grow. Adding a fixture
without documenting it in PROVENANCE.md fails the suite.
"""

from __future__ import annotations

import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
PROVENANCE = FIXTURES / "PROVENANCE.md"


def fixture_files() -> list[pathlib.Path]:
    return sorted(p for p in FIXTURES.rglob("*") if p.is_file() and p.name != "PROVENANCE.md")


def test_provenance_file_exists():
    assert PROVENANCE.is_file()


def test_every_fixture_is_documented_in_provenance():
    text = PROVENANCE.read_text(encoding="utf-8")
    undocumented = [p.name for p in fixture_files() if p.name not in text]
    assert undocumented == [], f"add these to PROVENANCE.md: {undocumented}"


def test_no_fixture_lives_outside_a_documented_export_tree():
    allowed_roots = {"takeout_min", "takeout_edge"}
    for p in fixture_files():
        assert p.relative_to(FIXTURES).parts[0] in allowed_roots


def test_fixtures_do_not_contain_the_real_export_marker():
    # The owner's real lists have distinctive names; none may appear in fixtures.
    forbidden = ["Food NYC", "Food Seattle", "法拉盛", "Nostrand", "Massachoosits"]
    for p in fixture_files():
        content = p.read_bytes().decode("utf-8", "replace")
        for token in forbidden:
            assert token not in content, f"{p.name} contains real data: {token!r}"
