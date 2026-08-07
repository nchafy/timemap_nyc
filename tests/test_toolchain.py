"""The project is installable and the interpreter is the pinned one.

Without a test the CI job would pass trivially, and a green check that proves
nothing is worse than no check.
"""

from __future__ import annotations

import pathlib
import sys


def test_python_is_at_least_3_12():
    assert sys.version_info[:2] >= (3, 12)


def test_pinned_version_matches_the_running_interpreter():
    pinned = (pathlib.Path(__file__).parent.parent / ".python-version").read_text().strip()
    assert ".".join(str(v) for v in sys.version_info[:2]) == pinned


def test_package_is_importable():
    import timemap

    assert timemap is not None
