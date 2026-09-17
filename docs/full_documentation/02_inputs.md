# 2. Inputs

The pipeline is driven by **one input directory** (`hubs run --input-dir DIR`) holding the
per-run model exports, plus a **reference directory** of stable layers shipped with the
repository (`data/reference/`, overridable with `--reference-dir`). File discovery,
validation and the readers live in `src/pipeline/inputs.py`.

`hubs validate --input-dir DIR` prints which file was chosen for every input, the detected
encodings, and every problem (missing file, missing column, unreadable layer) before any
processing starts. Nothing is ever replaced by placeholder data.

## 2.1 Discovery rules

- Each input has a list of filename patterns (below). When several files match, the newest
  by the **date in the filename** wins (`18062026`, `18-06-2026`, `2026-06-18` are all
  recognised), then by modification time. Ignored older files are listed by `hubs validate`.
- A file in the input directory with a reference layer's name **overrides** the reference copy.
- `--file KEY=PATH` pins a specific file for a key.
- CSVs are read as `utf-8-sig` first and `cp1255` second; the Hebrew columns are checked for
  mojibake before an encoding is accepted. Shapefiles are read byte-exact and decoded with the
  code page from their `.cpg` (or detected), which avoids GDAL's truncated-Hebrew quirk.

## 2.2 Per-run inputs (`--input-dir`)

| Key | Filename pattern | Required | Columns | Notes |
|---|---|---|---|---|
| `nodeslines` | `All_nodeslines*.csv` | yes | `node`, `LINE_ID`, `X`,`Y` or WKT `geometry` (EPSG:2039) | One row per node × line. Built in GIS from `Routes_and_Nodes` + model node coordinates. |
| `lines_mode` | `Lines_and_Planned_Mode*.csv` | yes | `Line_ModelName`, `Mode_Planned`, `Area` (+ `Line_Name`, `Line_Description`) | Duplicated keys are collapsed (first wins) and reported; lines matching the drop rules (Haifa `m*`, Netanya `LRT151/152`) are removed. |
| `demand` | `Nodes_w_results*.xlsx` | yes | sheets `5040_Daily` (Haifa), `Daily_5087` (Tel Aviv), `Daily_BS`, `Daily_Hadera`, `Daily_Jerusalem`, `HaifaNewMetronit`, `Daily_5093` (Ashdod-Ashkelon), `National` | Per-sheet column aliases in `src/pipeline/demand.py::SHEET_COLUMN_CONFIG`; other sheets are ignored. |
| `line_names` | `linesNames*.csv` | optional | two columns: line ID, Hebrew name `(mode)`; headerless accepted | Gaps are filled from `data/reference/line_names_extra.csv`; still-unnamed lines are reported. |
| `line_status` | `line_status*.csv` or legacy `lines_exploded*.csv` | optional | `LineName`, `StatusID` (0–7) | Legacy files repeating a line with different statuses: last wins, conflicts reported. |
| `line_corrections` | `BS_lines*.csv` | optional | `LineName`, `LineName_Correct` | Spelling fixes applied before name/status lookups. |
| `routes` | `Routes_and_Nodes*.xlsx` | optional | — | Recorded in the report; not yet used (future stage 0). |

## 2.3 Reference layers (`data/reference/`)

| Key | File | Required | Fields | Used for |
|---|---|---|---|---|
| `h3_base` | `h3_base.parquet` (+ manifest) | yes (default `spatial_source=h3_base`) | `h3_index`, `area`, `location`, `term_type`, `term_id`, `bus_terminal`, `pop_2050`, `emp_2050` | the four polygon layers below, pre-allocated to H3 cells by `hubs prepare-base` |
| `metro` | `metro_2008.shp` | to rebuild `h3_base`, or `spatial_source=shapefiles` | `METRO_NAME`, `ZONE_NAME` | `area` and `location` (גלעין / טבעת פנימית / תיכונה / חיצונית) |
| `districts` | `Districts.shp` | idem | `MACHOZ` | `area` fallback outside the metros |
| `bus_terminals` | `BUS_TERMINAL_STRAT.shp` | idem | `term_type` | bus-terminal score (200 m) |
| `taz` | `TAZ_1270.shp` | idem | `POP_2050`, `EMPL_2050` | population & jobs rings |
| `hub_names` | `hub_names.csv` | optional | `h3_index`, `HubNameHE` | Hebrew display names |
| `line_names_extra` | `line_names_extra.csv` | optional | `LineName`, `Line_n_Mode` | names missing from the export |
| `is_same_group` | `is_same_group.csv` | optional | `Nodes in group`, optional `model` | manual hub merges |
| `manual_demand` | `manual_demand_updates.csv` | optional | `node`, `total_demand`, `total_transfers`, optional `model` | node-level demand overrides |
| `node_positions` | `node_position_overrides.csv` | optional | `node`, `X`, `Y` | corrected coordinates for nodes whose network rows disagree on position (see `06_manual_corrections.md`) |

See [`data/reference/README.md`](../../data/reference/README.md) for provenance and
[`H3_BASE_LAYER.md`](../H3_BASE_LAYER.md) for how the base layer is built and shared.

## 2.4 Coordinate reference systems

| CRS | Used where |
|-----|-----------|
| `EPSG:4326` (WGS84) | H3 indexing, hexagon geometry, output `x`/`y` (longitude, latitude) |
| `EPSG:2039` (Israel TM Grid) | every metre-based operation: 120 m grouping, 200 m terminal buffer, catchment rings |

## 2.5 Encoding

- Model CSVs arrive as `cp1255`; curated tables as UTF-8. Both are detected automatically.
- Everything written by the pipeline is UTF-8 (`utf-8-sig` for CSV so Excel shows Hebrew correctly).
- Add a `.cpg` next to any new shapefile (`CP1255` or `UTF-8`).
