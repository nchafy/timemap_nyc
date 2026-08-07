"""Ingest failures. Every error names the file or directory that caused it."""

from __future__ import annotations

import pathlib


class TakeoutError(Exception):
    """Base class for anything wrong with a Takeout export."""

    def __init__(self, path: pathlib.Path | str, detail: str) -> None:
        self.path = pathlib.Path(path)
        self.detail = detail
        super().__init__(f"{path}: {detail}")


class UnrecognizedExportLayout(TakeoutError):
    """The directory is missing or holds no recognisable saved-places sources."""


class SourceFileUnreadable(TakeoutError):
    """The bytes could not be decoded as text in any supported encoding."""


class SourceFileMalformed(TakeoutError):
    """The file decoded but its structure is not a saved-places source."""


class OutputWriteError(TakeoutError):
    """An output file could not be written."""
