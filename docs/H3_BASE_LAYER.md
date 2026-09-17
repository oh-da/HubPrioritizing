# The H3 base layer (`hubs prepare-base`)

**Status: prototype, opt-in.** The default run still tags hubs from the shapefiles.
Switch with `--set spatial_source=h3_base`.

## Idea

Three of the pipeline's inputs change rarely and only ever through a planning
decision: the 2050 population and jobs (TAZ), the strategic bus terminals, and the
metropolitan rings and districts. The network and demand exports change with every
model run. The base layer separates the two cadences:

```
hubs prepare-base                       once per vintage of the four shapefiles (~2.5 min)
    metro_2008 + Districts + BUS_TERMINAL_STRAT + TAZ_1270  ->  data/reference/h3_base.parquet

hubs run --set spatial_source=h3_base   every model run (no shapefile, no overlay)
    hexagons  x  h3_base  ->  area, ring, terminal class, pop/jobs per ring
```

`h3_base.parquet` has one row per resolution-10 cell of Israel (1.57 million rows,
about 20 MB):

| column | content | rule |
|---|---|---|
| `h3_index` | cell id | as in the hexagon table |
| `area`, `location` | metro name and ring, or district | polygon containing the **cell centre**; metro first, district fallback; same name fixes as the polygon stage (`מחוז חיפה` → `חיפה`) |
| `term_type`, `term_id`, `bus_terminal` | strategic terminal within 200 m | terminal buffered by 200 m **intersects the cell polygon**; highest class kept |
| `pop_2050`, `emp_2050` | TAZ population and jobs allocated to the cell | intersection area share of the zone (uniform density inside a zone, as the overlay assumes); shares normalised per zone so totals are conserved exactly |

`h3_base.manifest.json` records the source files with their SHA-256, the resolution,
the buffer distance, the allocation rules and the build time. The run report records
which layer a run used. A layer built at a different resolution than the run is refused.

At run time:

- `area` / `location`: lookup by `h3_index`.
- `bus_terminal`: max over the hub's cells. Because a hub polygon is the union of its
  cell polygons, this is *identical* to the hub-level buffer test.
- `pop_*` / `emp_*`: cells within `grid_disk` of the hub centroid's cell, assigned to
  rings by distance. `influence_cell_rule=fraction` (default) weights a cell by the share of its
  polygon inside the ring (exact polygon fractions are only computed for cells a ring
  boundary can cross); `center` puts it wholly in the ring its centre falls in.

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

With `spatial_source=h3_base` the June 2026 workbook is reproduced for group IDs,
nodes, demand, lines, modes, tiers, names and terminals, but population and jobs are
within a few percent rather than exact, and the four hubs above carry the corrected
ring. `spatial_source=shapefiles` (the default) keeps the exact legacy path.

## Rebuilding

```bash
hubs prepare-base                                  # from data/reference/*.shp, writes h3_base.parquet + manifest
hubs prepare-base --input-dir new_layers/          # same-named shapefiles there override the reference copies
hubs prepare-base --resolution 10 --terminal-buffer-m 200
python scripts/compare_base_layer.py --input-dir my_run --cell-rule fraction   # before switching
```

Rebuild whenever one of the four shapefiles changes; the manifest's hashes say which
vintage a layer came from. A run whose `h3_resolution` differs from the layer's is refused.

## Open points before making it the default

1. **Layer size in git.** 20 MB per vintage. Options: keep as is (a rebuild every year
   or two is fine), Git LFS, or store `h3_index` as `uint64` and round the floats
   (roughly halves it).
2. **Coverage.** Cells the districts do not cover but a TAZ does are kept (416 k cells,
   mostly desert zones with a few residents each). A node in a cell with no row is
   reported, never silently zero.
3. **Validation.** With `spatial_source=h3_base` the four shapefiles are no longer needed
   at run time; `hubs validate` still requires them. To be relaxed once the layer is the
   default.
4. **Terminal buffer.** Baked into the layer; a run that sets a different
   `terminal_buffer_m` gets a warning and the layer's value.
