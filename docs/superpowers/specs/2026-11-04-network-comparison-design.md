# Network comparison: HubPrioritizing vs the planning agency (MT_Network)

Status: design, approved in conversation 2026-11-04. Next step: implementation plan.

## 1. Purpose

The planning agency delivered `MT_Network.gpkg` (+ `MT_Network_MetaData.xlsx`): every transit
route it has and every hub it identified. This feature compares that network with the one
`hubs run` works from, in two steps:

1. **Routes**: which routes each source uses and where they differ. Route names differ between
   the sources, so matching is geometric.
2. **Hubs**: which hubs the agency identified, their routes, their type and (for ours) demand,
   compared with **all** the hub groups the pipeline formed, *before* the eligibility filter
   (including "Not Hub", groups under 1,000 passengers/day, single-mode and rail-only groups).

Success: one reproducible command produces an Excel workbook, a GeoPackage and two
self-contained HTML maps; every difference in the workbook can be traced to a route or a hub on
the map. The comparison lives in this repository (it replaces the geometric line comparison
that `HubsScraping/tod_scraper/compare_lines.py` did against the scraped TOD map).

### Facts about the inputs (from inspection, not assumptions)

- `MT_Network.gpkg`, EPSG:2039. Layer `lines`: 221 MultiLineString features, 132 distinct
  `line_id`, columns `type` (BRT, LRT, Metro, Rail, Rail fast, FUNI), `line_id`, `line_name`,
  `name`, `year_operation`, `year_cancel`, `source_plan`, `source_name`. **Rail features share
  `line_id = 0`**, so a route is identified by `(type, line_id)` and, for `line_id = 0`, by
  `name`. Layer `stations`: 3,741 Point rows (one per stop x line), 125 lines, `stop_id`,
  `station_name`, `hub_id` (set on 1,607 stops = **426 hubs**, each with >= 2 stops and >= 2
  lines), `rail_hub` (flag, 229 hubs), `hub_stop_id` (`hub_<id>` for hub stops, `stop_*`
  otherwise).
- The gpkg and the metadata workbook contain **no demand and no hub classification**. The
  metadata workbook is a code dictionary only (BRT = תאו"מ, LRT = רק"ל, metro = מטרו,
  rail = רכבת כבדה, rail fast = רכבת מהירה; strategic = תכנית אסטרטגית, detailed = תכנית
  מפורטת).
- The scraped TOD map (`HubsScraping/tod_scraper/data/out/tod_israel.gpkg`) has `hub_id`,
  `n_modes`, `type_sum` for 432 hubs. `type_sum` is the **number of distinct modes** at the hub
  (1..6), not a tier. Its distribution matches what the new gpkg gives, so it adds no
  information beyond the gpkg and is used only as an optional cross-check.
- Our side: `hubs run` keeps every group in memory (`RunResult.groups`) with `Line_Unique`,
  `Mode_Planned`, `TotalDemand`, `TotalTransfers`; `scoring.compute_eligibility` already adds
  `eligible`, `is_rail_only` and `HubType` to every row before `filter_eligible` drops rows.
  The results workbook has only the filtered hubs, and the calculation workbook's
  `1_Eligibility` sheet has no coordinates or line IDs, so neither can be the input of a spatial
  comparison.
- Our network has **no route geometry**: only node points per line (`node`, `LINE_ID`, X, Y in
  EPSG:2039). Each direction is a separate line.

### Out of scope

- No change to scoring, tiers, normalisation or any existing output column (golden tests stay
  as they are).
- No agency demand (no source). The column is present and empty.
- No agency tier classification. If the agency supplies one later it is an optional table keyed
  by `hub_id` (see 9).
- No route geometry reconstruction for our lines, no GUI integration (a later step).

## 2. Architecture

```
hubs run  (existing, +2 small CSV outputs)
   -> hub_groups_all.csv, network_nodes.csv           pure additions to write_outputs
hubs compare-network --run OUT_DIR --agency-gpkg MT_Network.gpkg
                     [--agency-meta MT_Network_MetaData.xlsx]
                     [--tod-gpkg tod_israel.gpkg] [--config compare.yaml] [--set k=v]
                     --out DIR
   -> reads the two CSVs + the gpkg, writes the comparison files
```

Approach A of the design discussion: a separate package that reads a *finished run*; the
pipeline stays pure and its contract is unchanged. A run made before this feature has no
`hub_groups_all.csv`; `hubs compare-network` stops with a clear message to re-run `hubs run`.

### 2.1 Pipeline additions (`src/pipeline/all_groups.py`)

Two pure functions, wired into `run.write_outputs` next to `hub_identity.csv`:

- `build_all_groups_table(groups, scored_all, hexes)` -> **`hub_groups_all.csv`**, one row per
  group formed from the H3 hexagons, before any filter. Columns: `hub_id` (stable hash of the
  node set), `group`, `HubNameHE`, `x`, `y` (WGS84 centroid), `x_itm`, `y_itm`, `area`,
  `Mode_Planned` (list), `n_modes`, `Line_Unique` (list), `n_lines`, `TotalDemand`,
  `TotalTransfers`, `eligible`, `exclusion_reason` (`demand < min`, `single mode`,
  `rail only`, or empty; several joined by `;`), `HubType`, and for scored hubs
  `TotalScore_MC`, `Rank_TS_MC`, `RankByHubTypeMetro`.
- `build_network_nodes_table(nodes, hexes)` -> **`network_nodes.csv`**, one row per node x line:
  `node`, `LINE_ID`, `Mode_Planned` of the line, `x_itm`, `y_itm`, `group`, `hub_id`.

`eligible` / `exclusion_reason` come from `scoring.classify` (which adds `HubType`,
`is_rail_only`, `eligible`) applied to the unfiltered groups after `prepare_scoring_frame`, with
`require_non_rail = cfg.require_non_rail_mode`; the thresholds are the constants of
`src/config.py` (`ELIGIBILITY_MIN_PASSENGERS`, `ELIGIBILITY_MIN_MODES`), never re-typed.
`RunResult` gains two fields, `nodes` (the node x line rows after `attach_modes`) and
`line_names` (the Hebrew display names loaded in Part 5), so that `write_outputs` can write
`network_nodes.csv` with a `line_name` column. Settings: `all_groups_basename` (default `hub_groups_all`) and
`network_nodes_basename` (default `network_nodes`); `""` turns either off, same convention as
`calc_workbook_basename`.

### 2.2 Comparison package (`src/compare/`)

| module | responsibility |
|---|---|
| `settings.py` | `CompareConfig` (thresholds below), YAML / `--set` overrides, written to the output as `compare_config.json` |
| `agency.py` | read `lines` / `stations` from the gpkg and the metadata workbook; build agency routes, stops and hubs |
| `modes.py` | our mode -> agency mode via `data/reference/agency_mode_map.csv` |
| `offset.py` | local shift field between our nodes and agency stops (port of `local_shift` from HubsScraping `compare_lines.py`) |
| `routes.py` | step 1: our routes vs agency routes |
| `hubs.py` | step 2: our groups vs agency hubs |
| `export.py` | workbook, GeoPackage, CSV |
| `maps.py` | the two self-contained Leaflet HTML pages |
| `run.py` | orchestrator and `compare_from_cli` entry point (`hubs compare-network`) |

All stage functions are pure (DataFrame in, DataFrame out) and record findings on a
`RunReport`, as in `src/pipeline/`. No stage reads or writes files except `agency.py` (reads)
and `export.py` / `maps.py` (write).

## 3. Mode mapping (`data/reference/agency_mode_map.csv`)

Curated table, one row per mode of ours. Columns: `our_mode`, `agency_type`, `note`.

| our mode | agency type |
|---|---|
| BRT | BRT |
| LRT | LRT |
| Metro | Metro |
| Suburban Rail, Interurban Rail | Rail |
| HighSpeed Rail | Rail fast |
| Funicular | FUNI |
| Cable Line | (none: always reported as unmatched, not an error) |

Agency types absent from the table are reported as a finding and treated as their own mode.

## 4. Step 1: route comparison

### 4.1 Route units

- **Ours.** Lines of the same mode whose node sets are equal are one *route* (the two
  directions). Route key: sorted member `LINE_ID`s joined with `+`. A line with no partner is a
  one-line route. Nodes with unparseable coordinates are dropped and counted.
- **Agency.** Key `(type, line_id)`; for `line_id = 0` the key adds the `lines` feature `name`.
  Geometry = union of the key's `lines` features. Stops = the key's `stations` rows. The
  `stations` layer has no `name` column, so the stations of rail `line_id = 0` cannot be joined
  to a named feature by attribute: each is assigned to the nearest rail feature within
  `rail_assign_tol_m`, and those that fit none are reported as a finding.

### 4.2 Offset

Earlier work found a systematic ~40-60 m shift between our nodes and the agency stops. Using
`local_shift` (median node -> nearest same-mode stop offset within 10 km radius, two passes) a
shift vector is estimated per our node and applied before matching. Raw and corrected distances
are both written. `apply_offset = false` skips the correction.

### 4.3 Matching

For each of our routes `R` (mode `m`) and each agency route `A` of the mapped mode:

- `cov_ours(R, A)` = share of `R`'s nodes within `route_tol_m` of `A`'s geometry
  (default 100 m; `rail_tol_m` 250 m for Rail / Rail fast).
- `cov_agency(R, A)` = share of `A`'s stops within `stop_tol_m` (150 m) of any node of `R`.
- `score = 2 * cov_ours * cov_agency / (cov_ours + cov_agency)`.

Pairs with `score >= only_max_score` (0.2) are *candidates*; each of our routes keeps all its
candidates ranked by score (ties broken by agency route key). A candidate whose agency type is
not the mapped mode of our route is a *cross-mode* candidate and is never counted as matched.

### 4.4 Status per route

Evaluated in this order for each of our routes (same-mode candidates only, unless stated):

| status | rule |
|---|---|
| `matched` | some candidate has `cov_ours >= full_cov` and `cov_agency >= full_cov` (0.8); the best-scoring such candidate is the match. A full match always wins, so routes that share a trunk (rail) are not mislabelled |
| `split_merge` | no full match, and either at least two candidates have both coverages `>= multi_cov` (0.3) (one of our routes runs over several agency routes), or the best candidate's agency route is used, with both coverages `>= multi_cov`, by at least two of our routes and none of those pairs is a full match (several of ours share one agency route); all candidates are listed with their coverages |
| `partial` | not the above, best candidate has `score >= match_min_score` (0.5) |
| `weak` | best candidate has `only_max_score <= score < match_min_score` |
| `mode_differs` | no same-mode candidate, but a cross-mode candidate with `score >= match_min_score` |
| `ours_only` | none of the above (includes a mode with no agency counterpart, e.g. Cable Line) |

Agency routes get status `agency_only` when no route of ours has a same-mode candidate on them
with `score >= match_min_score`. Routes of ours with fewer than 2 nodes are compared normally
but flagged `short_route = true`.

Each row also carries: both sides' names (our `LINE_ID`s and Hebrew line names from the run's
line-name tables when available; agency `name`, `line_name`), mode, node/stop counts, the
agency's `year_operation`, `year_cancel` and `source_plan` (translated through the metadata
workbook), and the distance statistics (raw and corrected median, max).

## 5. Step 2: hub comparison

### 5.1 Hubs on each side

- **Ours**: every row of `hub_groups_all.csv`, points taken from `network_nodes.csv`
  (all nodes of the group, offset-corrected).
- **Agency**: each `hub_id` of `stations`, points = its stops, with the mode set (mapped to the
  common vocabulary), the route keys of its stops, `rail_hub`, `n_modes` (distinct modes) and
  the date fields of its routes.
- **Agency type** = `n_modes` (the `type_sum` equivalent) together with `rail_hub` and the mode
  mix, e.g. "3 modes, rail hub: Rail+LRT+BRT". It is labelled **derived**, not the agency's own
  classification. If `--tod-gpkg` is given, each agency hub is joined to the nearest scraped hub
  within `tod_join_tol_m` (200 m) and `tod_type_sum` is added with a flag where it disagrees with
  `n_modes`.
- **Agency demand**: empty column `agency_total_demand`.

### 5.2 Matching

An agency hub `H` and one of our groups `G` are a *pair* when the minimum distance between a
point of `H` and a point of `G` is `<= hub_match_tol_m` (default 400 m, the tolerance used by
`compare_hubs.py`). Distances use the offset-corrected positions, computed in ITM with a
spatial index. Pairs are many-to-many; the relation is derived per connected component:

| relation | meaning |
|---|---|
| `1:1` | one agency hub, one group |
| `agency_splits` | one agency hub overlaps several of our groups |
| `ours_merges` | several agency hubs overlap one of our groups |
| `many_to_many` | both of the above |
| `agency_only` | no group within tolerance; nearest group, its distance, `eligible` and `exclusion_reason` are given |
| `ours_only` | no agency hub within tolerance; split by `eligible` (scored hubs vs filtered groups) |

Route-level evidence comes from step 1: for each pair, the agency routes at `H` are mapped to our
routes through the step-1 candidates (`matched` / `partial` / `split_merge`), giving the routes
**shared**, **only agency** and **only ours** at that hub. This is *evidence shown*, not part
of the matching rule.

### 5.3 Columns of the `hubs` sheet (one row per pair, plus unmatched rows)

`relation`, agency: `agency_hub_id`, name (most frequent `station_name`), `agency_modes`,
`agency_n_modes`, `agency_rail_hub`, `agency_type`, `agency_n_routes`, `agency_total_demand`
(empty), `tod_type_sum`; ours: `group`, `hub_id`, `HubNameHE`, `Mode_Planned`, `n_modes`,
`n_lines`, `TotalDemand`, `TotalTransfers`, `eligible`, `exclusion_reason`, `HubType`,
`TotalScore_MC`, `RankByHubTypeMetro`; comparison: `distance_m`, `modes_shared`,
`modes_only_agency`, `modes_only_ours`, `routes_shared`, `routes_only_agency`,
`routes_only_ours`, `n_modes_diff`.

## 6. Outputs

Written to `--out` (default: the run directory):

- `network_comparison.xlsx`: sheets `summary`, `routes`, `routes_only_ours`,
  `routes_only_agency`, `mode_summary` (routes per mode on each side and how many matched /
  partial / only), `hubs`, `hubs_agency_only`, `hubs_ours_only`, `hub_routes` (long format:
  one row per hub x route with side and step-1 status), `settings` (the effective
  `CompareConfig`), `inputs` (file names + SHA-256 + counts).
- `network_comparison.gpkg` (EPSG:2039): `route_pairs` (agency geometry with the match
  attributes), `our_routes` (nodes of each of our routes joined in order of the shortest path,
  as `compare_lines.py` does, drawn as a visual aid and labelled so), `agency_hubs`,
  `our_groups`, `hub_ties`.
- `network_comparison_routes.html` and `network_comparison_hubs.html`: self-contained Leaflet
  pages in the style of the HubsScraping comparison pages (layer toggles, mode filter, status
  filter, picker for one route / hub, popups with the columns above, offset toggle).
- `compare_config.json`, `compare_report.md` / `.json` (findings: unmatched modes, stations that
  fit no rail feature, dropped nodes, cross-check disagreements).

## 7. Configuration (`CompareConfig`, defaults)

| key | default |
|---|---|
| `route_tol_m` | 100 |
| `rail_tol_m` | 250 |
| `stop_tol_m` | 150 |
| `rail_assign_tol_m` | 250 |
| `match_min_score` | 0.5 |
| `full_cov` | 0.8 |
| `only_max_score` | 0.2 |
| `multi_cov` | 0.3 |
| `apply_offset` | true |
| `offset_radius_m` / `offset_passes` | 10000 / 2 |
| `hub_match_tol_m` | 400 |
| `tod_join_tol_m` | 200 |

Set with `--config compare.yaml` or `--set key=value`, as the pipeline does. Values are written
to `compare_config.json` and the workbook's `settings` sheet. No threshold is hard-coded in a
stage.

## 8. Errors and edge cases

- Missing layer or column in the gpkg (`lines`, `stations`, `type`, `hub_id`...): `InputError`
  listing every problem, exit code 1.
- Run directory without `hub_groups_all.csv` / `network_nodes.csv`: stop with "re-run `hubs run`
  with this version".
- Our line whose mode has no mapping (Cable Line): kept in `routes_only_ours` with
  `reason = no agency mode`.
- Agency routes with no stations (7 of 132 line ids have none): matched on geometry alone
  (`cov_agency` computed on the line's vertices sampled every 100 m).
- Hebrew text is read and written as UTF-8 (`utf-8-sig` for CSV).
- Deterministic: no randomness, ties broken by the sorted route key.

## 9. Testing

- `tests/unit/test_compare_*.py` on small synthetic fixtures (built in `tests/synthetic.py`
  style): mode mapping, direction-pair collapsing, `line_id = 0` rail keys, offset estimation on
  a known shift, each route status (`matched`, `partial`, `split_merge`, `ours_only`,
  `agency_only`, `mode_differs`), each hub relation, agency-only rows reporting the nearest
  group and its exclusion reason, empty-input cases.
- `tests/unit/test_all_groups.py`: `hub_groups_all.csv` has every group (including ineligible),
  the exclusion reasons, and `eligible` agrees with `filter_eligible`; `network_nodes.csv`
  node x line counts equal the input's.
- Golden tests are untouched; one added assertion that the number of rows in
  `hub_groups_all.csv` equals `groups` and that its eligible rows equal the golden hub count,
  skipped when the real fixtures are absent.
- A smoke test runs `hubs compare-network` end to end on the synthetic run + a synthetic gpkg.
- `MT_Network.gpkg` itself is not committed (like the other real exports); an optional test
  runs on it when placed in `tests/fixtures/real/` and skips otherwise.

## 10. Documentation and dependencies

- New `docs/NETWORK_COMPARISON.md` (how to run, how to read each sheet, thresholds);
  `CLAUDE.md` gets the new command in 20 Key Commands, the package in 9 Codebase Structure and
  a v2.2 entry in 19; `data/reference/README.md` lists `agency_mode_map.csv`.
- No new runtime dependency: geopandas, shapely, pandas, numpy and openpyxl are already in
  `requirements.txt`. scipy is not a dependency and is not added: the port of `local_shift`
  (which used `cKDTree` in `HubsScraping`) and the point-to-point distances use numpy
  broadcasting (a few thousand points per side), point-to-line distances use shapely's
  vectorised `distance`. Each map page is one HTML file with its data embedded as JSON and
  Leaflet 1.9.4 loaded from cdnjs, as in `HubsScraping`.

## 11. Known limits and open points

- Agency demand is empty and the agency type is the mode count; both are stated in the workbook
  `summary` sheet so the figures are not read as an agency classification.
- Route matching can only be as good as the node positions: our lines have no stop order or
  geometry, so `our_routes` in the GeoPackage is an ordered visual aid, not a route.
- The offset estimate assumes a locally constant shift (as in the earlier comparison).
- Before comparing, the 28-10 run has to be repeated with this version so that the two new CSVs
  exist; the comparison does not re-run the pipeline.
- This container has no geopandas / shapely / h3 installed and `tests/fixtures/real/` is empty,
  so implementation and tests need the dependencies installed first, and golden checks run only
  where the real exports are available.
