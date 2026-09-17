# Known quirks kept behind flags, and intentional differences from the notebooks

The `hubs run` pipeline reproduces the June 2026 results of `COMPLETE_TRANSIT_PIPELINE.ipynb`
and `create_results_csv.ipynb` (see `tests/golden/`). Where the notebooks did something
questionable, the pipeline keeps the notebook behaviour **by default** so results stay
comparable, and exposes a configuration flag to switch to the documented method. This
page lists every such place, plus the few spots where the pipeline deliberately differs.

## Flags (see `hubs show-config --defaults`)

| Flag | Default (= notebook) | Alternative | What changes |
|---|---|---|---|
| `per_mode_lines_method` | `even` — `Line_Nunique` split evenly across the modes present | `exact` — true count of lines per mode | `<Mode> Lines` columns, `score`, `Num_Modes` unchanged |
| `influence_rings` | `500,1000,1500` (matches the `pop_0_500…` column names and CLAUDE.md) | any increasing radii, e.g. `600,1000,1200` | The old `influence_area_processor` ignored its configuration and always buffered 600/1000/1200 m, so the June 2026 `pop_*`/`emp_*` values were computed on those radii despite their names. `600,1000,1200` reproduces them exactly (verified: zero difference on all 142 hubs). |
| `pop_emp_decay_midpoints` | empty = midpoints of `influence_rings` (250/750/1250 for the defaults) | e.g. `250,750,1250` | The notebook applied the distance decay at 250/750/1250 m regardless of the actual buffers. **Legacy reproduction recipe:** `--set influence_rings=600,1000,1200 --set pop_emp_decay_midpoints=250,750,1250` reproduces the June 2026 `TotalScore_MC` for 141 of 142 hubs to 1e-12 (the exception is Netanya, below). With the defaults the geometry is consistent and the scores differ slightly. |
| `apply_eligibility_filter` | `true` — keep groups with ≥ 1,000 passengers, ≥ 2 modes and a non-rail mode | `false` — score every group | Row count of the workbook (142 with the June 2026 inputs) |
| `require_non_rail_mode` | `true` | `false` | Rail-only hubs (suburban + interurban only) become eligible |
| `mc_scope` | `per_hubtype` — one seeded random stream consumed tier by tier | `all_hubs` — one weight matrix for the whole table | CLAUDE.md describes `all_hubs`; the notebook implemented `per_hubtype`. Scores differ slightly. |
| `renormalize_globally` | `false` — `*_Norm` columns are the per-tier values the Monte Carlo score was built from | `true` — recompute them globally as `create_results_csv.ipynb` did | Only the five `*_Norm` display columns; `TotalScore_MC` is unaffected. The `true` setting reproduces the June 2026 workbook's `*_Norm` columns, which were inconsistent with its scores. |
| `drop_line_rules` | Haifa lines starting with `m` (old Metronit), Netanya `LRT151`/`LRT152` | any list of `area:regex` | Which lines are excluded before hexagon aggregation |
| `spatial_source` | `shapefiles` — metro/district, terminals and TAZ overlaid at run time | `h3_base` — everything looked up in `data/reference/h3_base.parquet` (`hubs prepare-base`) | Prototype. Terminals and tiers identical; pop/emp within ~1 % (with `influence_cell_rule=fraction`); ring tags of hexagons straddling a ring boundary follow the cell centre instead of shapefile order (4 of the 142 June 2026 hubs, see `H3_BASE_LAYER.md`). |
| `influence_cell_rule` | `fraction` — a cell counts by the share of its polygon inside the ring | `center` — a cell counts wholly in the ring its centre falls in (faster, coarser) | `h3_base` only; see `H3_BASE_LAYER.md` for the measured difference. |

## Notebook behaviours reproduced on purpose

- **Per-node line counting.** A line serving two nodes inside one hexagon counts twice in
  `Line_Nunique` (`network.aggregate_to_hexes`).
- **Hexagon order fixes group numbering.** Hexagons are processed in H3-index order, so the
  `group` IDs and the `area`/`location` a group inherits from its first hexagon match the notebook.
- **Group renumbering after manual merges** (`grouping.apply_manual_groups`): IDs are
  renumbered sequentially only when an `is_same_group.csv` is present, as in the notebook.
- **Generic `Rail` dropped** from `Mode_Planned` before classification (`scoring.correct_mode_planned`).
- **Weight cap before normalisation.** Random weights are redrawn while any raw value
  exceeds 0.5 and *then* normalised, so a normalised weight can exceed 0.5.
- **`TotalDemand_Norm` range over non-zero values**, applied to all values (a zero-demand hub in a
  tier can receive a value below 1).
- **`PopEmp_Score` mix**: only `עירוני` hubs weight population 80 %; `ארצי`, `מטרופוליני`,
  `Train Station` and `Not Hub` weight jobs 80 %.
- **`HubType_Filtered`** tests `Metro` for the substrings `tlv` / `מרכז` / `center`; with the
  Hebrew area names it is always 0, exactly as in the golden workbook.
- **`Modes_ForPlot` order** follows first appearance of the mode across the group's hexagons.
  The notebook used Python `set` order, which is not reproducible run to run.

## Intentional differences (fixes)

| Where | Notebook | Pipeline |
|---|---|---|
| Hebrew in `metro_2008.shp` | Truncated by a GDAL decode quirk (`חיפ`, `גלעי`) and patched with a lookup table | Read correctly (`inputs.read_shapefile`); the patch table is kept only for exotic inputs |
| Duplicated `Line_ModelName` rows | Silently duplicated node rows in a many-to-many merge | First row kept, duplicates reported |
| Lines without a mode row | Silently dropped by `groupby` | Dropped and listed in the run report |
| Overlay demand models (Hadera, Haifa Metronit) | Added on top of the base model in older runs | Override the base model (as the repository's `hub_demand_processor` fix intended) |
| Hardcoded demand overrides (4 National-Model nodes, Shefaim) | Python literals in cells 45/47 | Rows in `data/reference/manual_demand_updates.csv`; the Netanya update the notebook listed for CSV entry is included |
| Line IDs with apostrophes (`4.4_Bee'rSheva…`) | Quotes stripped before the status lookup, so those lines got no status | Looked up correctly |
| Two lines sharing a display name | Kept | Kept (the parser no longer de-duplicates *names*) |
| `Cable Line` in `Modes_ForPlot` | Untranslated (map key was `Cable`) | `רכבל` |
| `Line_Names_forPlot`, `RankByHubTypeMetro` | Excel formulas typed by hand | Computed columns (`postprocess.line_names_for_plot`, `rank_by_hubtype_metro`) |
| Multiple bus terminals within 200 m | Duplicate hub rows from the spatial join; whichever row survived downstream set the score (Netanya, group 25, kept חניון לילה = 1 although a מסוף בינוני = 2 is also within 200 m) | Highest-scoring terminal kept, tie reported |
| Missing inputs | Placeholder values (demand 5000, pop 1000 …) and a green "PIPELINE COMPLETE" | Hard failure listing every problem (`hubs validate`) |
| Hub names | Keyed by `group`, which changes between runs | Keyed by `h3_index` |

## Known inconsistencies in the June 2026 workbook itself

- Group 25 (Netanya) carries a `TotalScore_MC` / `Rank_TS_MC` that do not match its own
  `Average_Simulated_Score` / `Overall_Rank` (hand-edited after the run), and its
  `bus_terminal` is 1 although a class-2 terminal is also within 200 m (duplicate-row join).
  It is the single hub whose score the pipeline does not reproduce under the legacy settings.
- `Overall_Rank` reaches 147 on a 142-row table: the ranks were computed before some rows
  were removed.
- `Line_Names` contains `\'` escape artifacts from CSV round-trips (rendered as `\` in
  `Line_Names_forPlot`).
