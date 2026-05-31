# 3. Pipeline Overview

The pipeline runs as four parts, totalling twelve numbered steps. The
canonical implementation is `COMPLETE_TRANSIT_PIPELINE.ipynb`; the same
logic is exposed programmatically through `scripts/run_complete_pipeline.py`
which delegates the scoring stage to `src/scoring/monte_carlo.py::run_complete_scoring_pipeline`.

```
                          ┌─────────────────────────────────────────────────┐
INPUTS                    │   Transit nodes ─── Lines/modes ─── 2050 demand │
                          │   Metro+Districts shp ─── TAZ shp ─── Terminals │
                          └────────────────────┬────────────────────────────┘
                                               │
   ┌─── PART 1 ─ H3 hexagons ──────────────────▼──────────────────┐
   │  1.1 Setup / master config                                   │
   │  1.2 Configure Part-1 paths                                  │
   │  1.3 Load transit nodes                                      │
   │  1.4 Assign H3 indices + aggregate lines per node            │
   │  1.5 Group adjacent hexagons (120 m edge-to-edge buffer)     │
   │  1.5.1 🔧 Apply IsSameGroup.csv manual group corrections     │
   │  1.6 Geocode addresses (optional)                            │
   │  1.7 Create per-mode line-count columns                      │
   │  1.8 Export `transit_h3_hexagons.csv`                        │
   └──────────────────────────────────────────────────────────────┘
                                ▼
   ┌─── PART 2 ─ Demand & spatial tagging ────────────────────────┐
   │  2.1 Configure Part-2 paths                                  │
   │  2.2 Load H3 output from Part 1                              │
   │  2.3 Tag each hub with `area` + `location` (metro / district)│
   │  2.4 Per-sheet column config for the demand Excel            │
   │  2.5 Load demand Excel                                       │
   │  2.6 Match demand to hubs by area                            │
   │  2.6.1 🔧 Load manual demand updates CSV (optional)          │
   │  2.6.2 🔧 Apply 4 hardcoded National-Model node updates      │
   │  2.6.3 🔧 Update Shefaim LRT stop (node 511248)              │
   │  2.7 Create grouped hubs with demand                         │
   │  2.7.1 Add bus-terminal data (200 m proximity)               │
   │  2.7.2 Verify scoring columns                                │
   │  2.8 Export `grouped_hubs.csv`                               │
   └──────────────────────────────────────────────────────────────┘
                                ▼
   ┌─── PART 3 ─ Influence area (optional) ───────────────────────┐
   │  3.1 Configure Part-3 paths                                  │
   │  3.2 Load influence_area_processor                           │
   │  3.3 Check TAZ availability                                  │
   │  3.4 Initialize processor + run pipeline                     │
   │  3.5 Explore results                                         │
   │  3.6 Export `hubs_complete.xlsx`                             │
   └──────────────────────────────────────────────────────────────┘
                                ▼
   ┌─── PART 4 ─ Scoring & ranking ───────────────────────────────┐
   │  4.1 Scoring configuration (incl. AHP / MC distribution)     │
   │  4.2 Data cleaning + preparation                             │
   │  4.3 Calculate mode-service + bus-terminal scores            │
   │  4.4 Filter eligible hubs + classify tier                    │
   │  4.5 Normalize scores + calculate Pop/Emp score              │
   │  4.6 Monte Carlo aggregation + tier-aware ranking            │
   │  4.7 Export `scored_hubs_final.csv` / `.xlsx`                │
   └──────────────────────────────────────────────────────────────┘
                                ▼
OUTPUTS               scored hubs CSV / Excel / GeoJSON, interactive map
```

🔧 = manual / human-in-the-loop correction. See
[`06_manual_corrections.md`](06_manual_corrections.md) for the full list.

## 3.1 Parts at a glance

| Part | What it produces | Key inputs | Key output |
|------|------------------|-----------|------------|
| **1. H3 hexagons** | A geodataframe where every transit node has an H3 index and belongs to a *hub group* (120 m buffer clusters) with per-mode line counts | Nodes CSV, Lines+modes CSV, IsSameGroup.csv | `transit_h3_hexagons.csv` |
| **2. Demand + tagging** | Each hub group tagged with metropolitan position, district, 2050 demand, transfers, and nearby bus terminals | Part-1 output, Demand Excel, Metro/Districts shapefiles, Bus terminals shapefile, manual demand CSV, hardcoded overrides | `grouped_hubs.csv` |
| **3. Influence area** *(optional)* | Population and employment 2050 totals in concentric 0–500 / 500–1 000 / 1 000–1 500 m rings | Part-2 output, TAZ shapefile | `hubs_complete.csv/.xlsx` |
| **4. Scoring & ranking** | The five normalized scores, the Monte Carlo final score, the tier-aware rank, and (optionally) AHP scores + MC distributions | Part-2 or Part-3 output | `scored_hubs_final.csv/.xlsx` |

## 3.2 How to run the pipeline

There are two equivalent entry points:

1. **Notebook (canonical):** `COMPLETE_TRANSIT_PIPELINE.ipynb`. Edit the
   *MASTER CONFIGURATION* section, then run all cells. This is the path
   most planners use because they want to inspect each step.

2. **Script:** `python scripts/run_complete_pipeline.py`. Wraps the
   loaders, spatial operations, classification and scoring into a class
   (`HubPrioritizationPipeline`) and ends by calling
   `monte_carlo.run_complete_scoring_pipeline` and `maps.create_hub_map`.

Both paths share the same `src/` package and therefore the same
configuration, scoring formulas, and output schema.

## 3.3 Reproducibility

- Monte Carlo uses a fixed seed (`MONTE_CARLO_RANDOM_SEED = 42`).
- The notebook commits the file paths for every intermediate artefact,
  so re-running any single part produces byte-identical downstream
  outputs as long as the inputs and config are unchanged.
- The H3 resolution (10) and merge threshold (120 m) are configuration
  constants — changing either will change which nodes end up in which
  hub group and will therefore change the downstream ranks.
