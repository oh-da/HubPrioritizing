"""Step 2 of ``hubs compare-network``: compare our hub groups with the agency's hubs.

* **Ours** are every group of ``hub_groups_all.csv`` (scored hubs and filtered groups), each a
  MultiPoint of its nodes from ``network_nodes.csv`` (corrected ``x_corr`` / ``y_corr`` when
  present, else the raw ``x_itm`` / ``y_itm``).
* **Pairs.** An agency hub ``H`` and a group ``G`` are a pair when the minimum distance between
  a stop of ``H`` and a node of ``G`` is ``<= cfg.hub_match_tol_m`` (nearest points, not
  centroids). The relation (``1:1``, ``agency_splits``, ``ours_merges``, ``many_to_many``) is
  derived per connected component of the pair graph; ``agency_only`` rows name the nearest
  group in the ``nearest_*`` columns only (their ``group`` stays empty, so a filter or join on
  ``group`` never sees a pair), ``ours_only`` rows list scored and filtered groups alike with
  their ``eligible`` flag.
* **Route evidence** (shown, not part of the rule): the agency routes at ``H`` are mapped to our
  routes at ``G`` through the step-1 pairs of the same mode with ``score >= match_min_score``.

Distances are computed with numpy in chunks after a bounding-box prefilter; the output is
sorted by ``agency_hub_id`` then ``group``, so it is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import MultiPoint

from ..pipeline.report import RunReport
from ..spatial.merging import UnionFind
from .agency import CRS_ITM, AgencyNetwork
from .modes import map_mode
from .routes import AGENCY_ROW_STATUSES, RouteComparison
from .settings import CompareConfig

SECTION = "hubs"
CHUNK = 2048  # points per side in one distance block (<= 64 MB of float64 per block)
SEP = ";"
RELATIONS = ("1:1", "agency_splits", "ours_merges", "many_to_many", "agency_only", "ours_only")
HUB_SIDES = ("shared", "only_agency", "only_ours")

HUB_COMPARISON_COLUMNS = [
    "relation",
    "agency_hub_id", "agency_name", "agency_modes", "agency_n_modes", "agency_rail_hub",
    "agency_type", "agency_n_routes", "agency_total_demand", "tod_type_sum", "tod_disagrees",
    "group", "hub_id", "HubNameHE", "Mode_Planned", "n_modes", "n_lines", "TotalDemand",
    "TotalTransfers", "eligible", "exclusion_reason", "HubType", "TotalScore_MC",
    "RankByHubTypeMetro",
    "distance_m", "nearest_group", "nearest_hub_id", "nearest_HubNameHE", "nearest_eligible",
    "nearest_exclusion_reason",
    "modes_shared", "modes_only_agency", "modes_only_ours", "routes_shared",
    "routes_only_agency", "routes_only_ours", "n_modes_diff",
]  # fmt: skip
HUB_ROUTE_COLUMNS = [
    "agency_hub_id", "group", "side", "our_route_key", "agency_route_key", "route_status",
]
_OUR_FIELDS = [
    "group", "hub_id", "HubNameHE", "Mode_Planned", "n_modes", "n_lines", "TotalDemand",
    "TotalTransfers", "eligible", "exclusion_reason", "HubType", "TotalScore_MC",
    "RankByHubTypeMetro",
]
_NEAREST_FIELDS = ["group", "hub_id", "HubNameHE", "eligible", "exclusion_reason"]
NEAREST_COLUMNS = [f"nearest_{c}" for c in _NEAREST_FIELDS]  # agency_only rows only


@dataclass
class HubComparison:
    """Result of :func:`match_hubs`.

    Attributes:
        hubs: One row per pair plus ``agency_only`` / ``ours_only`` rows
            (``HUB_COMPARISON_COLUMNS``); the ``nearest_*`` columns are filled on
            ``agency_only`` rows only.
        hub_routes: Route evidence per row of ``hubs`` (``HUB_ROUTE_COLUMNS``), ``side`` in
            ``shared`` / ``only_agency`` / ``only_ours``.
    """

    hubs: pd.DataFrame
    hub_routes: pd.DataFrame


# ----------------------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------------------


def _as_list(value: Any) -> list[str]:
    """A list column value that may arrive as a list or as a ``;``-joined string."""
    if isinstance(value, (list, tuple, set, np.ndarray)):
        items = list(value)
    elif value is None or (not isinstance(value, str) and pd.isna(value)):
        items = []
    else:
        items = str(value).split(SEP)
    return [s for s in (str(i).strip() for i in items) if s]


def _join(items: Iterable[str]) -> str:
    return SEP.join(items)


def _to_bool(value: Any) -> Any:
    """``True`` / ``False`` from a bool or its CSV text; ``pd.NA`` when unknown."""
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return pd.NA
    text = str(value).strip().lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    return pd.NA


def _group_ids(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").astype("Int64")


def _coords(geom: Any) -> np.ndarray:
    if geom is None or geom.is_empty:
        return np.empty((0, 2))
    return shapely.get_coordinates(geom)


def _min_dist_by_owner(a: np.ndarray, b: np.ndarray, owner: np.ndarray, n: int) -> np.ndarray:
    """Per owner of the points ``b``: the minimum distance to any point of ``a`` (inf if none)."""
    out = np.full(n, np.inf)
    if len(a) == 0 or len(b) == 0:
        return out
    for j in range(0, len(b), CHUNK):
        bj = b[j:j + CHUNK]
        best = np.full(len(bj), np.inf)
        for i in range(0, len(a), CHUNK):
            d2 = ((a[i:i + CHUNK, None, :] - bj[None, :, :]) ** 2).sum(axis=2)
            best = np.minimum(best, d2.min(axis=0))
        np.minimum.at(out, owner[j:j + CHUNK], np.sqrt(best))
    return out


# ----------------------------------------------------------------------------------------
# Our hubs
# ----------------------------------------------------------------------------------------


def build_our_hubs(
    groups_all: pd.DataFrame,
    network_nodes: pd.DataFrame,
    mode_map: Mapping[str, str | None],
    route_key_of_line: Mapping[str, str],
) -> gpd.GeoDataFrame:
    """One row per group of ``hub_groups_all`` with its modes, routes and node positions.

    Args:
        groups_all: ``hub_groups_all.csv`` frame; ``Mode_Planned`` / ``Line_Unique`` as lists
            or ``;``-joined text.
        network_nodes: ``network_nodes.csv`` frame, optionally with corrected
            ``x_corr`` / ``y_corr`` (used where both parse, else ``x_itm`` / ``y_itm``).
        mode_map: Our mode -> agency type (``None`` = no counterpart).
        route_key_of_line: ``LINE_ID`` -> our route key (:func:`routes.line_route_map`).

    Returns:
        The input columns (``group`` as ``Int64``, the list columns as lists) plus
        ``common_modes`` (sorted distinct agency types, unmapped modes dropped),
        ``route_keys`` (sorted distinct route keys of the group's lines; lines without a route
        skipped) and a MultiPoint geometry of the group's distinct nodes in EPSG:2039 (empty
        for a group without nodes). Sorted by ``group``.
    """
    df = groups_all.copy().reset_index(drop=True)
    df["group"] = _group_ids(df["group"]) if "group" in df.columns else pd.Series(dtype="Int64")
    for col in ("Mode_Planned", "Line_Unique"):
        df[col] = [_as_list(v) for v in df[col]] if col in df.columns else [[]] * len(df)
    df["common_modes"] = [
        sorted({t for t in (map_mode(m, mode_map) for m in modes) if t}) for modes in
        df["Mode_Planned"]
    ]
    df["route_keys"] = [
        sorted({route_key_of_line[ln] for ln in lines if ln in route_key_of_line})
        for lines in df["Line_Unique"]
    ]

    points: dict[int, list[tuple[float, float]]] = {}
    if network_nodes is not None and len(network_nodes):
        nn = network_nodes.copy()
        x = pd.to_numeric(nn["x_itm"], errors="coerce")
        y = pd.to_numeric(nn["y_itm"], errors="coerce")
        if "x_corr" in nn.columns and "y_corr" in nn.columns:
            cx = pd.to_numeric(nn["x_corr"], errors="coerce")
            cy = pd.to_numeric(nn["y_corr"], errors="coerce")
            ok = cx.notna() & cy.notna()
            x, y = cx.where(ok, x), cy.where(ok, y)
        nn = nn.assign(_g=_group_ids(nn["group"]), _x=x, _y=y)
        nn = nn[nn["_g"].notna() & nn["_x"].notna() & nn["_y"].notna()]
        nn = nn.drop_duplicates(["_g", "node"]).sort_values(["_g", "node"], kind="stable")
        for g, grp in nn.groupby("_g", sort=True):
            points[int(g)] = list(zip(grp["_x"], grp["_y"]))
    geoms = [MultiPoint(points.get(int(g), [])) if pd.notna(g) else MultiPoint() for g in
             df["group"]]
    out = gpd.GeoDataFrame(df, geometry=geoms, crs=CRS_ITM)
    return out.sort_values("group", kind="stable").reset_index(drop=True)


# ----------------------------------------------------------------------------------------
# Matching
# ----------------------------------------------------------------------------------------


def _pairs_and_nearest(
    a_pts: list[np.ndarray], b_pts: list[np.ndarray], tol: float
) -> tuple[dict[tuple[int, int], float], dict[int, tuple[int, float]]]:
    """Pairs ``(agency index, group index) -> min distance <= tol`` and, for agency hubs
    without a pair, the nearest group ``(index, distance)``."""
    sizes = [len(p) for p in b_pts]
    b_all = np.vstack(b_pts) if sum(sizes) else np.empty((0, 2))
    owner = np.repeat(np.arange(len(b_pts)), sizes)
    pairs: dict[tuple[int, int], float] = {}
    nearest: dict[int, tuple[int, float]] = {}
    for i, a in enumerate(a_pts):
        if len(a) == 0 or len(b_all) == 0:
            continue
        lo, hi = a.min(axis=0) - tol, a.max(axis=0) + tol
        near = np.all((b_all >= lo) & (b_all <= hi), axis=1)
        dist = _min_dist_by_owner(a, b_all[near], owner[near], len(b_pts))
        hits = np.flatnonzero(dist <= tol)
        for j in hits:
            pairs[(i, int(j))] = float(dist[j])
        if len(hits) == 0:
            full = _min_dist_by_owner(a, b_all, owner, len(b_pts))
            j = int(np.argmin(full))
            nearest[i] = (j, float(full[j]))
    return pairs, nearest


def _relations(n_a: int, pairs: Iterable[tuple[int, int]]) -> dict[tuple[int, int], str]:
    """Relation of each pair from the connected components of the bipartite pair graph."""
    pairs = list(pairs)
    if not pairs:
        return {}
    n_b = max(j for _, j in pairs) + 1
    uf = UnionFind(n_a + n_b)
    for i, j in pairs:
        uf.union(i, n_a + j)
    members: dict[int, tuple[set, set]] = {}
    for i, j in pairs:
        side_a, side_b = members.setdefault(uf.find(i), (set(), set()))
        side_a.add(i)
        side_b.add(j)
    out = {}
    for i, j in pairs:
        n_hubs, n_groups = (len(s) for s in members[uf.find(i)])
        if n_hubs == 1:
            out[(i, j)] = "1:1" if n_groups == 1 else "agency_splits"
        else:
            out[(i, j)] = "ours_merges" if n_groups == 1 else "many_to_many"
    return out


def _tod_join(hubs: gpd.GeoDataFrame, tod: gpd.GeoDataFrame | None, tol: float) -> pd.DataFrame:
    """``tod_type_sum`` / ``tod_disagrees`` per agency hub (centroid of its stops -> nearest
    scraped hub within ``tol``; ties: lowest ``tod_hub_id``)."""
    out = pd.DataFrame({"tod_type_sum": pd.array([pd.NA] * len(hubs), dtype="Int64"),
                        "tod_disagrees": pd.array([pd.NA] * len(hubs), dtype="boolean")})
    if tod is None or len(tod) == 0 or len(hubs) == 0:
        return out
    tod = tod.to_crs(CRS_ITM).sort_values("tod_hub_id", kind="stable")
    t_xy = shapely.get_coordinates(tod.geometry.to_numpy())
    t_sum = pd.to_numeric(tod["type_sum"], errors="coerce").to_numpy(dtype=float)
    for k, (geom, n_modes) in enumerate(zip(hubs.geometry, hubs["n_modes"])):
        xy = _coords(geom)
        if len(xy) == 0:
            continue
        d = np.hypot(*(t_xy - xy.mean(axis=0)).T)
        j = int(np.argmin(d))
        if d[j] <= tol and not np.isnan(t_sum[j]):
            out.loc[k, "tod_type_sum"] = int(round(t_sum[j]))
            out.loc[k, "tod_disagrees"] = int(round(t_sum[j])) != int(n_modes)
    return out


# ----------------------------------------------------------------------------------------
# Row building
# ----------------------------------------------------------------------------------------


def _agency_fields(row: Mapping[str, Any], tod: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "agency_hub_id": row["agency_hub_id"], "agency_name": row["name"],
        "agency_modes": _join(_as_list(row["modes"])), "agency_n_modes": row["n_modes"],
        "agency_rail_hub": bool(row["rail_hub"]), "agency_type": row["agency_type"],
        "agency_n_routes": row["n_routes"], "agency_total_demand": np.nan,
        "tod_type_sum": tod["tod_type_sum"], "tod_disagrees": tod["tod_disagrees"],
    }


def _our_fields(row: Mapping[str, Any], names: Iterable[str] = _OUR_FIELDS) -> dict[str, Any]:
    out = {c: row.get(c) for c in names}
    if "Mode_Planned" in out:
        out["Mode_Planned"] = _join(_as_list(out["Mode_Planned"]))
    out["eligible"] = _to_bool(out["eligible"])
    return out


class _RouteEvidence:
    """Shared / only-agency / only-ours routes at a hub pair from the step-1 result."""

    def __init__(self, routes: RouteComparison, cfg: CompareConfig) -> None:
        p = routes.pairs
        good = p[p["same_mode"].astype(bool) & (pd.to_numeric(p["score"]) >= cfg.match_min_score)]
        self.matched = set(zip(good["our_route_key"], good["agency_route_key"]))
        r = routes.routes
        own = r["our_route_key"].notna() & ~r["status"].isin(AGENCY_ROW_STATUSES)
        ours = r[own].drop_duplicates("our_route_key")
        self.our_status = dict(zip(ours["our_route_key"], ours["status"]))
        self.agency_status: dict[str, str] = {}
        for key, grp in r[r["agency_route_key"].notna()].groupby("agency_route_key"):
            self.agency_status[key] = _join(sorted(set(grp["status"].astype(str))))

    def compare(self, agency_keys: list[str], our_keys: list[str]) -> list[tuple]:
        """``(side, our_route_key, agency_route_key, route_status)`` rows, sorted."""
        shared = sorted((o, a) for o in our_keys for a in agency_keys if (o, a) in self.matched)
        rows = [("shared", o, a, self.our_status.get(o)) for o, a in shared]
        used_a, used_o = {a for _, a in shared}, {o for o, _ in shared}
        rows += [("only_agency", None, a, self.agency_status.get(a)) for a in agency_keys
                 if a not in used_a]
        rows += [("only_ours", o, None, self.our_status.get(o)) for o in our_keys
                 if o not in used_o]
        return rows


def _comparison(agency_modes: list[str] | None, our_modes: list[str] | None,
                evidence: list[tuple]) -> dict[str, Any]:
    a, o = set(agency_modes or []), set(our_modes or [])
    return {
        "modes_shared": _join(sorted(a & o)),
        "modes_only_agency": _join(sorted(a - o)),
        "modes_only_ours": _join(sorted(o - a)),
        "routes_shared": _join(f"{ak}={ok}" for s, ok, ak, _ in evidence if s == "shared"),
        "routes_only_agency": _join(ak for s, _, ak, _ in evidence if s == "only_agency"),
        "routes_only_ours": _join(ok for s, ok, _, _ in evidence if s == "only_ours"),
        "n_modes_diff": (len(a) - len(o)) if agency_modes is not None and our_modes is not None
        else pd.NA,
    }


def _finish(rows: list[dict], route_rows: list[dict]) -> HubComparison:
    hubs = pd.DataFrame(rows, columns=HUB_COMPARISON_COLUMNS)
    for col in ("agency_hub_id", "group", "agency_n_modes", "agency_n_routes", "tod_type_sum",
                "n_modes", "n_lines", "n_modes_diff", "nearest_group"):
        hubs[col] = pd.to_numeric(hubs[col], errors="coerce").astype("Int64")
    for col in ("agency_rail_hub", "tod_disagrees", "eligible", "nearest_eligible"):
        hubs[col] = hubs[col].astype("boolean")
    for col in ("agency_total_demand", "TotalDemand", "TotalTransfers", "TotalScore_MC",
                "RankByHubTypeMetro", "distance_m"):
        hubs[col] = pd.to_numeric(hubs[col], errors="coerce").astype(float)
    hubs = hubs.sort_values(["agency_hub_id", "group"], kind="stable", na_position="last")
    hub_routes = pd.DataFrame(route_rows, columns=HUB_ROUTE_COLUMNS)
    for col in ("agency_hub_id", "group"):
        hub_routes[col] = hub_routes[col].astype("Int64")
    for col in HUB_ROUTE_COLUMNS[2:]:
        hub_routes[col] = hub_routes[col].astype(object).where(hub_routes[col].notna(), None)
    hub_routes = hub_routes.sort_values(["agency_hub_id", "group"], kind="stable",
                                        na_position="last")
    return HubComparison(hubs=hubs.reset_index(drop=True),
                         hub_routes=hub_routes.reset_index(drop=True))


def match_hubs(
    our_hubs: gpd.GeoDataFrame,
    agency: AgencyNetwork,
    routes: RouteComparison,
    cfg: CompareConfig,
    tod: gpd.GeoDataFrame | None = None,
    report: RunReport | None = None,
) -> HubComparison:
    """Pair the agency's hubs with our groups and describe every pair and unmatched hub.

    Args:
        our_hubs: :func:`build_our_hubs` output.
        agency: The agency network (``hubs`` is used).
        routes: Step-1 result; its same-mode pairs with ``score >= cfg.match_min_score`` give
            the shared routes, its ``routes`` frame the ``route_status``.
        cfg: ``hub_match_tol_m``, ``match_min_score`` and ``tod_join_tol_m`` are used.
        tod: Optional :func:`agency.read_tod_hubs` output for the ``tod_type_sum`` cross-check.
        report: Optional report; relation counts become ``hubs_<relation>`` metrics.

    Returns:
        The comparison; empty inputs give frames with every column.
    """
    ours = our_hubs.reset_index(drop=True)
    hubs = agency.hubs.sort_values("agency_hub_id", kind="stable").reset_index(drop=True)
    a_pts = [_coords(g) for g in hubs.geometry]
    b_pts = [_coords(g) for g in ours.geometry]
    pairs, nearest = _pairs_and_nearest(a_pts, b_pts, cfg.hub_match_tol_m)
    relation = _relations(len(hubs), pairs)
    tod_fields = _tod_join(hubs, tod, cfg.tod_join_tol_m)
    evidence = _RouteEvidence(routes, cfg)

    rows: list[dict] = []
    route_rows: list[dict] = []

    def add(rel: str, i: int | None, j: int | None, dist: float, near: int | None = None):
        a = hubs.iloc[i] if i is not None else None
        o = ours.iloc[j] if j is not None else None
        a_keys = _as_list(a["route_keys"]) if a is not None else []
        o_keys = _as_list(o["route_keys"]) if o is not None else []
        ev = evidence.compare(a_keys, o_keys)
        row = {c: None for c in HUB_COMPARISON_COLUMNS}
        row["relation"], row["distance_m"] = rel, dist
        if a is not None:
            row.update(_agency_fields(a, tod_fields.iloc[i]))
        if o is not None:
            row.update(_our_fields(o))
        elif near is not None:
            fields = _our_fields(ours.iloc[near], _NEAREST_FIELDS)
            row.update({f"nearest_{c}": fields[c] for c in _NEAREST_FIELDS})
        row.update(_comparison(_as_list(a["modes"]) if a is not None else None,
                               list(o["common_modes"]) if o is not None else None, ev))
        rows.append(row)
        for side, ok, ak, status in ev:
            route_rows.append({
                "agency_hub_id": a["agency_hub_id"] if a is not None else pd.NA,
                "group": o["group"] if o is not None else pd.NA, "side": side,
                "our_route_key": ok, "agency_route_key": ak, "route_status": status,
            })

    for (i, j), dist in sorted(pairs.items()):
        add(relation[(i, j)], i, j, dist)
    paired_a = {i for i, _ in pairs}
    paired_b = {j for _, j in pairs}
    for i in range(len(hubs)):
        if i not in paired_a:
            j, dist = nearest.get(i, (None, np.nan))
            add("agency_only", i, None, dist, near=j)
    for j in range(len(ours)):
        if j not in paired_b:
            add("ours_only", None, j, np.nan)

    result = _finish(rows, route_rows)
    if report is not None:
        _report(report, result.hubs, len(hubs), len(ours))
    return result


def _report(report: RunReport, hubs: pd.DataFrame, n_agency: int, n_ours: int) -> None:
    counts = hubs["relation"].value_counts()
    for rel in RELATIONS:
        report.set_metric(f"hubs_{rel}", int(counts.get(rel, 0)))
    ours_only = hubs[hubs["relation"] == "ours_only"]
    n_scored = int(ours_only["eligible"].fillna(False).astype(bool).sum())
    report.set_metric("hubs_ours_only_eligible", n_scored)
    report.set_metric("hubs_agency", n_agency)
    report.set_metric("hubs_ours", n_ours)
    summary = ", ".join(f"{int(counts.get(r, 0))} {r}" for r in RELATIONS)
    report.info(
        SECTION,
        f"{n_agency} agency hubs vs {n_ours} groups of ours: {summary} rows "
        f"({n_scored} of the ours_only groups are scored hubs)",
    )
