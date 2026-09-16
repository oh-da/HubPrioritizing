"""
Parts 2.7 and 3: hexagons -> hub groups, bus terminals, influence area.

Ports cells 49, 53 and 58-70 of ``COMPLETE_TRANSIT_PIPELINE.ipynb``:

- :func:`aggregate_to_groups`  one row per ``group`` (lists flattened, demand and
  per-mode line counts summed, geometry dissolved, ``Num_Modes``)
- :func:`tag_bus_terminals`    ``term_type`` / ``term_id`` of a strategic terminal within
  200 m and the 0-3 ``bus_terminal`` score
- :func:`add_influence_area`   2050 population / jobs in concentric rings around the hub
  centroid, allocated from TAZ polygons proportionally to overlap area
"""

from __future__ import annotations

from typing import Iterable, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd

from ..config import CRS_ISRAEL_TM, MODE_LINE_COLS, TERMINAL_PROXIMITY_DISTANCE_M
from .report import RunReport

DEFAULT_RINGS: tuple[int, ...] = (500, 1000, 1500)
TERMINAL_TYPE_CANDIDATES = ("term_type", "type", "terminal_type")
TERMINAL_ID_CANDIDATES = ("id", "ID", "term_id", "OBJECTID")
FIRST_STRING_COLS = ("address", "area", "district", "metro_area")
TAZ_POP_COL = "POP_2050"
TAZ_EMP_COL = "EMPL_2050"


# ----------------------------------------------------------------------------------------
# hexagons -> groups
# ----------------------------------------------------------------------------------------


def _unique_in_order(values: Iterable) -> list:
    seen: set = set()
    out: list = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _flatten_unique(series: pd.Series) -> list:
    items = []
    for v in series:
        if isinstance(v, list):
            items.extend(v)
        elif pd.notna(v):
            items.append(v)
    return _unique_in_order(items)


def _first_string(series: pd.Series) -> str:
    for v in series:
        if isinstance(v, list):
            if v:
                return str(v[0])
            continue
        if pd.notna(v) and str(v) != "":
            return str(v)
    return "Unknown"


def _first_list(series: pd.Series) -> list:
    for v in series:
        if isinstance(v, list) and v:
            return v
        if not isinstance(v, list) and pd.notna(v) and v != "":
            return [str(v)]
    return ["Unknown"]


def _merge_counts(series: pd.Series) -> dict:
    out: dict = {}
    for d in series:
        if isinstance(d, dict):
            for k, v in d.items():
                out[k] = out.get(k, 0) + v
    return out


def aggregate_to_groups(hexes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Collapse hexagons into one row per ``group``.

    - ``h3_index``, ``Line_Unique``: sorted unique lists; ``node``: sorted unique ints;
      ``Mode_Planned``: unique modes in first-appearance order
    - ``Line_Nunique``, ``TotalDemand``, ``TotalTransfers`` and the ``<Mode> Lines``
      columns are summed
    - ``area`` / ``address``: first non-empty value; ``location``: first non-empty list
    - ``Num_Modes``: number of ``<Mode> Lines`` columns > 0
    - ``geometry``: union of the group's hexagons (same CRS as the input)
    """
    if "group" not in hexes.columns:
        raise ValueError("hexes need a 'group' column (run grouping first)")

    agg: dict = {"h3_index": lambda s: sorted(_flatten_unique(s)), "node": lambda s: sorted(int(n) for n in _flatten_unique(s))}
    if "Mode_Planned" in hexes.columns:
        agg["Mode_Planned"] = _flatten_unique
    if "Line_Unique" in hexes.columns:
        agg["Line_Unique"] = lambda s: sorted(_flatten_unique(s))
    if "Lines_by_Mode" in hexes.columns:
        agg["Lines_by_Mode"] = _merge_counts
    for col in ("Line_Nunique", "TotalDemand", "TotalTransfers", *MODE_LINE_COLS):
        if col in hexes.columns:
            agg[col] = "sum"
    for col in FIRST_STRING_COLS:
        if col in hexes.columns:
            agg[col] = _first_string
    if "location" in hexes.columns:
        agg["location"] = _first_list
    if "hub_id" in hexes.columns:
        agg["hub_id"] = "first"

    plain = pd.DataFrame(hexes.drop(columns=hexes.geometry.name))
    grouped = plain.groupby("group", sort=True).agg(agg).reset_index()

    mode_cols = [c for c in MODE_LINE_COLS if c in grouped.columns]
    grouped["Num_Modes"] = (grouped[mode_cols] > 0).sum(axis=1).astype(int) if mode_cols else 0

    dissolved = hexes[["group", hexes.geometry.name]].dissolve(by="group", as_index=True)
    grouped["geometry"] = dissolved.loc[grouped["group"], hexes.geometry.name].to_numpy()
    return gpd.GeoDataFrame(grouped, geometry="geometry", crs=hexes.crs)


# ----------------------------------------------------------------------------------------
# bus terminals
# ----------------------------------------------------------------------------------------


def bus_terminal_score(term_type) -> int:
    """Terminal class -> 0-3 score (notebook cell 53)."""
    if term_type is None or (isinstance(term_type, float) and np.isnan(term_type)):
        return 0
    s = str(term_type).strip()
    if "חניון לילה" in s:
        return 1
    if "מסוף קטן" in s or "מסוף בינוני" in s:
        return 2
    if "מסוף גדול" in s or "מתקן משולב" in s:
        return 3
    return 0


def tag_bus_terminals(
    groups: gpd.GeoDataFrame,
    terminals: gpd.GeoDataFrame | None,
    buffer_m: float = TERMINAL_PROXIMITY_DISTANCE_M,
    report: RunReport | None = None,
) -> gpd.GeoDataFrame:
    """Attach the strategic bus terminal within ``buffer_m`` of each hub.

    Adds ``term_type``, ``term_id`` (when the layer has an id column) and
    ``bus_terminal``. When several terminals touch a hub the highest-scoring one is
    kept (the notebook produced duplicate rows in that case) and the tie is reported.
    """
    out = groups.copy()
    out["term_type"] = None
    out["term_id"] = None
    if terminals is None or len(terminals) == 0:
        out["bus_terminal"] = 0
        if report is not None:
            report.warn("terminals", "no bus terminal layer; bus_terminal score is 0 for every hub")
        return out

    type_col = next((c for c in TERMINAL_TYPE_CANDIDATES if c in terminals.columns), None)
    if type_col is None:
        raise ValueError(f"terminal layer needs one of {TERMINAL_TYPE_CANDIDATES}; has {list(terminals.columns)}")
    id_col = next((c for c in TERMINAL_ID_CANDIDATES if c in terminals.columns), None)

    term = terminals.to_crs(CRS_ISRAEL_TM)[[c for c in (type_col, id_col) if c] + [terminals.geometry.name]].copy()
    term = term.rename(columns={type_col: "term_type", **({id_col: "term_id"} if id_col else {})})
    term["geometry"] = term.geometry.buffer(buffer_m)
    term = term.set_geometry("geometry")
    term["bus_terminal"] = term["term_type"].map(bus_terminal_score)

    hubs = out[["group", out.geometry.name]].to_crs(CRS_ISRAEL_TM)
    joined = gpd.sjoin(hubs, term, how="inner", predicate="intersects")
    if len(joined):
        multi = joined.groupby("group").size()
        multi = multi[multi > 1]
        if len(multi) and report is not None:
            report.info("terminals", f"{len(multi)} hubs touch more than one terminal; keeping the highest-scoring", groups=multi.index.tolist()[:30])
        best = joined.sort_values(["group", "bus_terminal"], ascending=[True, False]).drop_duplicates("group")
        best = best.set_index("group")
        out = out.set_index("group")
        out.loc[best.index, "term_type"] = best["term_type"]
        if "term_id" in best.columns:
            out.loc[best.index, "term_id"] = best["term_id"]
        out = out.reset_index()

    out["bus_terminal"] = out["term_type"].map(bus_terminal_score).astype(int)
    if report is not None:
        report.set_metric("hubs_near_terminal", int((out["bus_terminal"] > 0).sum()))
    return gpd.GeoDataFrame(out, geometry=groups.geometry.name, crs=groups.crs)


# ----------------------------------------------------------------------------------------
# influence area (population and jobs)
# ----------------------------------------------------------------------------------------


def ring_column_names(rings: Sequence[int]) -> list[tuple[str, str, int, int]]:
    """``[(pop_col, emp_col, inner, outer), ...]`` e.g. ``pop_0_500, emp_0_500, 0, 500``."""
    out, inner = [], 0
    for outer in rings:
        out.append((f"pop_{inner}_{outer}", f"emp_{inner}_{outer}", inner, outer))
        inner = outer
    return out


def add_influence_area(
    groups: gpd.GeoDataFrame,
    taz: gpd.GeoDataFrame | None,
    rings: Sequence[int] = DEFAULT_RINGS,
    report: RunReport | None = None,
) -> gpd.GeoDataFrame:
    """Add ``pop_<a>_<b>`` / ``emp_<a>_<b>`` for each ring around the hub centroid.

    Each TAZ contributes ``POP_2050 * (overlap area / TAZ area)`` (capped at 1) to the
    ring it overlaps, exactly like the notebook's proportional allocation, computed with
    a vectorised overlay instead of a row loop.
    """
    rings = list(rings)
    if rings != sorted(rings) or rings[0] <= 0:
        raise ValueError("rings must be strictly increasing positive outer radii")
    cols = ring_column_names(rings)

    out = groups.copy()
    if taz is None or len(taz) == 0:
        for pop_col, emp_col, _, _ in cols:
            out[pop_col] = 0.0
            out[emp_col] = 0.0
        if report is not None:
            report.warn("influence", "no TAZ layer; population and employment set to 0 for every hub")
        return out

    for c in (TAZ_POP_COL, TAZ_EMP_COL):
        if c not in taz.columns:
            raise ValueError(f"TAZ layer is missing '{c}'")

    taz_p = taz.to_crs(CRS_ISRAEL_TM)[[TAZ_POP_COL, TAZ_EMP_COL, taz.geometry.name]].copy()
    taz_p = taz_p.rename_geometry("geometry") if taz_p.geometry.name != "geometry" else taz_p
    taz_p["_taz_area"] = taz_p.geometry.area
    taz_p = taz_p[taz_p["_taz_area"] > 0].reset_index(drop=True)
    taz_p["_taz_id"] = np.arange(len(taz_p))

    centroids = out.to_crs(CRS_ISRAEL_TM).geometry.centroid
    inner_circle = None
    for pop_col, emp_col, inner, outer in cols:
        outer_circle = centroids.buffer(outer)
        ring_geom = outer_circle if inner_circle is None else outer_circle.difference(inner_circle)
        inner_circle = outer_circle

        ring_gdf = gpd.GeoDataFrame({"group": out["group"].to_numpy()}, geometry=ring_geom.to_numpy(), crs=CRS_ISRAEL_TM)
        inter = gpd.overlay(ring_gdf, taz_p, how="intersection", keep_geom_type=False)
        if len(inter):
            share = np.minimum(inter.geometry.area / inter["_taz_area"], 1.0)
            inter["_pop"] = inter[TAZ_POP_COL].astype(float) * share
            inter["_emp"] = inter[TAZ_EMP_COL].astype(float) * share
            sums = inter.groupby("group")[["_pop", "_emp"]].sum()
            out[pop_col] = out["group"].map(sums["_pop"]).fillna(0.0).to_numpy()
            out[emp_col] = out["group"].map(sums["_emp"]).fillna(0.0).to_numpy()
        else:
            out[pop_col] = 0.0
            out[emp_col] = 0.0

    if report is not None:
        pop_total = out[[c[0] for c in cols]].sum(axis=1)
        n_zero = int((pop_total == 0).sum())
        report.set_metric("hubs_without_taz_coverage", n_zero)
        if n_zero:
            report.warn("influence", f"{n_zero} hubs have no population within {rings[-1]} m (outside TAZ coverage?)")
    return out
