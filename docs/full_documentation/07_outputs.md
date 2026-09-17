# 7. Outputs

`hubs run --output-dir OUT` writes:

| File | Content |
|------|---------|
| `hub_prioritization_results.xlsx` | The display workbook: one sheet (`hubs_final_results`), one Excel Table (`טבלה1`), values only, the 70 columns below in this order. Sorted by `Rank_TS_MC`. |
| `hub_prioritization_results.csv` | Same table, `utf-8-sig` |
| `hub_identity.csv` | `group, hub_id, n_hexes, nodes, demand_models, HubNameHE, HubType` — the stable identity of each hub and the demand model(s) its nodes were read from |
| `h3_layer.gpkg` | Shareable H3 cell layer (GeoPackage, layer `h3_cells`, EPSG:2039): every hub cell and every cell within the outer catchment ring of a scored hub, with the base attributes (area, ring, terminal, 2050 population and jobs), the hub identity, network, demand model and scores, and the nearest hub. `h3_layer_format` (gpkg / geojson / parquet / csv / none) and `h3_layer_extent` (hubs / influence / all); see `docs/H3_BASE_LAYER.md`. |
| `run_report.md`, `run_report.json` | Inputs and encodings, metrics (nodes, hexagons, groups, matched demand nodes, hub type counts…), and every finding: lines without a mode, duplicated keys, nodes without demand, manual rows applied or unmatched, unnamed lines, status conflicts, hubs without a name, top 10 hubs |
| `run_config.json` | The effective configuration |
| `run.log` | Log of the run |
| `intermediate/` (with `keep_intermediates=true`) | `hexes.geojson`, `groups.geojson`, `scored.csv` for auditing |

Sheet and table names, the file stem and extra columns (e.g. `hub_id`, `eligible`) are
configurable (`output_sheet_name`, `output_table_name`, `output_basename`, `extra_columns`).

## 7.1 Columns of `hub_prioritization_results.xlsx`

Defined once in `src/pipeline/export.py::FINAL_COLUMNS`; the writer refuses to emit a table
whose columns differ.

| # | Column | Meaning |
|---|--------|---------|
| 1 | `group` | Hub ID (sequential after manual merges; reproducible for unchanged inputs) |
| 2–3 | `x`, `y` | Longitude, latitude of the hub centroid (WGS84) |
| 4 | `h3_index` | List of the hub's resolution-10 H3 cells |
| 5 | `node` | List of model node IDs |
| 6–7 | `Mode_Planned`, `Modes_ForPlot` | Planned modes (list) and their Hebrew comma-joined form |
| 8–9 | `Line_Unique`, `Line_Names` | Line IDs (list) and their Hebrew names (list) |
| 10 | `address` | `Not geocoded` (geocoding is off) |
| 11–14 | `area`, `Metro`, `location`, `LocationForChart` | Metropolitan area / district, its copy, ring list, ring in Hebrew (גלעין / טבעת / חוץ) |
| 15–17 | `TotalDemand`, `TotalTransfers`, `TransferRate` | 2050 daily passengers, transfers, transfers ÷ demand |
| 18–25 | `BRT Lines` … `Suburban Rail Lines` | Lines per mode |
| 26–33 | `pop_0_500` … `emp_1000_1500`, `TotalPop_2050`, `TotalEmp_2050` | Population / jobs per ring and totals |
| 34–39 | `Region_category`, `Location_category`, `RegionLocation`, `Num_Modes`, `score`, `bus_terminal` | Raw criterion inputs |
| 40–43 | `HubType`, `HubType_Filtered`, `HubTypeHE`, `BusTERMINAL_Clone` | Tier, TLV low-transfer flag, tier (Hebrew), copy of `bus_terminal` |
| 44–48 | `RegionLocation_Norm`, `score_Norm`, `bus_terminal_Norm`, `TotalDemand_Norm`, `PopEmp_Score_Norm` | The five 1–10 criteria (per tier) |
| 49–51 | `TotalScore_MC`, `Rank_TS_MC`, `Rank_By_TS_MC_By_Metro` | Monte Carlo score, overall rank, rank within tier |
| 52 | `TotalNumLines` | Sum of the per-mode line columns |
| 53–61 | `NumLinesStatus_0` … `NumLinesStatus_7`, `TotalLinesAllStatuses` | Lines per planning-status code |
| 62–67 | `Line_Nunique`, `Average_Simulated_Score`, `Overall_Rank`, `Rank_within_HubType`, `LogDemand`, `PopEmp_Score` | Notebook-era columns kept for compatibility (`Average_Simulated_Score` = `TotalScore_MC`) |
| 68 | `HubNameHE` | Hebrew display name (from `hub_names.csv`, keyed by H3 index) |
| 69 | `Line_Names_forPlot` | `Line_Names` comma-joined (formerly an Excel formula) |
| 70 | `RankByHubTypeMetro` | National hubs ranked nationwide, others within (tier, metro); competition rank (formerly an Excel formula) |

List-valued columns are written as their Python representation (`[400080, 513001]`,
`['Metro', 'LRT']`) to match the previous workbook.

## 7.2 Optional analyses

- **AHP** (`src/scoring/ahp.py`, `AHP_QUICKSTART.md`): expert-weighted score and rank; run
  separately on the scored table.
- **Monte Carlo distribution** (`src/scoring/mc_distribution.py`): per-hub score
  distributions, top-K probabilities and plots for sensitivity analysis.
