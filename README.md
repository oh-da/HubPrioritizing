# Hub Prioritization Framework
**Centralized Logic for Assessing, Understanding & Determining Evaluation**

A systematic framework for identifying, classifying, and prioritizing integrated transport hubs (מתח"מים) in Israel.

---

## Overview

The framework evaluates multi-modal transit hubs on five criteria:
- **Passenger activity** (2050 forecasts)
- **Service quality** (modes and lines)
- **Strategic location** (national region and metropolitan ring)
- **Development potential** (2050 population and employment catchment)
- **Bus network integration** (strategic terminal within 200 m)

The criteria are aggregated with a **Monte Carlo simulation** (10,000 random weight sets) so that no
single criterion dominates. The result is one workbook, `hub_prioritization_results.xlsx`, consumed
by the results display page.

---

## Quick Start

```bash
git clone https://github.com/oh-da/HubPrioritizing.git
cd HubPrioritizing
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .[dev]

# 1. put the model exports of this run in one directory
ls my_run/
#   All_nodeslines_18062026.csv  Lines_and_Planned_Mode_18-06-2026.csv  Nodes_w_results_04022026.xlsx
#   linesNames_noDuplicates.csv  lines_exploded.csv  BS_lines.csv

# 2. check the inputs (lists every missing file or column, exits non-zero if anything is wrong)
hubs validate --input-dir my_run

# 3. run
hubs run --input-dir my_run --output-dir my_run/out
```

`my_run/out/` then contains:

| File | Content |
|---|---|
| `hub_prioritization_results.xlsx` | The display workbook: one sheet, one Excel Table, the 70 columns the page reads |
| `hub_prioritization_results.csv` | The same table as UTF-8 CSV |
| `hub_identity.csv` | `group`, stable `hub_id`, node list and name per hub |
| `h3_layer.gpkg` | Shareable H3 cell layer: every hub cell and its catchment with area, ring, terminal, 2050 population/jobs, hub identity and scores (`h3_layer_format`, `h3_layer_extent`) |
| `run_report.md` / `.json` | Inputs, detected encodings, metrics, and every data-quality finding |
| `run_config.json`, `run.log` | The effective configuration and the log |

Stable layers (metropolitan rings, districts, bus terminals, TAZ 2050, hub names, manual merges,
demand overrides) live in [`data/reference/`](data/reference/README.md) and do not need to be
copied per run. A same-named file in the input directory overrides the reference copy.
The four polygon layers are pre-allocated once to H3 cells (`data/reference/h3_base.parquet`,
built by `hubs prepare-base`); a run reads that table and never touches a shapefile. See
[`docs/H3_BASE_LAYER.md`](docs/H3_BASE_LAYER.md).

See [INSTALL.md](INSTALL.md) for installation details.

### Configuration

Every methodological parameter has a default that reproduces the canonical notebook. Override
with a YAML file or on the command line:

```bash
hubs show-config --defaults > pipeline.yaml       # edit, then:
hubs run --input-dir my_run --output-dir out --config pipeline.yaml
hubs run --input-dir my_run --output-dir out --set mc_iterations=20000

# reproduce the June 2026 workbook's numbers (the notebook's accidental ring geometry)
hubs run --input-dir my_run --output-dir out --set influence_rings=600,1000,1200 --set pop_emp_decay_midpoints=250,750,1250

# the legacy path: overlay the shapefiles at run time instead of reading the H3 base layer
hubs run --input-dir my_run --output-dir out --set spatial_source=shapefiles

# maintain and share the H3 base layer
hubs prepare-base                                  # rebuild after a reference shapefile changes (~2.5 min)
hubs export-h3 --out israel_cells.gpkg             # every cell of Israel with all attributes, for GIS / SQL
```

[`docs/DEVIATIONS.md`](docs/DEVIATIONS.md) explains each flag and which notebook quirk it controls;
[`docs/H3_BASE_LAYER.md`](docs/H3_BASE_LAYER.md) describes the H3 base layer and how it compares.

---

## Project Structure

```
HubPrioritizing/
├── src/
│   ├── cli.py                    # `hubs validate | run | show-config | prepare-base`
│   ├── config.py                 # thresholds, weights, CRS, column constants
│   ├── pipeline/                 # the one-command pipeline (pure DataFrame stages)
│   │   ├── settings.py           #   PipelineConfig, YAML / --set overrides
│   │   ├── inputs.py             #   input directory contract, discovery, validation, readers
│   │   ├── network.py            #   nodes x lines -> H3 hexagons -> per-mode line counts
│   │   ├── grouping.py           #   120 m union-find groups, manual merges, stable hub_id
│   │   ├── spatial_tags.py       #   metro ring / district -> area, location (shapefile path)
│   │   ├── demand.py             #   2050 demand workbook -> TotalDemand, TotalTransfers
│   │   ├── aggregate.py          #   hexagons -> hubs; terminals and pop/jobs rings (shapefile path)
│   │   ├── base_layer.py         #   H3 base layer: prepare-base builder + run-time lookups
│   │   ├── h3_export.py          #   shareable H3 cell layer (h3_layer.gpkg, hubs export-h3)
│   │   ├── scoring.py            #   categories, mode score, tiers, normalisation, Monte Carlo
│   │   ├── postprocess.py        #   display columns (incl. the former Excel formulas)
│   │   ├── export.py             #   xlsx (Excel Table) and CSV writers, FINAL_COLUMNS
│   │   ├── report.py             #   RunReport
│   │   └── run.py                #   orchestrator
│   ├── spatial/                  # H3 helpers, union-find proximity grouping
│   ├── classification/           # tier rules (classify_hub_tier)
│   ├── scoring/                  # optional extras: AHP, Monte Carlo distribution analysis
│   └── utils/                    # encoding detection, logging
├── data/reference/               # stable inputs shipped with the repo (see its README)
├── tests/                        # unit (synthetic), golden (real exports, gitignored), smoke
├── notebooks/archive/            # the superseded Colab notebooks, kept for provenance
├── app/                          # Streamlit AHP questionnaire (optional)
├── docs/                         # methodology, inputs, outputs, deviations, refactor plan
├── pyproject.toml                # package + `hubs` console script
└── CLAUDE.md                     # framework specification
```

---

## Methodology

### Pipeline Steps

1. **Network**: node x line rows joined to planned modes; H3 resolution-10 hexagons with node, mode and line lists.
2. **Grouping**: hexagons within 120 m (edge to edge) form a hub; manual merges from `is_same_group.csv`.
3. **Spatial tagging**: metropolitan area and ring (core / inner / middle / outer) or district, looked up per hexagon in the H3 base layer.
4. **Demand**: 2050 boardings + alightings per node from the regional models; overlay models override; node-level manual overrides.
5. **Aggregation**: per hub demand, lines, modes, bus terminal within 200 m, population and jobs in 500 / 1000 / 1500 m rings, all from the pre-allocated H3 cells.
6. **Scoring**: eligibility (≥ 1,000 passengers, ≥ 2 modes, a non-rail mode), tier, five criteria normalised 1–10 per tier, Monte Carlo aggregation, ranks.
7. **Display table**: Hebrew names, line status counts, transfer rate, formula columns, xlsx export.

### Hub Hierarchy

| Tier | Hebrew | Rule (as implemented) |
|------|--------|------|
| **National** | ארצי | high-speed or interurban rail, ≥ 3 lines, ≥ 50,000 passengers/day |
| **Metropolitan** | מטרופוליני | suburban rail / metro / interurban / high-speed, ≥ 3 lines, ≥ 5,000 passengers/day |
| **Local** | עירוני | BRT or LRT, ≥ 3 lines, ≥ 1,000 passengers/day |
| Train Station | — | rail modes but ≤ 2 lines |
| Not Hub | — | everything else |

### Scoring Criteria

| # | Criterion | Column | Normalisation |
|---|-----------|--------|---------------|
| 1 | Passenger activity (log₁₀ demand) | `TotalDemand_Norm` | per tier |
| 2 | Service & modes (Σ lines × mode weight × diversity bonus) | `score_Norm` | per tier |
| 3 | Location (region × metropolitan position) | `RegionLocation_Norm` | per tier |
| 4 | Population & jobs 2050 (rings with distance decay, tier-specific mix) | `PopEmp_Score_Norm` | per tier |
| 5 | Bus terminal proximity (0–3 by terminal class) | `bus_terminal_Norm` | per tier |

Final score `TotalScore_MC` = mean over 10,000 random weight sets (seed 42). `RankByHubTypeMetro`
ranks national hubs nationwide and other tiers within (tier, metropolitan area).

---

## Testing

```bash
pytest                       # unit + smoke tests on synthetic data (no external files)
pytest tests/golden          # regression against the June 2026 results; needs tests/fixtures/real/
```

`tests/fixtures/README.md` lists the real files the golden tests expect. On the June 2026 exports
the pipeline reproduces all 142 hubs of the results workbook: group IDs, nodes, demand, lines, modes,
tiers, names, population and jobs, and, with the legacy ring settings, the Monte Carlo score of
141 hubs to 1e-12 (the exception is a hand-edited row; see `docs/DEVIATIONS.md`).

---

## Documentation

- **[CLAUDE.md](CLAUDE.md)** — framework specification and methodology
- **[docs/full_documentation/](docs/full_documentation/)** — inputs, pipeline, step-by-step, scoring, manual corrections, outputs, code reference
- **[docs/DEVIATIONS.md](docs/DEVIATIONS.md)** — notebook quirks kept behind flags and intentional fixes
- **[docs/PIPELINE_REFACTOR_PLAN.md](docs/PIPELINE_REFACTOR_PLAN.md)** — the review and plan that produced the current structure
- **[data/reference/README.md](data/reference/README.md)** — the stable reference layers and tables
- **[AHP_QUICKSTART.md](AHP_QUICKSTART.md)**, **[docs/AHP_SCORING_GUIDE.md](docs/AHP_SCORING_GUIDE.md)** — optional expert weighting
- **[docs/PROJECT_EXECUTIVE_SUMMARY.md](docs/PROJECT_EXECUTIVE_SUMMARY.md)**, **[docs/SCORING_CRITERIA_EXECUTIVE_SUMMARY.md](docs/SCORING_CRITERIA_EXECUTIVE_SUMMARY.md)** — summaries for stakeholders

---

## Contributing

This is a proprietary planning framework for Israeli transport infrastructure.
It is not open to external contribution. For access or collaboration requests,
contact the author (see below).

---

## License

**PROPRIETARY AND CONFIDENTIAL** — Copyright © 2026 Ohad Dahan. All Rights Reserved.

This software and all associated materials are proprietary and confidential.
Unauthorized copying, distribution, modification, or use, in whole or in part,
is strictly prohibited without prior express written permission. See the
[LICENSE](LICENSE) file for full terms.

---

## Contact

**Author:** Ohad Dahan
**Email:** [ohad@ayalonhw.co.il](mailto:ohad@ayalonhw.co.il)
