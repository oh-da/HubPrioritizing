# 7. Outputs

The pipeline produces three kinds of artefacts: **tabular** (CSV /
Excel), **geospatial** (GeoJSON), and **interactive** (HTML maps). All
of them are derived from the same scored-hubs GeoDataFrame, so column
schemas are consistent across formats.

## 7.1 Intermediate outputs (between parts)

| Step | File | What it contains |
|------|------|------------------|
| 1.8 | `transit_h3_hexagons.csv` | Every H3 hexagon that contains at least one transit node, with `node` list, `Mode_Planned`, per-mode line counts, `group`, geometry (WKT) |
| 2.8 | `hubs_with_demand.csv` | Ungrouped: one row per hub-hexagon with demand and area/location tags |
| 2.8 | `grouped_hubs.csv` | One row per hub group with aggregated demand, modes, line counts, terminal flags |
| 3.6 | `hubs_complete.csv` / `.xlsx` | Same as `grouped_hubs.csv` plus the 2050 population/employment ring totals (`pop_0_500`, `emp_0_500`, … `pop_1000_1500`, `emp_1000_1500`) |

These intermediate files are auditable — if a hub's final score looks
wrong, the cause can be diagnosed by tracing back through them.

## 7.2 Primary outputs (after scoring)

Written by Step 4.7.

### `scored_hubs_final.csv` / `scored_hubs_final.xlsx`

| Column | Description |
|--------|-------------|
| `group` | Hub group ID (stable within a run; renumbered after IsSameGroup corrections) |
| `HubName` | Human display name (from `data/hub_names.csv`) when available |
| `node` | List of node IDs that compose the hub |
| `Mode_Planned` | Set / list of modes serving the hub |
| `BRT Lines`, `LRT Lines`, `Metro Lines`, … | Per-mode line counts |
| `TotalDemand`, `TotalTransfers` | 2050 demand and transfers (after manual corrections) |
| `area`, `location` | Region (district) and metropolitan position |
| `pop_0_500`, `emp_0_500`, `pop_500_1000`, `emp_500_1000`, `pop_1000_1500`, `emp_1000_1500` | 2050 population/employment in each ring (when Part 3 ran) |
| `near_bus_terminal`, `term_type` | Terminal proximity flag and type |
| `tier` | ארצי / מטרופוליני / עירוני |
| `activity_score`, `service_score`, `location_score`, `pop_jobs_score`, `terminal_score` | Five 1–10 criterion scores |
| `final_score` | Monte Carlo aggregated score (mean over 10 000 iterations) |
| `rank` | Tier-aware rank (Nationals globally; Metro/Local per area) |
| `ahp_score`, `ahp_rank` | Present only when `AHP_ENABLED=True` |
| `geometry` | WKT (CSV) or GeoJSON geometry |

Encoding: **`utf-8-sig`** (so Excel renders Hebrew correctly).

### `hub_results_{timestamp}.geojson`

Identical content, geometry as proper GeoJSON, suitable for QGIS / ArcGIS
/ web maps.

### `hub_map_{timestamp}.html`

Interactive Folium map (`src/visualization/maps.py::create_hub_map`):

- centred on Israel (`MAP_CENTER_ISRAEL = [31.5, 34.9]`),
- coloured by `final_score` or by `tier` (`TIER_COLORS = {National: red,
  Metro: orange, Local: green}`),
- click-through popups with the hub's modes, demand, tier, and scores,
- OpenStreetMap tiles by default (`config.MAP_TILES`).

## 7.3 Optional Monte Carlo distribution outputs

Produced by `src/scoring/mc_distribution.py::run_mc_distribution_analysis`
when MC distribution analysis is enabled. Files land under
`data/results/mc_distribution_{timestamp}/`:

| File | Purpose |
|------|---------|
| `mc_hub_stats.csv` | Per-hub mean, median, std, p5/p25/p75/p95, top-K probabilities, rank statistics |
| `raw_scores_long_format.csv` | One row per (hub × iteration); used for downstream sensitivity analysis. ~10 000 × #hubs rows |
| `boxplot_scores.png` | Score box-plot for the top-N (default 30) hubs |
| `top_k_probability_chart.png` | Stacked-bar chart: P(Top 1), P(Top 3), P(Top 5) per hub |
| `histogram_hub_<id>.png` | Per-hub score distribution histograms (50 bins by default) |

These let analysts answer questions like *"how often does Hub X end up
in the top 10?"* and *"which ranking is fragile to weight choice?"*.

## 7.4 Logging

If `config.LOG_TO_FILE = True`, every run also writes a timestamped log
file under `logs/`. Format:

```
2026-05-31 09:14:22 - hub_pipeline - INFO - Stage 3 complete: 86 hub groups
```

These logs include every manual correction that was applied (which
nodes, which CSV rows, how many groups were merged), making the run
fully auditable.
