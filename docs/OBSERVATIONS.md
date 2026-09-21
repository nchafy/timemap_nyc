# OBSERVATIONS

**What this is for:** recording what this project measured or was surprised by, one dated line
each, so a later decision — in particular any decision about what this project shares with its
sibling `council_access_nyc` — is made from evidence instead of memory. **When to read it:**
before you generalise, extract, or copy anything between the two projects. Add to it at the
moment of noticing, not afterwards.

**Nothing here is approved, decided, or designed.** The source of truth remains
`isochrone-project-outline.md` and the settled calls remain in `CLAUDE.md`. Do not implement
anything from this file. Append only, newest at the bottom; never rewrite, reorder or tidy an
entry, because a stale entry is still a true dated observation. Long-form investigations keep
their existing home in `scripts/README.md`, which already records the 2026-08-03 geocoder
comparison in that format; this file does not replace it.

Write an entry when a source or a test surprised you, when you wrote something for the second or
third time or copied it from `council_access_nyc` (**including when you tried and it did not
fit** — the misfits are worth more than the matches), or when you decided against something for
a measured reason. Format: `- DATE | WHERE | WHAT | SO-WHAT`, where `WHERE` is an anchor you can
grep for, `WHAT` has the number in it, and `SO-WHAT` is one clause — what would survive a second
source, or `copied:` / `misfit:` / `refused:`. One bullet. If it needs a heading or a table, it
belongs in `scripts/README.md`.

## Entries

- 2026-09-21 | `tests/contract/test_output_contract.py` (`allowed = {..."zero_coordinates"}`) vs
  `normalize.py` (`REASON_NO_COORDINATES`, `REASON_NOT_A_PLACE`, `REASON_NO_URL`) | The contract
  test's allowed reason set has four members and the module defines three: `zero_coordinates` is
  admitted but no code path emits it, because `geojson_source` turns the export's explicit
  `[0,0]` sentinel into `(None, None)` and the reason collapses to `no_coordinates`. | An
  adapter can flatten a source-specific "I could not resolve this" signal into a generic
  absence, invisibly. Whether the flattening was intended is unrecorded.
- 2026-09-21 | `tests/contract/schemas/report.schema.json` vs `report.py` (`build_report`) | The
  schema declares an optional `source_files` array that `build_report` never emits and omits
  `source_entry_count` which it always emits; both are invisible because no schema closes
  `additionalProperties`. | A data contract drifts silently unless the property set is closed.
- 2026-09-21 | `tests/integration/test_ingest_fixture.py`
  (`test_second_run_is_byte_identical`) | The byte-identity test enumerates only
  `places.geojson` and `places.unresolved.geojson`, not `places.report.json`, so a timestamp
  could be added to the report today without breaking determinism while adding one to either
  GeoJSON would fail CI. | This is where time is allowed to live under a byte-determinism rule —
  and it is a property of what the test happens to name, not of any stated requirement.
- 2026-09-21 | `tests/test_privacy_guard.py` (`forbidden = ["Food NYC", ...]`) | The guard works
  by committing five of the owner's real list names into a public file so they can be asserted
  absent from fixtures; it only works because the private set is finite and self-owned. |
  misfit: `council_access_nyc` protects an open set of third parties it has never seen, so this
  mechanism does not transfer even though both projects call the test a privacy guard.
- 2026-09-21 | `data/places/places.report.json` (untracked, run 2026-09-21) | `located_count` is
  10 and `outside_region_count` is 10 on the owner's real export of 768 entries: every located
  place falls outside the NYC bbox, so the region flag currently discriminates nothing.
  Aggregate counts only, no names. | Nothing generic yet — a bbox is an untested jurisdiction
  model. The number disappears the moment geocoding lands.
