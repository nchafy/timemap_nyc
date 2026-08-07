"""`timemap-places`: turn a Google Takeout export into map-ready GeoJSON.

Reads only local files. No network, no geocoding -- unresolved places are
reported so the geocoding decision can be made with real numbers instead of
guesses.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from .csv_source import parse_csv_list
from .discovery import discover_sources
from .errors import TakeoutError
from .geojson_source import parse_saved_places
from .models import RawEntry
from .normalize import normalize
from .report import build_report, format_summary
from .writer import write_outputs

# NYC metro, generous: five boroughs plus Jersey City and Yonkers. Used only to
# flag out-of-region places, never to exclude them.
DEFAULT_BBOX = (-74.35, 40.45, -73.65, 41.00)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_THRESHOLD = 2


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        entries = _read_sources(args.takeout_dir)
        located, unresolved = normalize(entries, region_bbox=args.region_bbox)
        report = build_report(
            located,
            unresolved,
            source_count=len(entries),
            duplicates_merged=len(entries) - (len(located) + len(unresolved)),
        )
        write_outputs(args.out_dir, located, unresolved, report)
    except TakeoutError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED

    if not args.quiet:
        print(format_summary(report), file=sys.stderr)

    total = report["total_places"]
    if args.max_unresolved_fraction is not None and total:
        fraction = report["unresolved_count"] / total
        if fraction > args.max_unresolved_fraction:
            print(
                f"error: {fraction:.0%} of places need coordinates, "
                f"above the {args.max_unresolved_fraction:.0%} limit",
                file=sys.stderr,
            )
            return EXIT_THRESHOLD
    return EXIT_OK


def _read_sources(takeout_dir: pathlib.Path) -> list[RawEntry]:
    sources = discover_sources(takeout_dir)
    entries: list[RawEntry] = []
    for csv_path in sources.csv_lists:
        entries.extend(parse_csv_list(csv_path))
    if sources.saved_places_json is not None:
        entries.extend(parse_saved_places(sources.saved_places_json))
    return entries


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="timemap-places",
        description="Import Google Maps saved places from a Takeout export into GeoJSON.",
    )
    parser.add_argument(
        "--takeout-dir",
        type=pathlib.Path,
        default=pathlib.Path("data/takeout"),
        help="unzipped Takeout export (default: data/takeout)",
    )
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=pathlib.Path("data/places"),
        help="where to write the output files (default: data/places)",
    )
    parser.add_argument(
        "--region-bbox",
        type=_bbox,
        default=DEFAULT_BBOX,
        metavar="LON_MIN,LAT_MIN,LON_MAX,LAT_MAX",
        help="places outside this box are flagged, not dropped",
    )
    parser.add_argument(
        "--max-unresolved-fraction",
        type=float,
        default=None,
        metavar="FRACTION",
        help="exit 2 if more than this fraction need coordinates (default: no limit)",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress the summary")
    return parser.parse_args(argv)


def _bbox(raw: str) -> tuple[float, float, float, float]:
    parts = raw.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("expected LON_MIN,LAT_MIN,LON_MAX,LAT_MAX")
    try:
        lon_min, lat_min, lon_max, lat_max = (float(p) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not four numbers: {exc}") from exc
    return lon_min, lat_min, lon_max, lat_max


if __name__ == "__main__":
    raise SystemExit(main())
