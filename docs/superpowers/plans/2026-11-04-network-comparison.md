# Network comparison (HubPrioritizing vs the planning agency) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `hubs compare-network` compares the pipeline's network and all pre-filter hub groups with the agency's `MT_Network.gpkg`, by route and by hub, writing a workbook, a GeoPackage and two HTML maps.

**Architecture:** `hubs run` additionally writes `hub_groups_all.csv` and `network_nodes.csv`. A new `src/compare/` package of pure DataFrame stages (settings, mode map, agency reader, offset, routes, hubs) reads a finished run directory plus the agency files; `export.py` / `maps.py` write the outputs; `run.py` orchestrates and is wired to a new CLI subcommand.

**Tech Stack:** Python 3.11+, pandas, numpy, geopandas, shapely 2, openpyxl, pytest. No new dependency (no scipy).

**Spec:** `docs/superpowers/specs/2026-11-04-network-comparison-design.md` (read it first; section numbers below refer to it).

## Global Constraints

- Work on branch `claude/pensive-hawking-pa0tvm`; end every commit message with the two attribution lines from the session (`Co-Authored-By: ...`, `Claude-Session: ...`).
- Distances in EPSG:2039 metres; maps in WGS84; CSV written `utf-8-sig`; Hebrew never re-encoded.
- Deterministic: no randomness; ties broken by sorted route key / id.
- No threshold or tolerance hard-coded in a stage: all come from `CompareConfig` (defaults, spec 7): `route_tol_m=100`, `rail_tol_m=250`, `stop_tol_m=150`, `rail_assign_tol_m=250`, `match_min_score=0.5`, `full_cov=0.8`, `only_max_score=0.2`, `multi_cov=0.3`, `apply_offset=True`, `offset_radius_m=10000`, `offset_passes=2`, `hub_match_tol_m=400`, `tod_join_tol_m=200`.
- Eligibility thresholds come from `src/config.py` constants and `classify`; scoring, tiers and every existing output column are unchanged (golden tests untouched).
- Stages are pure (frame in, frame out) and record findings on `src.pipeline.report.RunReport`; only `agency.py` (read), `export.py` and `maps.py` (write) touch files. Google-style docstrings, PEP 8, line length 100.
- Importing any module must have no side effects (`tests/unit/test_import_side_effects.py`).

## Review Focus

1. A route of ours with a single node (the synthetic fixture has them): compared normally, flagged `short_route`, never crashes `order_points` (Task 5).
2. Agency rail features sharing `line_id = 0` and duplicate names ("Haifa Rail 22" twice): one route key, deterministic station assignment, stations that fit no feature reported (Task 3).
3. Placeholder station names (`"- 239"`, `"406 - 4"`) and `hub_id` stored as float: ids come out as ints, hub name falls back to `hub <id>` (Task 3).
4. Empty or no-match inputs (run with zero eligible hubs, a mode with no agency routes, an agency layer with no rows): empty tables with the right columns, no exception (Tasks 5-8).
5. Gpkg in a CRS other than EPSG:2039, and nodes with no agency stop within the offset radius: reprojected / zero-shift fallback to the global median (Tasks 3, 4).

---

### Task 1: Pipeline outputs `hub_groups_all.csv` and `network_nodes.csv`

**Files:**
- Create: `src/pipeline/all_groups.py`, `tests/unit/test_all_groups.py`
- Modify: `src/pipeline/settings.py` (two keys), `src/pipeline/run.py` (`RunResult`, `run_pipeline` return, `write_outputs`), `tests/test_smoke.py` (assertions), `tests/golden/test_groups_golden.py` (one skipped-without-fixtures assertion)

**Interfaces:**
- Consumes: `scoring.prepare_scoring_frame`, `scoring.classify(df, require_non_rail)`, `postprocess.hub_name_lookup(hubs, hub_names, report)`, `RunResult.groups/results/hexes`.
- Produces:
  - `PipelineConfig.all_groups_basename: str = "hub_groups_all"`, `network_nodes_basename: str = "network_nodes"` (`""` = not written; spec 2.1).
  - `RunResult.nodes: gpd.GeoDataFrame | None = None`, `RunResult.line_names: dict[str, str]` (default empty), `RunResult.hub_names: pd.DataFrame | None = None` (the optional `hub_names` table read in Part 5); all filled by `run_pipeline`.
  - `build_all_groups_table(groups: pd.DataFrame, results: pd.DataFrame, hub_names: pd.DataFrame | None, require_non_rail: bool) -> pd.DataFrame` with the columns of spec 2.1 (`exclusion_reason` joins `demand < min`, `single mode`, `rail only` with `;`; score/rank columns NaN for groups not in `results`; list columns written as `;`-joined strings by the writer, kept as lists in memory).
  - `build_network_nodes_table(nodes: gpd.GeoDataFrame, hexes: gpd.GeoDataFrame, line_names: Mapping[str, str]) -> pd.DataFrame` with `node, LINE_ID, line_name, Mode_Planned, x_itm, y_itm, group, hub_id`.
  - `write_all_groups(...)` is not needed: `write_outputs` calls `to_csv(..., encoding="utf-8-sig")` itself and records both paths as `paths["hub_groups_all"]`, `paths["network_nodes"]`.

- [ ] **Step 1: Write failing tests** in `tests/unit/test_all_groups.py`, using `make_synthetic_dirs` + `run_pipeline` (default filter on, `mc_iterations=50`): `test_all_groups_has_every_group_including_ineligible` (row count == `len(result.groups)`; the lone rail node's group, node 9, has `eligible == False` and `exclusion_reason` containing `single mode` and `rail only`; hubs A and B are eligible); `test_eligible_rows_match_scored_hubs` (set of `group` where `eligible` == set of `result.results["group"]`); `test_exclusion_reason_empty_when_eligible`; `test_network_nodes_counts` (rows == distinct node x line pairs of `result.nodes`; every row has a `group` and `hub_id` that exist in `hub_groups_all`); `test_outputs_can_be_switched_off` (`all_groups_basename=""` writes no file); `test_hub_groups_all_roundtrips_lists` (`Line_Unique` split on `;` equals the in-memory list).
- [ ] **Step 2: Run** `pytest tests/unit/test_all_groups.py -v`; expect FAIL (module missing).
- [ ] **Step 3: Implement** the two builders in `src/pipeline/all_groups.py` (reuse `prepare_scoring_frame` + `classify`; WGS84 `x`/`y` and `x_itm`/`y_itm` from the group geometry centroid; group centroid for `x`, `y` is the pipeline's existing `x`, `y` columns on `groups`), add the settings keys (validate: strings), store `nodes` and `names` on `RunResult`, and write both CSVs in `write_outputs` next to `hub_identity.csv`.
- [ ] **Step 4: Run** `pytest tests/unit/test_all_groups.py tests/test_smoke.py tests/unit/test_settings.py -v`; expect PASS. Extend `test_run_pipeline_end_to_end`: both files exist in `tmp_path/"out"`.
- [ ] **Step 5: Golden assertion** in `tests/golden/test_groups_golden.py`: `hub_groups_all` row count equals the golden group count (1,033) and its `eligible` rows equal the golden hub count (142 per CLAUDE.md section 15); skipped when fixtures are absent (use the module's existing skip mechanism).
- [ ] **Step 6: Commit** `git add src/pipeline tests && git commit -m "feat: write hub_groups_all.csv and network_nodes.csv with every run"`.

### Task 2: `CompareConfig` and the mode map

**Files:**
- Create: `src/compare/__init__.py`, `src/compare/settings.py`, `src/compare/modes.py`, `data/reference/agency_mode_map.csv`, `tests/unit/test_compare_settings.py`, `tests/unit/test_compare_modes.py`
- Modify: `data/reference/README.md` (one table row)

**Interfaces:**
- Produces:
  - `CompareConfig` (frozen dataclass, fields/defaults per Global Constraints; `to_dict()`, `to_json()`, `validate()` raising `ConfigError`: tolerances `> 0`, scores/coverages in `[0, 1]`, `only_max_score <= match_min_score`, `offset_passes >= 0`).
  - `load_compare_config(yaml_path: Path | str | None = None, overrides: Mapping[str, Any] | None = None) -> CompareConfig` (defaults < yaml < overrides; unknown key -> `ConfigError`; bools/ints/floats coerced like `pipeline.settings`; reuse `ConfigError` and `parse_set_overrides` from there).
  - `COMPARE_KEYS: tuple[str, ...]`.
  - `MODE_MAP_PATH = REFERENCE_DATA_DIR / "agency_mode_map.csv"`; `load_mode_map(path: Path | None = None) -> dict[str, str | None]` (our mode -> agency type, `None` for no counterpart); `map_mode(our_mode: str, mode_map: Mapping[str, str | None]) -> str | None`; unknown modes return `None`.

- [ ] **Step 1: Failing tests.** Settings: `test_defaults_match_spec` (every default value above), `test_yaml_then_set_precedence`, `test_unknown_key_raises`, `test_validate_rejects_bad_scores` (`only_max_score=0.9` with `match_min_score=0.5`). Modes: `test_shipped_map_covers_every_pipeline_mode` (every name in `src.config.MODE_TO_COLUMN` has a row), `test_rail_variants` (`Suburban Rail` and `Interurban Rail` -> `Rail`, `HighSpeed Rail` -> `Rail fast`, `Funicular` -> `FUNI`, `Cable Line` -> `None`), `test_unknown_mode_is_none`.
- [ ] **Step 2: Run** both files; expect FAIL.
- [ ] **Step 3: Implement** the modules and the CSV (columns `our_mode,agency_type,note`, table of spec 3, UTF-8). Add the README row for `agency_mode_map.csv`.
- [ ] **Step 4: Run** the two test files plus `tests/unit/test_import_side_effects.py`; expect PASS.
- [ ] **Step 5: Commit** `feat: add CompareConfig and the agency mode map`.

### Task 3: Agency reader

**Files:**
- Create: `src/compare/agency.py`, `tests/synthetic_agency.py`, `tests/unit/test_compare_agency.py`

**Interfaces:**
- Consumes: `CompareConfig`, `RunReport`.
- Produces (EPSG:2039 everywhere):
  - `@dataclass AgencyNetwork`: `routes: gpd.GeoDataFrame` (`route_key, type, line_id, name, line_name, year_operation, year_cancel, source_plan, source_name, n_stops, has_stops, geometry`), `stops: gpd.GeoDataFrame` (`stop_id, route_key, type, line_id, station_name, hub_id` (nullable Int64), `rail_hub` bool, `hub_stop_id, geometry`), `hubs: gpd.GeoDataFrame` (`agency_hub_id` int, `name, modes` (list of agency types), `n_modes, rail_hub, agency_type, route_keys` (list), `n_routes`, MultiPoint geometry), `labels: dict[str, dict[str, str]]` (`{"type": ..., "source_plan": ...}` from the metadata workbook, case-insensitive keys, `{}` when no workbook).
  - `build_route_key(type_: str, line_id: int, name: str | None) -> str` -> `"LRT:3106"`, and `"Rail:0:<name>"` when `line_id == 0`.
  - `read_agency_network(gpkg: Path, meta: Path | None, cfg: CompareConfig, report: RunReport | None = None) -> AgencyNetwork`; raises `src.pipeline.inputs.InputError` listing every missing layer/column.
  - `read_tod_hubs(path: Path) -> gpd.GeoDataFrame` (`tod_hub_id, n_modes, type_sum`, Point geometry in ITM; one row per `hub_id`).
  - `hub_type_label(modes: Sequence[str], rail_hub: bool) -> str`: `"1 mode: LRT"`, `"3 modes, rail hub: BRT+LRT+Rail"` (modes sorted, joined with `+`).
- `tests/synthetic_agency.py::make_agency_gpkg(path: Path, crs: str = "EPSG:2039") -> Path` writes layers `lines` and `stations` with the real column names for the synthetic run of `tests/synthetic.py`: one LRT route 1001 along y=665000 from x=179950 to 180100 with stops near node 1; a Metro route 2001 near node 2; two `Rail` features with `line_id = 0` (names `Rail A`, `Rail A` duplicated, and `Rail B`) near nodes 3 and 9; BRT 3001 and LRT 1002 near hub B (x=182000..182040) forming one agency hub with `hub_id` stored as float; an agency-only hub far east (x=195000) with two LRT routes; placeholder station names like `"- 7"`. Also `make_metadata_xlsx(path)` mirroring `MT_Network_MetaData.xlsx` (header row + 5 type rows + 2 plan rows).

- [ ] **Step 1: Failing tests:** `test_route_keys` (`build_route_key("Rail", 0, "Haifa Rail 22")`, duplicate-named rail features collapse to one route), `test_rail_stations_assigned_to_nearest_feature_within_tol` (a station 300 m from any rail feature is dropped and reported as a warning), `test_hub_ids_are_ints_and_hubs_have_two_stops`, `test_hub_name_ignores_placeholder_suffix` (`"אליעזר בן יהודה - 471"` -> `"אליעזר בן יהודה"`; only `"- 7"` names -> `"hub 7"`), `test_agency_type_label`, `test_other_crs_is_reprojected` (`make_agency_gpkg(crs="EPSG:4326")` gives the same coordinates in ITM within 1 m), `test_missing_layer_raises_input_error_listing_all_problems`, `test_labels_from_metadata_are_case_insensitive` (`metro` -> `Metro`), `test_read_tod_hubs`.
- [ ] **Step 2: Run** `pytest tests/unit/test_compare_agency.py -v`; expect FAIL.
- [ ] **Step 3: Implement.** Stations with `line_id != 0` take `build_route_key` directly; stations with `line_id == 0` are assigned to the nearest same-type `lines` feature within `cfg.rail_assign_tol_m` (shapely `STRtree.query_nearest`, tie -> lowest `fid`). `has_stops` False for routes without stations. Convert to EPSG:2039 when the layer CRS differs; error when it has none.
- [ ] **Step 4: Run** the test file; expect PASS.
- [ ] **Step 5: Commit** `feat: read the agency network (routes, stops, hubs)`.

### Task 4: Offset estimation

**Files:**
- Create: `src/compare/offset.py`, `tests/unit/test_compare_offset.py`

**Interfaces:**
- Produces: `estimate_shift(nodes_xy: np.ndarray, stops_xy: np.ndarray, tol_m: float, radius_m: float, passes: int, min_pairs: int = 5) -> tuple[np.ndarray, np.ndarray]` returning `(shift (n, 2), global_shift (2,))`, to be *added* to node coordinates; `apply_shift(nodes_xy, shift) -> np.ndarray`.

- [ ] **Step 1: Failing tests:** `test_recovers_constant_offset` (stops = nodes + (60, -37) with noise < 5 m: shift within 3 m of (60, -37) for every node), `test_local_offsets_vary_by_region` (two clusters 30 km apart with different offsets get different shifts), `test_fewer_pairs_than_min_returns_zero_shift`, `test_node_far_from_any_pair_gets_global_median` (radius smaller than the gap), `test_empty_inputs`, `test_passes_zero_returns_zero`.
- [ ] **Step 2: Run**; expect FAIL.
- [ ] **Step 3: Implement** as a port of `local_shift` in `/HubsScraping/tod_scraper/compare_lines.py` (read it: same two-pass median logic, same return) replacing `cKDTree` by chunked numpy pairwise distances; the sign convention is "stop minus node".
- [ ] **Step 4: Run**; expect PASS. **Step 5: Commit** `feat: estimate the node-to-agency offset`.

### Task 5: Route comparison

**Files:**
- Create: `src/compare/routes.py`, `tests/compare_helpers.py`, `tests/unit/test_compare_routes.py`

**Interfaces:**
- Consumes: `AgencyNetwork` (Task 3), `CompareConfig`, `map_mode`, `network_nodes.csv` frame (Task 1) with optional `x_corr`, `y_corr`.
- Produces:
  - `build_our_routes(network_nodes: pd.DataFrame, mode_map: Mapping[str, str | None]) -> pd.DataFrame`: one row per route (lines of one mode with equal node sets are one route): `route_key` (sorted `LINE_ID`s joined `+`), `line_ids` (list), `line_names` (list), `mode`, `agency_type` (or None), `node_ids` (list), `n_nodes`, `short_route` (n_nodes < 2), `xy` (corrected, (n, 2) array), `xy_raw`.
  - `line_route_map(routes: pd.DataFrame) -> dict[str, str]`: `LINE_ID` -> `route_key` for every line of `build_our_routes` output.
  - `order_points(xy: np.ndarray) -> list[int]` (port from `compare_lines.py`; `n <= 2` returns `list(range(n))`, `n == 0` returns `[]`).
  - `@dataclass RouteComparison`: `pairs: pd.DataFrame` (one row per candidate: `our_route_key, agency_route_key, cov_ours, cov_agency, score, same_mode, median_dist_raw_m, median_dist_corr_m, max_dist_corr_m`), `routes: pd.DataFrame` (spec 4.4 statuses; columns `status, our_route_key, our_line_ids, our_line_names, our_mode, our_n_nodes, short_route, agency_route_key, agency_type, agency_name, agency_line_name, agency_n_stops, cov_ours, cov_agency, score, candidates` (`"key (0.83); key (0.41)"`), `agency_n_our_routes, year_operation, year_cancel, source_plan, reason`; one row per our route plus one `agency_only` row per unmatched agency route).
  - `match_routes(ours: pd.DataFrame, agency: AgencyNetwork, cfg: CompareConfig, report: RunReport | None = None) -> RouteComparison`.
- `tests/compare_helpers.py`: `make_agency_network(routes: dict[str, dict]) -> AgencyNetwork` and `make_our_routes(lines: dict[str, dict]) -> pd.DataFrame` taking coordinate lists, so tests need no files.

- [ ] **Step 1: Failing tests** (all with hand-made straight-line geometries, tolerances at defaults): `test_direction_pair_collapses_to_one_route` (`LRT11`, `LRT12` same nodes -> one route `LRT11+LRT12`; different modes with equal nodes stay two), `test_matched` (our nodes on an agency LRT line and all agency stops covered: status `matched`, `cov_ours` and `cov_agency` >= 0.8), `test_full_match_wins_over_trunk_sharing` (two agency rail routes share a trunk; our route equals one: `matched`, not `split_merge`), `test_split` (our route runs over two consecutive agency routes: `split_merge`, both listed in `candidates`), `test_merge` (two of our routes cover halves of one agency route: both `split_merge`, `agency_n_our_routes == 2`), `test_partial`, `test_weak` (score 0.3), `test_mode_differs` (our BRT nodes on an agency LRT line), `test_ours_only_for_unmapped_mode` (Cable Line, reason `no agency mode`), `test_agency_only_row`, `test_rail_uses_rail_tolerance` (nodes 200 m off a rail line match, 200 m off an LRT line do not), `test_agency_route_without_stops_uses_sampled_vertices`, `test_single_node_route_is_flagged_not_fatal` (Review Focus 1, also `order_points` of 0/1/2 points), `test_no_agency_routes_gives_all_ours_only`, `test_distance_columns_raw_vs_corrected` (nodes shifted by 60 m: corrected median < raw median), `test_deterministic_ties`.
- [ ] **Step 2: Run** `pytest tests/unit/test_compare_routes.py -v`; expect FAIL.
- [ ] **Step 3: Implement.** Coverage: `cov_ours` by `shapely.distance(points, geometry) <= tol` (tol per type, `rail_tol_m` for `Rail`/`Rail fast`); `cov_agency` over the route's stops (or `shapely.segmentize(geom, 100)` vertices when `has_stops` is False) against our nodes (numpy pairwise, `stop_tol_m`); skip pairs whose expanded bounding boxes do not overlap; `score` is the harmonic mean (0 when either coverage is 0). Status logic exactly as spec 4.4 (the order of the table); agency routes follow the `agency_only` rule. Record counts per status as report metrics.
- [ ] **Step 4: Run**; expect PASS. **Step 5: Commit** `feat: route comparison with matched/partial/split/only statuses`.

### Task 6: Hub comparison

**Files:**
- Create: `src/compare/hubs.py`, `tests/unit/test_compare_hubs.py`

**Interfaces:**
- Consumes: `AgencyNetwork`, `RouteComparison`, `CompareConfig`, `hub_groups_all` frame and `network_nodes` frame (Task 1), `read_tod_hubs` output (optional), `src.spatial.merging.UnionFind`.
- Produces:
  - `build_our_hubs(groups_all: pd.DataFrame, network_nodes: pd.DataFrame, mode_map: Mapping[str, str | None], route_key_of_line: Mapping[str, str]) -> gpd.GeoDataFrame`: one row per group, adds `common_modes` (mapped agency types, unmapped dropped), `route_keys`, MultiPoint geometry of the corrected node positions (empty geometry for a group without nodes, never an exception).
  - `@dataclass HubComparison`: `hubs: pd.DataFrame` (the columns of spec 5.3, one row per pair plus `agency_only` / `ours_only` rows), `hub_routes: pd.DataFrame` (`agency_hub_id, group, side` in `shared|only_agency|only_ours`, `our_route_key, agency_route_key, route_status`).
  - `match_hubs(our_hubs: gpd.GeoDataFrame, agency: AgencyNetwork, routes: RouteComparison, cfg: CompareConfig, tod: gpd.GeoDataFrame | None = None, report: RunReport | None = None) -> HubComparison`.

- [ ] **Step 1: Failing tests** (small hand-built frames): `test_one_to_one`, `test_agency_splits` (one agency hub, two groups within 400 m), `test_ours_merges`, `test_many_to_many`, `test_pair_distance_is_nearest_point_not_centroid` (hub 700 m wide whose nearest points are 100 m apart still pairs), `test_agency_only_reports_nearest_group_and_exclusion_reason` (nearest group, `distance_m`, `eligible`, `exclusion_reason` filled), `test_ours_only_split_by_eligible` (a scored hub and a filtered group are both listed with `eligible` True/False), `test_routes_shared_only_agency_only_ours` (uses a `RouteComparison` with one matched and one unmatched route), `test_modes_difference_columns` (`modes_only_agency`, `n_modes_diff`), `test_agency_demand_column_is_empty`, `test_tod_type_sum_and_disagreement_flag` (`tod_type_sum != agency_n_modes` flagged, join beyond `tod_join_tol_m` gives NaN), `test_no_eligible_hubs_and_no_agency_hubs` (empty frames keep all columns), `test_group_without_nodes`.
- [ ] **Step 2: Run**; expect FAIL.
- [ ] **Step 3: Implement.** Pair when the minimum point-to-point distance (numpy, chunked) is `<= cfg.hub_match_tol_m`; relations from connected components over the bipartite pairs (spec 5.2 table); shared routes = pairs in `routes.pairs` with `same_mode` and `score >= cfg.match_min_score`.
- [ ] **Step 4: Run**; expect PASS. **Step 5: Commit** `feat: hub comparison against all pre-filter groups`.

### Task 7: Workbook, GeoPackage and report writers

**Files:**
- Create: `src/compare/export.py`, `tests/unit/test_compare_export.py`

**Interfaces:**
- Produces: `write_workbook(path: Path, sheets: Mapping[str, pd.DataFrame]) -> Path` (list cells joined with `; `, header frozen, autofilter, widths capped at 60, Excel-safe sheet names <= 31 chars); `build_sheets(routes: RouteComparison, hubs: HubComparison, agency: AgencyNetwork, cfg: CompareConfig, inputs: Mapping[str, dict]) -> dict[str, pd.DataFrame]` returning exactly `summary, routes, routes_only_ours, routes_only_agency, mode_summary, hubs, hubs_agency_only, hubs_ours_only, hub_routes, settings, inputs` (spec 6); `write_gpkg(path: Path, layers: Mapping[str, gpd.GeoDataFrame]) -> Path` (EPSG:2039); `build_layers(...) -> dict[str, gpd.GeoDataFrame]` with `route_pairs, our_routes, agency_hubs, our_groups, hub_ties`. `summary` states agency demand is empty and agency type is the derived mode count.

- [ ] **Step 1: Failing tests:** `test_sheet_names_and_order`, `test_mode_summary_counts` (routes per mode on each side, matched/partial/only counts add up), `test_hubs_only_sheets_are_filters_of_hubs`, `test_summary_states_derived_type_and_empty_demand`, `test_lists_are_joined_and_hebrew_survives_roundtrip` (write, reload with openpyxl, compare a Hebrew value), `test_gpkg_layers_crs_and_counts`, `test_our_routes_layer_survives_single_node_route`, `test_empty_comparison_still_writes_all_sheets`.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement**; `our_routes` geometry joins nodes in `order_points` order and is labelled `visual_aid = True`. **Step 4: Run**; expect PASS. **Step 5: Commit** `feat: write the comparison workbook and GeoPackage`.

### Task 8: HTML maps

**Files:**
- Create: `src/compare/maps.py`, `tests/unit/test_compare_maps.py`

**Interfaces:**
- Produces: `write_routes_map(path: Path, layers: Mapping[str, gpd.GeoDataFrame]) -> Path` and `write_hubs_map(path: Path, layers: Mapping[str, gpd.GeoDataFrame]) -> Path`, taking the output of `export.build_layers`. Each writes one HTML file with the data embedded as a JSON constant (WGS84), Leaflet 1.9.4 from cdnjs, layer toggles, a mode filter, a status/relation filter, a picker for one route / hub, popups with the workbook columns, and (routes page) a toggle that draws our nodes raw vs offset-corrected.

- [ ] **Step 1: Failing tests:** `test_pages_embed_json_with_expected_counts` (parse the embedded JSON; feature counts equal the layer lengths), `test_coordinates_are_wgs84` (longitudes in 34..36), `test_hebrew_not_escaped_into_garbage` (a Hebrew popup value round-trips through `json.loads`), `test_script_closing_tag_in_data_is_escaped` (a name containing `</script>` does not terminate the page), `test_empty_layers_render`.
- [ ] **Step 2: Run**; expect FAIL. **Step 3: Implement** with a string template (look at `/HubsScraping/tod_scraper/compare_hubs.py` and `make_hub_map.py` for the existing look and reuse its structure). **Step 4: Run**; expect PASS. **Step 5: Commit** `feat: Leaflet pages for the route and hub comparison`.

### Task 9: Orchestrator and `hubs compare-network`

**Files:**
- Create: `src/compare/run.py`, `tests/unit/test_compare_run.py`
- Modify: `src/cli.py` (subcommand `compare-network`, handler, module docstring), `tests/unit/test_cli.py`

**Interfaces:**
- Consumes: Tasks 1-8.
- Produces: `compare_networks(run_dir: Path, agency_gpkg: Path, cfg: CompareConfig, agency_meta: Path | None = None, tod_gpkg: Path | None = None, report: RunReport | None = None) -> NetworkComparison` (dataclass: `routes`, `hubs`, `agency`, `ours`, `report`); `write_comparison(result: NetworkComparison, out_dir: Path) -> dict[str, Path]` (writes `network_comparison.xlsx`, `.gpkg`, `network_comparison_routes.html`, `network_comparison_hubs.html`, `compare_config.json`, `compare_report.md/.json`); `compare_network_from_cli(args) -> int`. CLI: `hubs compare-network --run DIR --agency-gpkg FILE [--agency-meta FILE] [--tod-gpkg FILE] [--out DIR] [--config YAML] [--set key=value]`; `--out` defaults to `--run`. Exit code 1 with a printed message when `hub_groups_all.csv` / `network_nodes.csv` are missing (text: "re-run `hubs run` with this version") or the gpkg is invalid.

- [ ] **Step 1: Failing tests:** `test_cli_parser_has_compare_network`, `test_missing_run_files_exit_1_with_message`, `test_bad_set_value_exits`, and an end-to-end `test_compare_network_end_to_end` in `test_compare_run.py`: `make_synthetic_dirs` -> `run_pipeline` + `write_outputs` (`mc_iterations=50`) -> `make_agency_gpkg` -> `main(["compare-network", ...])` returns 0; the workbook has the Task 7 sheets; route `Red-N+Red-S` is `matched` to agency `LRT:1001`; the agency-only hub at x=195000 is in `hubs_agency_only`; the synthetic rail-only node 9 group (filtered by the pipeline) appears in `hubs_ours_only` with `eligible == False` and its `exclusion_reason`, and hub B (eligible, scored) pairs with the agency hub near x=182000 as `1:1`; rerunning twice gives byte-identical CSV/JSON outputs and identical sheet values; agency demand column empty.
- [ ] **Step 2: Run** `pytest tests/unit/test_compare_run.py tests/unit/test_cli.py -v`; expect FAIL.
- [ ] **Step 3: Implement.** Order: read run CSVs (lists split on `;`, `utf-8-sig`), `read_agency_network`, `build_our_routes` and `line_route_map`, `estimate_shift` (skipped when `apply_offset` is False; shift written to `x_corr`/`y_corr`), `match_routes`, `build_our_hubs`, `match_hubs`, `build_sheets`/`build_layers`, writers. Findings recorded on the report (`compare_report`). Add the subcommand next to `compare` in `build_parser` and `handlers`.
- [ ] **Step 4: Run** the full suite `pytest -q`; expect PASS (golden tests skip).
- [ ] **Step 5: Commit** `feat: hubs compare-network command`.

### Task 10: Documentation and a run on the real exports

**Files:**
- Create: `docs/NETWORK_COMPARISON.md`
- Modify: `CLAUDE.md` (section 9 structure, section 19 v2.2 entry, section 20 commands), `docs/DEVIATIONS.md` only if a pipeline default changed (none expected)

- [ ] **Step 1: Write `docs/NETWORK_COMPARISON.md`:** prerequisites (re-run `hubs run` with this version), the command, each sheet and map explained, the `routes.status` and `hubs.relation` vocabularies (spec 4.4, 5.2), the thresholds table, the limits of spec 11 (agency demand empty, agency type = mode count, offset assumption).
- [ ] **Step 2: Update `CLAUDE.md`** (new package in the structure tree, `hubs compare-network` in Key Commands, v2.2 entry in Version History, bump Last Updated / Document Version).
- [ ] **Step 3: Verify** `pytest -q` passes and `python -m src.cli compare-network --help` lists the options.
- [ ] **Step 4: Real data (only when the exports are available):** re-run `hubs run` on the 28-10 inputs, then `hubs compare-network` with `MT_Network.gpkg`; check that `hub_groups_all.csv` has ~1,040 rows with 142+ eligible, 426 agency hubs are read, and report the route and hub status counts to the user. Skip and say so when the exports are not in the container.
- [ ] **Step 5: Commit** `docs: network comparison guide and CLAUDE.md update`; push `git push -u origin claude/pensive-hawking-pa0tvm`.

---

## Self-review notes

- Spec coverage: 2.1 -> Task 1; 2.2/7 -> Tasks 2-9; 3 -> Task 2; 4 -> Tasks 4-5; 5 -> Task 6; 6 -> Tasks 7-8; 8 -> Tasks 3, 5, 9; 9 -> every task's tests; 10 -> Task 10; 11 -> Task 10.
- Spec 4.4 was refined while planning (full match wins; `weak` and `mode_differs` statuses; both coverages >= `multi_cov`) and the spec file was updated to match.
