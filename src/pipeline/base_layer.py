"""
H3 base layer: the slow-changing spatial context pre-allocated to H3 cells.

``hubs prepare-base`` runs :func:`build_base_layer` once per vintage of the reference
layers and writes one Parquet table, one row per resolution-10 cell of Israel:

======================  =====================================================================
column                  content
======================  =====================================================================
``h3_index``            cell id (string, as in the hexagon table)
``area``                metropolitan area (``METRO_NAME``) or district (``MACHOZ``) containing
                        the cell centre; ``Unknown`` when neither does
``location``            metropolitan ring (``ZONE_NAME``) or the district name
``term_type``           class of the strategic bus terminal whose ``terminal_buffer_m`` buffer
                        touches the cell polygon (the highest-scoring one when several do)
``term_id``             its id column, when the layer has one
``bus_terminal``        the 0-3 terminal score of that class
``pop_2050``            population allocated from the TAZ layer
``emp_2050``            jobs allocated from the TAZ layer
======================  =====================================================================

Allocation rules (see ``docs/H3_BASE_LAYER.md``):

- *Population and jobs*: each TAZ is spread over the cells it overlaps proportionally to
  the intersection area (uniform density within the zone, the same assumption the
  polygon overlay of :func:`aggregate.add_influence_area` makes). Shares are normalised
  per zone so totals are conserved exactly.
- *Terminals*: a cell carries a terminal when the terminal polygon buffered by
  ``terminal_buffer_m`` intersects the cell polygon. Because a hub polygon is the union
  of its cell polygons, "max over the hub's cells" is identical to the hub-level
  buffer test.
- *Area and ring*: by cell centre. The polygon stage tags a hexagon by intersection
  (first match), so cells straddling a ring boundary may differ.

The runtime side (:func:`tag_area_and_location_from_base`,
:func:`tag_bus_terminals_from_base`, :func:`add_influence_area_from_base`) needs only
the table and ``h3``: no shapefiles, no overlay.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from ..config import CRS_ISRAEL_TM, CRS_WGS84, TERMINAL_PROXIMITY_DISTANCE_M
from .aggregate import TAZ_EMP_COL, TAZ_POP_COL, TERMINAL_ID_CANDIDATES, TERMINAL_TYPE_CANDIDATES, bus_terminal_score, ring_column_names
from .report import RunReport
from .spatial_tags import (
    AREA_COL,
    DISTRICT_NAME_CANDIDATES,
    LOCATION_COL,
    METRO_NAME_CANDIDATES,
    UNKNOWN,
    ZONE_NAME_CANDIDATES,
    _first_present,
    fix_hebrew_name,
)

BASE_LAYER_COLUMNS = ("h3_index", "area", "location", "term_type", "term_id", "bus_terminal", "pop_2050", "emp_2050")
BASE_LAYER_FILENAME = "h3_base.parquet"
MANIFEST_SUFFIX = ".manifest.json"
BASE_LAYER_FORMAT = 1
LARGE_POLYGON_KM2 = 100.0  # above this, fill coarse and expand children (see cells_covering)

_to_itm = Transformer.from_crs(CRS_WGS84, CRS_ISRAEL_TM, always_xy=True)
_to_wgs = Transformer.from_crs(CRS_ISRAEL_TM, CRS_WGS84, always_xy=True)


# ----------------------------------------------------------------------------------------
# cell geometry helpers
# ----------------------------------------------------------------------------------------


def cell_centres_itm(cells: Sequence[str]) -> tuple[np.ndarray, np.ndarray]:
    """``(x, y)`` of the cell centres in EPSG:2039."""
    if len(cells) == 0:
        return np.empty(0), np.empty(0)
    latlng = np.array([h3.cell_to_latlng(c) for c in cells], dtype=float)
    x, y = _to_itm.transform(latlng[:, 1], latlng[:, 0])
    return np.asarray(x), np.asarray(y)


def cell_polygons_itm(cells: Sequence[str]) -> np.ndarray:
    """Shapely polygons of the cells in EPSG:2039 (one array, vectorised construction)."""
    if len(cells) == 0:
        return np.empty(0, dtype=object)
    rings = [h3.cell_to_boundary(c) for c in cells]  # [(lat, lng), ...] per cell, 5-6 vertices
    lengths = np.fromiter((len(r) for r in rings), dtype=int, count=len(rings))
    flat = np.concatenate([np.asarray(r, dtype=float) for r in rings])
    x, y = _to_itm.transform(flat[:, 1], flat[:, 0])
    coords = np.column_stack([x, y])
    offsets = np.concatenate([[0], np.cumsum(lengths)])
    polys = np.empty(len(cells), dtype=object)
    for i in range(len(cells)):
        ring = coords[offsets[i] : offsets[i + 1]]
        polys[i] = shapely.Polygon(np.vstack([ring, ring[:1]]))
    return polys


def cells_covering(geoms_wgs: Iterable, resolution: int, contain: str = "overlap") -> list[str]:
    """Cells of ``resolution`` that overlap (or whose centre lies in) the given WGS84 geometries.

    Small polygons are filled directly. Large ones (bounding box above
    ``LARGE_POLYGON_KM2``) are filled three resolutions coarser and expanded to children,
    which is far faster than filling a country-sized polygon at resolution 10 directly and
    over-covers the boundary; the exact containment test is then the caller's.
    """
    coarse = max(resolution - 3, 0)
    out: set[str] = set()
    for geom in geoms_wgs:
        if geom is None or geom.is_empty:
            continue
        parts = geom.geoms if hasattr(geom, "geoms") else [geom]
        for part in parts:
            shape = h3.geo_to_h3shape(part)
            minx, miny, maxx, maxy = part.bounds
            bbox_km2 = (maxx - minx) * 94.0 * (maxy - miny) * 111.0  # degrees -> km at Israel's latitude
            if coarse == resolution or bbox_km2 < LARGE_POLYGON_KM2:
                out.update(h3.h3shape_to_cells_experimental(shape, resolution, contain=contain))
                continue
            for parent in h3.h3shape_to_cells_experimental(shape, coarse, contain="overlap"):
                out.update(h3.cell_to_children(parent, resolution))
    return sorted(out)


def _tag_by_centre(cells: Sequence[str], layer: gpd.GeoDataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """First polygon (layer order) containing each cell centre; NaN where none does."""
    x, y = cell_centres_itm(cells)
    pts = gpd.GeoDataFrame({"_i": np.arange(len(cells))}, geometry=gpd.points_from_xy(x, y), crs=CRS_ISRAEL_TM)
    lyr = layer.to_crs(CRS_ISRAEL_TM)[list(columns) + [layer.geometry.name]].reset_index(drop=True)
    lyr["_order"] = np.arange(len(lyr))
    joined = gpd.sjoin(pts, lyr, how="left", predicate="within").sort_values(["_i", "_order"])
    joined = joined[~joined["_i"].duplicated(keep="first")].set_index("_i")
    return joined.reindex(range(len(cells)))[list(columns)].reset_index(drop=True)


# ----------------------------------------------------------------------------------------
# builders
# ----------------------------------------------------------------------------------------


def allocate_taz(taz: gpd.GeoDataFrame, resolution: int, report: RunReport | None = None) -> pd.DataFrame:
    """``h3_index, pop_2050, emp_2050``: every TAZ spread over its cells by intersection area."""
    for c in (TAZ_POP_COL, TAZ_EMP_COL):
        if c not in taz.columns:
            raise ValueError(f"TAZ layer is missing '{c}'")
    itm = taz.to_crs(CRS_ISRAEL_TM).reset_index(drop=True)
    wgs = itm.to_crs(CRS_WGS84)
    values = {}
    for c in (TAZ_POP_COL, TAZ_EMP_COL):
        numeric = pd.to_numeric(itm[c], errors="coerce")
        bad = int(numeric.isna().sum())
        if bad and report is not None:
            report.warn("base_layer", f"{bad} TAZ rows have a non-numeric {c}; treated as 0")
        values[c] = numeric.fillna(0.0).astype(float).to_numpy()

    idx_parts: list[np.ndarray] = []
    share_parts: list[np.ndarray] = []
    zone_parts: list[np.ndarray] = []
    n_tiny = 0
    for i, (geom_itm, geom_wgs) in enumerate(zip(itm.geometry, wgs.geometry)):
        if geom_itm is None or geom_itm.is_empty or geom_itm.area <= 0:
            continue
        cells = cells_covering([geom_wgs], resolution, contain="overlap")
        if not cells:  # a zone smaller than a cell: give it to the cell under its centroid
            c = geom_wgs.centroid
            cells = [h3.latlng_to_cell(c.y, c.x, resolution)]
            areas = np.array([1.0])
            n_tiny += 1
        else:
            polys = cell_polygons_itm(cells)
            areas = shapely.area(shapely.intersection(polys, geom_itm))
            keep = areas > 0
            cells = [c for c, k in zip(cells, keep) if k]
            areas = areas[keep]
            if len(cells) == 0:
                c = geom_wgs.centroid
                cells = [h3.latlng_to_cell(c.y, c.x, resolution)]
                areas = np.array([1.0])
                n_tiny += 1
        idx_parts.append(np.asarray(cells, dtype=object))
        share_parts.append(areas / areas.sum())
        zone_parts.append(np.full(len(cells), i))

    if not idx_parts:
        return pd.DataFrame({"h3_index": pd.Series(dtype=str), "pop_2050": pd.Series(dtype=float), "emp_2050": pd.Series(dtype=float)})
    cells_all = np.concatenate(idx_parts)
    share = np.concatenate(share_parts)
    zone = np.concatenate(zone_parts)
    df = pd.DataFrame(
        {
            "h3_index": cells_all.astype(str),
            "pop_2050": values[TAZ_POP_COL][zone] * share,
            "emp_2050": values[TAZ_EMP_COL][zone] * share,
        }
    )
    out = df.groupby("h3_index", sort=True, as_index=False)[["pop_2050", "emp_2050"]].sum()
    if report is not None:
        report.info(
            "base_layer",
            f"TAZ allocated to {len(out)} cells; totals pop {out['pop_2050'].sum():.0f} / emp {out['emp_2050'].sum():.0f}",
            zones=int(len(itm)),
            zones_smaller_than_a_cell=n_tiny,
        )
    return out


def terminals_to_cells(
    terminals: gpd.GeoDataFrame, resolution: int, buffer_m: float = TERMINAL_PROXIMITY_DISTANCE_M, report: RunReport | None = None
) -> pd.DataFrame:
    """``h3_index, term_type, term_id, bus_terminal`` for every cell a buffered terminal touches."""
    type_col = next((c for c in TERMINAL_TYPE_CANDIDATES if c in terminals.columns), None)
    if type_col is None:
        raise ValueError(f"terminal layer needs one of {TERMINAL_TYPE_CANDIDATES}; has {list(terminals.columns)}")
    id_col = next((c for c in TERMINAL_ID_CANDIDATES if c in terminals.columns), None)

    itm = terminals.to_crs(CRS_ISRAEL_TM).reset_index(drop=True)
    buffered = itm.geometry.buffer(buffer_m)
    buffered_wgs = gpd.GeoSeries(buffered, crs=CRS_ISRAEL_TM).to_crs(CRS_WGS84)
    rows = []
    for i, (geom_itm, geom_wgs) in enumerate(zip(buffered, buffered_wgs)):
        if geom_itm is None or geom_itm.is_empty:
            continue
        cells = cells_covering([geom_wgs], resolution, contain="overlap")
        if not cells:
            continue
        polys = cell_polygons_itm(cells)
        hit = shapely.intersects(polys, geom_itm)
        for c in np.asarray(cells, dtype=object)[hit]:
            rows.append((str(c), itm.at[i, type_col], itm.at[i, id_col] if id_col else None))
    df = pd.DataFrame(rows, columns=["h3_index", "term_type", "term_id"])
    df["bus_terminal"] = df["term_type"].map(bus_terminal_score).astype(int)
    # the highest class wins when several terminals touch a cell (as tag_bus_terminals does)
    df = df.sort_values(["h3_index", "bus_terminal"], ascending=[True, False]).drop_duplicates("h3_index").reset_index(drop=True)
    if report is not None:
        report.info("base_layer", f"{len(terminals)} terminals tagged {len(df)} cells within {buffer_m:.0f} m")
    return df


def tag_cells_area_and_location(
    cells: Sequence[str], metro: gpd.GeoDataFrame | None, districts: gpd.GeoDataFrame | None, report: RunReport | None = None
) -> pd.DataFrame:
    """``h3_index, area, location`` by cell centre: metro ring first, district as fallback."""
    out = pd.DataFrame({"h3_index": list(cells)})
    out[AREA_COL] = None
    out[LOCATION_COL] = None
    if metro is not None and len(metro):
        metro_col = _first_present(metro.columns, METRO_NAME_CANDIDATES)
        zone_col = _first_present(metro.columns, ZONE_NAME_CANDIDATES)
        if metro_col is not None:
            cols = [c for c in (metro_col, zone_col) if c]
            tags = _tag_by_centre(cells, metro, cols)
            out[AREA_COL] = tags[metro_col].to_numpy()
            out[LOCATION_COL] = tags[zone_col].to_numpy() if zone_col else tags[metro_col].to_numpy()
    if districts is not None and len(districts):
        district_col = _first_present(districts.columns, DISTRICT_NAME_CANDIDATES)
        untagged = out[AREA_COL].isna().to_numpy()
        if district_col is not None and untagged.any():
            sub = [c for c, u in zip(cells, untagged) if u]
            tags = _tag_by_centre(sub, districts, [district_col])[district_col].to_numpy()
            out.loc[untagged, AREA_COL] = tags
            loc = out.loc[untagged, LOCATION_COL].to_numpy()
            out.loc[untagged, LOCATION_COL] = np.where(pd.isna(loc), tags, loc)
    # same vocabulary as the polygon stage: the notebook's name fixes fold district names
    # into the metro vocabulary ('מחוז חיפה' -> 'חיפה'), which the scoring relies on
    out[AREA_COL] = out[AREA_COL].map(lambda v: fix_hebrew_name(v) if isinstance(v, str) else UNKNOWN)
    out[LOCATION_COL] = out[LOCATION_COL].map(lambda v: fix_hebrew_name(v) if isinstance(v, str) else UNKNOWN)
    if report is not None:
        report.info("base_layer", "area tags", counts=out[AREA_COL].value_counts().to_dict())
    return out


def build_base_layer(
    metro: gpd.GeoDataFrame | None,
    districts: gpd.GeoDataFrame | None,
    terminals: gpd.GeoDataFrame | None,
    taz: gpd.GeoDataFrame | None,
    resolution: int = 10,
    terminal_buffer_m: float = TERMINAL_PROXIMITY_DISTANCE_M,
    report: RunReport | None = None,
) -> pd.DataFrame:
    """Combine the four reference layers into one table with :data:`BASE_LAYER_COLUMNS`.

    The cell universe is every cell whose centre lies in a district or metro polygon,
    plus every cell that carries population, jobs or a terminal.
    """
    universe: set[str] = set()
    for layer in (districts, metro):
        if layer is not None and len(layer):
            universe.update(cells_covering(layer.to_crs(CRS_WGS84).geometry, resolution))
    pop = allocate_taz(taz, resolution, report) if taz is not None and len(taz) else None
    term = terminals_to_cells(terminals, resolution, terminal_buffer_m, report) if terminals is not None and len(terminals) else None
    for part in (pop, term):
        if part is not None:
            universe.update(part["h3_index"])
    cells = sorted(universe)

    tags = tag_cells_area_and_location(cells, metro, districts, report)
    # cells that came in through the coarse fill but whose centre lies outside every polygon
    # and carry no data are dropped
    out = tags
    if term is not None:
        out = out.merge(term, on="h3_index", how="left")
    else:
        out["term_type"] = None
        out["term_id"] = None
        out["bus_terminal"] = 0
    if pop is not None:
        out = out.merge(pop, on="h3_index", how="left")
    else:
        out["pop_2050"] = 0.0
        out["emp_2050"] = 0.0
    out["bus_terminal"] = out["bus_terminal"].fillna(0).astype(int)
    out["pop_2050"] = out["pop_2050"].fillna(0.0).astype(float)
    out["emp_2050"] = out["emp_2050"].fillna(0.0).astype(float)
    empty = (out[AREA_COL] == UNKNOWN) & (out["bus_terminal"] == 0) & (out["pop_2050"] == 0) & (out["emp_2050"] == 0)
    out = out[~empty].reset_index(drop=True)
    out = out[list(BASE_LAYER_COLUMNS)]
    out["term_type"] = out["term_type"].astype(object).where(out["term_type"].notna(), None)
    out["term_id"] = out["term_id"].astype(object).where(out["term_id"].notna(), None)
    if report is not None:
        report.set_metric("base_layer_cells", len(out))
        report.set_metric("base_layer_resolution", resolution)
    return out


# ----------------------------------------------------------------------------------------
# storage
# ----------------------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(sources: dict[str, Path | None], resolution: int, terminal_buffer_m: float, n_rows: int) -> dict:
    """Provenance record written next to the layer (``h3_base.manifest.json``)."""
    src = {}
    for key, path in sources.items():
        if path is None:
            continue
        p = Path(path)
        files = sorted(p.parent.glob(p.stem + ".*")) if p.suffix.lower() == ".shp" else [p]
        src[key] = {
            "file": p.name,
            "sha256": _sha256(p),
            "sidecars": {f.name: _sha256(f) for f in files if f != p},
        }
    return {
        "format": BASE_LAYER_FORMAT,
        "built": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "h3_version": h3.__version__,
        "resolution": resolution,
        "terminal_buffer_m": terminal_buffer_m,
        "rows": n_rows,
        "columns": list(BASE_LAYER_COLUMNS),
        "allocation": {
            "pop_emp": "TAZ value x (cell ∩ zone area / Σ cell ∩ zone areas)",
            "terminal": "cell polygon intersects terminal buffered by terminal_buffer_m; highest class kept",
            "area_location": "polygon containing the cell centre; metro ring first, district fallback",
        },
        "sources": src,
    }


def manifest_path(layer_path: Path | str) -> Path:
    p = Path(layer_path)
    return p.with_name(p.name[: -len(p.suffix)] + MANIFEST_SUFFIX)


def write_base_layer(df: pd.DataFrame, path: Path | str, manifest: dict | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df[list(BASE_LAYER_COLUMNS)].to_parquet(path, index=False, compression="zstd")
    if manifest is not None:
        manifest_path(path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_base_layer(path: Path | str) -> tuple[pd.DataFrame, dict | None]:
    """Read the layer (indexed by ``h3_index``) and its manifest when present."""
    path = Path(path)
    df = pd.read_parquet(path)
    missing = [c for c in BASE_LAYER_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name} is missing base layer columns {missing}")
    df = df.set_index("h3_index", drop=True)
    if df.index.duplicated().any():
        raise ValueError(f"{path.name} has duplicated h3_index values")
    mp = manifest_path(path)
    manifest = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else None
    return df, manifest


# ----------------------------------------------------------------------------------------
# runtime lookups (replace the shapefile stages)
# ----------------------------------------------------------------------------------------


def tag_area_and_location_from_base(hexes: gpd.GeoDataFrame, base: pd.DataFrame, report: RunReport | None = None) -> gpd.GeoDataFrame:
    """``area`` / ``location`` of every hexagon by lookup in the base layer."""
    out = hexes.copy().reset_index(drop=True)
    hit = base.reindex(out["h3_index"].astype(str))
    area = hit[AREA_COL].to_numpy(dtype=object)
    loc = hit[LOCATION_COL].to_numpy(dtype=object)
    missing = pd.isna(area)
    out[AREA_COL] = [UNKNOWN if pd.isna(a) else a for a in area]
    out[LOCATION_COL] = [[UNKNOWN] if pd.isna(v) else [v] for v in loc]
    if report is not None:
        n = int(missing.sum())
        report.set_metric("hexes_without_area", int((out[AREA_COL] == UNKNOWN).sum()))
        if n:
            report.warn("spatial_tags", f"{n} hexagons are not in the base layer (outside its coverage?)", h3_index=out.loc[missing, "h3_index"].tolist()[:20])
    return out


def tag_bus_terminals_from_base(
    groups: gpd.GeoDataFrame, hexes: pd.DataFrame, base: pd.DataFrame, report: RunReport | None = None
) -> gpd.GeoDataFrame:
    """Highest terminal class over the hub's cells (identical to the hub-level buffer test)."""
    cells = hexes[["group", "h3_index"]].copy()
    cells["h3_index"] = cells["h3_index"].astype(str)
    hit = base.reindex(cells["h3_index"])[["term_type", "term_id", "bus_terminal"]].reset_index(drop=True)
    cells = pd.concat([cells.reset_index(drop=True), hit], axis=1)
    cells["bus_terminal"] = cells["bus_terminal"].fillna(0).astype(int)
    best = cells.sort_values(["group", "bus_terminal"], ascending=[True, False]).drop_duplicates("group").set_index("group")
    out = groups.copy()
    # object dtype on purpose: pandas' string dtype would turn None into NaN
    out["term_type"] = pd.Series([None if pd.isna(v) else v for v in out["group"].map(best["term_type"])], dtype=object, index=out.index)
    out["term_id"] = pd.Series([None if pd.isna(v) else v for v in out["group"].map(best["term_id"])], dtype=object, index=out.index)
    out["bus_terminal"] = out["group"].map(best["bus_terminal"]).fillna(0).astype(int).to_numpy()
    if report is not None:
        report.set_metric("hubs_near_terminal", int((out["bus_terminal"] > 0).sum()))
    return gpd.GeoDataFrame(out, geometry=groups.geometry.name, crs=groups.crs)


def grid_disk_radius(outer_m: float, resolution: int) -> int:
    """Number of rings of cells needed to reach ``outer_m`` from a cell centre, with margin."""
    spacing = h3.average_hexagon_edge_length(resolution, unit="m") * math.sqrt(3)  # centre-to-centre
    return int(math.ceil(outer_m / spacing)) + 2


def add_influence_area_from_base(
    groups: gpd.GeoDataFrame,
    base: pd.DataFrame,
    rings: Sequence[int],
    resolution: int = 10,
    cell_rule: str = "center",
    report: RunReport | None = None,
) -> gpd.GeoDataFrame:
    """``pop_<a>_<b>`` / ``emp_<a>_<b>`` per hub from the pre-allocated cells.

    ``cell_rule='center'`` counts a cell in the band its centre falls in;
    ``'fraction'`` weights each cell by the share of its polygon inside the band (slower,
    closer to the polygon overlay).
    """
    rings = list(rings)
    if rings != sorted(rings) or rings[0] <= 0:
        raise ValueError("rings must be strictly increasing positive outer radii")
    if cell_rule not in ("center", "fraction"):
        raise ValueError("cell_rule must be 'center' or 'fraction'")
    cols = ring_column_names(rings)
    out = groups.copy()
    for pop_col, emp_col, _, _ in cols:
        out[pop_col] = 0.0
        out[emp_col] = 0.0

    centroids = out.to_crs(CRS_ISRAEL_TM).geometry.centroid
    k = grid_disk_radius(rings[-1], resolution)
    pop_base = base["pop_2050"]
    emp_base = base["emp_2050"]
    n_zero = 0
    for row, (cx, cy) in enumerate(zip(centroids.x.to_numpy(), centroids.y.to_numpy())):
        lng, lat = _to_wgs.transform(cx, cy)
        origin = h3.latlng_to_cell(lat, lng, resolution)
        cells = list(h3.grid_disk(origin, k))
        pop = pop_base.reindex(cells).fillna(0.0).to_numpy()
        emp = emp_base.reindex(cells).fillna(0.0).to_numpy()
        keep = (pop > 0) | (emp > 0)
        if not keep.any():
            n_zero += 1
            continue
        cells = [c for c, kk in zip(cells, keep) if kk]
        pop, emp = pop[keep], emp[keep]
        if cell_rule == "center":
            x, y = cell_centres_itm(cells)
            dist = np.hypot(x - cx, y - cy)
            band = np.searchsorted(np.asarray(rings, dtype=float), dist, side="left")  # 0..len(rings)
            for b, (pop_col, emp_col, _, _) in enumerate(cols):
                m = band == b
                out.at[row, pop_col] = float(pop[m].sum())
                out.at[row, emp_col] = float(emp[m].sum())
        else:
            # exact polygon fractions only for the cells a ring boundary can cross; the rest
            # are entirely inside or outside a band and are decided by their centre distance
            x, y = cell_centres_itm(cells)
            dist = np.hypot(x - cx, y - cy)
            reach = h3.average_hexagon_edge_length(resolution, unit="m") * 1.1  # circumradius with margin
            polys = None
            cell_area = None
            centre = shapely.Point(cx, cy)
            inner_circle = None
            for pop_col, emp_col, inner, outer in cols:
                outer_circle = centre.buffer(outer, quad_segs=64)
                annulus = outer_circle if inner_circle is None else outer_circle.difference(inner_circle)
                inner_circle = outer_circle
                fully_inside = (dist + reach < outer) & ((inner == 0) | (dist - reach >= inner))
                frac = fully_inside.astype(float)
                on_edge = (np.abs(dist - outer) < reach) | ((inner > 0) & (np.abs(dist - inner) < reach))
                if on_edge.any():
                    if polys is None:
                        polys = cell_polygons_itm(cells)
                        cell_area = shapely.area(polys)
                    frac[on_edge] = shapely.area(shapely.intersection(polys[on_edge], annulus)) / cell_area[on_edge]
                out.at[row, pop_col] = float((pop * frac).sum())
                out.at[row, emp_col] = float((emp * frac).sum())
    if report is not None:
        report.set_metric("hubs_without_taz_coverage", n_zero)
        if n_zero:
            report.warn("influence", f"{n_zero} hubs have no population or jobs within {rings[-1]} m of their centroid in the base layer")
    return out
