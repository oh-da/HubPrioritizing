<!-- Written 2026-09-16 from the project review session. Source inputs reviewed: All_nodeslines_18062026.csv, Lines_and_Planned_Mode_18-06-2026.csv, Nodes_w_results_04022026.xlsx, Routes_and_Nodes_07-04-2025.xlsx, linesNames_noDuplicates.csv, lines_exploded.csv, BS_lines.csv, and the target hub_prioritization_results.xlsx. -->

# HubPrioritizing: review and "one stop shop" pipeline plan

> **Status (2026-09-16): implemented.** PRs 1–9 landed on `claude/lucid-lovelace-riqjaa`;
> `hubs run` reproduces the June 2026 results workbook (see `tests/golden/`): every reference
> layer is in `data/reference/` (TAZ 2050 arrived 2026-09-17) and, with the legacy ring
> settings, the final scores match for 141/142 hubs. Still open: the optional stage 0 that would
> build `All_nodeslines` from `Routes_and_Nodes` + node coordinates.
> The pre-cleanup repository is on the branch `legacy/v1-notebooks`. `docs/DEVIATIONS.md` records the
> behaviour flags and fixes that came out of the golden comparisons.

## Context

The user (transport modeler) reruns the hub prioritization whenever new model exports arrive. Today that means
uploading ~6 files into Colab, editing hardcoded `/content/drive/...` paths in two notebooks
(`COMPLETE_TRANSIT_PIPELINE.ipynb`, `create_results_csv.ipynb`), running them cell by cell, then finishing in
Excel by hand (two formula columns, an Excel Table, a rename) to produce `hub_prioritization_results.xlsx`,
the workbook the display page reads.

Goal: **one command, one input directory, one output workbook.**
`hubs run --input-dir <dir> --output-dir <dir>` produces `hub_prioritization_results.xlsx` with exactly the
70 columns the page expects, plus a run report. No notebooks, no Colab, no Excel formulas.

Decisions already taken by the user:
- Source of truth = the **notebook logic** and its column names. The `scripts/run_complete_pipeline.py` + `src/scoring/*` track (`final_score/rank/tier`) is replaced, not fixed.
- Shapefiles and curated tables are **stable reference data shipped in the repo** (`data/reference/`), not per-run inputs.
- `All_nodeslines_*.csv` is built **by hand in GIS** from `Routes_and_Nodes_*.xlsx` + model node coordinates. The pipeline accepts `All_nodeslines` directly (required); building it automatically is an optional later stage.

---

## Part A: Review findings (current state)

### A1. Three parallel, incompatible implementations
| Track | Entry | State |
|---|---|---|
| Notebook (canonical) | `notebooks/COMPLETE_TRANSIT_PIPELINE.ipynb` (92 cells) + `notebooks/create_results_csv.ipynb` | Produces the real results. Colab-only paths, `drive.mount()`, manual steps. |
| Script | `scripts/run_complete_pipeline.py` (1,274 lines) | `input()` prompt at import (`:75`), `os.chdir` at import, no CLI. **Crashes at step 10**: `hierarchy.assign_hub_tiers` writes `HubType` but everything downstream wants `tier`; `activity.py:61` passes a non-existent `_dummy_tier` → `KeyError`. `assign_hub_tiers` also looks for `Total_Unique_Lines`, which no `.py` produces → every hub silently becomes Local. |
| Legacy script | `scripts/run_pipeline.py` | 7 steps, no demand/demographics; advertises a `--config` flag that does not exist. README still points here. |

### A2. Manual labor the pipeline must absorb (found in code, confirmed by the uploads)
1. Edit 8 path constants in notebook cell 9 and 6 more in `create_results_csv.ipynb` cell 6 (+ cells 36, 41).
2. `IsSameGroup.csv` merges, then **groups are renumbered sequentially** (cell 21) → `group` IDs are unstable, so `HubsNames_*.csv` (keyed by `group`) drifts between runs.
3. Demand overrides hardcoded in code: 4 national-model nodes (cell 45) + Shefaim node 511248 (cell 47).
4. `lines_exploded.csv` is exploded by hand from a per-hub status table; the same line carries different `StatusID` in different rows; the notebook's `dict(zip)` silently keeps the last.
5. `linesNames_noDuplicates.csv` has no header and a stray header row mid-file; 34 lines in the current network have no Hebrew name (all `m0xxx` Metronit, `M1-*` metro, `LRT9/10/151/152`, `R326-*`, `brt02x`, `s01x0a`, `4.5_*`).
6. Two Excel formulas typed by hand into the final workbook: `Line_Names_forPlot` (strip brackets, substitute 4 metro IDs) and `RankByHubTypeMetro` (national ranked globally, others within HubType × Metro, COUNTIFS "min" rank). The notebook's `Rank_By_TS_MC_By_Metro` is actually rank within HubType only and differs from the formula in 98 of 142 rows.
7. Convert CSV → xlsx, insert an Excel Table (`טבלה1`), rename to `hub_prioritization_results.xlsx`.
8. `create_results_csv.ipynb` cell 41 has a live bug (`KeyError: 'HubName'` when the names file exists); cells 42/47/50/51 are interactive debris.
9. `create_results_csv.ipynb` cell 30 **re-normalises** `RegionLocation/score/bus_terminal/PopEmp` globally, overwriting the per-HubType values the Monte Carlo score was built from → `*_Norm` columns in the final file are inconsistent with `TotalScore_MC`.
10. `src/data/influence_area_processor.py:347-349` hardcodes 600/1000/1200 m buffers and ignores the `buffer_zones` the notebook sets (500/1000/1500). The golden `pop_0_500` … columns were therefore computed on 600/1000/1200 m rings despite their names.

### A3. Input data facts (uploaded samples)
| File | Encoding | Notes |
|---|---|---|
| `All_nodeslines_18062026.csv` | cp1255 | `עמודה1,node,LINE_ID,X,Y,geometry`, EPSG:2039; 5,013 rows, 1,593 nodes, 220 lines |
| `Lines_and_Planned_Mode_18-06-2026.csv` | cp1255 | `Line_ModelName,Mode_Planned,Line_Name,Line_Description,Area`; **4 duplicated keys** (`m0610a,m0620a,m0810a,m0820a`) → many-to-many merge double-counts; 4 lines have no mode row (`BluRT1,BluRT2,LRT9,LRT10`) |
| `Nodes_w_results_04022026.xlsx` | – | demand sheets `5040_Daily, Daily_5087, Daily_BS, Daily_Hadera, Daily_Jerusalem, HaifaNewMetronit, Daily_5093, National(empty)`; other sheets ignored |
| `Routes_and_Nodes_07-04-2025.xlsx` | – | not consumed by any code; older than All_nodeslines, disagrees on ~60 lines |
| `linesNames_noDuplicates.csv` | cp1255 | headerless; LineID → "Hebrew name (mode)" |
| `lines_exploded.csv` | utf-8 | `,LineName,StatusID`; leading spaces; conflicting statuses per line |
| `BS_lines.csv` | utf-8-sig | `ID,LineName,LineName_Correct`; stray backslashes/spaces |
| `hub_prioritization_results_2.xlsx` (**target**) | – | 1 sheet as Excel Table `טבלה1` (`A1:BR143`), 142 rows (incl. 27 `Not Hub`), 70 columns, 2 formula columns; HubType counts מטרופוליני 67 / עירוני 33 / Not Hub 27 / ארצי 15 |

### A4. Code-quality findings in `src/` (feeds the cleanup list)
- `requirements.txt` pins `h3>=3.7.0` but the code uses the h3 **v4** API → must be `h3>=4,<5`. Nothing pinned; dev/app deps mixed into runtime.
- No `pyproject.toml`; every entry point does `sys.path.insert`. `src/config.py` creates directories at import; `src/utils/logging.py` opens a log file by default.
- Dead: `src/data/validators.py`, `src/visualization/charts.py`, `DemandDataProcessor` (imported, never used, wrong sheet names), `encoding_fix.read_shapefile_with_encoding` (best encoding ladder in the repo, used only by its test).
- `src/classification/hierarchy.py:84` lacks the `total_demand >= 5000` condition the notebook (cell 82) applies to the metro tier.
- Tests: one file, covering the one module production never calls (~2% coverage).
- Failure masking: missing demand → placeholder 5000; missing TAZ → placeholder pop/emp; broad `except: warn-and-continue` → "PIPELINE COMPLETE" on synthetic data.
- Docs drift: `docs/07_outputs.md` describes the script schema under the notebook filename; `CLAUDE.md` says MC "runs on all hubs together" and Location/Terminal are "global" normalisation, but the notebook loops per HubType and normalises all five per HubType; `CLAUDE.md` §20 says H3 res 9 / 300 m / rings 0-400-800-1500, code uses res 10 / 120 m / 500-1000-1500.

---

## Part B: Target design

### B1. Command and input contract
```
hubs run      --input-dir DIR [--output-dir OUT] [--reference-dir data/reference] [--config pipeline.yaml] [--set key=value ...]
hubs validate --input-dir DIR          # discovery + validation only, no processing
```
Discovery picks the **newest file per pattern** by the date in its name (`(\d{2})-?(\d{2})-?(\d{4})`), tie-break by mtime, logging what was chosen and ignored.

| Key | Pattern in `--input-dir` | Required | Notes |
|---|---|---|---|
| `nodeslines` | `All_nodeslines*.csv` | yes | cp1255/utf-8 auto; `node,LINE_ID,(X,Y|geometry)` |
| `lines_mode` | `Lines_and_Planned_Mode*.csv` | yes | dedupe `Line_ModelName` with warning |
| `demand` | `Nodes_w_results*.xlsx` | yes | sheet → region via `SHEET_NAME_MAPPING`; unknown sheets logged |
| `line_names` | `linesNames*.csv` | optional (warn) | headerless; stray header row dropped |
| `line_status` | `line_status*.csv` (clean `LineName,StatusID`) else `lines_exploded*.csv` (legacy) | optional (warn) | strip names; warn on conflicts, last wins |
| `line_corrections` | `BS_lines*.csv` | optional | strip `\` and spaces |
| `routes` + `node_coords` | `Routes_and_Nodes*.xlsx` + `Nodes_coords*.(csv|shp)` | optional, later | stage 0 auto-build of nodeslines (only when both present) |

Reference set in `data/reference/` (committed; Git LFS if shapefiles exceed ~50 MB): `metro_2008.shp`, `Districts.shp`, `BUS_TERMINAL_STRAT.shp`, `TAZ_1270.shp`, `hub_names.csv`, `is_same_group.csv`, `manual_demand_updates.csv` (the 5 formerly hardcoded overrides become rows with a `notes` column). A same-named file in `--input-dir` overrides the reference copy.

`validate_inputs` raises one `InputError` listing **all** problems (missing files, missing columns, missing reference files). Real runs fail loudly; there is no placeholder data. Encoding: try `utf-8-sig` then `cp1255`, validate Hebrew columns with `src/utils/encoding_fix.py::is_valid_hebrew_text`, record the chosen encoding in the report. Shapefiles go through `read_shapefile_with_encoding` (prints → logger).

Config precedence: defaults < `pipeline.yaml` < `--set`. Effective config written to `OUT/run_config.json`.

### B2. Package layout (`src/pipeline/`, pure DataFrame-in/DataFrame-out stages)
| Module | Public functions | Ports |
|---|---|---|
| `settings.py` | `PipelineConfig` (frozen dataclass), `load_config(yaml, overrides)` | nb cell 9 |
| `inputs.py` | `InputSet`, `discover_inputs()`, `validate_inputs()`, `read_csv_auto()`, `read_shapefile()` | cells 9, 13 |
| `report.py` | `RunReport.warn(section, msg, **data)`; sections listed in B4 | new |
| `network.py` | `load_nodeslines(df) -> gdf`, `attach_modes(gdf, lines_mode, report)`, `aggregate_to_hexes(gdf, resolution=10)`, `add_mode_line_columns(hexes, method='even'|'exact')`, later `build_nodeslines_from_routes(...)` | 13, 15, 25 |
| `grouping.py` | `group_hexes(hexes, threshold_m=120, tolerance_m=0.1)` (wraps `src/spatial/merging.py::create_proximity_groups`), `apply_manual_groups(hexes, is_same_group, report)` (union + sequential renumber, as cell 21), `assign_hub_ids(hexes)` | 17-21 |
| `spatial_tags.py` | `tag_area_and_location(hexes, metro, districts, report)` (+ `fix_truncated_hebrew` moved here), `get_regions_for_area(area)` | 30, 34 |
| `demand.py` | `SHEET_NAME_MAPPING`, `SHEET_COLUMN_CONFIG` (verbatim), `load_demand_workbook(sheets, report)`, `assign_demand(hexes, by_region, overlays=('Hadera','Haifa Metronit'), report)` (overlay overrides), `apply_manual_demand(hexes, updates, report)` | 36-47 |
| `aggregate.py` | `aggregate_to_groups(hexes)` (cell 49 semantics: flatten lists, sum demand and mode-line cols, dissolve, `Num_Modes`), `tag_bus_terminals(groups, terminals, buffer_m=200)`, `add_influence_area(groups, taz, rings=(500,1000,1500))` (reuses `InfluenceAreaProcessor.calculate_zone_statistics` after fixing the hardcoded radii; renames `pop_zone1→pop_0_500` …) | 49, 53, 58-70 |
| `scoring.py` | `prepare_scoring_frame(groups)` (`correct_mode_planned`, `Total_Unique_Lines`, `Region_category`, `Location_category`, `RegionLocation`), `add_mode_score(df, MODE_WEIGHTS, alpha=0.1)`, `classify(df, require_non_rail=True)` → `HubType`, `eligible`, `filter_eligible(df, enabled)`, `normalize_scores(df, decay_beta=1.5)` (cell 86 semantics), `draw_weights(rng, n_iter, n=5, max_w=0.5)`, `monte_carlo_by_type(df, n_iter=10000, seed=42)` → `Average_Simulated_Score`, `Rank_within_HubType`, `Overall_Rank` | 78-88 |
| `postprocess.py` | `finalize_columns(df, line_names, line_status, corrections, hub_names, renormalize_globally=False)` → all 70 columns incl. `Line_Names_forPlot` and `RankByHubTypeMetro` (`rank(method='min')` = COUNTIFS); helpers `load_line_names`, `load_line_status`, `parse_line_unique_full`, `rank_by_hubtype_metro`, `line_names_for_plot` | `create_results_csv.ipynb` cells 6-44 + 2 Excel formulas |
| `export.py` | `FINAL_COLUMNS` (70 names, ordered), `write_results_xlsx(df, path, sheet_name, table_name='טבלה1')` (openpyxl `Table`, values only, asserts column order), `write_results_csv`, `write_run_report` | cell 90 + results cell 49 |
| `run.py` | `run_pipeline(cfg, inputs) -> RunResult(results, groups, report)`; optional `intermediate/` dumps | glue |
| `src/cli.py` | `main(argv)`: `run`, `validate`, `show-config` | new |

Monte Carlo fidelity: cell 88 iterates `HubType.unique()` (first-appearance order) with one `np.random.seed(42)` stream. Port: sort by `group`, use `np.random.RandomState(42)`, per type draw the 10,000×5 weight matrix with the same rejection loop, then `X @ W.T / n` (vectorised, bit-compatible to ~1e-12).

Existing code: **reuse** `src/spatial/h3_operations.py`, `src/spatial/merging.py`, `src/utils/encoding_fix.py`, `src/config.py` constants. **Modify** `src/config.py` (remove import-time mkdir; add `MODE_LINE_COLS`, `MODE_TO_COLUMN`, `MODE_HEBREW_MAP` (+`'Cable Line'` key), `LOCATION_HEBREW_MAP`, `HUBTYPE_HEBREW_MAP`, `BUS_TERMINAL_SCORES`), `src/utils/logging.py` (file handler opt-in), `src/classification/hierarchy.py` (add metro `>= 5000`), `src/data/influence_area_processor.py` (honour ring radii, prints → logger). **Keep as optional extras**: `src/scoring/ahp.py`, `src/scoring/mc_distribution.py` (move `generate_random_weights` into it before `monte_carlo.py` is deleted), `app/ahp_questionnaire.py`. **Delete** in the final PR: `src/scoring/{activity,service,location,demographics,terminals,monte_carlo}.py`, `src/classification/eligibility.py`, `src/data/{loaders,validators,hub_demand_processor}.py`, `src/visualization/charts.py`, `scripts/run_pipeline.py`, `scripts/run_complete_pipeline.py`, `scripts/install_dependencies.py`.

### B3. Stable hub identity
Keep `group` as-is for the page. Add `hub_id = "H" + sha1(sorted node ids)[:10]` (stable while membership is unchanged) written to `OUT/hub_identity.csv` (`group,hub_id,nodes,HubNameHE`). Key reference tables by stable spatial IDs, never by `group`: `is_same_group.csv` and `manual_demand_updates.csv` are keyed by **node ID**; the user's hub-names table (`Hubs_Names_H3_exploded_V1.01.csv`, delivered 2026-09-16) is already keyed by **H3 index** (`name_id,h3_index,HubNameHE`, 264 hexes → 135 names), so it is adopted as-is under `data/reference/hub_names.csv` and no migration script is needed. Lookup: a group takes the name of the first row whose `h3_index` is in the group's hex list; a group matching two different names, or a name matching two groups, goes to the report as a warning.

**Encoding finding (PR 1):** the "truncated Hebrew" in `metro_2008.shp` (`חיפ`, `גלעי`, ...) that the notebook patches with `fix_truncated_hebrew` is a GDAL/pyogrio decode quirk: the DBF bytes are complete. Reading with `encoding='latin1'` and re-decoding each string with `.encode('latin1').decode('cp1255')` yields the full names. The `inputs.read_shapefile` helper (PR 2) does this, and `fix_truncated_hebrew` becomes unnecessary.

### B4. Outputs
`OUT/hub_prioritization_results.xlsx` (single sheet, Excel Table over `A1:BR{n+1}`, 70 `FINAL_COLUMNS` in order, no formulas, sorted by `group`), `hub_prioritization_results.csv` (utf-8-sig), `hub_identity.csv`, `run_report.md` + `.json`, `run_config.json`, `run.log`, optional `intermediate/`.
Report sections: inputs + detected encodings; lines dropped by pattern; lines without a mode row; duplicate `Line_ModelName` rows; nodes without demand per region; manual demand rows applied/unmatched; manual group merges applied/skipped; lines without Hebrew name; status conflicts; groups without `HubNameHE`; HubType counts; top 10 by `TotalScore_MC`.

### B5. Deliberate behaviour flags (documented in `docs/DEVIATIONS.md`)
| Flag | Default | Why |
|---|---|---|
| `per_mode_lines_method` | `even` (notebook workaround) | `exact` computes true per-mode counts; changes `score` |
| `influence_rings` | `(500,1000,1500)` | matches column names and CLAUDE.md; golden was computed on 600/1000/1200 by accident. **User may set `(600,1000,1200)` to reproduce the golden exactly.** |
| `apply_eligibility_filter` | decided by the golden row count in PR 6 | 27 `Not Hub` rows are consistent with either setting |
| `require_non_rail_mode` | `True` | from `src/config.py` |
| `renormalize_globally` | `False` | the notebook's cell-30 re-normalisation is a bug; `True` reproduces the golden `*_Norm` columns |
| `mc_scope` | `per_hubtype` | reproduces the notebook; `all_hubs` is what CLAUDE.md describes |
| `rank_by_hubtype_metro` | always computed | replaces the hand-typed Excel formula |

---

## Part C: PR sequence (all on branch `claude/lucid-lovelace-riqjaa`, merged in order)

| # | Title | Size | Contents | Verified by |
|---|---|---|---|---|
| 1 | Packaging and side-effect hygiene | S | `pyproject.toml` (console script `hubs`, pytest config, extras `ahp`,`viz`,`dev`), pinned `requirements.txt` (`h3>=4,<5`, `geopandas>=0.14`, `shapely>=2`, `pandas>=2`, `openpyxl`, `pyyaml`, `pyogrio`, `rtree`), remove mkdir from `src/config.py`, opt-in file logging, `tests/conftest.py` synthetic fixtures, fix `hierarchy.py` metro threshold, fix influence ring radii | fresh venv `pip install -e .[dev]`; `pytest` green; `python -c "import src.config"` creates no dirs |
| 2 | Input contract | M | `settings.py`, `inputs.py`, `report.py`, `cli.py validate` | latest-by-date discovery test; `hubs validate` on the uploaded samples lists exactly the missing reference files |
| 3 | Network + grouping | M-L | `network.py`, `grouping.py`, `is_same_group.csv` template, hub identity | unit tests; informational group-set comparison vs golden `node` column; report lists BluRT1/2, LRT9/10, 4 duplicate mode rows |
| 4 | Spatial tags + demand | L | `spatial_tags.py`, `demand.py`, `manual_demand_updates.csv` with the 5 ex-hardcoded rows | synthetic polygon/workbook tests; every real demand sheet maps to a region |
| 5 | Aggregation, terminals, influence | M | `aggregate.py`; delete `hub_demand_processor.py` | synthetic e2e through stage 6; ring radii test |
| 6 | Scoring | M | `scoring.py`; delete old criterion modules | **golden scoring test**: from golden raw columns, `HubType` equal, `Average_Simulated_Score` within 1e-6, ranks equal; fixes `apply_eligibility_filter` default |
| 7 | Post-processing + export | M | `postprocess.py`, `export.py`, `migrate_hub_names.py` | **golden postprocess test**: both formula columns, `TransferRate`, `Modes_ForPlot`, `NumLinesStatus_*` etc. equal; xlsx opens as a 70-column Table |
| 8 | Orchestrator + CLI | M | `run.py`, `cli.py run`, report writer, smoke tests | `hubs run` on synthetic fixtures; rerun byte-identical CSV; real-sample run with a test-only `HUBS_ALLOW_SKIP_STAGES=1` escape for the absent shapefiles |
| 9 | Cleanup + docs | M | archive notebooks to `notebooks/archive/` (outputs stripped), delete scripts/dead modules, update `README.md`, `CLAUDE.md` (§6/§7/§9/§15/§20), `docs/full_documentation/*`, `INSTALL.md`, add `docs/DEVIATIONS.md`, merge `data/README_*.md` into `06_manual_corrections.md` | `pytest` green; `grep -r "run_complete_pipeline\|scored_hubs_final" README.md CLAUDE.md docs` empty |

Test layout: `tests/unit/` (synthetic, always), `tests/golden/` (uses the uploaded samples + target workbook under `tests/fixtures/real/`, skipped if absent), `tests/test_smoke.py`.

## Part D: What the user must still provide
1. ~~All four shapefiles~~ (received 2026-09-16/17, in `data/reference/`). The population/jobs columns match the golden exactly with 600/1000/1200 m rings, and the final scores match for 141/142 hubs under the legacy settings documented in `DEVIATIONS.md`.
2. ~~Hub names and IsSameGroup~~ (received 2026-09-16 as `Hubs_Names_H3_exploded_V1.01.csv` and `IsSameGroup_V1.01.csv`).
3. Ring radii: the default stays 500/1000/1500 m (B5); the legacy geometry is one `--set` away. Later, a node-coordinates layer if stage 0 (auto-build of `All_nodeslines`) is wanted.

## Part E: Verification (end-to-end)
1. `pip install -e .[dev] && pytest` green after every PR.
2. `hubs validate --input-dir <uploads>` prints the exact missing-file list and exits non-zero.
3. `hubs run --input-dir tests/fixtures/real --output-dir /tmp/out` (with reference shapefiles in place) writes `hub_prioritization_results.xlsx`; a Python check reads it back with openpyxl: 70 columns in `FINAL_COLUMNS` order, one Table, 142 rows, `RankByHubTypeMetro` and `Line_Names_forPlot` equal to the golden workbook, `TotalScore_MC` within 1e-6.
4. Run twice → CSV byte-identical (determinism, seed 42).
5. Plan copy committed to the repo as `docs/PIPELINE_REFACTOR_PLAN.md` in PR 1.
