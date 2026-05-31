# 4. Step-by-Step Details

This document walks through every step the pipeline performs. Steps are
numbered to match `COMPLETE_TRANSIT_PIPELINE.ipynb`. The equivalent code
in the `src/` package is named for each step in the *Implementation*
column.

> Manual corrections are flagged with 🔧. The full description of each one
> lives in [`06_manual_corrections.md`](06_manual_corrections.md).

---

## Part 1 — H3 hexagon processing

### Step 1.1 — Setup and configuration
Imports libraries, sets random seeds, configures matplotlib/folium. The
**MASTER CONFIGURATION** cell sets every input/output path used by the
remaining cells, and the notebook prints a summary so the user can
sanity-check paths before running.

### Step 1.2 — Configure Part-1 paths
Resolves Part-1-specific paths: `INPUT_NODES_CSV`, `LINES_MODE_CSV`,
`OUTPUT_H3_HEXAGONS`.

### Step 1.3 — Load transit nodes
Reads `INPUT_NODES_CSV` with `encoding='windows-1255'`. If the file has a
`geometry` column the WKT is parsed; otherwise the geometry is built
from `X` / `Y`. The result is a GeoDataFrame in **EPSG:2039**.

| Implementation | `src/data/loaders.py::load_transit_nodes` |
|----------------|-------------------------------------------|

### Step 1.4 — Assign H3 indices and aggregate lines per node
Each node is converted to WGS84, an H3 index at **resolution 10** is
assigned, and lines visiting the node are aggregated into:
- `Mode_Planned` (set of modes serving the node, via merge with
  `LINES_MODE_CSV`),
- `Line_Nunique` (count of distinct lines), and
- `Line_Unique` (list of line IDs).

| Implementation | `src/spatial/h3_operations.py::assign_h3_to_points`, `aggregate_by_h3` |
|----------------|----------------------------------------------------------------------|

### Step 1.5 — Create groups based on a 120 m edge-to-edge buffer
Each H3 hexagon is buffered by **120 m** in EPSG:2039, and any pair of
hexagons whose buffered geometries intersect is connected. A
**Union-Find** structure (`src/spatial/merging.py::UnionFind`) computes
connected components — these are the candidate **hub groups**. The
grouping is **transitive**: if A is near B and B is near C, all three
end up in one group, even if A and C are more than 120 m apart.

| Implementation | `src/spatial/merging.py::create_proximity_groups` |

### Step 1.5.1 — 🔧 Apply IsSameGroup manual corrections
Reads `data/IsSameGroup.csv` (if present) and forces specified node IDs
into the same hub group, even when the 120 m buffer would not have
linked them. After all manual merges are applied the group IDs are
**re-normalised** to a sequential range. See
[`06_manual_corrections.md`](06_manual_corrections.md) for the file
format and worked examples.

### Step 1.6 — Geocode addresses (optional)
Uses Nominatim with rate limiting to reverse-geocode the centroid of
each hub group, populating an `address` column. This is for human
readability only; nothing downstream depends on it.

### Step 1.7 — Create per-mode line-count columns
For every mode in `MODE_WEIGHTS`, a `<Mode> Lines` column is added
(`BRT Lines`, `LRT Lines`, `Metro Lines`, …). Each cell is the number
of unique lines of that mode serving the hub. These columns are the
direct input to the service score (see
[`05_scoring_methodology.md`](05_scoring_methodology.md) and
`data/README_MODE_LINE_COLUMNS.md`).

### Step 1.8 — Export H3 hexagons with groups
Writes `OUTPUT_H3_HEXAGONS` (default `transit_h3_hexagons.csv`). Geometry
is serialised as WKT and node IDs are coerced to lists. Encoding:
`utf-8-sig`.

---

## Part 2 — Demand and spatial tagging

### Step 2.1 — Configure Part-2 paths
Sets `INPUT_H3_FOR_DEMAND`, `DEMAND_EXCEL`, `METRO_SHP`, `DISTRICTS_SHP`,
`BUS_TERMINALS_SHP`, and the demand-update CSV path.

### Step 2.2 — Load H3 output from Part 1
Reads the CSV produced in 1.8, parses WKT back into geometries and
restores `node` as a list type.

### Step 2.3 — Tag hubs with area and location
Spatial-joins each hub centroid against `METRO_SHP` and `DISTRICTS_SHP`
to produce:
- `area` — national district (תל אביב / חיפה / צפון / דרום / ירושלים),
- `location` — metropolitan position (גלעין / טבעת / periphery).

Hebrew strings are passed through
`src/scoring/location.py::fix_truncated_hebrew` to repair common shapefile
truncations (e.g. `גלעי` → `גלעין`, `תל אבי` → `תל אביב`).

### Step 2.4 — Per-sheet column configuration for the demand Excel
The demand Excel contains multiple regional models, each with slightly
different column conventions (Haifa, Tel Aviv, Beer Sheva, Hadera,
Jerusalem, HaifaMetronit, Ashdod-Ashkelon, Rail). This cell maps each
sheet's `node` / `boardings` / `alightings` / `transfers` columns to a
common schema.

### Step 2.5 — Load demand data from Excel
Reads every sheet in `DEMAND_EXCEL`, applies the sheet-specific column
mapping from 2.4 and concatenates into a long-format DataFrame keyed by
node ID.

### Step 2.6 — Match demand to hubs by area
For every node in every hub, the matching demand record is fetched
based on the hub's `area` tag and the node's region. Per-node totals
are aggregated into `TotalDemand` and `TotalTransfers` per hub. Some
regions are *overlay* models (e.g. Hadera, HaifaMetronit) and **add to**
existing demand rather than replacing it.

### Step 2.6.1 — 🔧 Load manual demand updates CSV (optional)
If `MANUAL_DEMAND_UPDATES_CSV` is configured, reads it and overrides
`TotalDemand` / `TotalTransfers` for the listed `node` IDs. Node IDs
are stable across runs, so this method is safe.

### Step 2.6.2 — 🔧 Apply hardcoded National-Model node updates
Four specific node-level overrides are burned into the notebook:

| Node ID | Station | Demand | Transfers |
|---------|---------|-------:|----------:|
| 400424  | Moshe Dayan (Rishon) | 64,985 | 43,032 |
| 400021  | Netanya Sapir        | 23,083 | 10,140 |
| 400030  | Beit Yehoshua Rail   | 14,518 | 6,101  |
| 511246  | Beit Yehoshua LRT    | 13,601 | 6,101  |

Three additional updates that exist in the old code (Netanya 400020,
Modiin Merkaz 400470, Modiin West 400460) are **deliberately skipped**
because they were keyed by DataFrame index rather than node ID and are
not safe to apply blindly; the notebook prints instructions to add them
through Step 2.6.1 instead.

### Step 2.6.3 — 🔧 Update Shefaim LRT stop
Overrides node `511248` with demand `255.3`. Reflects an updated
forecast for the Shefaim LRT stop.

### Step 2.7 — Create grouped hubs with demand
Aggregates demand per hub group, producing the working dataframe for
scoring: one row per hub with `TotalDemand`, `TotalTransfers`, modes,
per-mode line counts, `area`, `location`, geometry.

### Step 2.7.1 — Add bus terminal data
Reads `BUS_TERMINALS_SHP` (≈673 terminals), builds a 200 m buffer
around each hub centroid (EPSG:2039), and tags hubs with the closest
terminal's `term_type` plus a boolean `near_bus_terminal`.

### Step 2.7.2 — Verify scoring columns
Runs a checklist over the dataframe to ensure every column the scoring
stage needs is present and non-null. Failures here are loud — the
pipeline refuses to continue with missing inputs to scoring.

### Step 2.8 — Export grouped hubs with demand
Writes `OUTPUT_GROUPED_HUBS` (default `grouped_hubs.csv`) — this is the
hand-off file between Part 2 and Parts 3 / 4.

---

## Part 3 — Influence area (optional)

### Step 3.1 — Configure Part-3 paths
`TAZ_SHAPEFILE`, `OUTPUT_FINAL`, `OUTPUT_FINAL_EXCEL`.

### Step 3.2 — Load the influence-area processor module
Imports `influence_area_processor.InfluenceAreaProcessor` — a
performance-tuned refactor of the original notebook code that is ~3.7×
faster.

### Step 3.3 — Check TAZ data availability
If the TAZ shapefile is missing, Part 3 is skipped gracefully and the
pipeline continues with whatever population/employment fields exist.

### Step 3.4 — Run the influence-area pipeline
For each hub:
1. Build three concentric rings: 0–500 m, 500–1 000 m, 1 000–1 500 m
   (in EPSG:2039).
2. Intersect each ring with the TAZ polygons.
3. Distribute each TAZ's 2050 population and employment proportionally
   to the area inside each ring.

Result columns: `pop_0_500`, `emp_0_500`, `pop_500_1000`, `emp_500_1000`,
`pop_1000_1500`, `emp_1000_1500`.

### Step 3.5 — Explore results
Diagnostic counts/checks for sanity.

### Step 3.6 — Export `hubs_complete.csv` / `.xlsx`
Final pre-scoring snapshot.

---

## Part 4 — Scoring and ranking

### Step 4.1 — Scoring configuration
Echoes back the active configuration: `MONTE_CARLO_ITERATIONS`,
`MAX_CRITERION_WEIGHT`, `MONTE_CARLO_RANDOM_SEED`, `AHP_ENABLED`,
distribution-analysis parameters.

### Step 4.2 — Data cleaning and preparation
Final column cleanup, dtype coercion, missing-value handling.

### Step 4.3 — Calculate mode-service and bus-terminal scores
Runs the **Service** score (mode weights × line counts with diminishing
returns and the modal-diversity bonus) and the **Bus Terminal Proximity**
score (200 m buffer, weighted by terminal type).

| Implementation | `src/scoring/service.py::calculate_service_score`, `src/scoring/terminals.py::calculate_terminal_score` |

### Step 4.4 — Filter eligible hubs and classify tier
Applies the eligibility rules and assigns one of the three tiers:

1. Drop hubs with `TotalDemand < 1,000` or fewer than 2 mass-transit
   modes (`src/classification/eligibility.py::filter_eligible_hubs`).
2. *(Optional but enabled by default)* drop hubs whose only mass-transit
   modes are rail (Suburban Rail / Interurban Rail / generic Rail) and
   that have **no** Metro / LRT / BRT / HighSpeed Rail —
   `config.REQUIRE_NON_RAIL_MODE = True`.
3. Assign `tier` ∈ {ארצי, מטרופוליני, עירוני} based on `TotalDemand`
   plus mode/line counts
   (`src/classification/hierarchy.py::assign_hub_tiers`).

### Step 4.5 — Normalize scores and calculate the Pop/Emp score
Normalisation:
- Activity, Service, Pop/Jobs → **per-tier** min-max to 1–10
  (after `log10` for Activity).
- Location, Terminal → **global** min-max to 1–10.

Pop/Emp score uses three rings (0–500 / 500–1 000 / 1 000–1 500 m) with
inverse-distance weights (`β = 1.5`) producing ring weights
`{0: 0.78, 1: 0.15, 2: 0.07}`. The pop-vs-jobs mix is **80 / 20** for
National and Metropolitan tiers and **20 / 80** for Local.

| Implementation | `src/scoring/normalization.py`, `src/scoring/demographics.py`, `src/scoring/activity.py`, `src/scoring/location.py` |

### Step 4.6 — Monte Carlo aggregation and tier-aware ranking
For 10,000 iterations:
1. Draw five random weights, each uniformly in [0, 0.5], renormalised to
   sum to 1.
2. Compute the weighted sum of the five criterion scores.

The hub's `final_score` is the mean over all iterations. Ranking is
then applied **after** Monte Carlo:
- **National**: ranked globally.
- **Metropolitan**: ranked **within geographic area** (Tel Aviv+Center,
  Haifa+North, South).
- **Local**: ranked **within geographic area**.

If `AHP_ENABLED=True`, expert pairwise comparisons in
`data/ahp_expert_comparisons.csv` are also loaded, validated for
consistency (CR < 0.10) and aggregated (geometric mean). The hub then
also gets `ahp_score` and `ahp_rank` columns.

If MC distribution analysis is enabled, the per-iteration scores are
preserved and additional statistics (mean, std, p5/p25/p75/p95, top-N
probabilities) are exported.

| Implementation | `src/scoring/monte_carlo.py::run_complete_scoring_pipeline`, `src/scoring/ahp.py::run_ahp_scoring_pipeline`, `src/scoring/mc_distribution.py::run_mc_distribution_analysis` |

### Step 4.7 — Export scored and ranked hubs
Writes:
- `scored_hubs_final.csv` (UTF-8-BOM, geometry as WKT),
- `scored_hubs_final.xlsx`,
- A GeoJSON layer for GIS, and
- An interactive HTML map (`src/visualization/maps.py::create_hub_map`).
