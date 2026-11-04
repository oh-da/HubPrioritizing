"""Hand-built inputs for the network-comparison unit tests (no files needed).

Coordinates are ITM metres. Agency routes are given by their route key (``"LRT:1"``,
``"Rail:0:A"``); the type is the part before the first ``:``. Our lines are given by
``LINE_ID``; a node id defaults to its rounded raw position, so two lines through the same
points share their nodes (the two directions of one route).
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiLineString, Point

from src.compare.agency import HUB_COLUMNS, ROUTE_COLUMNS, STOP_COLUMNS, AgencyNetwork
from src.compare.modes import load_mode_map
from src.compare.routes import build_our_routes
from src.pipeline.all_groups import NETWORK_NODES_COLUMNS

CRS_ITM = "EPSG:2039"
X0, Y0 = 200000.0, 600000.0  # every helper coordinate is relative to this origin


def pts(x0: float, x1: float, step: float, y: float = 0.0) -> list[tuple[float, float]]:
    """Points ``(x, y)`` from ``x0`` to ``x1`` inclusive every ``step`` metres (relative)."""
    n = int(round((x1 - x0) / step)) + 1
    return [(x0 + i * step, y) for i in range(n)]


def _abs(coords: Iterable[Sequence[float]]) -> list[tuple[float, float]]:
    return [(X0 + float(x), Y0 + float(y)) for x, y in coords]


def make_agency_network(routes: dict[str, dict[str, Any]]) -> AgencyNetwork:
    """Build an :class:`AgencyNetwork` from route specs.

    Args:
        routes: Route key -> spec with ``coords`` (one polyline) or ``parts`` (several
            polylines), optional ``stops`` (points; absent or empty = no stations),
            ``name``, ``line_name``, ``year_operation``, ``year_cancel``, ``source_plan``.

    Returns:
        The network; ``hubs`` is empty and ``labels`` translates ``detailed``.
    """
    route_rows, stop_rows = [], []
    for key, spec in routes.items():
        type_ = key.split(":")[0]
        line_id = int(key.split(":")[1]) if ":" in key else 1
        parts = spec.get("parts") or [spec["coords"]]
        geom = MultiLineString([LineString(_abs(p)) for p in parts])
        stops = _abs(spec.get("stops") or [])
        route_rows.append({
            "route_key": key, "type": type_, "line_id": line_id,
            "name": spec.get("name", f"name {key}"), "line_name": spec.get("line_name"),
            "year_operation": spec.get("year_operation", 2040),
            "year_cancel": spec.get("year_cancel"),
            "source_plan": spec.get("source_plan", "detailed"), "source_name": None,
            "n_stops": len(stops), "has_stops": len(stops) > 0, "geometry": geom,
        })
        for i, (x, y) in enumerate(stops):
            stop_rows.append({
                "stop_id": f"{key}#{i}", "route_key": key, "type": type_, "line_id": line_id,
                "station_name": f"stop {i}", "hub_id": pd.NA, "rail_hub": False,
                "hub_stop_id": None, "geometry": Point(x, y),
            })
    rframe = gpd.GeoDataFrame(
        pd.DataFrame(route_rows, columns=ROUTE_COLUMNS), geometry="geometry", crs=CRS_ITM
    )
    sframe = gpd.GeoDataFrame(
        pd.DataFrame(stop_rows, columns=STOP_COLUMNS), geometry="geometry", crs=CRS_ITM
    )
    sframe["hub_id"] = sframe["hub_id"].astype("Int64")
    hubs = gpd.GeoDataFrame(pd.DataFrame(columns=HUB_COLUMNS), geometry="geometry", crs=CRS_ITM)
    labels = {"source_plan": {"detailed": "מפורטת"}}
    return AgencyNetwork(routes=rframe, stops=sframe, hubs=hubs, labels=labels)


def make_network_nodes(lines: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Build a ``network_nodes`` frame from line specs.

    Args:
        lines: ``LINE_ID`` -> spec with ``mode`` (pipeline mode), ``coords`` (raw node
            positions), optional ``corr`` (corrected positions, same length; adds
            ``x_corr`` / ``y_corr`` columns), ``nodes`` (node ids) and ``name``.

    Returns:
        One row per node x line in the ``network_nodes.csv`` layout.
    """
    rows = []
    with_corr = any("corr" in spec for spec in lines.values())
    for line_id, spec in lines.items():
        coords = _abs(spec["coords"])
        corr = _abs(spec["corr"]) if "corr" in spec else coords
        ids = spec.get("nodes") or [f"n{round(x)}_{round(y)}" for x, y in coords]
        for node, (x, y), (cx, cy) in zip(ids, coords, corr):
            row = {
                "node": node, "LINE_ID": line_id, "line_name": spec.get("name", ""),
                "Mode_Planned": spec["mode"], "x_itm": x, "y_itm": y, "group": 1, "hub_id": None,
            }
            if with_corr:
                row.update(x_corr=cx, y_corr=cy)
            rows.append(row)
    columns = list(NETWORK_NODES_COLUMNS) + (["x_corr", "y_corr"] if with_corr else [])
    return pd.DataFrame(rows, columns=columns)


def make_our_routes(lines: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """``build_our_routes`` over :func:`make_network_nodes` with the shipped mode map."""
    return build_our_routes(make_network_nodes(lines), load_mode_map())


__all__ = ["X0", "Y0", "make_agency_network", "make_network_nodes", "make_our_routes", "pts"]
