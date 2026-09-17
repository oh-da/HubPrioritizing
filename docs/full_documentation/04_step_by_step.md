# 4. Step-by-Step Details

This document walks through every step the pipeline performs. Steps are
numbered to match the Colab notebook the `hubs run` command replaced (kept on the branch
`legacy/v1-notebooks`). The implementation of each step lives in `src/pipeline/`:

| Step(s) | Function |
|---|---|
| 1.3 | `network.load_nodeslines`, then `network.apply_node_position_overrides` and `network.check_node_positions` (one position per node: small spreads snapped, conflicts reported, `node_position_overrides.csv` resolves them) |
| 1.4 | `network.attach_modes`, `network.aggregate_to_hexes` |
| 1.5 / 1.5.1 | `grouping.group_hexes`, `grouping.apply_manual_groups`, `grouping.assign_hub_ids` |
| 1.6 | not ported (geocoding off; `address` = `Not geocoded`) |
| 1.7 | `network.add_mode_line_columns` |
| 1.8, 2.8, 3.6, 4.7 | no intermediate files; `run.write_outputs` (optionally `intermediate/`) |
| 2.3 | `base_layer.tag_area_and_location_from_base` (`spatial_tags.tag_area_and_location` with `spatial_source=shapefiles`) |
| 2.4 / 2.5 | `demand.SHEET_COLUMN_CONFIG`, `demand.load_demand_workbook` |
| 2.6 / 2.6.1–2.6.3 | `demand.assign_demand`, `demand.apply_manual_demand` (all overrides are rows of `manual_demand_updates.csv`) |
| 2.7 / 2.7.1 | `aggregate.aggregate_to_groups`, `base_layer.tag_bus_terminals_from_base` (`aggregate.tag_bus_terminals` with shapefiles) |
| 3.x | `base_layer.add_influence_area_from_base` (`aggregate.add_influence_area` with shapefiles) |
| once per vintage | `base_layer.build_base_layer` via `hubs prepare-base` |
| 4.2–4.6 | `scoring.prepare_scoring_frame`, `add_mode_score`, `classify`, `filter_eligible`, `normalize_scores`, `monte_carlo` |
| post-processing | `postprocess.finalize_columns`, `export.write_results_xlsx` |

Where the text below says "the notebook", the same logic runs in the function named above;
`docs/DEVIATIONS.md` lists the places where behaviour is configurable or was fixed.

> Manual corrections are flagged with 🔧. The full description of each one
> lives in [`06_manual_corrections.md`](06_manual_corrections.md).

---

## Part 1 — H3 hexagon processing

### Step 1.1 — Setup and configuration
Replaced by `hubs validate`: inputs are discovered by name in the input and reference
directories, every parameter comes from `PipelineConfig` (`--config` / `--set`), and the
effective values are written to `run_config.json` with the results.

### Step 1.2 — Configure Part-1 paths
Resolves Part-1-specific paths: `INPUT_NODES_CSV`, `LINES_MODE_CSV`,
`OUTPUT_H3_HEXAGONS`.

### Step 1.3 — Load transit nodes
Reads the `All_nodeslines*.csv` found in the input directory (encoding detected: `cp1255`
or UTF-8). If the file has a `geometry` column the WKT is parsed; otherwise the geometry is
built from `X` / `Y`. The result is a GeoDataFrame in **EPSG:2039**.

| Implementation | `src/pipeline/inputs.py::read_csv_auto`, `src/pipeline/network.py::load_nodeslines` |
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
Looks each hexagon up in the H3 base layer (`h3_base.parquet`, built once by
`hubs prepare-base` from `metro_2008` and `Districts`) to produce:
- `area` — metro name or national district (תל אביב / חיפה / צפון / דרום / ירושלים),
- `location` — metropolitan position (גלעין / טבעת פנימית / תיכונה / חיצונית, or the district).

The base layer tags a cell by the polygon containing its **centre** (metro ring first,
district fallback). A hexagon with no row in the layer is reported and tagged `Unknown`.
With `spatial_source=shapefiles` the notebook's spatial join runs instead: the hexagon
polygon against the metro layer by intersection (first match in layer order), then the
districts by containment; shapefile text is decoded byte-exact by
`src/pipeline/inputs.py::read_shapefile`. Both paths apply the notebook's name repairs
(`גלעי` → `גלעין`, `מחוז חיפה` → `חיפה`) so the `area` vocabulary is identical.

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
Every cell of the base layer carries the class of the strategic terminal (≈673 terminals)
whose 200 m buffer touches the cell polygon; a hub takes the highest class over its cells
(`term_type`, `term_id`, 0–3 `bus_terminal`). Because a hub polygon is the union of its
cell polygons this is identical to buffering the terminals and intersecting the hub, which
is what `spatial_source=shapefiles` does at run time. When several terminals touch a hub
the highest-scoring one is kept (the notebook produced duplicate rows).

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

### Step 3.2 — Influence-area computation
`hubs prepare-base` spreads each TAZ's `POP_2050` / `EMPL_2050` over the H3 cells it
overlaps, proportionally to the intersection area (uniform density inside a zone, shares
normalised so zone totals are conserved exactly). At run time
`src/pipeline/base_layer.py::add_influence_area_from_base` sums those cells around each hub
centroid into concentric rings (default 0–500 / 500–1 000 / 1 000–1 500 m,
`influence_rings`). With `spatial_source=shapefiles`,
`src/pipeline/aggregate.py::add_influence_area` overlays the rings with the TAZ polygons
directly. (The former `influence_area_processor` ignored its ring configuration and always
used 600 / 1 000 / 1 200 m; see `docs/DEVIATIONS.md`.)

### Step 3.3 — Layer availability
The base layer is **required** for the default run: `hubs validate` lists it as missing and
`hubs run` refuses to start without it, pointing to `hubs prepare-base`. The TAZ shapefile
is needed only to rebuild the layer or with `spatial_source=shapefiles`, where the
test/dry-run escape hatch `HUBS_ALLOW_MISSING_LAYERS=1` lets a run continue with zero
population and employment.

### Step 3.4 — Run the influence-area computation
For each hub:
1. Find the cell under the hub centroid and take a grid disk around it that covers the
   outer ring.
2. Compute each cell's distance to the centroid (EPSG:2039). With
   `influence_cell_rule=fraction` (default) a cell contributes the share of its polygon
   inside each ring; exact fractions are only computed for cells a ring boundary can
   cross. With `center` a cell counts wholly in the ring its centre falls in.
3. Sum the cells' 2050 population and employment per ring.

Result columns: `pop_0_500`, `emp_0_500`, `pop_500_1000`, `emp_500_1000`,
`pop_1000_1500`, `emp_1000_1500`. Against the polygon overlay the fraction rule is within
about 1 % (median 0.3 %); see `docs/H3_BASE_LAYER.md` for the measurement.

### Step 3.5 — Explore results
Diagnostic counts/checks for sanity.

### Step 3.6 — Export `hubs_complete.csv` / `.xlsx`
Final pre-scoring snapshot.

---

## Part 4 — Scoring and ranking

### Step 4.1 — Scoring configuration
The active configuration (`mc_iterations`, `mc_seed`, `mc_scope`, `influence_rings`,
`distance_decay_beta`, `mode_diversity_alpha`, the eligibility flags) is recorded in the run
report and in `run_config.json`.

### Step 4.2 — Data cleaning and preparation
Final column cleanup, dtype coercion, missing-value handling.

### Step 4.3 — Calculate mode-service and bus-terminal scores
Computes the **Service** score `score = Σ(<Mode> Lines × MODE_WEIGHTS[mode]) × (1 + 0.1 ×
(Num_Modes − 1))` and carries the 0–3 **bus_terminal** class score from Step 2.7.1.

| Implementation | `src/pipeline/scoring.py::add_mode_score`, `src/pipeline/aggregate.py::bus_terminal_score` |

### Step 4.4 — Filter eligible hubs and classify tier
Applies the eligibility rules and assigns `HubType`:

1. Eligible = `TotalDemand ≥ 1,000` **and** at least 2 planned modes (after dropping generic
   `Rail`) **and**, with `require_non_rail_mode` (default on), at least one of Metro / LRT /
   BRT / HighSpeed Rail. With `apply_eligibility_filter` (default on) only eligible groups
   continue.
2. `HubType` ∈ {ארצי, מטרופוליני, עירוני, Train Station, Not Hub} from demand, modes and
   `Total_Unique_Lines` (`src/classification/hierarchy.py::classify_hub_tier`; metropolitan
   requires ≥ 5,000 passengers/day).

| Implementation | `src/pipeline/scoring.py::classify`, `filter_eligible` |

### Step 4.5 — Normalize scores and calculate the Pop/Emp score
All five criteria are min-max normalised to 1–10 **per HubType** (5.5 when a type is
constant): `RegionLocation_Norm`, `score_Norm`, `bus_terminal_Norm`, `TotalDemand_Norm`
(log₁₀, range over the non-zero values) and `PopEmp_Score_Norm`.

The Pop/Emp raw score sums, over the rings (default 0–500 / 500–1 000 / 1 000–1 500 m),
`(w_pop × pop + w_emp × emp) / midpoint^β` with `β = 1.5`. The mix is **20 % population /
80 % jobs** for ארצי and מטרופוליני and **80 / 20** for עירוני.

| Implementation | `src/pipeline/scoring.py::normalize_scores`, `normalize_by_type`, `normalize_log_demand_by_type`, `pop_emp_raw_score` |

### Step 4.6 — Monte Carlo aggregation and ranking
For 10,000 iterations per hub type (one seeded stream, `mc_scope = per_hubtype`):
1. Draw five weights in [0, 1]; redraw while any exceeds 0.5; normalise to sum to 1.
2. Compute the weighted sum of the five `*_Norm` criteria.

`Average_Simulated_Score` (`TotalScore_MC`) is the mean over the iterations. Ranks:
`Overall_Rank` / `Rank_TS_MC` (dense, all hubs), `Rank_within_HubType` /
`Rank_By_TS_MC_By_Metro` (dense, per type) and, in post-processing, `RankByHubTypeMetro`
(national hubs nationwide, other tiers within their metropolitan area, competition rank).

| Implementation | `src/pipeline/scoring.py::monte_carlo`, `src/pipeline/postprocess.py::rank_by_hubtype_metro` |

### Step 4.7 — Export
`postprocess.finalize_columns` derives the display columns (Hebrew names, line statuses,
transfer rate, the two former Excel formula columns) and `run.write_outputs` writes
`hub_prioritization_results.xlsx` (one Excel Table), its CSV twin, `hub_identity.csv`,
the run report and the effective configuration. See [`07_outputs.md`](07_outputs.md).
