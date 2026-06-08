# Appendix — Code Reference

This appendix is a navigable index of the code that implements the
framework. It is organised by package, then by module, then by public
function or class. For each function the entry point, signature and
one-line purpose are given. Inputs and outputs (return values) are
described where the function is non-trivial.

> Code is in two places: the canonical, end-to-end **`COMPLETE_TRANSIT_PIPELINE.ipynb`**
> (which is what most planners run) and the reusable **`src/`** package (which
> the script entry points and the notebook both call). The notebook contains
> the "glue" — the rest of this appendix focuses on the reusable package.

## Repository layout

```
HubPrioritizing/
├── CLAUDE.md                       # Framework specification
├── COMPLETE_TRANSIT_PIPELINE.ipynb # Canonical end-to-end notebook
├── scripts/
│   ├── run_complete_pipeline.py    # Full pipeline as a class (CompleteHubPipeline)
│   ├── run_pipeline.py             # Simplified pipeline (no demand / demographics)
│   └── test_ahp_scoring.py         # AHP smoke test
├── src/                            # Reusable library
│   ├── config.py                   # ALL constants, thresholds, weights, paths
│   ├── data/
│   │   ├── loaders.py
│   │   ├── validators.py
│   │   ├── hub_demand_processor.py     # Demand-matching (Part 2) processor class
│   │   └── influence_area_processor.py # Influence-area (Part 3) processor class
│   ├── spatial/
│   │   ├── h3_operations.py
│   │   └── merging.py
│   ├── classification/
│   │   ├── eligibility.py
│   │   └── hierarchy.py
│   ├── scoring/
│   │   ├── activity.py
│   │   ├── service.py
│   │   ├── location.py
│   │   ├── demographics.py
│   │   ├── terminals.py
│   │   ├── normalization.py
│   │   ├── monte_carlo.py
│   │   ├── mc_distribution.py
│   │   └── ahp.py
│   ├── visualization/
│   │   ├── maps.py
│   │   └── charts.py
│   └── utils/
│       ├── constants.py
│       ├── encoding_fix.py
│       └── logging.py
├── data/                           # Templates + manual-correction CSVs
└── docs/                           # Documentation (incl. this folder)
```

## A.1 `src/config.py`

Single source of truth for every parameter. Importing
`from src import config` is the supported way to read it.

| Category | Constants |
|----------|-----------|
| Paths | `PROJECT_ROOT`, `DATA_DIR`, `RAW_DATA_DIR`, `PROCESSED_DATA_DIR`, `RESULTS_DIR`, `LOGS_DIR` |
| CRS | `CRS_WGS84 = 'EPSG:4326'`, `CRS_ISRAEL_TM = 'EPSG:2039'` |
| H3 | `H3_RESOLUTION = 10`, `HUB_MERGE_THRESHOLD_M = 120`, `HUB_MERGE_TOLERANCE_M = 0.1` |
| Eligibility | `ELIGIBILITY_MIN_PASSENGERS = 1000`, `ELIGIBILITY_MIN_MODES = 2`, `MASS_TRANSIT_MODES`, `REQUIRE_NON_RAIL_MODE = True`, `RAIL_ONLY_MODES`, `NON_RAIL_TRANSIT_MODES` |
| Hierarchy | `NATIONAL_HUB_MIN_PASSENGERS = 50000`, `METRO_HUB_MIN_PASSENGERS = 5000`, `METRO_HUB_MAX_PASSENGERS = 50000`, `LOCAL_HUB_MAX_PASSENGERS = 5000`, `TIER_NATIONAL / TIER_METRO / TIER_LOCAL` |
| Scoring | `SCORE_MIN = 1`, `SCORE_MAX = 10`, `MONTE_CARLO_ITERATIONS = 10000`, `MONTE_CARLO_RANDOM_SEED = 42`, `MAX_CRITERION_WEIGHT = 0.5`, `MIN_CRITERION_WEIGHT = 0.0` |
| MC distribution | `MC_DIST_TOP_N_HUBS = 30`, `MC_DIST_HISTOGRAM_BINS = 50`, `MC_DIST_EXPORT_RAW_SCORES = True`, `MC_DIST_PRECISION = 6` |
| AHP | `AHP_ENABLED = False`, `AHP_CONSISTENCY_RATIO_THRESHOLD = 0.10`, `AHP_AGGREGATION_METHOD = 'geometric_mean'`, `AHP_EXPERT_CSV_PATH`, `AHP_SAATY_SCALE` |
| Activity | `ACTIVITY_SCORE_USE_LOG = True`, `ACTIVITY_SCORE_LOG_BASE = 10` |
| Service | `MODE_WEIGHTS` (see below), `MODE_LINE_DIMINISHING_RETURNS = True`, `MODE_DIVERSITY_BONUS_PCT = 0.10` |
| Location | `REGION_WEIGHTS` (Hebrew + English), `METRO_POSITION_WEIGHTS` |
| Demographics | `CATCHMENT_RINGS = [(0,500), (500,1000), (1000,1500)]`, `DISTANCE_DECAY_BETA = 1.5`, `RING_WEIGHTS` (computed), `POP_JOB_MIX` |
| Terminals | `TERMINAL_PROXIMITY_DISTANCE_M = 200`, `TERMINAL_WEIGHTS` |
| Encoding | `DEFAULT_ENCODING = 'windows-1255'`, `UTF8_ENCODING = 'utf-8-sig'` |
| Maps | `MAP_TILES = 'OpenStreetMap'`, `MAP_CENTER_ISRAEL = [31.5, 34.9]`, `MAP_ZOOM_DEFAULT = 8`, `TIER_COLORS` |
| Logging | `LOG_LEVEL`, `LOG_FORMAT`, `LOG_DATE_FORMAT`, `LOG_TO_FILE`, `LOG_TO_CONSOLE` |
| Exports | `EXPORT_CSV / GEOJSON / EXCEL / SHAPEFILE` |

`MODE_WEIGHTS` (active values):

```
Funicular      2.0    Cable Line     3.0    BRT             4.0
LRT            5.0    Metro          6.0    Suburban Rail   6.0
Interurban     7.0    Rail (generic) 7.0    HighSpeed Rail  8.0
Express Bus    3.0    Bus            1.0
```

Helpers exported:

- `get_tier_from_ridership(ridership) → str`
- `is_mass_transit_mode(mode) → bool`
- `get_mode_weight(mode) → float`
- `print_config_summary()` — pretty-prints the active configuration.

## A.2 `src/data`

### `loaders.py`

Reads raw inputs to GeoDataFrames / DataFrames and validates required
columns and CRS.

| Function | Returns |
|----------|---------|
| `load_transit_nodes(filepath, encoding=DEFAULT_ENCODING)` | `gpd.GeoDataFrame` in EPSG:2039 with `node`, `LINE_ID`, `geometry` |
| `load_lines_and_modes(filepath, encoding=DEFAULT_ENCODING)` | `pd.DataFrame` with `LINE_ID`, `Mode_Planned`, `Area` |
| `load_demand_data(filepath)` | `pd.DataFrame` of merged demand sheets |
| `load_spatial_layer(filepath, ...)` | Generic shapefile loader with encoding fallback |
| `load_metro_areas(filepath)` | Metropolitan polygons with `METRO_NAME` |
| `load_districts(filepath)` | District polygons |
| `load_taz_zones(filepath)` | 2050 TAZ polygons with `POP_2050`, `EMPL_2050` |
| `load_bus_terminals(filepath)` | Bus-terminal points with `term_type` |
| `load_processed_hubs(filepath)` | Re-load a hubs CSV (geometry from WKT) |

### `validators.py`

`ValidationError` exception plus the following checks (all raise on
failure unless documented otherwise):

- `validate_required_columns`, `validate_geometry`, `validate_crs`,
- `validate_numeric_range`, `validate_score_column`,
- `validate_hub_count`, `validate_no_duplicates`,
- `validate_completeness`,
- `validate_hubs_dataset`, `validate_scored_hubs`
  (composite checks for end-to-end sanity).

## A.3 `src/spatial`

### `h3_operations.py`

| Function | Purpose |
|----------|---------|
| `assign_h3_to_points(gdf, resolution=H3_RESOLUTION)` | Add `h3_index` column (using WGS84 lat/lon) |
| `h3_to_polygon(h3_index)` | H3 cell → Shapely `Polygon` |
| `create_h3_hexagons(gdf, ...)` | Build a hex-polygon GeoDataFrame |
| `aggregate_by_h3(gdf, mode_column, line_column, node_column)` | Group rows by H3 cell, aggregate modes / line counts / node lists |
| `get_h3_neighbors(h3_index, ring=1)` | Neighbour H3 cells |
| `calculate_h3_centroids(gdf)` | Add centroid column |

### `merging.py`

- `class UnionFind` — disjoint-set with `find`, `union`, `get_groups`.
- `create_proximity_groups(gdf, distance_threshold=HUB_MERGE_THRESHOLD_M, tolerance=HUB_MERGE_TOLERANCE_M)` — adds a `group` column based on edge-to-edge proximity.
- `aggregate_groups(gdf)` — collapse hexagons of the same group into one row, merging modes and line counts.
- `filter_single_mode_hubs(gdf)` — drop hubs with fewer than two distinct mass-transit modes (mirrors the eligibility check).

## A.4 `src/classification`

### `eligibility.py`

| Function | Purpose |
|----------|---------|
| `count_mass_transit_modes(modes)` | Counts modes from `MASS_TRANSIT_MODES` |
| `has_non_rail_transit_mode(modes)` | True if any of Metro/LRT/BRT/HighSpeed Rail present |
| `is_rail_only_hub(modes)` | True if only rail-family modes (used when `REQUIRE_NON_RAIL_MODE=True`) |
| `is_eligible_hub(modes, demand)` | Combined eligibility check |
| `filter_eligible_hubs(gdf, ...)` | Returns the filtered GeoDataFrame |
| `add_eligibility_flags(gdf)` | Adds explanatory boolean columns |
| `get_eligibility_summary(gdf)` | Tabular summary of dropped vs kept |

### `hierarchy.py`

| Function | Purpose |
|----------|---------|
| `classify_hub_tier(total_demand, modes, num_lines)` | Single-row tier decision (uses ridership thresholds + mode mix) |
| `assign_hub_tiers(gdf, demand_column='TotalDemand')` | Adds `tier` column |
| `add_tier_metadata(gdf)` | Adds friendly descriptions per tier |
| `get_tier_statistics(gdf)` | Per-tier counts and summary stats |
| `filter_by_tier(gdf, tier)` | Subset to a single tier |

## A.5 `src/scoring`

### `activity.py`
- `calculate_activity_score(gdf, demand_column, tier_column, use_log=True) → pd.Series` — log₁₀ transform + per-tier min-max to 1–10.

### `service.py`
- `calculate_line_score_with_diminishing_returns(n_lines) → float` — `sqrt(n_lines)`.
- `calculate_mode_service_score(modes, line_counts, use_diminishing_returns=True) → float` — raw weighted sum with the diversity bonus.
- `calculate_service_score(gdf, modes_column, line_count_columns, tier_column) → pd.Series` — full normalised score per hub.

### `location.py`
- `fix_truncated_hebrew(text) → str` — repairs known shapefile truncations (`גלעי → גלעין`, `תל אבי → תל אביב`, …).
- `get_region_weight(region) → float` — `REGION_WEIGHTS` lookup with fallbacks.
- `get_metro_position_weight(position) → float` — `METRO_POSITION_WEIGHTS` lookup.
- `calculate_location_score(gdf, region_column, metro_position_column) → pd.Series` — region × metro position, global min-max to 1–10.

### `demographics.py`
- `calculate_weighted_pop_jobs(pop_values, job_values, tier, ring_weights, pop_job_mix) → float` — single-row weighted sum over rings.
- `calculate_pop_jobs_score(gdf, tier_column, pop_zone_columns, emp_zone_columns) → pd.Series` — per-tier normalised 1–10.

### `terminals.py`
- `get_terminal_weight(terminal_type) → float` — `TERMINAL_WEIGHTS` lookup.
- `calculate_terminal_score(gdf, near_terminal_column, terminal_type_column) → pd.Series` — global min-max to 1–10.

### `normalization.py`
- `normalize_minmax(values, min_val=1, max_val=10, input_min=None, input_max=None)` — min-max with optional explicit bounds.
- `normalize_by_tier(df, value_column, tier_column, min_val=1, max_val=10)` — independent min-max per tier (this is what most criteria use).
- `normalize_log10(values, ...)` — log₁₀ + min-max in one call.
- `normalize_log10_by_tier(df, value_column, tier_column, ...)` — same but per tier (Activity).

### `monte_carlo.py`
- `generate_random_weights(n_criteria, max_weight=MAX_CRITERION_WEIGHT, min_weight=MIN_CRITERION_WEIGHT, random_state=None) → np.ndarray` — one weight draw, renormalised to sum to 1.
- `monte_carlo_scoring(score_matrix, n_iterations=MONTE_CARLO_ITERATIONS, random_seed=MONTE_CARLO_RANDOM_SEED) → np.ndarray` — mean of per-iteration weighted scores.
- `calculate_all_scores(gdf, ...) → gpd.GeoDataFrame` — runs all five scorers in order.
- `calculate_final_scores(gdf, criteria_columns, tier_column) → gpd.GeoDataFrame` — Monte Carlo aggregation + tier-aware rank.
- `_calculate_tier_based_ranking(gdf, score_column, tier_column, area_column)` — Nationals globally, Metro/Local per geographic area.
- `get_score_summary(gdf, tier_column='tier') → pd.DataFrame` — printable per-tier score summary.
- `run_complete_scoring_pipeline(gdf, tier_column='tier') → gpd.GeoDataFrame` — **the function the notebook and `scripts/run_complete_pipeline.py` both call**. Returns the scored, ranked GeoDataFrame with the columns documented in `07_outputs.md`.

### `mc_distribution.py`
- `monte_carlo_with_distributions(score_matrix, n_iterations, …)` — same as `monte_carlo_scoring` but keeps every per-iteration score.
- `calculate_distribution_statistics(iteration_scores)` — mean / median / std / percentiles per hub.
- `calculate_rank_robustness(iteration_ranks)` — `P(Top-1)`, `P(Top-3)`, `P(Top-5)` per hub.
- `export_hub_stats_csv`, `export_raw_scores_long` — CSV outputs.
- `create_score_boxplot`, `create_top_k_probability_chart`, `create_hub_distribution_histogram`, `create_all_hub_histograms` — matplotlib visualisations.
- `class MCDistributionResults` — container for the full analysis result.
- `run_mc_distribution_analysis(score_matrix, output_dir, n_iterations, …) → MCDistributionResults` — orchestrator (called by Part 4 when distribution analysis is enabled).
- `get_conservative_ranking`, `identify_robust_winners`, `compare_hubs` — downstream helpers.

### `ahp.py`
- `validate_pairwise_matrix(matrix)` — square / positive / reciprocal / diagonal-1 checks.
- `calculate_priority_vector(matrix, method='eigenvector')` — principal-eigenvector weights.
- `calculate_consistency_ratio(matrix, weights)` — CR vs `AHP_CONSISTENCY_RATIO_THRESHOLD`.
- `load_expert_comparisons_from_csv(csv_path, criteria_names=None)` — accepts both long and matrix formats.
- `aggregate_expert_weights(expert_matrices, method=AHP_AGGREGATION_METHOD)` — geometric mean / arithmetic mean / median.
- `calculate_ahp_scores(scores_df, weights)` — apply aggregated weights.
- `run_ahp_scoring_pipeline(gdf, expert_csv, …)` — end-to-end AHP path; returns the GeoDataFrame with `ahp_score` and `ahp_rank`.
- `create_expert_template_csv(out_path)` — emits a blank template for experts to fill in.
- `compare_monte_carlo_vs_ahp(gdf)` — correlation / rank-overlap comparison.
- `saaty_scale_description()`, `print_saaty_scale()` — reference helpers.

## A.6 `src/visualization`

### `maps.py`
- `create_hub_map(gdf, color_by='final_score', popup_columns=…, output_file=…)` — Folium map, OpenStreetMap tiles, centred on Israel, popups per hub.

### `charts.py`
- `plot_score_distribution(gdf, score_column, tier_column, …)` — histogram by tier.
- `plot_tier_comparison(gdf, …)` — side-by-side tier comparison.

## A.7 `src/utils`

### `constants.py`
Hard enums for cross-module references:
- `class HubTier(Enum)`: `NATIONAL`, `METROPOLITAN`, `LOCAL`.
- `class TransportMode(Enum)`, `class Region(Enum)`,
  `class MetroPosition(Enum)`, `class TerminalType(Enum)`.

### `encoding_fix.py`
Hebrew-aware encoding helpers:
- `is_valid_hebrew_text(text, min_hebrew_ratio=0.3, verbose=False)`,
- `validate_hebrew_in_gdf(gdf, ...)`,
- `read_shapefile_with_encoding(filepath, ...)` — tries `windows-1255`,
  `cp1255`, `utf-8`, … in order,
- `diagnose_encoding_issue(shapefile_path, ...)`,
- `fix_encoding_in_dataframe(df, ...)`.

### `logging.py`
- `setup_logger(name, level='INFO', log_file=None, log_to_console=True)` — file + console handlers.
- `get_logger(name)`.
- `class LoggerMixin` — for classes that want a `self.logger`.

## A.8 Top-level scripts and processors

### `scripts/run_complete_pipeline.py`
Defines `CompleteHubPipeline`. The recommended programmatic entry
point — orchestrates all 12 stages from raw inputs through scoring and
export.

Run order:
1. `load_all_data()` — `src.data.loaders.*`
2. `create_h3_hexagons()` — `src.spatial.h3_operations.aggregate_by_h3`
3. `group_hubs()` — `src.spatial.merging.create_proximity_groups` + `aggregate_groups`
4. `add_demand_data()` — multi-sheet Excel matching (in-script, mirrors notebook Step 2.5–2.6)
5. `add_spatial_tags()` — district / region join
6. `add_demographics()` — `InfluenceAreaProcessor.process_full_pipeline`
7. `add_terminal_proximity()` — 200 m buffer check
8. `filter_eligibility()` — `src.classification.eligibility.filter_eligible_hubs`
9. `classify_hierarchy()` — `src.classification.hierarchy.assign_hub_tiers`
10. `calculate_scores()` — `src.scoring.monte_carlo.run_complete_scoring_pipeline`
11. *(opt.)* `run_mc_distribution_analysis()` — when `RUN_MC_DISTRIBUTION=true`
12. `export_results()` — CSV + GeoJSON + Folium HTML.

### `scripts/run_pipeline.py`
Defines `HubPrioritizationPipeline` — same shape as
`CompleteHubPipeline` but **skips demand, demographics, and terminal
proximity** (stages 4–7). Useful for rapid prototyping when only the
H3 + grouping + scoring path needs to be exercised.

### `src/data/influence_area_processor.py`
`class InfluenceAreaProcessor` — the Part-3 (population/employment ring)
processor, refactored from notebook code for ~3.7× performance. Key
public methods:
- `load_grouped_hubs(filepath)`,
- `load_taz_data(filepath)`,
- `process_full_pipeline(hubs_csv, taz_shp, terminals_shp, output_csv)`.

### `src/data/hub_demand_processor.py`
`class DemandDataProcessor` — Part 2 demand-matching logic refactored
out of the notebook. Key public methods:
- `load_gdf_from_csv(filepath)`,
- `load_demand_data(filepath)`,
- `standardize_demand_dataframes(demand_data)`,
- `assign_demand_by_area(gdf, demand_data)`,
- `aggregate_hubs(gdf)`.

## A.9 Templates and supporting data files

| File | Purpose |
|------|---------|
| `data/IsSameGroup_TEMPLATE.csv` | Skeleton for the manual-group-corrections file (Step 1.5.1) |
| `data/manual_demand_updates_TEMPLATE.csv` | Skeleton for the demand-overrides file (Step 2.6.1) |
| `data/ahp_expert_comparisons_TEMPLATE.csv` | Blank AHP pairwise template |
| `data/ahp_expert_comparisons_example.csv` | Worked example with three experts |
| `data/hub_names_TEMPLATE.csv` | Hub-name display table |
| `data/README_MANUAL_GROUP_CORRECTIONS.md` | Operator guide for IsSameGroup |
| `data/README_MANUAL_DEMAND_UPDATES.md` | Operator guide for demand overrides |
| `data/README_MODE_LINE_COLUMNS.md` | Field-level reference for the per-mode line-count columns |

## A.10 Notebooks

| Notebook | Status / use |
|----------|--------------|
| `COMPLETE_TRANSIT_PIPELINE.ipynb` | Canonical end-to-end pipeline (the source of truth for the model) |
| `notebooks/complete_hub_scoring_pipeline.ipynb` | Alternate scoring-focused entry point |
| `notebooks/HubsScoring_vAugust2025.ipynb` | Historical reference (August 2025 scoring run) |
| `notebooks/Group_n_Filter_Hubs.ipynb` | Earlier grouping/filtering implementation, kept for traceability |
| `notebooks/hub_data_postprocess.ipynb` | Post-processing utilities for the scored hubs |
| `notebooks/map_hub_results.ipynb` | Mapping / visualisation utilities |
| `notebooks/ahp_expert_questionnaire.ipynb` | Interactive AHP elicitation |
| `notebooks/create_results_csv.ipynb`, `notebooks/test_spatial_alignment.ipynb`, … | Diagnostic / utility notebooks |

## A.11 Running the pipeline

```bash
# Programmatic (full pipeline, requires all inputs)
python scripts/run_complete_pipeline.py

# Programmatic (simplified — no demand / no demographics)
python scripts/run_pipeline.py

# Notebook (canonical, recommended path)
jupyter nbconvert --to notebook --execute COMPLETE_TRANSIT_PIPELINE.ipynb
```

Both paths read configuration from `src/config.py`; the notebook
additionally has a **MASTER CONFIGURATION** cell that lets you override
file paths for a one-off run.
