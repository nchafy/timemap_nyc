# Isochrone + Google Saved Places — Project Outline

An interactive isochrone tool for NYC (MTA subway + bus) that overlays the user's
Google Maps saved places, computed on demand from current transit schedules rather
than a precomputed database. Inspired by [howfar.nyc](https://howfar.nyc/)
([repo](https://github.com/ahmed-machine/howfar)).

## Decisions made
- **Basemap: open source.** No Google Maps JS API. "Google Maps integration"
  means importing saved places only (via Takeout export). Map rendering with
  MapLibre GL or Leaflet on free/open tiles.
- **Data: static GTFS for v1.** Isochrones computed from the current published
  MTA schedules; graph rebuilt when feeds update. GTFS-RT (real-time) is a
  later milestone — the routing-engine choice below keeps that door open.
- **Departure time defaults to "now"**, user-overridable.
- **Tooling: industry standard where free, open source elsewhere.**

> **What GTFS stands for:** *General Transit Feed Specification* — originally
> "Google Transit Feed Specification," created in 2005 by Google and Portland's
> TriMet so transit agencies could publish schedules to Google Maps; later
> renamed "General" as it became the worldwide open standard. It's a zip of
> CSV files (`stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`,
> `calendar.txt`, …) describing a transit network's schedule.
> **GTFS-RT** (GTFS *Realtime*) is the companion live-data spec — protocol-buffer
> feeds of trip updates (delays), vehicle positions, and service alerts.
> Intro: https://gtfs.org/getting-started/what-is-GTFS/

## The three views

### View 1 — Saved places + isochrone overlay
- **Input:** a single starting location (typed address, map click, or device
  geolocation via the browser Geolocation API).
- **Output:** the isochrone (multiple time bands, e.g. 15/30/45/60 min)
  rendered over the map, with all saved places shown as pins.
- **Computation:** one origin → one travel-time surface → contour polygons.

### View 2 — "What can I reach in T minutes?"
- **Input:** starting location + a time budget T.
- **Output:** a single border polygon for T, plus only the saved places whose
  pins fall **inside** the polygon (point-in-polygon filter).
- Note: this is View 1 with a single band and a pin filter — same backend
  call, different presentation. Build them as one view with options.

### View 3 — Equal-travel-time ("meet in the middle")
- **Input:** two starting locations A and B, a buffer ±b minutes, and a time
  cap C (so the region doesn't extend to the edge of the network).
- **Output:** the region where `|t_A(x) − t_B(x)| ≤ b` and `t_A(x) ≤ C`,
  `t_B(x) ≤ C`, plus saved-place pins inside it.
- **Computation:** this **cannot** be done with isochrone polygons alone. You
  need a full travel-time *grid* (raster) from each origin — a value per cell,
  not just contour lines — then compare grids cell-by-cell and polygonize the
  matching cells. This constrains the routing-engine choice (see below).
- Transit caveat: travel time is not symmetric (A→X ≠ X→A). For a meetup, the
  correct direction is origin→destination from both A and B, which is what the
  formula above does.

## Architecture sketch

```
Google Takeout (saved places export)      MTA static GTFS (+ GTFS-RT later)
              │                                        │
              ▼                                        ▼
   import script → places store            OTP2 or R5 routing engine
   (GeoJSON file to start)                 (Java, Dockerized, NYC graph)
              │                                        │
              └────────────► Thin backend API ◄────────┘
                     (isochrone proxy, grid math for View 3,
                      caching, places endpoint)
                                   │
                                   ▼
                     MapLibre GL / Leaflet frontend
                     (open tiles, pins, GeoJSON bands)
```

## The three hard problems (biggest risks first)

### 1. Getting your Google Maps saved places
There is **no official API** for personal saved places. The path:
- **Google Takeout** — https://takeout.google.com → export **"Saved"** and
  **"Maps (your places)"**. Starred/default places come as GeoJSON with
  coordinates; custom lists export as CSV with a name + Maps URL, and some
  entries lack coordinates.
- Backfill missing coordinates with the **Google Places API** (the one part of
  Google's stack worth keeping — official, has a free monthly credit):
  https://developers.google.com/maps/documentation/places/web-service
  For a fully-open alternative, geocode by name with **Nominatim**
  (https://nominatim.org, OSM's geocoder; mind the 1 req/s usage policy) or
  **Photon** (https://photon.komoot.io) — expect lower match quality for
  business names than Google.
- Consequence: places are a **periodic manual export**, not live sync. Write
  an import script that normalizes everything to one GeoJSON file.

### 2. "Live" isochrones on static GTFS
- **v1 (decided):** current-schedule isochrones. Download MTA static GTFS,
  build the routing graph, rebuild when the feed updates (MTA refreshes
  schedule feeds several times a year, plus service changes). "Live" here
  means *accurate to today's timetable and departing now* — which already
  beats howfar's fixed "10am Friday" snapshot.
- **Later (GTFS-RT):** OTP2 has built-in updaters that consume GTFS-RT
  TripUpdates/Alerts and adjust routing in real time — this is why engine
  choice matters. MTA subway GTFS-RT feeds are free with an API key; bus
  real-time comes via the BusTime/OneBusAway API.
  - MTA developer portal: https://www.mta.info/developers (note: blocks
    scrapers/curl — open in a browser; API endpoint host is api.mta.info)
  - MTA BusTime developer docs: https://bt.mta.info/wiki/Developers/Index
  - GTFS-RT spec: https://gtfs.org/documentation/realtime/reference/
- Departure time is a first-class input, default "now". Note for testing:
  a graph built from static GTFS is only valid for dates inside the feed's
  calendar window.

### 3. Routing engine choice
Precomputing everything (howfar's approach: 73GB DB, days of compute) is
unnecessary for on-demand single-origin queries. Candidates, all open source:
- **OpenTripPlanner 2 (OTP2)** — the industry-standard open-source transit
  router (used by national journey planners in Norway, Finland, etc.).
  Ingests GTFS + OSM, serves a GraphQL API, has GTFS-RT updaters, and a
  Travel Time / isochrone sandbox API that returns contours **and**
  travel-time rasters (GeoTIFF) — covering Views 1–3.
  - Repo: https://github.com/opentripplanner/OpenTripPlanner
  - Docs: https://docs.opentripplanner.org/en/latest/
  - Travel-time analysis (isochrones/rasters): https://docs.opentripplanner.org/en/latest/Analysis/
  - Getting-started tutorial: https://docs.opentripplanner.org/en/latest/Basic-Tutorial/
  - The howfar author's in-bundle complaint about OTP was about *batch
    precomputing every intersection*; single-origin on-demand queries take
    seconds, which is fine interactively.
- **R5 (Conveyal) via r5py** — purpose-built for transit travel-time
  analysis; natively produces travel-time matrices/grids (ideal for View 3)
  and is typically faster for this workload. Python-friendly, but batch/
  analysis-oriented rather than a long-running query server, and no GTFS-RT.
  - R5 repo: https://github.com/conveyal/r5
  - r5py docs: https://r5py.readthedocs.io
- Non-options: Mapbox/Valhalla/OpenRouteService isochrones (no real scheduled-
  transit support); TravelTime API (commercial, closed).

**Recommendation:** OTP2 in Docker as the primary engine — it's the standard,
serves live queries, and is the only one with a GTFS-RT path. Keep r5py as the
fallback for View 3 if OTP's raster output proves awkward. An MTA-only graph
is laptop-scale (~4–8GB RAM vs howfar's 15×12GB regional cluster).

## Open-source frontend stack
- **Map rendering:** **MapLibre GL JS** (https://maplibre.org/maplibre-gl-js/docs/)
  — the open-source fork of Mapbox GL, current industry standard for
  vector-tile maps. Simpler alternative: **Leaflet** (https://leafletjs.com),
  what howfar used; older but very approachable, raster tiles.
- **Basemap tiles (free/open):**
  - **OpenFreeMap** (https://openfreemap.org) — free hosted OSM vector tiles,
    no API key, no usage cap; pairs directly with MapLibre.
  - **Protomaps** (https://protomaps.com) — single-file (PMTiles) basemap you
    can self-host on any static host; fully self-sufficient option.
- **Geocoding the origin input:** Photon (https://photon.komoot.io) has a
  free API and typo-tolerant search; or Nominatim (https://nominatim.org).
- **Geolocation:** browser `navigator.geolocation`
  (https://developer.mozilla.org/en-US/docs/Web/API/Geolocation_API) —
  requires HTTPS (or localhost) and a permission prompt. No Google anything.
- **Client-side geometry:** **Turf.js** (https://turfjs.org) for
  point-in-polygon pin filtering and misc geo ops.

## Backend + geometry (View 3 math)
- **Thin API server:** **FastAPI** (https://fastapi.tiangolo.com) — Python,
  industry standard, pairs with the geo libraries below and with r5py if
  needed. (Node/Express + Turf is a fine alternative if you prefer JS
  end-to-end.)
- **Grid → polygon toolchain (Python):**
  - **rasterio** (https://rasterio.readthedocs.io) — read OTP's GeoTIFF
    travel-time rasters, do the `|t_A − t_B| ≤ b` cell math with NumPy.
  - **Shapely** (https://shapely.readthedocs.io) — polygon ops, and
    `rasterio.features.shapes` to polygonize the masked grid.
  - (JS equivalent if you go Node: **d3-contour**,
    https://github.com/d3/d3-contour, marching squares over a grid.)
- **No database initially.** howfar needed Postgres/PostGIS only because of
  precomputation. A GeoJSON file of places + on-demand OTP queries + an
  in-memory cache is enough. Add PostGIS later only if you start persisting
  results.
- **Docker Compose** to run OTP reproducibly
  (https://docs.docker.com/compose/).

## Open questions (remaining)
1. **Saved places scale & freshness** — how many places/lists? Is a Takeout
   re-export every few weeks acceptable?
2. **Geocoding backfill** — Google Places API (better business-name matching,
   needs a billing account even within free tier) vs Nominatim/Photon (fully
   open)? Can decide after seeing how many Takeout entries lack coordinates.
3. **Walking assumptions** — max walk distance to/from transit and walking
   speed dramatically change isochrone shape; pick defaults, maybe expose.
4. **View 3 parameters** — grid cell size (100–200m?), default cap (60 min?),
   default buffer (±5 min?). Do A and B depart at the same time?
5. **Latency budget & caching** — is 2–10s per isochrone acceptable? Cache
   same-origin requests within N minutes?
6. **Hosting** — laptop-only vs deployed? OTP wants several GB of resident
   RAM; a small VPS may not cut it.
7. **Band structure for View 1** — how many contour bands, at what intervals?

## Lessons from howfar.nyc
1. **Precompute only if you must.** Their 73GB DB / 15-instance OTP cluster
   existed to make drag-anywhere instant for every NYC intersection at 3-hour
   range across 5 agencies. Single-origin on-demand queries skip all of it.
2. **Scope the network down.** They ingested 17 GTFS feeds across 4 states;
   MTA subway + bus is a far smaller graph — laptop-scale.
3. **You still need OSM data** even for transit isochrones (walking legs
   to/from stops). Source: Geofabrik New York extract,
   https://download.geofabrik.de/north-america/us/new-york.html
4. **OTP is powerful but has a learning curve** — budget time for graph
   building and config; keep r5py as the escape hatch for grid math.
5. **Time-of-day defines the result.** Their fixed "10am Friday" snapshot is
   the main thing your live approach improves on — hence departure time as a
   first-class input.
6. **Keep the frontend thin.** Map, draggable origin marker, colored GeoJSON
   bands, legend, mode toggle — that's the whole scope. (Don't copy their
   ClojureScript stack; use mainstream tools.)
7. **UX details worth copying:** draggable marker, loading state while
   computing, transit stops/lines as context layers, compare legend.

## What to learn (ordered, with references)
1. **GTFS** — the transit data model (stops/routes/trips/stop_times/calendar).
   - What is GTFS: https://gtfs.org/getting-started/what-is-GTFS/
   - Schedule reference: https://gtfs.org/documentation/schedule/reference/
   - GTFS-RT reference (for later): https://gtfs.org/documentation/realtime/reference/
   - MTA feeds: https://www.mta.info/developers (browser only)
   - Ecosystem catalog (tools, validators, more feeds):
     https://github.com/MobilityData/awesome-transit
2. **OpenTripPlanner 2** — build a graph (GTFS + OSM → graph), run the server,
   query isochrones/rasters.
   - Tutorial: https://docs.opentripplanner.org/en/latest/Basic-Tutorial/
   - Travel-time analysis: https://docs.opentripplanner.org/en/latest/Analysis/
   - Repo: https://github.com/opentripplanner/OpenTripPlanner
   - Alternative track: r5py — https://r5py.readthedocs.io (its docs are also
     an excellent conceptual intro to transit travel-time analysis)
3. **GeoJSON + geospatial basics** — polygons, point-in-polygon, contouring.
   - GeoJSON spec, readable: https://datatracker.ietf.org/doc/html/rfc7946
   - Turf.js: https://turfjs.org · Shapely: https://shapely.readthedocs.io
   - rasterio (grids): https://rasterio.readthedocs.io
4. **MapLibre GL JS** — map, layers, GeoJSON sources, markers.
   - Docs + examples: https://maplibre.org/maplibre-gl-js/docs/
   - Tiles: https://openfreemap.org (hosted) or https://protomaps.com (self-host)
   - Geolocation API: https://developer.mozilla.org/en-US/docs/Web/API/Geolocation_API
5. **Google Takeout format + geocoding backfill**
   - Takeout: https://takeout.google.com
   - Places API (if used): https://developers.google.com/maps/documentation/places/web-service
   - Open geocoders: https://nominatim.org · https://photon.komoot.io
6. **FastAPI** — https://fastapi.tiangolo.com (thin proxy + grid math +
   places endpoint).
7. **Docker Compose** — https://docs.docker.com/compose/ (run OTP
   reproducibly; howfar's `docker-compose.yml` +
   [otp-config](https://github.com/ahmed-machine/howfar/tree/main/otp-config)
   are a working reference for OTP-in-a-container, minus the cluster part).

## Suggested milestone path
1. **M0:** Takeout export → import script → clean GeoJSON → pins on a
   MapLibre map with OpenFreeMap tiles. (No routing; validates the riskiest,
   most Google-dependent piece first.)
2. **M1:** OTP2 in Docker with MTA *subway-only* GTFS + Geofabrik NY extract;
   isochrone for a hardcoded origin rendered on the map. Add buses after it
   works (bus GTFS is much bigger).
3. **M2:** Views 1/2 — origin input (click / Photon search / geolocate),
   departure time (default now), time budget, bands, in-polygon pin filter.
4. **M3:** View 3 — travel-time rasters from two origins, `|t_A − t_B| ≤ b`
   masking with cap, polygonize, render.
5. **M4:** GTFS-RT ingestion via OTP updaters for true real-time; caching;
   polish.
