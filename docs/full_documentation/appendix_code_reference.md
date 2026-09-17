# Appendix — Code Reference

## Repository layout

```
src/
  cli.py                 hubs validate | run | compare | runs | serve | show-config | prepare-base | export-h3
  gui/                   server.py (JSON API + static page for `hubs serve`), index.html
  config.py              thresholds, weights, CRS, MODE_LINE_COLS, MODE_TO_COLUMN, tier labels
  pipeline/              the one-command pipeline
  spatial/               h3_operations.py (H3 helpers), merging.py (UnionFind, proximity groups)
  classification/        hierarchy.py (classify_hub_tier)
  utils/                 encoding_fix.py (Hebrew validation), logging.py
data/reference/          stable layers and curated tables (see its README)
tests/                   unit/ (synthetic), golden/ (real exports, gitignored fixtures), test_smoke.py
scripts/                 compare_base_layer.py (H3 base layer vs shapefile overlay)
```

## A.1 `src/pipeline` — public functions

All functions take frames and return frames. `report` is an optional `RunReport` that
collects findings.

### `settings.py`
- `PipelineConfig` — frozen dataclass of every parameter (defaults = notebook behaviour).
- `load_config(yaml_path, overrides) -> PipelineConfig`; `parse_set_overrides(["k=v", ...])`.
- `default_yaml()` — defaults as YAML (`hubs show-config --defaults`).

### `inputs.py`
- `INPUT_SPECS` — key, filename patterns, required columns, Hebrew columns, reference flag.
- `discover_inputs(input_dir, reference_dir, overrides) -> InputSet`; `pick_latest(paths)`.
- `validate_inputs(inputs, report) -> list[str]`; `require_valid_inputs(...)` raises `InputError`.
- `read_csv_auto(path, hebrew_columns=..., **read_csv) -> (DataFrame, encoding)`.
- `read_shapefile(path, hebrew_columns=..., encoding=None) -> (GeoDataFrame, code page)`.
- `read_excel_sheets(path) -> dict[str, DataFrame]`.

### `network.py`
- `load_nodeslines(df) -> GeoDataFrame` (EPSG:2039 points; `node`, `LINE_ID`).
- `attach_modes(nodes, lines_mode, drop_rules, report)` — dedupe keys, drop rules, left join, drop rows without a mode.
- `aggregate_to_hexes(nodes, resolution=10)` — `h3_index, node, Mode_Planned, Line_Nunique, Line_Unique, Lines_by_Mode, geometry`.
- `add_mode_line_columns(hexes, method='even'|'exact')` — the eight `<Mode> Lines`.

### `grouping.py`
- `group_hexes(hexes, threshold_m=120, tolerance_m=0.1)` → `group`.
- `apply_manual_groups(hexes, is_same_group_df, report, renumber=True)`.
- `assign_hub_ids(hexes)` → `hub_id`; `hub_identity_table(hexes)`; `stable_hub_id(nodes)`.

### `base_layer.py` (the default spatial source)
- `build_base_layer(metro, districts, terminals, taz, resolution=10, terminal_buffer_m=200, report) -> DataFrame` — one row per cell: `h3_index, area, location, term_type, term_id, bus_terminal, pop_2050, emp_2050` (`allocate_taz`, `terminals_to_cells`, `tag_cells_area_and_location`).
- `write_base_layer(df, path, manifest)`, `read_base_layer(path) -> (DataFrame indexed by h3_index, manifest)`, `build_manifest(sources, resolution, buffer_m, n_rows)`.
- `tag_area_and_location_from_base(hexes, base, report)` → `area`, `location`.
- `tag_bus_terminals_from_base(groups, hexes, base, report)` → `term_type`, `term_id`, `bus_terminal`.
- `add_influence_area_from_base(groups, base, rings, resolution, cell_rule='fraction'|'center', report)` → `pop_<a>_<b>`, `emp_<a>_<b>`.
- Helpers: `cells_covering(geoms, resolution)`, `cell_polygons_itm(cells)`, `cell_centres_itm(cells)`, `grid_disk_radius(outer_m, resolution)`.

### `h3_export.py`
- `build_h3_layer(base, hexes, results, groups, rings, resolution, extent='hubs'|'influence'|'all') -> GeoDataFrame` (`LAYER_COLUMNS`, EPSG:2039).
- `write_h3_layer(layer, path, fmt='gpkg'|'geojson'|'parquet'|'csv') -> Path`; `hub_cell_table`, `influence_cells`.

### `spatial_tags.py` (shapefile path, `spatial_source=shapefiles`)
- `tag_area_and_location(hexes, metro, districts, report)` → `area` (str), `location` (list).
- `get_regions_for_area(area) -> list[str]` — candidate demand models; `fix_hebrew_name(text)` (also used when the base layer is built).

### `demand.py`
- `SHEET_NAME_MAPPING`, `SHEET_COLUMN_CONFIG`, `DEFAULT_COLUMN_CONFIG`.
- `load_demand_workbook(sheets, report) -> {region: DataFrame(node, demand, transfers)}`.
- `assign_demand(hexes, by_region, overlay_regions, report)` → `TotalDemand`, `TotalTransfers`.
- `apply_manual_demand(hexes, updates_df, report)`.

### `aggregate.py`
- `aggregate_to_groups(hexes)` — one row per group, dissolved geometry, `Num_Modes`.
- `tag_bus_terminals(groups, terminals, buffer_m=200, report)` → `term_type`, `term_id`, `bus_terminal` (shapefile path).
- `add_influence_area(groups, taz, rings=(500,1000,1500), report)` → `pop_<a>_<b>`, `emp_<a>_<b>` (shapefile path).
- `bus_terminal_score(term_type) -> int`; `ring_column_names(rings)` (both paths).

### `scoring.py`
- `prepare_scoring_frame(groups)` → `Total_Unique_Lines`, `Region_category`, `Location_category`, `RegionLocation`.
- `add_mode_score(df, mode_weights, alpha=0.1)` → `score`.
- `classify(df, require_non_rail=True)` → `HubType`, `is_rail_only`, `eligible`; `filter_eligible(df, enabled, report)`.
- `normalize_scores(df, rings, decay_beta=1.5, report)` → the five `*_Norm`, `LogDemand`, `PopEmp_Score_Raw`.
- `draw_weight_matrix(rng, n_iter, n_criteria=5, max_weight=0.5)`; `monte_carlo(df, n_iter, seed, scope, report)` → `Average_Simulated_Score`, `Rank_within_HubType`, `Overall_Rank`.
- `score_hubs(groups, **config) -> DataFrame` — steps in order.

### `postprocess.py`
- `load_line_names(df, report) -> dict`; `load_line_status(df, report) -> dict`; `load_line_corrections(df) -> dict`; `hub_name_lookup(hubs, hub_names_df, report) -> Series`.
- `finalize_columns(scored, *, line_names, line_status, line_corrections, hub_names, renormalize_globally=False, report) -> DataFrame` — every display column.
- `rank_by_hubtype_metro(df)`, `line_names_for_plot(names)`, `parse_line_unique(value)`, `modes_to_hebrew(modes)`.

### `export.py`
- `FINAL_COLUMNS` (70 names, ordered); `select_final_columns(df, extra_columns)`.
- `write_results_xlsx(df, path, sheet_name, table_name, extra_columns)`; `write_results_csv(...)`; `read_results_xlsx(path)`.

### `versioning.py`
- `build_run_manifest(inputs, cfg, results, version, outputs) -> dict`; `write_run_manifest`, `read_run_manifest`, `default_version(inputs)`, `list_runs(root) -> DataFrame`.
- `RunDir(path)`; `match_hubs(a, b)` (by `hub_id`, then shared nodes); `compare_runs(dir_a, dir_b) -> {summary, table, tier_changes, score_moves, rank_moves}`; `comparison_markdown`, `write_comparison(comp, out_dir)`.

### `report.py`
- `RunReport` — `info/warn/error(section, message, **data)`, `record_input`, `set_metric`, `to_markdown`, `to_json`, `write(out_dir)`.

### `run.py`
- `run_pipeline(cfg, inputs, report=None, allow_missing_layers=False) -> RunResult(results, groups, scored, hexes, report, config, base)`.
- `write_outputs(result, output_dir) -> {name: Path}` (workbook, csv, identity, `h3_layer.<ext>`, report, config); `run_from_cli(args)`.
- `prepare_base_layer(inputs, out_path, resolution, terminal_buffer_m, report)`; `prepare_base_from_cli(args)`; `export_h3_from_cli(args)`; `compare_from_cli(args)`; `runs_from_cli(args)`.

### `gui/server.py`
- `make_server(root, reference_dir, host, port) -> ThreadingHTTPServer`; `serve_from_cli(args)`.
- `ServerState` (jobs, access rules); `api_state`, `api_browse`, `api_validate`, `api_runs`, `api_compare`, `api_report` — the JSON API as plain functions.

## A.2 `src/config.py` — constants used by the pipeline

| Constant | Value | Used by |
|---|---|---|
| `H3_RESOLUTION` | 10 | network |
| `HUB_MERGE_THRESHOLD_M`, `HUB_MERGE_TOLERANCE_M` | 120, 0.1 | grouping |
| `ELIGIBILITY_MIN_PASSENGERS` | 1000 | scoring.classify |
| `NATIONAL_HUB_MIN_PASSENGERS`, `METRO_HUB_MIN_PASSENGERS` | 50000, 5000 | hierarchy.classify_hub_tier |
| `REQUIRE_NON_RAIL_MODE`, `RAIL_ONLY_MODES` | True; Rail, Suburban Rail, Interurban Rail | scoring.classify |
| `TIER_NATIONAL / TIER_METRO / TIER_LOCAL` | ארצי / מטרופוליני / עירוני | everywhere |
| `MODE_WEIGHTS` | Funicular 2 … HighSpeed Rail 8 | scoring.add_mode_score |
| `MODE_LINE_COLS`, `MODE_TO_COLUMN` | the eight `<Mode> Lines` columns | network, aggregate, scoring |
| `MONTE_CARLO_ITERATIONS`, `MONTE_CARLO_RANDOM_SEED`, `MAX_CRITERION_WEIGHT` | 10000, 42, 0.5 | scoring.monte_carlo |
| `TERMINAL_PROXIMITY_DISTANCE_M` | 200 | base_layer.terminals_to_cells (prepare-base), aggregate.tag_bus_terminals |
| `CRS_WGS84`, `CRS_ISRAEL_TM` | EPSG:4326, EPSG:2039 | all spatial stages |
| `REFERENCE_DATA_DIR` | `data/reference` | inputs |

Run-time parameters (rings, filter flags, MC scope, output names) live in
`PipelineConfig`, not in `config.py`.

## A.3 Tests

| Location | Needs | Covers |
|---|---|---|
| `tests/unit/` | nothing external | every stage on small synthetic frames, settings, inputs, report, CLI |
| `tests/test_smoke.py` | nothing external (`tests/synthetic.py` builds a full input + reference set) | end-to-end run, byte-identical reruns, loud failure on missing layers, CLI |
| `tests/golden/` | `tests/fixtures/real/` (June 2026 exports + results workbook) | groups, demand, aggregates, scoring, display columns and the full run against the golden workbook |
