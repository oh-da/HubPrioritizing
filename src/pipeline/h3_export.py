"""
Shareable H3 cell layer: the base data plus the run's hub data, one row per cell.

``hubs run`` writes ``h3_layer.<ext>`` next to the workbook (``h3_layer_format`` /
``h3_layer_extent`` in the configuration); ``hubs export-h3`` writes the base layer on
its own. Every cell carries the base attributes (area, ring, terminal, pop/jobs); hub
cells also carry the hub's identity, network and scores; cells within the outer
catchment ring of a scored hub carry which hubs reach them.

Formats: GeoPackage (``gpkg``, one layer ``h3_cells``, EPSG:2039), GeoJSON (WGS84),
GeoParquet (``parquet``) and CSV with a WKT geometry column (EPSG:2039). List-valued
columns are ``;``-joined strings so every format reads the same in GIS and SQL.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import shapely

from ..config import CRS_ISRAEL_TM, CRS_WGS84
from .base_layer import _to_wgs, cell_centres_itm, cell_polygons_itm, grid_disk_radius

H3_LAYER_NAME = "h3_cells"
H3_LAYER_FORMATS = {"gpkg": ".gpkg", "geojson": ".geojson", "parquet": ".parquet", "csv": ".csv"}

HUB_RESULT_COLUMNS = ("HubNameHE", "HubType", "Metro", "TotalScore_MC", "Rank_TS_MC", "RankByHubTypeMetro")
LAYER_COLUMNS = (
    "h3_index",
    "role",
    "area",
    "location",
    "bus_terminal",
    "term_type",
    "term_id",
    "pop_2050",
    "emp_2050",
    "group",
    "hub_id",
    "HubNameHE",
    "HubType",
    "Metro",
    "scored",
    "TotalScore_MC",
    "Rank_TS_MC",
    "RankByHubTypeMetro",
    "nodes",
    "modes",
    "lines",
    "n_lines",
    "TotalDemand",
    "TotalTransfers",
    "demand_models",
    "nearest_hub",
    "dist_nearest_hub_m",
    "hubs_within",
    "n_hubs_within",
)


def _join(values) -> str | None:
    if isinstance(values, (list, tuple, set, np.ndarray)):
        return ";".join(str(v) for v in values)
    return None if values is None or (isinstance(values, float) and math.isnan(values)) else str(values)


def hub_cell_table(hexes: pd.DataFrame, results: pd.DataFrame | None) -> pd.DataFrame:
    """One row per hub hexagon: identity, network and, for scored hubs, the results."""
    out = pd.DataFrame(
        {
            "h3_index": hexes["h3_index"].astype(str).to_numpy(),
            "group": hexes["group"].to_numpy(),
            "hub_id": hexes["hub_id"].to_numpy() if "hub_id" in hexes.columns else None,
            "nodes": [_join(v) for v in hexes["node"]] if "node" in hexes.columns else None,
            "modes": [_join(v) for v in hexes["Mode_Planned"]] if "Mode_Planned" in hexes.columns else None,
            "lines": [_join(v) for v in hexes["Line_Unique"]] if "Line_Unique" in hexes.columns else None,
            "n_lines": hexes["Line_Nunique"].to_numpy() if "Line_Nunique" in hexes.columns else None,
            "TotalDemand": hexes["TotalDemand"].to_numpy() if "TotalDemand" in hexes.columns else None,
            "TotalTransfers": hexes["TotalTransfers"].to_numpy() if "TotalTransfers" in hexes.columns else None,
            "demand_models": [_join(v) for v in hexes["DemandModels"]] if "DemandModels" in hexes.columns else None,
        }
    )
    out["scored"] = False
    for c in HUB_RESULT_COLUMNS:
        out[c] = None
    if results is not None and len(results):
        res = results.set_index("group")
        hit = out["group"].isin(res.index)
        out.loc[hit, "scored"] = True
        for c in HUB_RESULT_COLUMNS:
            if c in res.columns:
                out.loc[hit, c] = out.loc[hit, "group"].map(res[c]).to_numpy()
    return out


def influence_cells(
    groups: gpd.GeoDataFrame, results: pd.DataFrame | None, outer_m: float, resolution: int
) -> pd.DataFrame:
    """Cells whose centre lies within ``outer_m`` of a scored hub's centroid.

    Returns ``h3_index, nearest_hub, dist_nearest_hub_m, hubs_within, n_hubs_within``.
    """
    if results is None or len(results) == 0 or len(groups) == 0:
        return pd.DataFrame(columns=["h3_index", "nearest_hub", "dist_nearest_hub_m", "hubs_within", "n_hubs_within"])
    scored = groups[groups["group"].isin(results["group"])]
    centroids = scored.to_crs(CRS_ISRAEL_TM).geometry.centroid
    k = grid_disk_radius(outer_m, resolution)
    parts = []
    for grp, cx, cy in zip(scored["group"].to_numpy(), centroids.x.to_numpy(), centroids.y.to_numpy()):
        lng, lat = _to_wgs.transform(cx, cy)
        cells = list(h3.grid_disk(h3.latlng_to_cell(lat, lng, resolution), k))
        x, y = cell_centres_itm(cells)
        dist = np.hypot(x - cx, y - cy)
        keep = dist <= outer_m
        parts.append(pd.DataFrame({"h3_index": np.asarray(cells, dtype=object)[keep], "group": grp, "dist": dist[keep]}))
    df = pd.concat(parts, ignore_index=True).sort_values(["h3_index", "dist"])
    nearest = df.drop_duplicates("h3_index").set_index("h3_index")
    within = df.groupby("h3_index")["group"].agg(lambda s: ";".join(str(g) for g in sorted(set(s))))
    out = pd.DataFrame(
        {
            "h3_index": nearest.index.astype(str),
            "nearest_hub": nearest["group"].to_numpy(),
            "dist_nearest_hub_m": nearest["dist"].round(1).to_numpy(),
            "hubs_within": within.reindex(nearest.index).to_numpy(),
            "n_hubs_within": df.groupby("h3_index").size().reindex(nearest.index).to_numpy(),
        }
    ).reset_index(drop=True)
    return out


def build_h3_layer(
    base: pd.DataFrame,
    hexes: pd.DataFrame | None = None,
    results: pd.DataFrame | None = None,
    groups: gpd.GeoDataFrame | None = None,
    rings: Sequence[int] = (500, 1000, 1500),
    resolution: int = 10,
    extent: str = "influence",
) -> gpd.GeoDataFrame:
    """Assemble the cell layer (EPSG:2039 polygons) for ``extent`` = hubs | influence | all."""
    if extent not in ("hubs", "influence", "all"):
        raise ValueError("extent must be 'hubs', 'influence' or 'all'")
    hubs = hub_cell_table(hexes, results) if hexes is not None and len(hexes) else None
    infl = None
    if extent != "hubs" and groups is not None and results is not None:
        infl = influence_cells(groups, results, float(max(rings)), resolution)

    cells: list[str] = []
    if extent == "all":
        cells = list(base.index.astype(str))
    if hubs is not None:
        cells.extend(hubs["h3_index"])
    if infl is not None:
        cells.extend(infl["h3_index"])
    cells = sorted(set(cells))

    layer = pd.DataFrame({"h3_index": cells})
    layer = layer.merge(base.reset_index()[["h3_index", "area", "location", "bus_terminal", "term_type", "term_id", "pop_2050", "emp_2050"]], on="h3_index", how="left")
    if hubs is not None:
        layer = layer.merge(hubs, on="h3_index", how="left")
    if infl is not None:
        layer = layer.merge(infl, on="h3_index", how="left")
    for c in LAYER_COLUMNS:
        if c not in layer.columns:
            layer[c] = None
    is_hub = layer["group"].notna()
    is_infl = layer["nearest_hub"].notna()
    layer["role"] = np.where(is_hub, "hub", np.where(is_infl, "influence", "base"))
    layer["scored"] = layer["scored"].fillna(False).astype(bool)
    layer["bus_terminal"] = layer["bus_terminal"].fillna(0).astype(int)
    for c in ("pop_2050", "emp_2050"):
        layer[c] = layer[c].fillna(0.0).astype(float)
    layer = layer[list(LAYER_COLUMNS)]
    # GIS drivers want plain types: object columns with None become strings/NaN as needed
    for c in ("group", "n_lines", "Rank_TS_MC", "RankByHubTypeMetro", "nearest_hub", "n_hubs_within"):
        layer[c] = pd.to_numeric(layer[c], errors="coerce").astype("Int64")
    for c in ("TotalScore_MC", "TotalDemand", "TotalTransfers", "dist_nearest_hub_m", "term_id"):
        layer[c] = pd.to_numeric(layer[c], errors="coerce").astype(float)
    for c in ("area", "location", "term_type", "hub_id", "HubNameHE", "HubType", "Metro", "nodes", "modes", "lines", "demand_models", "hubs_within", "role"):
        layer[c] = layer[c].astype(object).where(layer[c].notna(), None)
    geometry = cell_polygons_itm(cells)
    return gpd.GeoDataFrame(layer, geometry=geometry, crs=CRS_ISRAEL_TM)


def write_h3_layer(layer: gpd.GeoDataFrame, path: Path | str, fmt: str = "gpkg") -> Path:
    """Write the layer; the extension is set from ``fmt`` when missing."""
    if fmt not in H3_LAYER_FORMATS:
        raise ValueError(f"fmt must be one of {list(H3_LAYER_FORMATS)}")
    path = Path(path)
    if path.suffix.lower() != H3_LAYER_FORMATS[fmt]:
        path = path.with_suffix(H3_LAYER_FORMATS[fmt])
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "gpkg":
        if path.exists():
            path.unlink()
        layer.to_file(path, layer=H3_LAYER_NAME, driver="GPKG")
    elif fmt == "geojson":
        layer.to_crs(CRS_WGS84).to_file(path, driver="GeoJSON")
    elif fmt == "parquet":
        layer.to_parquet(path, index=False)
    else:
        plain = pd.DataFrame(layer.drop(columns=layer.geometry.name))
        plain["geometry_wkt"] = shapely.to_wkt(layer.geometry.to_numpy(), rounding_precision=2)
        plain.to_csv(path, index=False, encoding="utf-8-sig")
    return path
