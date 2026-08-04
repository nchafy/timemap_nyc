# Scripts

One-off investigations that answer a question before it gets baked into the real
package. Not imported by `src/`, and not held to the project's test-first rule —
but the *findings* belong in the repo, which is what this file is for.

The scripts are committed. Their outputs are not: `scripts/*.json` is gitignored
because it contains real saved-place names and coordinates. Same for
`data/nyc_lists.json`, which holds the owner's list names.

## 001 — Geocoder comparison (2026-08-03)

**Question.** Google Takeout exports saved places without usable coordinates. Which
geocoder should backfill them: Nominatim, Photon, or Google Places?

**Why it mattered.** The project outline left this as an open question and assumed
it could be deferred. It cannot. Measuring the real export showed 758 of 768 saved
places have no coordinates, so geocoding is not a follow-up — without it the map
renders 10 pins.

### What the export actually contains

| | Count |
|---|---|
| CSV rows across 35 custom lists | 754 |
| GeoJSON features (`Saved Places.json`) | 14 |
| **Places with usable coordinates** | **10** |
| Duplicate rows across lists | 35 |

Three findings that contradicted the original plan:

1. **No URL carries coordinates — 0 of 768.** Checked every entry for `!3d!4d`,
   `@lat,lng`, `ll=`, `center=`, and `q=<coords>`. Not one match. CSV URLs are
   `/maps/place/<Name>/data=!4m2!3m1!1s0x…:0x…`, where the hex pair is a *feature
   id*, not a coordinate. A URL-coordinate-extraction module would have been dead
   code.
2. **`Title` is populated for all 754 rows** and matches the URL-path name exactly,
   so it is the geocoding query. No parsing needed.
3. **Uniform format.** Every CSV has header `Title,Note,URL,Tags,Comment` and is
   UTF-8 without BOM. The localized-header and UTF-16 handling the plan called for
   does not apply to this export — though two list *filenames* are CJK and one has
   a curly apostrophe, so filename encoding still matters.

Also: `[0,0]` coordinates mean "absent", not a valid location off West Africa. The
4 zero-coordinate GeoJSON entries are exactly the 4 lacking a `location` block.

### Method

60 NYC-area places sampled with a fixed seed (reproducible), geocoded by each
provider by name. No ground truth exists — the only coordinate-bearing entries are
9 foreign places and 1 US place, none of which appear in the CSV lists — so scoring
uses exact-name-match rate plus cross-provider agreement.

### Results

| | Nominatim | Photon | **Google** |
|---|---|---|---|
| Found anything | 41/60 (68%) | 56/60 (93%) | **60/60 (100%)** |
| Exact name match | 34 (57%) | 33 (55%) | **53 (88%)** |
| Returned wrong business | 1 (2%) | 14 (23%) | **3 (5%)** |
| Found nothing | 19 (32%) | 4 (7%) | **0** |
| Wall clock | 101s | 42s | **26s** |

**Google wins decisively.** Cost: 60 Text Search Pro calls, 1.2% of the
5,000/month free cap.

The decisive number is not the hit rate: **Photon disagreed with Google by >2km on
36% of places both found.** Its 93% hit rate masked wrong answers rather than
missing ones — it answers confidently and is often a different business ("Cha Kee"
→ "McKee Place", 471km; "title of work" → "School of Social Work", 11km).
Nominatim has the opposite temperament: when it answers it is usually right, but it
silently fails on a third of the places. Neither is safe unsupervised — Photon puts
pins in wrong places, Nominatim leaves holes.

Where providers agreed they agreed strongly (30 of 41 Nominatim/Photon pairs within
100m, median 0m — often the identical OSM object). Disagreements cluster on
one-word and chain names: `Frank`, `Tong`, `Verse`, `Cove`,
`Artichoke Basille's Pizza`.

### Conclusions

1. **Use Google Places for coordinate backfill.** This conflicts with the
   open-source-only principle, which should be amended honestly rather than
   quietly violated: open source for rendering, routing, and tiles; Google Places
   permitted for one-time coordinate backfill. Place IDs are explicitly exempt
   from Google's caching restrictions, so results may be stored indefinitely and
   never re-billed.
2. **Region filtering must flag, not reject.** The one Google result outside the
   NYC bbox — "Issaquah Value Village" — is genuinely in Washington state. Google
   was right and the bbox filter was wrong. Lists mix cities.
3. **Next: test feature-id resolution.** All 746 CSV place rows carry a Google
   feature id identifying the *exact* venue saved. Name search cannot disambiguate
   a chain — every provider returned a real Artichoke Basille's, just not
   necessarily the right one. Resolving ids directly would be exact rather than
   best-guess, at ~15% of one month's free cap for all 768 places. This is the
   likeliest shape for the real ingest pipeline.

### Reproducing

```bash
python3 scripts/build_candidates.py                  # writes scripts/candidates.json
python3 scripts/geocode_compare.py nominatim         # ~101s (1 req/s policy limit)
python3 scripts/geocode_compare.py photon            # ~42s
GOOGLE_PLACES_KEY=... python3 scripts/geocode_compare.py google
python3 scripts/geocode_compare.py compare
```

Requires a Takeout export at `data/takeout/`. Optionally
`data/nyc_lists.json` (a JSON array of NYC list names); without it the script
falls back to substring matching on list names.

Results are cached per provider and skipped on re-run, so re-running costs no
additional API calls. The Google arm is hard-capped at 70 calls client-side;
note that a real guarantee requires a per-day quota in the Cloud console, since a
client-side cap cannot constrain anything else using the same key.

Extract Takeout zips with Python's `zipfile`, not `unzip` — `unzip` mangles the
CJK and curly-apostrophe filenames in this export and aborts with a misleading
"disk full" error.
