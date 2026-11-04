"""Writers of ``hubs compare-network``: workbook sheets, GeoPackage layers and the files.

* :func:`build_sheets` turns the two comparisons into the 11 sheets of ``network_comparison.xlsx``
  (spec 6) and :func:`write_workbook` writes them.
* :func:`build_layers` builds the map layers (EPSG:2039) that :func:`write_gpkg` writes and
  the map pages read.

Everything is a pure function of its inputs: the same comparison gives identical sheet values.
List cells are joined with ``"; "``; geometry columns never reach the workbook.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import geopandas as gpd
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points

from .agency import CRS_ITM, AgencyNetwork
from .hubs import RELATIONS, HubComparison
from .routes import AGENCY_ROW_STATUSES, STATUSES, RouteComparison, order_points
from .settings import CompareConfig

LIST_SEP = "; "
MAX_WIDTH = 60
WIDTH_SAMPLE_ROWS = 1000  # rows looked at to size a column
SHEET_NAMES = (
    "summary", "routes", "routes_only_ours", "routes_only_agency", "mode_summary", "hubs",
    "hubs_agency_only", "hubs_ours_only", "hub_routes", "settings", "inputs",
)
LAYER_NAMES = (
    "route_pairs", "our_routes", "our_routes_raw", "agency_hubs", "our_groups", "hub_ties",
)
PAIR_STATS = ("median_dist_raw_m", "median_dist_corr_m", "max_dist_corr_m")
PAIRED = ("1:1", "agency_splits", "ours_merges", "many_to_many")
MODE_SUMMARY_COLUMNS = ["side", "mode", "n_routes", *STATUSES]
_LIMITS = (
    "our_routes in the GeoPackage is an ordered visual aid (our lines have no stop order or "
    "geometry), not a route",
    "the offset between the two networks is estimated as a locally constant shift",
    "route matching is only as good as the node positions",
)


# ----------------------------------------------------------------------------------------
# Cell and frame helpers
# ----------------------------------------------------------------------------------------


def _is_listlike(value: Any) -> bool:
    return isinstance(value, (list, tuple, set, frozenset, np.ndarray))


def _join(value: Any) -> str:
    items = sorted(value, key=str) if isinstance(value, (set, frozenset)) else value
    return LIST_SEP.join(str(v) for v in items)


def _flat(frame: pd.DataFrame) -> pd.DataFrame:
    """Copy of ``frame`` with every list-valued column joined with ``"; "`` (geometry kept)."""
    out = frame.copy()
    for col in out.columns:
        if out[col].dtype == object and any(_is_listlike(v) for v in out[col]):
            out[col] = [_join(v) if _is_listlike(v) else v for v in out[col]]
    return out


def _is_geometry(frame: pd.DataFrame, col: Any) -> bool:
    return isinstance(frame[col].dtype, gpd.array.GeometryDtype) or col == "geometry"


def _cell(value: Any) -> Any:
    """Excel cell value: lists joined, NaN / NA / '' empty, numpy scalars as Python ones."""
    if _is_listlike(value):
        value = _join(value)
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    text = ILLEGAL_CHARACTERS_RE.sub("", str(value))
    return text or None


def _sheet_title(name: str, used: set[str]) -> str:
    """Excel-safe, unique sheet name of at most 31 characters."""
    title = "".join("_" if ch in '[]:*?/\\' else ch for ch in str(name)).strip("'") or "sheet"
    title, n = title[:31], 1
    while title.lower() in used:
        n += 1
        suffix = f"_{n}"
        title = f"{title[:31 - len(suffix)]}{suffix}"
    used.add(title.lower())
    return title


# ----------------------------------------------------------------------------------------
# Workbook
# ----------------------------------------------------------------------------------------


def write_workbook(path: Path, sheets: Mapping[str, pd.DataFrame]) -> Path:
    """Write the sheets to an ``.xlsx``: frozen bold header, autofilter, widths capped at 60.

    Args:
        path: Output file.
        sheets: Sheet name -> frame; names are made Excel-safe (at most 31 characters).
            List cells are joined with ``"; "``, NaN / NA are empty cells, geometry columns
            are not written, text starting with ``=`` stays text.

    Returns:
        ``path``.
    """
    path = Path(path)
    wb = Workbook()
    wb.remove(wb.active)
    used: set[str] = set()
    for name, frame in sheets.items():
        ws = wb.create_sheet(_sheet_title(name, used))
        columns = [c for c in frame.columns if not _is_geometry(frame, c)]
        if not columns:
            continue
        ws.append([str(c) for c in columns])
        data = [[_cell(v) for v in row] for row in frame[columns].itertuples(index=False)]
        widths = [len(str(c)) for c in columns]
        for r, row in enumerate(data, start=2):
            for c, value in enumerate(row, start=1):
                cell = ws.cell(row=r, column=c, value=value)
                if isinstance(value, str):
                    cell.data_type = "s"  # a text that starts with "=" is not a formula
                if value is not None and r <= WIDTH_SAMPLE_ROWS:
                    widths[c - 1] = max(widths[c - 1], len(str(value)))
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{len(data) + 1}"
        for c, width in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(c)].width = min(max(width + 2, 8), MAX_WIDTH)
    if not wb.sheetnames:
        wb.create_sheet("sheet")
    wb.save(path)
    return path


# ----------------------------------------------------------------------------------------
# Sheets
# ----------------------------------------------------------------------------------------


def _routes_with_stats(routes: RouteComparison) -> pd.DataFrame:
    """The routes table with the chosen pair's distance statistics after ``score``."""
    frame = routes.routes
    keys = ["our_route_key", "agency_route_key"]
    stats = routes.pairs[keys + list(PAIR_STATS)].drop_duplicates(keys)
    merged = frame.merge(stats, on=keys, how="left")
    columns = list(frame.columns)
    at = columns.index("score") + 1 if "score" in columns else len(columns)
    return merged[columns[:at] + list(PAIR_STATS) + columns[at:]]


def _ours_rows(routes: pd.DataFrame) -> pd.DataFrame:
    """The rows of our routes (not the ``agency_only`` / ``covered`` rows of agency routes)."""
    return routes[routes["our_route_key"].notna() & ~routes["status"].isin(AGENCY_ROW_STATUSES)]


def _mode_summary(routes: pd.DataFrame, agency: AgencyNetwork) -> pd.DataFrame:
    """Routes per mode on each side by status; the sides use their own mode names.

    Our side groups on ``our_mode``; the agency side on the agency route type, each agency
    route counted once: ``agency_only`` / ``covered`` if it has such a row, else the best status
    of the rows of ours that chose it.
    """
    rows = []
    ours = _ours_rows(routes)
    for mode, grp in ours.groupby(ours["our_mode"].fillna(""), sort=True):
        rows.append(("ours", mode, grp["status"].astype(str).tolist()))
    rank = {s: i for i, s in enumerate(STATUSES)}
    agency_rows = routes[routes["status"].isin(AGENCY_ROW_STATUSES)]
    own_row = dict(zip(agency_rows["agency_route_key"], agency_rows["status"]))
    chosen: dict[str, str] = {}
    for key, status in zip(ours["agency_route_key"], ours["status"]):
        if pd.notna(key) and (key not in chosen or rank[status] < rank[chosen[key]]):
            chosen[key] = status
    by_type: dict[str, list[str]] = {}
    for key, type_ in zip(agency.routes["route_key"], agency.routes["type"]):
        status = own_row.get(key) or chosen.get(key, "covered")
        by_type.setdefault(str(type_), []).append(status)
    rows += [("agency", mode, by_type[mode]) for mode in sorted(by_type)]
    out = []
    for side, mode, statuses in rows:
        counts = pd.Series(statuses).value_counts()
        out.append({"side": side, "mode": mode, "n_routes": len(statuses),
                    **{s: int(counts.get(s, 0)) for s in STATUSES}})
    return pd.DataFrame(out, columns=MODE_SUMMARY_COLUMNS).astype(
        {c: "int64" for c in MODE_SUMMARY_COLUMNS[2:]}
    )


def _inputs_sheet(inputs: Mapping[str, Mapping[str, Any]]) -> pd.DataFrame:
    keys: list[str] = []
    for spec in inputs.values():
        keys += [k for k in spec if k not in keys]
    keys = keys or ["file", "sha256", "rows"]
    rows = [{"input": name, **{k: spec.get(k) for k in keys}} for name, spec in inputs.items()]
    return pd.DataFrame(rows, columns=["input", *keys])


def _summary(routes: pd.DataFrame, hubs: pd.DataFrame, agency: AgencyNetwork,
             inputs: Mapping[str, Mapping[str, Any]]) -> pd.DataFrame:
    run = inputs.get("run", {})
    rows: list[tuple[str, str, Any]] = [
        ("about", "run version", run.get("version", "not recorded")),
        ("about", "run directory", run.get("dir", "not recorded")),
        ("about", "agency demand",
         "empty - the agency files carry no demand, so column agency_total_demand is empty"),
        ("about", "agency type",
         "derived: the number of distinct modes (n_modes) with the rail_hub flag and the mode "
         "mix; it is not an agency classification"),
        ("about", "thresholds", "the effective configuration is on the settings sheet"),
    ]
    counts = routes["status"].value_counts()
    rows.append(("routes", "routes: ours", int(len(_ours_rows(routes)))))
    rows.append(("routes", "routes: agency", int(len(agency.routes))))
    rows += [("routes", f"routes: {s}", int(counts.get(s, 0))) for s in STATUSES]
    relation = hubs["relation"].value_counts()
    own = hubs[hubs["group"].notna()]  # agency_only rows name a group only as nearest_group
    rows.append(("hubs", "hubs: agency hubs", int(len(agency.hubs))))
    rows.append(("hubs", "hubs: groups of ours", int(own["group"].nunique())))
    rows += [("hubs", f"hubs: relation {r}", int(relation.get(r, 0))) for r in RELATIONS]
    rows += [("limits", "limit", text) for text in _LIMITS]
    return pd.DataFrame(rows, columns=["section", "item", "value"])


def build_sheets(
    routes: RouteComparison,
    hubs: HubComparison,
    agency: AgencyNetwork,
    cfg: CompareConfig,
    inputs: Mapping[str, Mapping[str, Any]],
) -> dict[str, pd.DataFrame]:
    """Build the 11 sheets of ``network_comparison.xlsx`` (spec 6), in order.

    Args:
        routes: Step-1 result; ``routes`` gets the best pair's distance statistics.
        hubs: Step-2 result.
        agency: The agency network (its routes and hubs give the denominators).
        cfg: Effective configuration, written to ``settings``.
        inputs: Input name -> dict of file name / SHA-256 / counts, written to ``inputs``.
            The entry ``"run"`` (``version``, ``dir``) is quoted on ``summary``.

    Returns:
        ``summary, routes, routes_only_ours, routes_only_agency, mode_summary, hubs,
        hubs_agency_only, hubs_ours_only, hub_routes, settings, inputs`` (empty comparisons
        keep every header).
    """
    route_table = _flat(_routes_with_stats(routes))
    hub_table = _flat(hubs.hubs)
    status = route_table["status"]
    relation = hub_table["relation"]
    sheets = {
        "summary": _summary(route_table, hub_table, agency, inputs),
        "routes": route_table,
        "routes_only_ours": route_table[status == "ours_only"].reset_index(drop=True),
        "routes_only_agency": route_table[status == "agency_only"].reset_index(drop=True),
        "mode_summary": _mode_summary(route_table, agency),
        "hubs": hub_table,
        "hubs_agency_only": hub_table[relation == "agency_only"].reset_index(drop=True),
        "hubs_ours_only": hub_table[relation == "ours_only"].reset_index(drop=True),
        "hub_routes": _flat(hubs.hub_routes),
        "settings": pd.DataFrame(
            [{"key": k, "value": v} for k, v in cfg.to_dict().items()], columns=["key", "value"]
        ),
        "inputs": _inputs_sheet(inputs),
    }
    return {name: sheets[name] for name in SHEET_NAMES}


# ----------------------------------------------------------------------------------------
# Layers
# ----------------------------------------------------------------------------------------


def _layer(frame: pd.DataFrame, geoms: list) -> gpd.GeoDataFrame:
    """A GeoDataFrame in ITM from ``frame`` (lists joined) and a geometry per row."""
    return gpd.GeoDataFrame(_flat(frame).reset_index(drop=True), geometry=geoms, crs=CRS_ITM)


def _route_geometry(xy: np.ndarray, order: list[int]) -> Any:
    pts = [tuple(xy[i]) for i in order]
    return Point(pts[0]) if len(pts) == 1 else LineString(pts)


def _our_route_layers(routes: RouteComparison, ours: pd.DataFrame) -> tuple:
    """``our_routes`` (corrected positions) and ``our_routes_raw`` (raw), one row per route."""
    best = _ours_rows(routes.routes).drop_duplicates("our_route_key")
    info = best.set_index("our_route_key")[["status", "agency_route_key", "score"]]
    rows, corrected, raw = [], [], []
    for rec in ours.to_dict("records"):
        xy = np.asarray(rec["xy"], dtype=float).reshape(-1, 2)
        if len(xy) == 0:
            continue
        order = order_points(xy)  # the same path for both layers, so they stay comparable
        corrected.append(_route_geometry(xy, order))
        raw.append(_route_geometry(np.asarray(rec["xy_raw"], dtype=float).reshape(-1, 2), order))
        found = info.loc[rec["route_key"]] if rec["route_key"] in info.index else None
        rows.append({
            "route_key": rec["route_key"], "line_ids": rec["line_ids"],
            "line_names": rec["line_names"], "mode": rec["mode"],
            "agency_type": rec["agency_type"], "n_nodes": int(rec["n_nodes"]),
            "short_route": bool(rec["short_route"]), "visual_aid": True,
            "status": None if found is None else found["status"],
            "agency_route_key": None if found is None else found["agency_route_key"],
            "score": np.nan if found is None else found["score"],
        })
    columns = ["route_key", "line_ids", "line_names", "mode", "agency_type", "n_nodes",
               "short_route", "visual_aid", "status", "agency_route_key", "score"]
    frame = pd.DataFrame(rows, columns=columns)
    return _layer(frame, corrected), _layer(frame, raw)


def _route_pairs_layer(routes: RouteComparison, agency: AgencyNetwork) -> gpd.GeoDataFrame:
    """Chosen pairs (our route -> agency geometry), then the ``agency_only`` and ``covered``
    rows (agency routes with no chosen pair), each with its agency route geometry."""
    table = _routes_with_stats(routes)
    geom = dict(zip(agency.routes["route_key"], agency.routes.geometry))
    wanted = table["agency_route_key"].isin(geom) & (
        table["our_route_key"].notna() | (table["status"] == "agency_only")
    )
    sel = table[wanted]
    return _layer(sel, [geom[k] for k in sel["agency_route_key"]])


def _first_by(frame: pd.DataFrame, key: str, value: str) -> dict:
    """``key -> value`` per key; the last row of a key wins (frames are sorted, so it is
    stable)."""
    sub = frame[frame[key].notna()]
    return dict(zip(sub[key].astype(int), sub[value]))


def _joined_ids(frame: pd.DataFrame, key: str, other: str) -> dict:
    sub = frame[frame[key].notna() & frame[other].notna()]
    out: dict[int, list[int]] = {}
    for k, o in zip(sub[key].astype(int), sub[other].astype(int)):
        out.setdefault(k, []).append(o)
    return {k: LIST_SEP.join(str(i) for i in sorted(v)) for k, v in out.items()}


def _hub_layers(hubs: HubComparison, agency: AgencyNetwork, our_hubs: gpd.GeoDataFrame) -> tuple:
    table = hubs.hubs
    paired = table[table["relation"].isin(PAIRED)]
    alone = table[table["relation"] == "agency_only"]  # group empty, nearest_* filled
    a_rel = _first_by(table, "agency_hub_id", "relation")
    g_rel = _first_by(table, "group", "relation")
    a_near = _first_by(alone, "agency_hub_id", "nearest_group")
    a_dist = _first_by(alone, "agency_hub_id", "distance_m")
    a_groups = _joined_ids(paired, "agency_hub_id", "group")
    g_hubs = _joined_ids(paired, "group", "agency_hub_id")

    a = agency.hubs.reset_index(drop=True).copy()
    a["relation"] = [a_rel.get(int(i)) for i in a["agency_hub_id"]]
    a["paired_groups"] = [a_groups.get(int(i), "") for i in a["agency_hub_id"]]
    a["nearest_group"] = pd.array([a_near.get(int(i)) for i in a["agency_hub_id"]], dtype="Int64")
    a["nearest_distance_m"] = [a_dist.get(int(i), np.nan) for i in a["agency_hub_id"]]
    g = pd.DataFrame(our_hubs.drop(columns="geometry")).reset_index(drop=True)
    g["relation"] = [g_rel.get(int(i)) if pd.notna(i) else None for i in g["group"]]
    g["paired_agency_hubs"] = [g_hubs.get(int(i), "") if pd.notna(i) else "" for i in g["group"]]

    a_geom = dict(zip(a["agency_hub_id"].astype(int), agency.hubs.geometry))
    g_geom = {int(k): v for k, v in zip(our_hubs["group"], our_hubs.geometry) if pd.notna(k)}
    ties, rows = [], []
    for rec in paired.to_dict("records"):
        ga, gb = a_geom.get(int(rec["agency_hub_id"])), g_geom.get(int(rec["group"]))
        if ga is None or gb is None or ga.is_empty or gb.is_empty:
            continue
        p, q = nearest_points(ga, gb)
        ties.append(LineString([p, q]))
        rows.append({k: rec[k] for k in ("agency_hub_id", "group", "hub_id", "relation",
                                         "distance_m", "agency_name", "HubNameHE", "eligible")})
    columns = ["agency_hub_id", "group", "hub_id", "relation", "distance_m", "agency_name",
               "HubNameHE", "eligible"]
    return (
        _layer(a.drop(columns="geometry"), list(agency.hubs.geometry)),
        _layer(g, list(our_hubs.geometry)),
        _layer(pd.DataFrame(rows, columns=columns), ties),
    )


def build_layers(
    routes: RouteComparison,
    our_routes: pd.DataFrame,
    hubs: HubComparison,
    agency: AgencyNetwork,
    our_hubs: gpd.GeoDataFrame,
) -> dict[str, gpd.GeoDataFrame]:
    """Build the GeoPackage / map layers, all in EPSG:2039.

    Args:
        routes: Step-1 result.
        our_routes: :func:`routes.build_our_routes` output (``xy``, ``xy_raw``).
        hubs: Step-2 result.
        agency: The agency network.
        our_hubs: :func:`hubs.build_our_hubs` output.

    Returns:
        ``route_pairs`` (agency route geometry with the match attributes of the route of ours
        that chose it, one row per route of ours with a candidate, then one ``agency_only`` row
        per agency route nothing of ours covers, with null ``our_*`` attributes, and one
        ``covered`` row per covered agency route no route of ours chose, with its best pair),
        ``our_routes`` (the nodes of
        each route joined in ``order_points`` order from the corrected positions, a Point for a
        one-node route, ``visual_aid = True``), ``our_routes_raw`` (the same rows and order from
        the raw positions), ``agency_hubs`` (with ``relation``, ``paired_groups`` and, for an
        ``agency_only`` hub, ``nearest_group`` / ``nearest_distance_m``), ``our_groups`` (with
        ``relation``) and
        ``hub_ties`` (nearest points of each paired agency hub and group).
    """
    corrected, raw = _our_route_layers(routes, our_routes)
    agency_hubs, groups, ties = _hub_layers(hubs, agency, our_hubs)
    layers = {
        "route_pairs": _route_pairs_layer(routes, agency), "our_routes": corrected,
        "our_routes_raw": raw, "agency_hubs": agency_hubs, "our_groups": groups,
        "hub_ties": ties,
    }
    return {name: layers[name] for name in LAYER_NAMES}


def _gpkg_ready(layer: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Plain dtypes the GeoPackage driver accepts (lists joined, nullable ints kept as ints)."""
    out = _flat(layer)
    if out.crs is None:
        out = out.set_crs(CRS_ITM)
    elif out.crs.to_epsg() != 2039:
        out = out.to_crs(CRS_ITM)
    return out


def write_gpkg(path: Path, layers: Mapping[str, gpd.GeoDataFrame]) -> Path:
    """Write the layers to a GeoPackage in EPSG:2039 (an existing file is replaced).

    Args:
        path: Output ``.gpkg``.
        layers: Layer name -> GeoDataFrame; lists are joined with ``"; "``.

    Returns:
        ``path``.
    """
    path = Path(path)
    path.unlink(missing_ok=True)
    for i, (name, layer) in enumerate(layers.items()):
        _gpkg_ready(layer).to_file(path, layer=name, driver="GPKG", mode="w" if i == 0 else "a")
    return path

