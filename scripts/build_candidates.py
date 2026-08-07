"""Build the geocoder comparison sample from the local Takeout export.

One-off investigation, not part of the shipped package. Reads only from
data/takeout/ and writes only to scripts/, both gitignored.
"""

from __future__ import annotations

import csv
import json
import pathlib
import random
import re

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
SAVED = REPO / "data" / "takeout" / "Takeout" / "Saved"
PLACES_JSON = REPO / "data" / "takeout" / "Takeout" / "Maps (your places)" / "Saved Places.json"
OUT = HERE / "candidates.json"

# Which saved lists are NYC-area. Geocoding a Tokyo restaurant tells us nothing
# about accuracy for this project, and an unbiased sample would be mostly
# non-NYC. The list names themselves are personal data (they leak neighbourhoods
# and interests), so they live in the gitignored data/ dir, not in the repo.
# Falls back to substring matching if the file is absent.
NYC_LISTS_FILE = REPO / "data" / "nyc_lists.json"
NYC_LIST_HINTS = ("nyc", "brooklyn", "queens", "manhattan", "bronx")


def nyc_lists() -> set[str]:
    if NYC_LISTS_FILE.exists():
        return set(json.loads(NYC_LISTS_FILE.read_text(encoding="utf-8")))
    return set()


SAMPLE_SIZE = 60
SEED = 20260803  # fixed so the sample is reproducible across runs


def csv_rows() -> list[dict]:
    rows = []
    for path in sorted(SAVED.glob("*.csv")):
        text = path.read_bytes().decode("utf-8-sig")
        for row in csv.DictReader(text.splitlines()):
            title = (row.get("Title") or "").strip()
            url = (row.get("URL") or "").strip()
            if not title and not url:
                continue  # trailing blank row, present in 2 of 35 files
            if "google.com" not in url:
                continue  # 5 rows are article links, not places
            rows.append(
                {
                    "title": title,
                    "url": url,
                    "list": path.stem,
                    "feature_id": extract_feature_id(url),
                }
            )
    return rows


def extract_feature_id(url: str) -> str | None:
    m = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", url)
    return m.group(1) if m else None


def truth_from_geojson() -> dict[str, dict]:
    """The 10 places that already have coordinates — our only ground truth."""
    truth = {}
    data = json.loads(PLACES_JSON.read_text(encoding="utf-8"))
    for feat in data.get("features", []):
        coords = (feat.get("geometry") or {}).get("coordinates")
        if not coords or coords == [0, 0]:
            continue
        loc = feat.get("properties", {}).get("location") or {}
        name = (loc.get("name") or "").strip()
        if not name:
            continue
        truth[name.lower()] = {
            "name": name,
            "address": loc.get("address"),
            "lon": coords[0],
            "lat": coords[1],
        }
    return truth


def main() -> None:
    rows = csv_rows()
    truth = truth_from_geojson()

    # Deduplicate on feature id (falling back to title), unioning list membership.
    by_key: dict[str, dict] = {}
    for r in rows:
        key = r["feature_id"] or r["title"].lower()
        if key in by_key:
            by_key[key]["lists"].append(r["list"])
            continue
        by_key[key] = {
            "key": key,
            "title": r["title"],
            "url": r["url"],
            "lists": [r["list"]],
            "feature_id": r["feature_id"],
        }

    places = list(by_key.values())
    allow = nyc_lists()
    if allow:
        nyc = [p for p in places if any(lst in allow for lst in p["lists"])]
    else:
        nyc = [
            p for p in places if any(h in lst.lower() for lst in p["lists"] for h in NYC_LIST_HINTS)
        ]

    rng = random.Random(SEED)
    sample = rng.sample(nyc, min(SAMPLE_SIZE, len(nyc)))

    # Attach ground truth where the GeoJSON export happens to cover it.
    n_truth = 0
    for p in sample:
        t = truth.get(p["title"].lower())
        if t:
            p["truth"] = {"lat": t["lat"], "lon": t["lon"], "address": t["address"]}
            n_truth += 1

    # The 10 coordinate-bearing GeoJSON places turn out to be 9 foreign + 1 US,
    # none of which appear in any CSV list, so NYC ground truth is unavailable.
    # Scoring therefore relies on cross-geocoder agreement plus a borough-bbox
    # plausibility check, not on absolute error.
    OUT.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"csv place rows       : {len(rows)}")
    print(f"unique places        : {len(places)}")
    print(f"in NYC-area lists    : {len(nyc)}")
    print(f"sampled (seed {SEED}): {len(sample)}")
    print(f"  with ground truth  : {n_truth}")
    print(f"geojson truth places : {len(truth)}")
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()
