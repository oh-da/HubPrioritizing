# Reference data

Stable inputs that rarely change between runs. The pipeline reads them from this
directory by default (`--reference-dir`), so a run's `--input-dir` only needs the
per-run model exports. A file with the same name placed in the input directory
overrides the copy here.

| File | Purpose | Key fields | Encoding |
|---|---|---|---|
| `metro_2008.shp` (+ `.shx .dbf .prj .cpg`) | Metropolitan areas and rings → `area`, `location` | `METRO_NAME` (באר שבע / חיפה / ירושלים / תל אביב), `ZONE_NAME` (גלעין / טבעת פנימית / טבעת תיכונה / טבעת חיצונית) | dbf is CP1255; declared in `metro_2008.cpg` |
| `Districts.shp` (+ sidecars) | National districts, fallback for hubs outside a metro → `area` | `MACHOZ` (מחוז דרום / חיפה / ירושלים / מרכז / צפון / ת"א) | dbf is UTF-8; declared in `Districts.cpg` |
| `is_same_group.csv` | Manual hub merges: nodes that must share one group even if farther than 120 m apart | `Nodes in group` — comma-separated node IDs, one row per merge | UTF-8 |
| `hub_names.csv` | Hebrew display names per hub, keyed by H3 index (any hex of a group carries the group's name) | `name_id, h3_index, HubNameHE` | UTF-8 with BOM |
| `line_names_extra.csv` | Hebrew line names missing from the model export (currently the Metro M1 lines) | `LineName, Line_n_Mode, notes` | UTF-8 |
| `manual_demand_updates.csv` | Node-level 2050 demand overrides from the National Model (replaces values hardcoded in the notebook). A blank `total_transfers` keeps the computed transfers. Candidates not yet included because they are not in the current hub set: Modiin Merkaz node 400470 (40,628 / 0) and Modiin West node 400460 (41,000 / 12,133). | `node, total_demand, total_transfers, station_name, notes` | UTF-8 |

Both shapefiles are in WGS84 (EPSG:4326); the pipeline reprojects as needed.

## Still to add

These layers are referenced by the scoring methodology but are **not yet in the repo**:

| File | Used for | Required fields |
|---|---|---|
| `BUS_TERMINAL_STRAT.shp` | Bus-terminal proximity score (200 m buffer) | `term_type` (חניון לילה / מסוף קטן / מסוף בינוני / מסוף גדול / מתקן משולב) |
| `TAZ_1270.shp` | Population & jobs 2050 in 500 / 1000 / 1500 m rings | `POP_2050`, `EMPL_2050` |

Until they are present, `hubs validate` reports them as missing and `hubs run` refuses to
start (no placeholder data is ever substituted).

## Provenance

- `metro_2008`, `Districts`: `Location/` folder of the planning team's Drive, 2026-09-16.
- `is_same_group.csv`: `IsSameGroup_V1.01.csv`, 2026-09-16.
- `hub_names.csv`: `Hubs_Names_H3_exploded_V1.01.csv` (CP1255) converted to UTF-8, 2026-09-16, plus 20 hubs (name_id 135-154) that the June 2026 results workbook named but the file lacked; their H3 indexes and names were taken from that workbook.
- `line_names_extra.csv`: the four Metro M1 line names that were substituted by hand in the `Line_Names_forPlot` Excel formula. Loaded after the per-run `linesNames*.csv`, filling gaps only.
- `manual_demand_updates.csv`: values from `COMPLETE_TRANSIT_PIPELINE.ipynb` steps 2.6.2 / 2.6.3 (National Model) and the Netanya update the notebook listed for CSV entry; verified against the June 2026 results.
