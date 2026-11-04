"""Reader for the planning agency's network (``MT_Network.gpkg`` + metadata workbook).

Turns the agency's ``lines`` and ``stations`` layers into routes, stops and hubs in ITM
(EPSG:2039), the form the route and hub matching stages consume.

* A **route** is identified by ``(type, line_id)``; the ``Rail`` features share ``line_id = 0`` so
  for them the feature ``name`` completes the key. Features with the same key are one route.
* A **stop** is a ``stations`` row. The layer has no ``name`` column, so a station with
  ``line_id = 0`` is assigned to the nearest same-type ``line_id = 0`` feature within
  ``cfg.rail_assign_tol_m`` (ties: lowest ``fid``); those that fit none are dropped and reported.
* A **hub** is the set of stops sharing a ``hub_id``. The agency supplies no classification, so
  ``agency_type`` is *derived* from the distinct modes and the ``rail_hub`` flag.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS
from shapely import STRtree, unary_union
from shapely.geometry import MultiPoint, Point

from ..pipeline.inputs import InputError
from ..pipeline.report import RunReport
from .settings import CompareConfig

CRS_ITM = "EPSG:2039"
_ITM = CRS.from_user_input(CRS_ITM)
SECTION = "agency"

LINES_REQUIRED = ("type", "line_id", "name")
LINES_OPTIONAL = ("line_name", "year_operation", "year_cancel", "source_plan", "source_name")
STATIONS_REQUIRED = ("type", "line_id", "station_name", "stop_id", "hub_id", "rail_hub")
STATIONS_OPTIONAL = ("hub_stop_id",)
TOD_REQUIRED = ("hub_id", "n_modes", "type_sum")

ROUTE_COLUMNS = [
    "route_key", "type", "line_id", "name", "line_name", "year_operation", "year_cancel",
    "source_plan", "source_name", "n_stops", "has_stops", "geometry",
]
STOP_COLUMNS = [
    "stop_id", "route_key", "type", "line_id", "station_name", "hub_id", "rail_hub",
    "hub_stop_id", "geometry",
]
HUB_COLUMNS = [
    "agency_hub_id", "name", "modes", "n_modes", "rail_hub", "agency_type", "route_keys",
    "n_routes", "geometry",
]

# A trailing " - <digits>" index suffix (also the whole name "- 239") and a leading "- ".
_SUFFIX = re.compile(r"(?:^|\s)-\s*\d+\s*$")
_PREFIX = re.compile(r"^\s*-\s*")
_REPORT_LIST_LIMIT = 20


class LabelMap(dict):
    """``str -> str`` dict whose lookups ignore case and surrounding blanks.

    The metadata workbook says ``metro`` where the GeoPackage says ``Metro``; keys are stored
    lowercased and every lookup is lowercased the same way.
    """

    @staticmethod
    def _norm(key: Any) -> Any:
        return key.strip().lower() if isinstance(key, str) else key

    def __setitem__(self, key: Any, value: str) -> None:
        super().__setitem__(self._norm(key), value)

    def __getitem__(self, key: Any) -> str:
        return super().__getitem__(self._norm(key))

    def __contains__(self, key: object) -> bool:
        return super().__contains__(self._norm(key))

    def get(self, key: Any, default: Any = None) -> Any:
        """Return the label of ``key`` (case-insensitive) or ``default``."""
        return super().get(self._norm(key), default)


@dataclass
class AgencyNetwork:
    """The agency network in EPSG:2039.

    Attributes:
        routes: One row per route (``ROUTE_COLUMNS``), (Multi)LineString geometry.
        stops: One row per kept station (``STOP_COLUMNS``), ``hub_id`` nullable ``Int64``.
        hubs: One row per ``hub_id`` (``HUB_COLUMNS``), MultiPoint of its stops.
        labels: ``{"type": {...}, "source_plan": {...}}`` English code -> Hebrew label from the
            metadata workbook (case-insensitive keys); ``{}`` without a workbook.
    """

    routes: gpd.GeoDataFrame
    stops: gpd.GeoDataFrame
    hubs: gpd.GeoDataFrame
    labels: dict[str, dict[str, str]] = field(default_factory=dict)


# ----------------------------------------------------------------------------------------
# Small pure helpers
# ----------------------------------------------------------------------------------------


def build_route_key(type_: str, line_id: int, name: str | None) -> str:
    """Return the key of a route: ``"LRT:3106"``, or ``"Rail:0:<name>"`` when ``line_id == 0``."""
    key = f"{type_}:{int(line_id)}"
    if int(line_id) == 0:
        key += f":{'' if name is None or pd.isna(name) else str(name).strip()}"
    return key


def hub_type_label(modes: Sequence[str], rail_hub: bool) -> str:
    """Describe a hub by its modes: ``"1 mode: LRT"``, ``"3 modes, rail hub: BRT+LRT+Rail"``.

    Derived from the agency data, not a classification by the agency.

    Args:
        modes: Mode (agency ``type``) of each stop; duplicates are ignored.
        rail_hub: The agency's ``rail_hub`` flag of the hub.

    Returns:
        The label; modes are sorted and joined with ``+``.
    """
    distinct = sorted({str(m) for m in modes})
    n = len(distinct)
    head = f"{n} mode{'' if n == 1 else 's'}"
    if rail_hub:
        head += ", rail hub"
    return f"{head}: {'+'.join(distinct)}"


def _clean_station_name(name: Any) -> str:
    """Drop the trailing index suffix and a leading dash from a station name."""
    if name is None or pd.isna(name):
        return ""
    text = _SUFFIX.sub("", str(name).strip())
    return _PREFIX.sub("", text).strip()


def _hub_name(station_names: Sequence[Any], hub_id: int) -> str:
    """Most frequent cleaned station name of a hub; ``"hub <id>"`` when none is left."""
    counts = Counter(n for n in (_clean_station_name(x) for x in station_names) if n)
    if not counts:
        return f"hub {hub_id}"
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _warn(report: RunReport | None, message: str, **data: Any) -> None:
    if report is not None:
        report.warn(SECTION, message, **data)


# ----------------------------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------------------------


def _read_layer(
    path: Path,
    layer: str,
    available: Sequence[str],
    required: Sequence[str],
    optional: Sequence[str],
    problems: list[str],
) -> gpd.GeoDataFrame | None:
    """Read one layer in ITM with a ``_fid`` column; append every problem to ``problems``."""
    if layer not in available:
        problems.append(f"{path.name}: layer '{layer}' not found (layers: {list(available)})")
        return None
    try:
        gdf = gpd.read_file(path, layer=layer, fid_as_index=True)
    except TypeError:  # an engine without the fid option
        gdf = gpd.read_file(path, layer=layer)
    missing = [c for c in required if c not in gdf.columns]
    if missing:
        problems.append(f"{path.name}: layer '{layer}' lacks column(s) {', '.join(missing)}")
    if gdf.crs is None:
        problems.append(f"{path.name}: layer '{layer}' has no CRS (expected {CRS_ITM})")
    if missing or gdf.crs is None:
        return None
    for col in optional:
        if col not in gdf.columns:
            gdf[col] = None
    gdf = gdf.copy()
    gdf["_fid"] = np.asarray(gdf.index, dtype=np.int64)
    if not gdf.crs.equals(_ITM):
        gdf = gdf.to_crs(CRS_ITM)
    return gdf.reset_index(drop=True)


def _list_layers(path: Path, problems: list[str]) -> list[str]:
    if not path.exists():
        problems.append(f"{path}: file not found")
        return []
    try:
        return [str(n) for n in gpd.list_layers(path)["name"]]
    except Exception as exc:  # unreadable / not a GeoPackage
        problems.append(f"{path.name}: cannot be read as a GeoPackage ({exc})")
        return []


def _normalise_header(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).replace("_", " ")).strip().lower()


def _read_labels(meta: Path, problems: list[str]) -> dict[str, dict[str, str]]:
    """Read the code dictionary (``type`` / ``source plan`` -> Hebrew) of the metadata workbook."""
    if not meta.exists():
        problems.append(f"{meta}: file not found")
        return {}
    try:
        frame = pd.read_excel(meta, sheet_name=0, header=None, dtype=object)
    except Exception as exc:
        problems.append(f"{meta.name}: cannot be read as a workbook ({exc})")
        return {}
    if frame.empty:
        problems.append(f"{meta.name}: the sheet is empty")
        return {}
    headers = [_normalise_header(h) for h in frame.iloc[0]]
    body = frame.iloc[1:]
    labels: dict[str, dict[str, str]] = {}
    for key, code_header in (("type", "type"), ("source_plan", "source plan")):
        if code_header not in headers:
            problems.append(f"{meta.name}: no column '{code_header}' in the header row")
            continue
        i = headers.index(code_header)
        if i + 1 >= len(headers):
            problems.append(f"{meta.name}: no label column after '{code_header}'")
            continue
        pairs = LabelMap()
        for code, label in zip(body.iloc[:, i], body.iloc[:, i + 1]):
            if pd.notna(code) and pd.notna(label) and str(code).strip() and str(label).strip():
                pairs[str(code)] = str(label).strip()
        labels[key] = pairs
    return labels


def _int_column(frame: pd.DataFrame, column: str, where: str, problems: list[str]) -> pd.Series:
    """``frame[column]`` as integers; empty or non-numeric values are a problem."""
    values = pd.to_numeric(frame[column], errors="coerce")
    bad = int(values.isna().sum())
    if bad:
        problems.append(f"{where}: {bad} row(s) with an empty or non-numeric '{column}'")
        return values
    return values.astype("int64")


# ----------------------------------------------------------------------------------------
# Routes, stops, hubs
# ----------------------------------------------------------------------------------------


def _build_routes(lines: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """One row per route key; features with the same key are merged (geometry union)."""
    lines = lines.copy()
    lines["type"] = lines["type"].astype(str).str.strip()
    lines["route_key"] = [
        build_route_key(t, i, n) for t, i, n in zip(lines["type"], lines["line_id"], lines["name"])
    ]
    lines = lines.sort_values(["route_key", "_fid"], kind="stable")
    rows = []
    for key, grp in lines.groupby("route_key", sort=True):
        first = grp.iloc[0]
        geoms = list(grp.geometry)
        geom = geoms[0] if len(geoms) == 1 else unary_union(geoms)
        rows.append({
            "route_key": key,
            "type": first["type"],
            "line_id": int(first["line_id"]),
            "name": first["name"],
            "line_name": first["line_name"],
            "year_operation": first["year_operation"],
            "year_cancel": first["year_cancel"],
            "source_plan": first["source_plan"],
            "source_name": first["source_name"],
            "geometry": geom,
        })
    columns = [c for c in ROUTE_COLUMNS if c not in ("n_stops", "has_stops")]
    return gpd.GeoDataFrame(pd.DataFrame(rows, columns=columns), geometry="geometry", crs=CRS_ITM)


def _assign_zero_line_stations(
    stations: gpd.GeoDataFrame, lines: gpd.GeoDataFrame, routes: gpd.GeoDataFrame, tol_m: float
) -> pd.Series:
    """Route key of each ``line_id = 0`` station: nearest same-type ``line_id = 0`` feature
    within ``tol_m`` (ties: lowest ``fid``); ``None`` where there is none."""
    keys = pd.Series([None] * len(stations), index=stations.index, dtype=object)
    zero_lines = lines[lines["line_id"] == 0].copy()
    zero_lines["route_key"] = [
        build_route_key(t, 0, n) for t, n in zip(zero_lines["type"], zero_lines["name"])
    ]
    zero = stations[stations["line_id"] == 0]
    for type_, st in zero.groupby("type"):
        cand = zero_lines[zero_lines["type"] == type_]
        if cand.empty:
            continue
        tree = STRtree(cand.geometry.to_numpy())
        inp, tr = tree.query_nearest(st.geometry.to_numpy(), max_distance=tol_m, all_matches=True)
        if len(inp) == 0:
            continue
        pairs = pd.DataFrame({
            "i": inp,
            "fid": cand["_fid"].to_numpy()[tr],
            "key": cand["route_key"].to_numpy()[tr],
        }).sort_values(["i", "fid"], kind="stable").drop_duplicates("i")
        keys.loc[st.index[pairs["i"].to_numpy()]] = pairs["key"].to_numpy()
    return keys


def _build_stops(
    stations: gpd.GeoDataFrame,
    lines: gpd.GeoDataFrame,
    routes: gpd.GeoDataFrame,
    cfg: CompareConfig,
    report: RunReport | None,
) -> gpd.GeoDataFrame:
    st = stations.copy().reset_index(drop=True)
    st["type"] = st["type"].astype(str).str.strip()
    direct = [
        None if i == 0 else build_route_key(t, i, None) for t, i in zip(st["type"], st["line_id"])
    ]
    keys = pd.Series(direct, index=st.index, dtype=object)
    zero = st["line_id"] == 0
    if zero.any():
        keys[zero] = _assign_zero_line_stations(st, lines, routes, cfg.rail_assign_tol_m)[zero]
    st["route_key"] = keys

    dropped = st[st["route_key"].isna()]
    if len(dropped):
        shown = [str(x) for x in dropped["stop_id"].head(_REPORT_LIST_LIMIT)]
        hubs = sorted({int(h) for h in dropped["hub_id"].dropna()})
        _warn(
            report,
            f"{len(dropped)} station(s) with line_id 0 are farther than "
            f"{cfg.rail_assign_tol_m:g} m from every rail feature of their type; "
            "dropped from the stops",
            stop_ids=shown, hub_ids=hubs[:_REPORT_LIST_LIMIT],
        )
    st = st[st["route_key"].notna()].copy()

    unknown = sorted(set(st["route_key"]) - set(routes["route_key"]))
    if unknown:
        _warn(
            report,
            f"{len(unknown)} route key(s) of the stations have no feature in the lines layer",
            route_keys=unknown[:_REPORT_LIST_LIMIT],
        )

    st["hub_id"] = pd.to_numeric(st["hub_id"], errors="coerce").astype("Int64")
    st["rail_hub"] = pd.to_numeric(st["rail_hub"], errors="coerce").fillna(0).ne(0)
    st["stop_id"] = st["stop_id"].astype(str)
    stops = gpd.GeoDataFrame(st[STOP_COLUMNS], geometry="geometry", crs=CRS_ITM)
    return stops.reset_index(drop=True)


def _build_hubs(stops: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """One row per ``hub_id`` of the kept stops."""
    rows = []
    for hub_id, grp in stops[stops["hub_id"].notna()].groupby("hub_id", sort=True):
        hub_id = int(hub_id)
        modes = sorted(set(grp["type"]))
        rail_hub = bool(grp["rail_hub"].any())
        keys = sorted(set(grp["route_key"]))
        rows.append({
            "agency_hub_id": hub_id,
            "name": _hub_name(list(grp["station_name"]), hub_id),
            "modes": modes,
            "n_modes": len(modes),
            "rail_hub": rail_hub,
            "agency_type": hub_type_label(modes, rail_hub),
            "route_keys": keys,
            "n_routes": len(keys),
            "geometry": MultiPoint([(g.x, g.y) for g in grp.geometry]),
        })
    frame = pd.DataFrame(rows, columns=HUB_COLUMNS)
    frame["agency_hub_id"] = frame["agency_hub_id"].astype("int64")
    return gpd.GeoDataFrame(frame, geometry="geometry", crs=CRS_ITM)


def read_agency_network(
    gpkg: Path,
    meta: Path | None,
    cfg: CompareConfig,
    report: RunReport | None = None,
) -> AgencyNetwork:
    """Read the agency GeoPackage (and metadata workbook) into routes, stops and hubs.

    Args:
        gpkg: ``MT_Network.gpkg`` with layers ``lines`` and ``stations``.
        meta: ``MT_Network_MetaData.xlsx`` (code dictionary) or ``None``.
        cfg: Comparison settings (``rail_assign_tol_m`` is used here).
        report: Optional report; findings are recorded in section ``agency``.

    Returns:
        The network, every layer in EPSG:2039 (layers in another CRS are reprojected).

    Raises:
        InputError: Listing every problem at once: a missing file, layer, column or CRS, an
            unreadable workbook, a ``line_id`` that is empty.
    """
    gpkg = Path(gpkg)
    problems: list[str] = []
    available = _list_layers(gpkg, problems)
    lines = stations = None
    if available:
        lines = _read_layer(gpkg, "lines", available, LINES_REQUIRED, LINES_OPTIONAL, problems)
        stations = _read_layer(
            gpkg, "stations", available, STATIONS_REQUIRED, STATIONS_OPTIONAL, problems
        )
    labels = _read_labels(Path(meta), problems) if meta is not None else {}
    if lines is not None:
        lines["line_id"] = _int_column(lines, "line_id", "layer 'lines'", problems)
        if lines["type"].isna().any():
            problems.append("layer 'lines': feature(s) with an empty 'type'")
    if stations is not None:
        stations["line_id"] = _int_column(stations, "line_id", "layer 'stations'", problems)
        if stations["type"].isna().any():
            problems.append("layer 'stations': row(s) with an empty 'type'")
    if problems:
        raise InputError(problems)

    lines["type"] = lines["type"].astype(str).str.strip()
    routes = _build_routes(lines)
    stops = _build_stops(stations, lines, routes, cfg, report)
    counts = stops.groupby("route_key").size()
    routes["n_stops"] = routes["route_key"].map(counts).fillna(0).astype("int64")
    routes["has_stops"] = routes["n_stops"] > 0
    routes = routes[ROUTE_COLUMNS].reset_index(drop=True)
    hubs = _build_hubs(stops)

    if report is not None:
        report.info(
            SECTION,
            f"{len(routes)} routes ({int((~routes['has_stops']).sum())} without stations), "
            f"{len(stops)} stops, {len(hubs)} hubs",
        )
    return AgencyNetwork(routes=routes, stops=stops, hubs=hubs, labels=labels)


def read_tod_hubs(path: Path) -> gpd.GeoDataFrame:
    """Read the scraped TOD map into one row per hub (optional cross-check of the agency hubs).

    Args:
        path: GeoPackage with layer ``stations`` (``hub_id``, ``n_modes``, ``type_sum``; one row
            per station, ``hub_id`` empty for non-hub stations), in any CRS.

    Returns:
        Columns ``tod_hub_id`` (``Int64``), ``n_modes``, ``type_sum``, Point geometry in
        EPSG:2039 = the mean position of the hub's stations.

    Raises:
        InputError: If the layer, a column or the CRS is missing.
    """
    path = Path(path)
    problems: list[str] = []
    available = _list_layers(path, problems)
    gdf = None
    if available:
        gdf = _read_layer(path, "stations", available, TOD_REQUIRED, (), problems)
    if problems or gdf is None:
        raise InputError(problems)
    gdf = gdf[gdf["hub_id"].notna()].copy()
    gdf["tod_hub_id"] = pd.to_numeric(gdf["hub_id"]).astype("int64")
    gdf["x"] = gdf.geometry.x
    gdf["y"] = gdf.geometry.y
    grouped = gdf.groupby("tod_hub_id", sort=True).agg(
        n_modes=("n_modes", "max"), type_sum=("type_sum", "max"), x=("x", "mean"), y=("y", "mean")
    ).reset_index()
    out = pd.DataFrame({
        "tod_hub_id": grouped["tod_hub_id"].astype("Int64"),
        "n_modes": grouped["n_modes"].astype("Int64"),
        "type_sum": grouped["type_sum"].round().astype("Int64"),
    })
    return gpd.GeoDataFrame(
        out, geometry=[Point(x, y) for x, y in zip(grouped["x"], grouped["y"])], crs=CRS_ITM
    )
