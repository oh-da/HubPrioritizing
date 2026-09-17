# Reference data

Stable inputs that rarely change between runs. The pipeline reads them from this
directory by default (`--reference-dir`), so a run's `--input-dir` only needs the
per-run model exports. A file with the same name placed in the input directory
overrides the copy here.

| File | Purpose | Key fields | Encoding |
|---|---|---|---|
| `metro_2008.shp` (+ `.shx .dbf .prj .cpg`) | Metropolitan areas and rings → `area`, `location` | `METRO_NAME` (באר שבע / חיפה / ירושלים / תל אביב), `ZONE_NAME` (גלעין / טבעת פנימית / טבעת תיכונה / טבעת חיצונית) | dbf is CP1255; declared in `metro_2008.cpg` |
| `Districts.shp` (+ sidecars) | National districts, fallback for hubs outside a metro → `area` | `MACHOZ` (מחוז דרום / חיפה / ירושלים / מרכז / צפון / ת"א) | dbf is UTF-8; declared in `Districts.cpg` |
| `BUS_TERMINAL_STRAT.shp` (+ sidecars) | Strategic bus terminals (673 polygons, EPSG:2039) → `term_type`, `bus_terminal` score within 200 m | `term_type` (חניון לילה 40 · מסוף קטן 353 · מסוף בינוני 141 · מסוף גדול 18 · מתקן משולב 121), `id`, `term_name` | UTF-8 (`.cpg`) |
| `TAZ_1270.shp` (+ sidecars) | 2050 traffic analysis zones (1,270 polygons, EPSG:2039) → population and jobs in the catchment rings | `POP_2050`, `EMPL_2050` (stored as text in the DBF; coerced to numbers) | CP1255 (`.cpg` added) |
| `h3_base.parquet` (+ `h3_base.manifest.json`) | The four layers above pre-allocated to H3 resolution-10 cells (1.57 M rows, 12 MB) by `hubs prepare-base`; **what a run reads** (the shapefiles are only needed to rebuild it, or with `spatial_source=shapefiles`). The manifest records the source files and their SHA-256. Rebuild after changing any of the four shapefiles. See `docs/H3_BASE_LAYER.md`. | `h3_index, area, location, term_type, term_id, bus_terminal, pop_2050, emp_2050` | Parquet (zstd, pop/emp float32) |
| `is_same_group.csv` | Manual hub merges: nodes that must share one group even if farther than 120 m apart | `Nodes in group` — comma-separated node IDs, one row per merge | UTF-8 |
| `hub_names.csv` | Hebrew display names per hub, keyed by H3 index (any hex of a group carries the group's name) | `name_id, h3_index, HubNameHE` | UTF-8 with BOM |
| `line_names_extra.csv` | Hebrew line names missing from the model export (currently the Metro M1 lines) | `LineName, Line_n_Mode, notes` | UTF-8 |
| `manual_demand_updates.csv` | Node-level 2050 demand overrides from the National Model (replaces values hardcoded in the notebook). A blank `total_transfers` keeps the computed transfers. Candidates not yet included because they are not in the current hub set: Modiin Merkaz node 400470 (40,628 / 0) and Modiin West node 400460 (41,000 / 12,133). | `node, total_demand, total_transfers, station_name, notes` | UTF-8 |

Both shapefiles are in WGS84 (EPSG:4326); the pipeline reprojects as needed.

All layers the scoring methodology needs are present; `hubs validate` passes on the June 2026
exports with this directory alone. A missing required layer stops `hubs run` (no placeholder
data is ever substituted).

## Provenance

- `metro_2008`, `Districts`: `Location/` folder of the planning team's Drive, 2026-09-16.
- `BUS_TERMINAL_STRAT`: `BusHubs/` folder of the planning team's Drive, 2026-09-16 (the `.lyr`, `.sbn`, `.sbx` ArcGIS sidecars and the `BUS_TERMINAL_FCL` layer were not copied).
- `TAZ_1270`: `InfluenceArea/Israel2050/` folder of the planning team's Drive, 2026-09-17 (`.dat`, `.dbd`, `.key`, `.qpj` sidecars not copied; a `CP1255` code page file was added).
- `h3_base.parquet`: built by `hubs prepare-base` on 2026-09-17 from the four shapefiles above (hashes in the manifest).
- `is_same_group.csv`: `IsSameGroup_V1.01.csv`, 2026-09-16.
- `hub_names.csv`: `Hubs_Names_H3_exploded_V1.01.csv` (CP1255) converted to UTF-8, 2026-09-16, plus 20 hubs (name_id 135-154) that the June 2026 results workbook named but the file lacked; their H3 indexes and names were taken from that workbook.
- `line_names_extra.csv`: the four Metro M1 line names that were substituted by hand in the `Line_Names_forPlot` Excel formula. Loaded after the per-run `linesNames*.csv`, filling gaps only.
- `manual_demand_updates.csv`: values from `COMPLETE_TRANSIT_PIPELINE.ipynb` steps 2.6.2 / 2.6.3 (National Model) and the Netanya update the notebook listed for CSV entry; verified against the June 2026 results.
