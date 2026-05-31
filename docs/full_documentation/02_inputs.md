# 2. Inputs

The pipeline is configured in the **MASTER CONFIGURATION** section near the
top of `COMPLETE_TRANSIT_PIPELINE.ipynb` (lines ~248–310). Every input file
path is set there and propagates through the rest of the notebook. When
running outside the notebook (e.g. via `scripts/run_complete_pipeline.py`),
the same paths are read from `src/config.py`.

This document lists every input the model expects, what it is for, and
what column / field structure is required.

---

## 2.1 Core required inputs

### 2.1.1 Transit nodes — `INPUT_NODES_CSV`

| Field | Description |
|-------|-------------|
| `node` | Stable integer node ID (this is what manual corrections key off) |
| `LINE_ID` | Line identifier that visits this node |
| `X`, `Y` | Coordinates in **EPSG:2039 (Israel TM Grid)** — used for accurate metric buffers |
| `geometry` *(optional)* | WKT geometry; if absent, `X`/`Y` is used |

- **Encoding:** `windows-1255` (Hebrew).
- **Default path in notebook:** `…/Hubs/All_nodes+lines_29102025.csv`.
- **Purpose:** Every row is one (node × line) pairing. The pipeline
  aggregates this to a unique node, then assigns each node to an H3
  hexagon, then groups hexagons into hubs.

### 2.1.2 Lines and planned modes — `LINES_MODE_CSV`

| Field | Description |
|-------|-------------|
| `LINE_ID` | Same identifier as in the nodes file |
| `Mode_Planned` | Planned 2050 mode for the line (`Rail`, `Metro`, `LRT`, `BRT`, `Bus`, …) |
| `Area` *(optional)* | Metropolitan area; used to drop Metronit duplicates and similar cleanup |

- **Encoding:** `windows-1255`.
- **Default path in notebook:** `…/Hubs/Lines_and_Planned_Mode_30-10-2025.csv`.
- **Purpose:** Joined onto the nodes file so each node knows which modes
  serve it, how many distinct lines per mode, and which Hebrew/English
  mode tags apply.

### 2.1.3 Demand forecasts — `DEMAND_EXCEL`

- **Format:** Excel workbook with multiple sheets, one per metropolitan
  area / region.
- **Default path in notebook:** `…/Hubs/Nodes_w_results_28122025.xlsx`.
- **Per-sheet columns** are mapped in **Step 2.4** of the notebook
  (`## Step 2.4: Per-Sheet Column Configuration`). Each sheet provides at
  minimum a node identifier and 2050 boardings / alightings / transfers
  columns; the notebook normalises these to a common
  `TotalDemand` / `TotalTransfers` schema.
- **Purpose:** Provides the 2050 ridership used both for tier assignment
  and for the **Passenger Activity** score (criterion 1).

### 2.1.4 Geographic context layers

| Variable | Default file | Used for |
|----------|--------------|---------|
| `METRO_SHP` | `Location/metro_2008.shp` | Tagging each hub with its metropolitan position (גלעין / טבעת / periphery) — the **Location** score |
| `DISTRICTS_SHP` | `Location/Districts.shp` | Tagging each hub with its national region (תל אביב / חיפה / צפון / דרום / ירושלים) — the **Location** score |
| `TAZ_SHAPEFILE` | `InfluenceArea/Israel2050/TAZ_1270.shp` | 2050 traffic-analysis zones with population and employment, used by the **Population & Jobs** score |

All shapefiles are read with attention to Hebrew encoding (see
`src/utils/encoding_fix.py`).

### 2.1.5 Bus terminals — `BUS_TERMINALS_SHP`

- **Default file:** `BusHubs/BUS_TERMINAL_STRAT.shp` (≈673 terminals in
  the current dataset).
- **Key field:** `term_type` — one of:
  - `חניון לילה` (night parking) → weight 1.0
  - `מסוף קטן` (small terminal) → 2.0
  - `מסוף בינוני` (medium terminal) → 2.0
  - `מסוף גדול` (large terminal) → 3.0
  - `מתקן משולב` (integrated facility) → 3.0
- **Used by:** the **Bus Terminal Proximity** score (criterion 5), with a
  200 m buffer around each hub center.

---

## 2.2 Optional / manual-correction inputs

All four of these are **optional** — the pipeline runs without them — but
they are how planners inject expert knowledge into the model. They are
documented in detail in [`06_manual_corrections.md`](06_manual_corrections.md);
this section lists them so the input catalogue is complete.

| Variable | Default file | What it overrides |
|----------|--------------|-------------------|
| `MANUAL_GROUP_CSV` 🔧 | `data/IsSameGroup.csv` | Forces a set of nodes into the same hub group, even when 120 m buffering would not merge them |
| `MANUAL_DEMAND_UPDATES_CSV` 🔧 | `data/manual_demand_updates.csv` | Overrides 2050 demand and transfer totals for specific node IDs (e.g. from a more accurate National Model run) |
| `AHP_EXPERT_CSV_PATH` 🔧 | `data/ahp_expert_comparisons.csv` | Provides expert pairwise comparisons that drive the AHP scoring alternative (used only when `AHP_ENABLED=True`) |
| `hub_names.csv` 🔧 | `data/hub_names_TEMPLATE.csv` | Provides human-curated display names for hubs in maps and exports |

There are also **two hardcoded overrides** burned into the notebook
itself: Step 2.6.2 (four nodes from the National Model) and Step 2.6.3
(Shefaim LRT stop). See [`06_manual_corrections.md`](06_manual_corrections.md).

---

## 2.3 Coordinate reference systems

| CRS | Used where |
|-----|-----------|
| `EPSG:4326` (WGS84) | H3 indexing, output GeoJSON, web maps |
| `EPSG:2039` (Israel TM Grid) | All meter-based work: 120 m hex grouping, 200 m terminal buffers, 1.5 km catchment rings |

Helpers in `src/config.py` (`CRS_WGS84`, `CRS_ISRAEL_TM`) and in
`src/spatial/h3_operations.py` handle conversions consistently.

---

## 2.4 Encoding

Hebrew text is everywhere in the input data. The pipeline uses:

- `windows-1255` for reading the original CSVs (`config.DEFAULT_ENCODING`).
- `utf-8-sig` for everything written by the pipeline
  (`config.UTF8_ENCODING`) so that downstream Excel and BI tools display
  Hebrew correctly.
- `src/utils/encoding_fix.py` provides validation, diagnosis and
  shapefile readers that fall back across encodings.
