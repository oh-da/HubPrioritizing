# Shapefile export of a run

`scripts/export_shapefiles.py` turns a finished `hubs run` into two shapefile packages for GIS
(QGIS, ArcGIS Pro): the hubs as points and the lines of the network. Nothing is recomputed; the
script only reshapes the run's own tables.

```bash
hubs run --input-dir DIR --output-dir RUN
python scripts/export_shapefiles.py --run-dir RUN [--lines-file FILE] [--out-dir OUT] \
    [--version NAME] [--no-zip]
```

| Option | Meaning |
|---|---|
| `--run-dir` | output of `hubs run` (`hub_prioritization_results.csv`, `hub_identity.csv`, `network_nodes.csv`); required |
| `--lines-file` | the run's `Lines_and_Planned_Mode_*.csv`; default: the file recorded in `run_manifest.json` (`inputs.lines_mode.file`, looked up in the manifest's `input_dir`), else an error asking for it |
| `--out-dir` | default `<run-dir>/shapefiles` |
| `--version` | label in the zip names and READMEs; default the manifest `version`, else the run folder name |
| `--no-zip` | write the folders only |

A missing input stops the run with a one-line message (exit code 1) that names the file and the
command that produces it. The output is deterministic: the same run gives identical layers, CSVs
and zips.

## `pkg_hubs` (`hubs_hubprioritizing_<version>_shp.zip`)

`hubs_itm.shp` (EPSG:2039) and `hubs_wgs84.shp` (EPSG:4326): one point per hub the pipeline
exported, all hub types, at the hub centroid. `field_map_hubs.csv` maps every shapefile field to
its results column and meaning (names are limited to 10 characters). The fields, by group:

- **Identity and type**: `group` (this run only), `hub_id` (stable), `name_he`, `HubTypeHE`, `area`, `Metro`, `location`.
  `HubTypeHE` is the tier: ארצי (national), מטרופוליני (metropolitan), עירוני (local), or `Not Hub`
  (eligible but fewer than 3 lines).
- **Demand**: `TotDemand`, `TotTransf`, `TransfRate` (2050).
- **Network**: `Modes`, `ModesHe`, `NumModes`, `NumLines` and one `Lines<Mode>` count per mode.
- **Catchment**: `Pop2050`, `Emp2050`, `BusTermCls` (terminal class within 200 m, 0-3).
- **Scores**: the five criteria `NormLoc`, `NormBus`, `NormServ`, `NormDem`, `NormPopEmp` (1-10
  per tier), the final `ScoreMC` and the ranks `RankAll`, `RankType`, `RankTypMet` (the display rank).

`hub_lines.csv` lists hub x line (the full line list does not fit a 254-character DBF field).
Only exported hubs are included; the groups that failed the eligibility filter are in
`hub_groups_all.csv` of the run.

## `pkg_lines` (`lines_hubprioritizing_<version>_shp.zip`)

- `lines_itm.shp` / `lines_wgs84.shp`: one LineString per `LINE_ID` with two or more nodes (each
  direction is a line), with `Mode`, `LineName`, `Descr`, `Area`, `NumNodes`, `LengthKm`.
- `line_nodes_itm.shp` / `line_nodes_wgs84.shp`: one point per node x line; `Seq` is the position
  along the drawn line.
- `lines_attributes.csv`, and `lines_without_geometry.csv` for the lines with a single node.

**Caveat: the lines are a visual aid.** The pipeline has no route geometry, only node points per
line. Each line joins its nodes in shortest-open-path order (`src.compare.routes.order_points`):
long rail or BRT lines become straight chords between distant nodes, and branching or loop lines
can zig-zag. Do not use them as route alignments or for lengths (`LengthKm` is the drawn polyline).

## Hebrew

All text is UTF-8 and every shapefile has a `.cpg` sidecar saying so; open it with a recent QGIS
or ArcGIS Pro. The CSVs are UTF-8 with BOM. The lines file may be CP1255 or UTF-8; the encoding is
detected (`src.pipeline.inputs.read_csv_auto`).
