# 3. Pipeline Overview

One command runs everything:

```bash
hubs run --input-dir DIR --output-dir OUT [--reference-dir data/reference] [--config pipeline.yaml] [--set key=value]
```

The orchestrator (`src/pipeline/run.py::run_pipeline`) chains pure functions that take a
DataFrame and return a DataFrame; no stage reads or writes files itself. The step numbers
below match the archived notebook (`notebooks/archive/COMPLETE_TRANSIT_PIPELINE.ipynb`)
so older documents remain readable.

```
ONCE     hubs prepare-base:  metro_2008 · Districts · BUS_TERMINAL_STRAT · TAZ_1270
         -> data/reference/h3_base.parquet  (area, ring, terminal, pop/emp per H3 cell)

INPUTS   All_nodeslines · Lines_and_Planned_Mode · Nodes_w_results (demand)
         h3_base.parquet · curated tables
                                   │  inputs.discover_inputs / validate_inputs
   ┌─ PART 1  network.py, grouping.py ────────────────────────────────────────┐
   │ 1.3 load_nodeslines            nodes × lines -> points (EPSG:2039)       │
   │ 1.4 attach_modes, aggregate_to_hexes   drop rules, modes, H3 res 10      │
   │ 1.5 group_hexes                120 m edge-to-edge union-find -> group    │
   │ 1.5.1 🔧 apply_manual_groups   is_same_group.csv, renumber              │
   │ 1.7 add_mode_line_columns      <Mode> Lines (even split or exact)        │
   └──────────────────────────────────────────────────────────────────────────┘
   ┌─ PART 2  base_layer.py, demand.py ───────────────────────────────────────┐
   │ 2.3 tag_area_and_location_from_base   area, ring by h3_index lookup     │
   │ 2.5 load_demand_workbook       sheet -> region -> node demand           │
   │ 2.6 assign_demand              area's candidate models; overlays override│
   │ 2.6.1 🔧 apply_manual_demand   manual_demand_updates.csv                │
   └──────────────────────────────────────────────────────────────────────────┘
   ┌─ PART 3  aggregate.py, base_layer.py ────────────────────────────────────┐
   │ 2.7 aggregate_to_groups        one row per hub, dissolved geometry      │
   │ 2.7.1 tag_bus_terminals_from_base   max terminal class over hub cells   │
   │ 3.4 add_influence_area_from_base    pop/emp in 500/1000/1500 m rings    │
   │                                     (cells in a grid disk, fraction rule)│
   └──────────────────────────────────────────────────────────────────────────┘
   ┌─ PART 4  scoring.py ─────────────────────────────────────────────────────┐
   │ 4.2 prepare_scoring_frame      Region/Location categories, RegionLocation│
   │ 4.3 add_mode_score             score = Σ lines·weight × diversity bonus  │
   │ 4.4 classify, filter_eligible  HubType; ≥1000 pax, ≥2 modes, non-rail   │
   │ 4.5 normalize_scores           five *_Norm criteria, per HubType        │
   │ 4.6 monte_carlo                10,000 weight sets, seed 42, ranks       │
   └──────────────────────────────────────────────────────────────────────────┘
   ┌─ PART 5  postprocess.py, export.py ──────────────────────────────────────┐
   │ finalize_columns               display columns, names, statuses,        │
   │                                Line_Names_forPlot, RankByHubTypeMetro   │
   │ write_results_xlsx / csv       hub_prioritization_results.xlsx (Table)  │
   └──────────────────────────────────────────────────────────────────────────┘
   ┌─ h3_export.py ───────────────────────────────────────────────────────────┐
   │ build_h3_layer / write_h3_layer   hub + catchment cells with every       │
   │                                   attribute -> h3_layer.gpkg             │
   └──────────────────────────────────────────────────────────────────────────┘
OUTPUTS  workbook · csv · hub_identity.csv · h3_layer.gpkg · run_report.md/json · run_config.json · run.log
```

🔧 = human-in-the-loop input, all of them data files (see
[`06_manual_corrections.md`](06_manual_corrections.md)).

`--set spatial_source=shapefiles` replaces the three `*_from_base` steps with the notebook's
run-time overlay (`spatial_tags.tag_area_and_location`, `aggregate.tag_bus_terminals`,
`aggregate.add_influence_area`); see [`H3_BASE_LAYER.md`](../H3_BASE_LAYER.md).

## 3.1 Parts at a glance

| Part | Produces | Key inputs |
|------|----------|-----------|
| 1 Network & grouping | hexagons with node / mode / line lists, `group`, `hub_id`, per-mode line counts | nodes × lines, lines/modes, `is_same_group.csv` |
| 2 Tags & demand | `area`, `location`, `TotalDemand`, `TotalTransfers` per hexagon | `h3_base.parquet` (metro rings, districts), demand workbook, `manual_demand_updates.csv` |
| 3 Hubs, terminals, catchment | one row per hub; `term_type`, `bus_terminal`; `pop_*`, `emp_*` | `h3_base.parquet` (bus terminals, TAZ 2050) |
| 4 Scoring | `HubType`, five `*_Norm`, `Average_Simulated_Score`, ranks | config thresholds and weights |
| 5 Display table | the 70 columns of the workbook | line names, statuses, corrections, hub names |

## 3.2 Configuration

`hubs show-config --defaults` prints every parameter with its default; pass a YAML file with
`--config` or single values with `--set key=value`. The effective configuration is written
to `OUT/run_config.json`. [`docs/DEVIATIONS.md`](../DEVIATIONS.md) describes the flags that
switch between notebook behaviour and the documented method.

## 3.3 Reproducibility

- Same inputs, same configuration → byte-identical CSV (verified by `tests/test_smoke.py`).
- Monte Carlo uses `numpy.random.RandomState(42)` with the notebook's draw order, so scores
  match the notebook to ~1e-13.
- Hexagons are processed in H3-index order, which fixes group numbering; `hub_id` (a hash of
  the group's node set) additionally identifies a hub across runs when its nodes are unchanged.
- The run report records the chosen input files, their encodings and every data-quality
  finding; keep it with the results.
