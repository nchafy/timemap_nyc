from __future__ import annotations

import os
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def takeout_min() -> pathlib.Path:
    """A minimal well-formed export: the happy path."""
    return FIXTURES / "takeout_min"


@pytest.fixture(scope="session")
def takeout_edge() -> pathlib.Path:
    """Encoding and malformed-input cases."""
    return FIXTURES / "takeout_edge"


@pytest.fixture(scope="session")
def real_takeout_dir() -> pathlib.Path:
    """The owner's private export. Requesting this fixture is what skips the test.

    Never committed, so CI runs everything except tests that ask for it.
    """
    raw = os.environ.get("TIMEMAP_TAKEOUT_DIR")
    if not raw:
        pytest.skip("TIMEMAP_TAKEOUT_DIR not set; real-snapshot tests skipped")
    path = pathlib.Path(raw).expanduser()
    if not path.is_dir():
        pytest.skip(f"TIMEMAP_TAKEOUT_DIR={path} does not exist")
    return path
