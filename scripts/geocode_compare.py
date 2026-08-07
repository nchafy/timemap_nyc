"""Geocode the sample with Nominatim, Photon, and Google Places; compare.

One-off investigation. Reads scripts/candidates.json, writes scripts/results.json.

No ground truth exists for these NYC places (the only coordinate-bearing
entries in the export are 9 foreign + 1 US place, none of which appear in the
CSV lists). So this measures:

  1. hit rate      - did the provider return anything at all
  2. plausibility  - is the result inside the NYC metro bounding box
  3. agreement     - how far apart are the providers on the same place

Agreement is the strongest available signal: when two independent providers
land within ~100m, both are probably right. When they disagree by kilometres,
at least one is wrong, and the borough check usually says which.

Usage:
    python3 scripts/geocode_compare.py nominatim
    python3 scripts/geocode_compare.py photon
    GOOGLE_PLACES_KEY=... python3 scripts/geocode_compare.py google
    python3 scripts/geocode_compare.py compare
"""

from __future__ import annotations

import json
import math
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse as up
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
CANDIDATES = HERE / "candidates.json"
RESULTS = HERE / "results.json"

UA = "timemap_nyc/0.1 (personal isochrone project; contact chafyni)"

# NYC metro, generous: covers all five boroughs, Jersey City, Yonkers.
NYC_BBOX = (-74.35, 40.45, -73.65, 41.00)  # lon_min, lat_min, lon_max, lat_max

# Rate limits. Nominatim's usage policy is a hard 1 req/s -- exceeding it gets
# the project banned, so this is deliberately conservative.
DELAYS = {"nominatim": 1.1, "photon": 0.2, "google": 0.05}


def fetch(url: str, headers: dict | None = None, timeout: int = 20) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def in_bbox(lat: float, lon: float) -> bool:
    lon_min, lat_min, lon_max, lat_max = NYC_BBOX
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance in metres between (lat, lon) pairs."""
    r = 6_371_000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def query_text(place: dict) -> str:
    """The search string. Title is populated for all 754 rows and matches the
    URL-path name exactly, so it needs no cleanup. 'New York' is appended
    because a bare business name is ambiguous worldwide."""
    return f"{place['title']}, New York"


# --- providers -------------------------------------------------------------


def geocode_nominatim(place: dict) -> dict:
    q = up.urlencode(
        {
            "q": query_text(place),
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
            "viewbox": ",".join(str(c) for c in NYC_BBOX),
            "bounded": 1,
        }
    )
    data = fetch(f"https://nominatim.openstreetmap.org/search?{q}")
    if not data:
        return {"ok": False, "reason": "no_match"}
    top = data[0]
    return {
        "ok": True,
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "matched_name": top.get("display_name", "").split(",")[0],
        "category": f"{top.get('category')}/{top.get('type')}",
    }


def geocode_photon(place: dict) -> dict:
    q = up.urlencode(
        {
            "q": query_text(place),
            "limit": 1,
            "lat": 40.7128,  # bias toward NYC; Photon has no hard bbox filter
            "lon": -74.0060,
        }
    )
    data = fetch(f"https://photon.komoot.io/api/?{q}")
    feats = data.get("features") or []
    if not feats:
        return {"ok": False, "reason": "no_match"}
    top = feats[0]
    lon, lat = top["geometry"]["coordinates"]
    props = top.get("properties", {})
    return {
        "ok": True,
        "lat": lat,
        "lon": lon,
        "matched_name": props.get("name"),
        "category": f"{props.get('osm_key')}/{props.get('osm_value')}",
    }


# Client-side spend guard. This is defence-in-depth only -- the real guarantee
# is a per-day quota set in the Cloud console, because a cap in this file cannot
# stop anything else from using the key. Text Search Pro allows 5,000 free
# billable events/month; this ceiling keeps one run three orders of magnitude
# under that even if it is re-run repeatedly by mistake.
GOOGLE_MAX_CALLS = 70
_google_calls = 0


def geocode_google(place: dict) -> dict:
    global _google_calls
    key = os.environ.get("GOOGLE_PLACES_KEY")
    if not key:
        return {"ok": False, "reason": "no_api_key"}
    if _google_calls >= GOOGLE_MAX_CALLS:
        return {"ok": False, "reason": "local_cap_reached"}
    _google_calls += 1
    body = json.dumps(
        {
            "textQuery": query_text(place),
            "locationBias": {
                "rectangle": {
                    "low": {"latitude": NYC_BBOX[1], "longitude": NYC_BBOX[0]},
                    "high": {"latitude": NYC_BBOX[3], "longitude": NYC_BBOX[2]},
                }
            },
            "maxResultCount": 1,
        }
    ).encode()
    req = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchText",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "places.displayName,places.location,places.formattedAddress",
            "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        # Places API (New) may not be enabled on the project even when the
        # legacy Places API is. Same underlying place database and same 5,000
        # free events/month, so fall back rather than abandon the arm.
        if exc.code == 403 and ("has not been used in project" in detail or "disabled" in detail):
            return geocode_google_legacy(place, key)
        raise

    places = data.get("places") or []
    if not places:
        return {"ok": False, "reason": "no_match"}
    top = places[0]
    loc = top.get("location", {})
    return {
        "ok": True,
        "lat": loc.get("latitude"),
        "lon": loc.get("longitude"),
        "matched_name": (top.get("displayName") or {}).get("text"),
        "category": "places_new",
    }


def geocode_google_legacy(place: dict, key: str) -> dict:
    """Legacy Places Text Search. Same place data, same free cap as the new API."""
    q = up.urlencode(
        {
            "query": query_text(place),
            "location": "40.7128,-74.0060",
            "radius": 40000,
            "key": key,
        }
    )
    data = fetch(f"https://maps.googleapis.com/maps/api/place/textsearch/json?{q}")
    status = data.get("status")
    if status == "ZERO_RESULTS":
        return {"ok": False, "reason": "no_match"}
    if status != "OK":
        # Never echo the error message: it can contain the key.
        return {"ok": False, "reason": f"api_status_{status}"}
    top = (data.get("results") or [{}])[0]
    loc = top.get("geometry", {}).get("location", {})
    return {
        "ok": True,
        "lat": loc.get("lat"),
        "lon": loc.get("lng"),
        "matched_name": top.get("name"),
        "category": "places_legacy",
    }


PROVIDERS = {
    "nominatim": geocode_nominatim,
    "photon": geocode_photon,
    "google": geocode_google,
}


# --- run / compare ---------------------------------------------------------


def load_results() -> dict:
    if RESULTS.exists():
        return json.loads(RESULTS.read_text(encoding="utf-8"))
    return {}


def run(provider: str) -> None:
    fn = PROVIDERS[provider]
    places = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    results = load_results()
    bucket = results.setdefault(provider, {})
    delay = DELAYS[provider]

    started = time.monotonic()
    for i, place in enumerate(places, 1):
        key = place["key"]
        if key in bucket:
            continue  # resumable: never re-bill or re-hammer a provider
        try:
            out = fn(place)
        except Exception as exc:  # record and keep going
            out = {"ok": False, "reason": f"error: {type(exc).__name__}: {exc}"}
        out["title"] = place["title"]
        bucket[key] = out
        status = "ok" if out.get("ok") else out.get("reason", "fail")
        print(f"  [{i:2d}/{len(places)}] {place['title'][:42]:42s} {status}")
        if out.get("reason") == "no_api_key":
            print("  aborting: GOOGLE_PLACES_KEY not set")
            break
        RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(delay)

    elapsed = time.monotonic() - started
    hits = sum(1 for v in bucket.values() if v.get("ok"))
    print(f"\n{provider}: {hits}/{len(bucket)} hits in {elapsed:.1f}s")


def compare() -> None:
    places = {p["key"]: p for p in json.loads(CANDIDATES.read_text(encoding="utf-8"))}
    results = load_results()
    names = [p for p in PROVIDERS if p in results and results[p]]
    if not names:
        print("no results yet")
        return

    print(f"sample: {len(places)} NYC places\n")
    print(f"{'provider':<12} {'hit rate':>10} {'in NYC bbox':>13} {'outside/none':>13}")
    print("-" * 52)
    for n in names:
        b = results[n]
        ok = [v for v in b.values() if v.get("ok")]
        inb = [v for v in ok if in_bbox(v["lat"], v["lon"])]
        pct = 100 * len(ok) / len(places) if places else 0
        ipct = 100 * len(inb) / len(places) if places else 0
        print(
            f"{n:<12} {len(ok):>4}/{len(places):<4} {pct:>3.0f}% "
            f"{len(inb):>4} {ipct:>3.0f}%   {len(places) - len(inb):>6}"
        )

    # Pairwise agreement -- the strongest signal available without ground truth.
    print("\npairwise agreement (both providers returned a hit):")
    print(f"{'pair':<24} {'n':>4} {'<100m':>7} {'<500m':>7} {'>2km':>7} {'median':>9}")
    print("-" * 62)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            ds = []
            for k in places:
                ra, rb = results[a].get(k), results[b].get(k)
                if not (ra and rb and ra.get("ok") and rb.get("ok")):
                    continue
                ds.append(haversine_m((ra["lat"], ra["lon"]), (rb["lat"], rb["lon"])))
            if not ds:
                continue
            ds.sort()
            med = ds[len(ds) // 2]
            close = sum(1 for d in ds if d < 100)
            mid = sum(1 for d in ds if d < 500)
            far = sum(1 for d in ds if d > 2000)
            print(
                f"{a[:10]}/{b[:10]:<13} {len(ds):>4} {close:>7} {mid:>7} {far:>7} {med:>7.0f}m"
            )

    # Where they disagree most -- these are the cases worth eyeballing.
    if len(names) >= 2:
        a, b = names[0], names[1]
        rows = []
        for k, p in places.items():
            ra, rb = results[a].get(k), results[b].get(k)
            if not (ra and rb and ra.get("ok") and rb.get("ok")):
                continue
            d = haversine_m((ra["lat"], ra["lon"]), (rb["lat"], rb["lon"]))
            rows.append((d, p["title"], ra.get("matched_name"), rb.get("matched_name")))
        rows.sort(reverse=True)
        print(f"\nworst {a} vs {b} disagreements:")
        for d, title, na, nb in rows[:8]:
            print(f"  {d:>9.0f}m  {title[:30]:30s} | {a}={str(na)[:22]:22s} {b}={str(nb)[:22]}")

    # Coverage gaps: places nobody could find are the real ceiling on the map.
    missed = [
        places[k]["title"]
        for k in places
        if not any(results.get(n, {}).get(k, {}).get("ok") for n in names)
    ]
    print(f"\nfound by no provider: {len(missed)}/{len(places)}")
    for t in missed[:10]:
        print(f"  {t}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    cmd = sys.argv[1]
    if cmd == "compare":
        compare()
    elif cmd in PROVIDERS:
        run(cmd)
    else:
        print(f"unknown: {cmd}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
