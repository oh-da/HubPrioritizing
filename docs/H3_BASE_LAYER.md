# The H3 base layer (`hubs prepare-base`)

**Status: default.** `hubs run` reads the spatial context from `data/reference/h3_base.parquet`
and never opens a shapefile. `--set spatial_source=shapefiles` keeps the legacy overlay path,
which is the one that reproduces the June 2026 workbook exactly.

## Idea

Three of the pipeline's inputs change rarely and only ever through a planning
decision: the 2050 population and jobs (TAZ), the strategic bus terminals, and the
metropolitan rings and districts. The network and demand exports change with every
model run. The base layer separates the two cadences:

```
hubs prepare-base                       once per vintage of the four shapefiles (~2.5 min)
    metro_2008 + Districts + BUS_TERMINAL_STRAT + TAZ_1270  ->  data/reference/h3_base.parquet

hubs run                                every model run (no shapefile, no overlay)
    hexagons  x  h3_base  ->  area, ring, terminal class, pop/jobs per ring
    -> hub_prioritization_results.xlsx + h3_layer.gpkg
```

`h3_base.parquet` has one row per resolution-10 cell of Israel (1.57 million rows,
12 MB; population and jobs are stored as float32 and read back as float64):

| column | content | rule |
|---|---|---|
| `h3_index` | cell id | as in the hexagon table |
| `area`, `location` | metro name and ring, or district | polygon containing the **cell centre**; metro first, district fallback; same name fixes as the polygon stage (`מחוז חיפה` → `חיפה`) |
| `term_type`, `term_id`, `bus_terminal` | strategic terminal within 200 m | terminal buffered by 200 m **intersects the cell polygon**; highest class kept |
| `pop_2050`, `emp_2050` | TAZ population and jobs allocated to the cell | intersection area share of the zone (uniform density inside a zone, as the overlay assumes); shares normalised per zone so totals are conserved exactly |

`h3_base.manifest.json` records the source files with their SHA-256, the resolution,
the buffer distance, the allocation rules and the build time. The run report records
which layer a run used. A layer built at a different resolution than the run is refused;
a run that sets a different `terminal_buffer_m` gets a warning and the layer's value.

At run time:

- `area` / `location`: lookup by `h3_index`. A hexagon with no row is reported and tagged
  `Unknown`, never silently.
- `bus_terminal`: max over the hub's cells. Because a hub polygon is the union of its
  cell polygons, this is *identical* to the hub-level buffer test.
- `pop_*` / `emp_*`: cells within `grid_disk` of the hub centroid's cell, assigned to
  rings by distance. `influence_cell_rule=fraction` (default) weights a cell by the share of its
  polygon inside the ring (exact polygon fractions are only computed for cells a ring
  boundary can cross); `center` puts it wholly in the ring its centre falls in.

## Validation

`hubs validate` requires the base layer when `spatial_source=h3_base` (the default) and the
four shapefiles when `spatial_source=shapefiles`; without a configured source the shapefiles
are required only when the base layer is absent. A default run without the layer stops with
"run `hubs prepare-base` or set `spatial_source=shapefiles`".

## The shareable cell layer

Every run writes `h3_layer.gpkg` next to the workbook (GeoPackage, layer `h3_cells`,
EPSG:2039). `h3_layer_format` selects `gpkg` (default), `geojson` (WGS84), `parquet`
(GeoParquet) or `csv` (WKT geometry column), or `none`. `h3_layer_extent` selects the cells:

| extent | cells | typical size (June 2026) |
|---|---|---|
| `hubs` | the 1,244 hub hexagons | small |
| `influence` (default) | hub cells plus every cell within the outer ring (1,500 m) of a scored hub | ~38 k cells, 14 MB GeoPackage |
| `all` | every cell of the base layer | 1.57 M cells, hundreds of MB as GeoPackage |

Columns: `h3_index, role` (`hub` / `influence` / `base`), the base attributes (`area, location,
bus_terminal, term_type, term_id, pop_2050, emp_2050`), the hub identity and network for hub
cells (`group, hub_id, nodes, modes, lines, n_lines, TotalDemand, TotalTransfers, demand_models`), the results
for scored hubs (`scored, HubNameHE, HubType, Metro, TotalScore_MC, Rank_TS_MC,
RankByHubTypeMetro`) and, for cells in a catchment, `nearest_hub, dist_nearest_hub_m,
hubs_within, n_hubs_within`. Lists are `;`-joined strings so the file reads the same in
QGIS, ArcGIS, DuckDB and PostGIS.

`hubs export-h3 --out FILE [--format gpkg|geojson|parquet|csv]` writes the base layer on
its own (every cell, `role = base`) independently of a run.

## Measured against the shapefile stages (June 2026 inputs, 142 scored hubs)

`python scripts/compare_base_layer.py --cell-rule fraction`

| | `center` | `fraction` |
|---|---|---|
| bus_terminal differs | 0 hubs | 0 hubs |
| HubType differs | 0 | 0 |
| `area` differs (hexagons) | 1 (unscored) | 1 (unscored) |
| ring tag differs (hexagons / scored hubs) | 19 / 4 | 19 / 4 |
| pop/emp median relative difference, inner ring | 5.5 % | 0.3 % |
| pop/emp p90 relative difference, inner ring | 7.7 % | 1.2 % |
| total pop+emp within 1,500 m over all hubs | +0.60 % | +0.11 % |
| `TotalScore_MC` mean abs. difference | 0.010 | 0.006 |
| `RankByHubTypeMetro` changed | 4 hubs (by 1) | 2 hubs (by 1) |
| run time of the spatial stages | ≈ same as shapefiles | +25 s |

The inner ring at resolution 10 (cells ≈ 150 m across against a 500 m radius) is where
the `center` rule discretises most; `fraction` removes almost all of it. **`fraction` is the default.**

### The ring-tag differences are a fix, not an error

The polygon stage tags a hexagon with the *first* metro polygon, in layer order, that
intersects it. For a hexagon straddling a ring boundary the tag therefore depends on
the order of the shapefile, not on where the hexagon lies. The base layer uses the
polygon containing the cell centre, which for every affected hexagon is also the
polygon holding most of its area:

| hub | hexagon share by ring | shapefile tag | base layer tag | effect |
|---|---|---|---|---|
| 524 תחנת רכבת קרית מוצקין | 41 % גלעין / 59 % טבעת פנימית | גלעין | טבעת פנימית | RegionLocation 3 → 2; `TotalScore_MC` 4.60 → 4.01; rank 3 → 4 in חיפה |
| 546 (three hexagons) | 1–11 % פנימית / 89–99 % חיצונית | טבעת פנימית | טבעת חיצונית | score unchanged (group takes its first hexagon's tag) |
| 630 | 52 % גלעין / 48 % פנימית | טבעת פנימית | גלעין | small |
| 303 | 14 % חיצונית / 86 % תיכונה | טבעת חיצונית | טבעת תיכונה | small |

Because the score is normalised per tier, a hub whose ring changes can move by several
tenths of a point; no hub changes tier and at most one rank position moves.

## What this changes for the golden reproduction

The default run reproduces the June 2026 workbook for group IDs, nodes, demand, lines,
modes, tiers, names and terminals; population and jobs are within about one percent
rather than exact, and the four hubs above carry the corrected ring.
`--set spatial_source=shapefiles` together with the legacy ring settings in
`DEVIATIONS.md` reproduces the workbook's scores exactly (141 of 142 hubs).

## Rebuilding

```bash
hubs prepare-base                                  # from data/reference/*.shp, writes h3_base.parquet + manifest
hubs prepare-base --input-dir new_layers/          # same-named shapefiles there override the reference copies
hubs prepare-base --resolution 10 --terminal-buffer-m 200
python scripts/compare_base_layer.py --input-dir my_run    # H3 layer vs shapefile overlay on one run
```

Rebuild whenever one of the four shapefiles changes; the manifest's hashes say which
vintage a layer came from. The layer is committed to the repository (12 MB per vintage);
no Git LFS is needed at this rate of change.

**You cannot forget the rebuild.** `hubs validate` and `hubs run` compare the SHA-256 of every
source shapefile present next to the layer (main file and sidecars) with the manifest. A
changed or renamed source stops the run with
`h3_base is stale for 'taz': TAZ_1270.dbf changed since the layer was built on …; run 'hubs prepare-base'`.
`--set on_stale_base_layer=warn` turns that into a report warning; a source that is absent is
not checked (the layer is then simply not verifiable), and `spatial_source=shapefiles` skips
the check because it does not read the layer. After the rebuild, commit the shapefile, the
layer and the manifest together.

## Storage choices

- Population and jobs are float32 on disk (7 significant digits, far below the method's
  precision) and float64 in memory. This halved the file from 20 MB to 12 MB.
- H3 `compact_cells` was evaluated and not adopted: it only compresses the categorical
  area/ring part (1.57 M cells to 55 k), saves about 1 MB, and would make the layer harder
  to join as a plain table.
- Cells that the districts do not cover but a TAZ does (mostly desert zones with a few
  residents spread over many cells) are kept, so a node anywhere in a zone finds a row.
