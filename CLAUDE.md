# timemap_nyc

NYC transit isochrone map (MTA subway + bus) overlaying the owner's Google Maps
saved places. Read `isochrone-project-outline.md` first — it is the source of
truth for the plan, architecture, open questions, and reference links.

## Decisions already made — don't relitigate

- **Open source everywhere.** No Google Maps JS API. MapLibre GL JS +
  OpenFreeMap tiles. Google's involvement is limited to the Takeout export of
  saved places (and possibly the Places API for geocoding backfill — still an
  open question).
- **Static GTFS for v1.** Isochrones from current published MTA schedules.
  GTFS-RT is milestone M4, not before. Departure time is a first-class input
  defaulting to "now".
- **On-demand computation, not precomputation.** No 73GB PostGIS database à la
  howfar.nyc. Single-origin queries against a running OTP2 instance.
- **Engines:** OpenTripPlanner 2 in Docker (primary; keeps the GTFS-RT door
  open). r5py is the fallback for View 3 raster math only.
- **Backend:** FastAPI (Python). Geometry via rasterio + NumPy + Shapely.
  No database initially — saved places live in a GeoJSON file.

## Domain notes

- GTFS = General Transit Feed Specification (zip of CSVs: stops, routes,
  trips, stop_times, calendar). GTFS-RT = the realtime protobuf companion.
- View 3 ("meet in the middle") needs travel-time **rasters** (GeoTIFF from
  OTP's travel-time API), not contour polygons — `|t_A − t_B| ≤ buffer` is
  computed cell-wise, then polygonized.
- Transit travel time is asymmetric and highly departure-time-sensitive. A
  graph built from static GTFS is only valid for dates inside the feed's
  calendar window — watch for this in tests.
- Isochrone shape is very sensitive to walking assumptions (max walk distance,
  speed). Defaults are an open question in the outline.

## Spec workflow (GitHub Spec Kit)

This repo uses Spec Kit (skills installed in `.claude/skills/`, infrastructure
in `.specify/`). For any new feature, follow the SDD flow:

1. `/speckit-specify` — write the spec (what/why, user stories)
2. `/speckit-clarify` — resolve ambiguities before planning (optional but preferred)
3. `/speckit-plan` — technical plan
4. `/speckit-tasks` — task breakdown
5. `/speckit-implement` — execute

`isochrone-project-outline.md` predates Spec Kit and remains the project-level
vision doc; per-feature specs live where Spec Kit puts them (`.specify/`
conventions).

## Writing quality (subagents in .claude/agents/)

- **technical-writer** — drafting user-facing docs, guides, API references
- **documentation-engineer** — docs structure/systems, keeping docs in sync with code
- **ai-writing-auditor** — audit + rewrite prose to remove AI-isms; run on any
  substantial AI-drafted spec or doc before committing
- **content-quality-editor** — final editorial pass. Caveat: its instructions
  reference an `unslop` CLI whose npm namesake is a *different* tool (code
  analysis, not prose). Do NOT `npm install -g unslop`; skip the CLI step and
  apply the agent's editorial judgment manually, or use ai-writing-auditor.

Specs should be reviewed by ai-writing-auditor before they're considered done.

## Conventions

- Milestones M0–M4 are listed in README.md; work proceeds in that order.
  M0 (Takeout → GeoJSON → pins on map) comes before any routing work.
- Keep the frontend thin: map, origin marker(s), GeoJSON bands, legend,
  view switcher. Complexity belongs in the backend.
- Never commit GTFS zips, OSM extracts, OTP graphs, or personal Takeout
  exports — all are gitignored. Scripts should download/derive them.
- Personal saved-places data is private: anything under `data/` stays local.

## Sibling project and shared-core intent

`~/personal/council_access_nyc` — local path only; that repo has no git remote
configured. Same owner, a static site about NYC City Council hearings, and it is
a written plan for this repo's pipeline shape run against live public sources,
so it is where the hard cases are already described: HTTP 200 responses carrying
error bodies, publisher "updated" dates that contradict the rows, and a hard
commitment to no origin server that is forced by missing CORS headers upstream
rather than chosen. A core both projects sit on is a someday goal, not a plan.
`docs/shared-core-notes.md` holds the evidence, the candidate seams and the open
questions; nothing in it is approved architecture.

**Do not design the core, a plugin contract, or a shared interface.** Do not
generalise `region_bbox` into a jurisdiction abstraction. Not adopting pluggy,
entry points, or an ABC registry is a decision rather than an omission — adding
one to be helpful is reopening it. Keep `TakeoutError`, `feature_id`,
`list_name`, `Saved/` and the other Google-shaped names: they mark where the
domain leaks in, and neutral names erase that. Code taken from
council_access_nyc is copied verbatim with a comment naming its source file.

When you inline a Takeout-specific or NYC-specific value in otherwise generic
code (`DEFAULT_BBOX` in `cli.py` is one), mark it `# SEAM: <what varies>` at the
same time as the line. None exist yet, so an empty `grep -rn 'SEAM:'` means
nobody has marked one — not that the code has no seams.

Append one dated line to `docs/OBSERVATIONS.md` (a new directory here) when a
source or a test surprises you, when you measure a number worth citing later,
and when you copy something to or from council_access_nyc — including when you
try and it does not fit. The format is in that file's header.
