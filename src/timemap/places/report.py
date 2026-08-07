"""The ingest report.

Its job is to make the geocoding backlog legible: how many places need
coordinates, why, and which lists they came from. Measured on the owner's real
export, that backlog is ~98% of all saved places, so this is the document that
drives the geocoding decision rather than a footnote.
"""

from __future__ import annotations

from collections import Counter

from .models import SavedPlace


def build_report(
    located: list[SavedPlace],
    unresolved: list[SavedPlace],
    *,
    source_count: int,
    duplicates_merged: int,
) -> dict:
    reasons = Counter(p.geocode_reason for p in unresolved if p.geocode_reason)
    return {
        "total_places": len(located) + len(unresolved),
        "located_count": len(located),
        "unresolved_count": len(unresolved),
        "duplicates_merged": duplicates_merged,
        "outside_region_count": sum(1 for p in located if p.outside_region),
        "source_entry_count": source_count,
        "unresolved_by_reason": dict(sorted(reasons.items())),
        "unresolved": [
            {
                "name": p.name,
                "lists": list(p.lists),
                "url": p.url,
                "reason": p.geocode_reason or "",
            }
            for p in unresolved
        ],
    }


def format_summary(report: dict) -> str:
    """A one-screen human summary for stderr."""
    lines = [
        f"{report['total_places']} places "
        f"({report['located_count']} located, {report['unresolved_count']} need coordinates)",
    ]
    if report["duplicates_merged"]:
        lines.append(f"  merged {report['duplicates_merged']} duplicate entries")
    if report["outside_region_count"]:
        lines.append(f"  {report['outside_region_count']} outside the region (kept, flagged)")
    for reason, count in report["unresolved_by_reason"].items():
        lines.append(f"  {count} {reason}")
    return "\n".join(lines)
