"""Step 1 of ``hubs compare-network``: compare our routes with the agency's routes.

* **Our routes.** Lines of one mode whose node sets are equal (the two directions) are one
  route, keyed by their sorted ``LINE_ID``s joined with ``+``.
* **Candidates.** For every pair (our route ``R``, agency route ``A``): ``cov_ours`` = share of
  ``R``'s nodes within the route tolerance of ``A``'s geometry (``rail_tol_m`` for the rail
  types), ``cov_agency`` = share of ``A``'s stops (or of its vertices sampled every 100 m when it
  has none) within ``stop_tol_m`` of a node of ``R``; ``score`` = their harmonic mean. Pairs with
  ``score >= only_max_score`` are candidates.
* **Status** of each of our routes follows spec 4.4 in table order (``matched``,
  ``split_merge``, ``partial``, ``weak``, ``mode_differs``, ``ours_only``); agency routes no
  route of ours matches (same mode, ``score >= match_min_score``) get an ``agency_only`` row.

Coverages use the corrected node positions (``x_corr`` / ``y_corr`` when present); the pair
distances are given for both the raw and the corrected positions. Ties are broken by the sorted
route key, so the result is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd
import shapely

from ..pipeline.report import RunReport
from .agency import AgencyNetwork
from .modes import map_mode
from .settings import CompareConfig

SECTION = "routes"
RAIL_TYPES = frozenset({"Rail", "Rail fast"})
SAMPLE_STEP_M = 100.0  # vertex spacing standing in for the stops of a route without stations
STATUSES = (
    "matched", "split_merge", "partial", "weak", "mode_differs", "ours_only", "agency_only",
)

OUR_ROUTE_COLUMNS = [
    "route_key", "line_ids", "line_names", "mode", "agency_type", "node_ids", "n_nodes",
    "short_route", "xy", "xy_raw",
]
PAIR_COLUMNS = [
    "our_route_key", "agency_route_key", "cov_ours", "cov_agency", "score", "same_mode",
    "median_dist_raw_m", "median_dist_corr_m", "max_dist_corr_m",
]
ROUTE_COMPARISON_COLUMNS = [
    "status", "our_route_key", "our_line_ids", "our_line_names", "our_mode", "our_n_nodes",
    "short_route", "agency_route_key", "agency_type", "agency_name", "agency_line_name",
    "agency_n_stops", "cov_ours", "cov_agency", "score", "candidates", "agency_n_our_routes",
    "year_operation", "year_cancel", "source_plan", "reason",
]


@dataclass
class RouteComparison:
    """Result of :func:`match_routes`.

    Attributes:
        pairs: One row per candidate pair (``PAIR_COLUMNS``), any mode.
        routes: One row per route of ours plus one ``agency_only`` row per agency route no
            route of ours matches (``ROUTE_COMPARISON_COLUMNS``).
    """

    pairs: pd.DataFrame
    routes: pd.DataFrame


# ----------------------------------------------------------------------------------------
# Our routes
# ----------------------------------------------------------------------------------------


def _text(value: Any) -> str:
    return "" if value is None or (not isinstance(value, str) and pd.isna(value)) else str(value)


def build_our_routes(
    network_nodes: pd.DataFrame, mode_map: Mapping[str, str | None]
) -> pd.DataFrame:
    """Group the run's lines into routes (lines of one mode with equal node sets).

    Args:
        network_nodes: ``network_nodes.csv`` frame (``node, LINE_ID, line_name, Mode_Planned,
            x_itm, y_itm, ...``), optionally with corrected ``x_corr`` / ``y_corr``.
        mode_map: Our mode -> agency type (``None`` = no counterpart).

    Returns:
        One row per route, sorted by ``route_key`` (``OUR_ROUTE_COLUMNS``). ``node_ids`` follow
        the first member line; ``xy`` (corrected, falling back to raw) and ``xy_raw`` are
        ``(n, 2)`` arrays in that order. Nodes whose raw coordinates do not parse are dropped;
        their number is in ``attrs["dropped_nodes"]``.
    """
    if network_nodes is None or network_nodes.empty:
        empty = pd.DataFrame(columns=OUR_ROUTE_COLUMNS)
        empty.attrs["dropped_nodes"] = 0
        return empty
    df = network_nodes.copy()
    df["LINE_ID"] = df["LINE_ID"].astype(str).str.strip()
    df["_x"] = pd.to_numeric(df["x_itm"], errors="coerce")
    df["_y"] = pd.to_numeric(df["y_itm"], errors="coerce")
    has_corr = "x_corr" in df.columns and "y_corr" in df.columns
    cx = pd.to_numeric(df["x_corr"], errors="coerce") if has_corr else df["_x"]
    cy = pd.to_numeric(df["y_corr"], errors="coerce") if has_corr else df["_y"]
    corr_ok = cx.notna() & cy.notna()
    df["_cx"] = cx.where(corr_ok, df["_x"])
    df["_cy"] = cy.where(corr_ok, df["_y"])
    valid = df["_x"].notna() & df["_y"].notna()
    dropped = int(df.loc[~valid, "node"].nunique())

    good = df[valid]
    first = good.drop_duplicates("node")
    pos = dict(zip(first["node"], zip(first["_x"], first["_y"], first["_cx"], first["_cy"])))
    line_info: dict[str, tuple[str, str, list]] = {}
    for line_id, grp in df.groupby("LINE_ID", sort=True):
        mode = _text(grp["Mode_Planned"].iloc[0])
        names = [n for n in (_text(v) for v in grp["line_name"]) if n]
        nodes = list(dict.fromkeys(grp.loc[valid.loc[grp.index], "node"]))
        line_info[line_id] = (mode, names[0] if names else "", nodes)

    groups: dict[tuple[str, frozenset], list[str]] = {}
    for line_id, (mode, _, nodes) in line_info.items():
        groups.setdefault((mode, frozenset(nodes)), []).append(line_id)

    rows = []
    for (mode, _), line_ids in groups.items():
        line_ids = sorted(line_ids)
        nodes = line_info[line_ids[0]][2]
        coords = np.array([pos[n] for n in nodes], dtype=float).reshape(-1, 4)
        rows.append({
            "route_key": "+".join(line_ids),
            "line_ids": line_ids,
            "line_names": [line_info[i][1] for i in line_ids],
            "mode": mode,
            "agency_type": map_mode(mode, mode_map),
            "node_ids": nodes,
            "n_nodes": len(nodes),
            "short_route": len(nodes) < 2,
            "xy": coords[:, 2:4].copy(),
            "xy_raw": coords[:, 0:2].copy(),
        })
    rows.sort(key=lambda r: r["route_key"])
    out = pd.DataFrame(rows, columns=OUR_ROUTE_COLUMNS)
    out.attrs["dropped_nodes"] = dropped
    return out


def line_route_map(routes: pd.DataFrame) -> dict[str, str]:
    """Return ``LINE_ID`` -> ``route_key`` for every line of :func:`build_our_routes` output."""
    return {
        line: key for key, lines in zip(routes["route_key"], routes["line_ids"]) for line in lines
    }


def order_points(xy: np.ndarray) -> list[int]:
    """Order points along the shortest open path through them (for drawing a route).

    Greedy chains from a few starting points, each improved by 2-opt on a closed tour with a
    dummy node that is free to reach, then cut at the dummy; the shortest path wins.

    Args:
        xy: Point coordinates, shape ``(n, 2)``.

    Returns:
        Indices of ``xy`` in path order; ``list(range(n))`` when ``n <= 2``.
    """
    xy = np.asarray(xy, dtype=float).reshape(-1, 2)
    n = len(xy)
    if n <= 2:
        return list(range(n))
    dist = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1))
    dd = np.zeros((n + 1, n + 1))
    dd[:n, :n] = dist  # node n is the dummy (distance 0 to everything)
    centre = xy.mean(axis=0)
    far = np.argsort(-np.hypot(*(xy - centre).T), kind="stable")[:4]
    starts = list(far) + [int(np.argmin(xy[:, 1])), int(np.argmin(xy[:, 0]))]
    best: list[int] = list(range(n))
    best_len = np.inf
    for s in dict.fromkeys(int(v) for v in starts):
        path, used = [s], {s}
        while len(path) < n:
            cand = [j for j in range(n) if j not in used]
            j = cand[int(np.argmin(dist[path[-1], cand]))]
            path.append(j)
            used.add(j)
        tour = path + [n]
        improved = True
        while improved:
            improved = False
            for i in range(0, n):
                for j in range(i + 2, n + 1):
                    a, b, c, d = tour[i], tour[i + 1], tour[j], tour[(j + 1) % (n + 1)]
                    if a == d:
                        continue
                    if dd[a, c] + dd[b, d] < dd[a, b] + dd[c, d] - 1e-6:
                        tour[i + 1:j + 1] = tour[i + 1:j + 1][::-1]
                        improved = True
        k = tour.index(n)
        open_path = tour[k + 1:] + tour[:k]
        length = float(sum(dist[open_path[t], open_path[t + 1]] for t in range(n - 1)))
        if length < best_len:
            best, best_len = open_path, length
    return [int(i) for i in best]


# ----------------------------------------------------------------------------------------
# Candidates
# ----------------------------------------------------------------------------------------


def _agency_targets(routes: pd.DataFrame, stops: pd.DataFrame) -> list[np.ndarray]:
    """Stop coordinates of each route, or its vertices every 100 m when it has no stops."""
    by_key = {
        key: shapely.get_coordinates(grp.geometry.to_numpy())
        for key, grp in stops.groupby("route_key", sort=True)
    }
    out = []
    for key, geom, has_stops in zip(routes["route_key"], routes.geometry, routes["has_stops"]):
        xy = by_key.get(key)
        if not has_stops or xy is None or len(xy) == 0:
            xy = np.unique(shapely.get_coordinates(shapely.segmentize(geom, SAMPLE_STEP_M)), axis=0)
        out.append(np.asarray(xy, dtype=float).reshape(-1, 2))
    return out


def _covered_share(targets: np.ndarray, xy: np.ndarray, tol: float) -> float:
    """Share of ``targets`` within ``tol`` of any point of ``xy``."""
    if len(targets) == 0 or len(xy) == 0:
        return 0.0
    hit = 0
    for start in range(0, len(targets), 2000):
        block = targets[start:start + 2000]
        d2 = ((block[:, None, :] - xy[None, :, :]) ** 2).sum(axis=2).min(axis=1)
        hit += int((d2 <= tol * tol).sum())
    return hit / len(targets)


def _bounds(geom: Any, targets: np.ndarray) -> np.ndarray:
    b = np.asarray(shapely.bounds(geom), dtype=float)
    if len(targets):
        b = np.array([min(b[0], targets[:, 0].min()), min(b[1], targets[:, 1].min()),
                      max(b[2], targets[:, 0].max()), max(b[3], targets[:, 1].max())])
    return b


def _candidate_pairs(ours: pd.DataFrame, ar: pd.DataFrame, targets: list, cfg: CompareConfig):
    """Every candidate pair (``score >= only_max_score``) as ``PAIR_COLUMNS`` dicts."""
    tols = [cfg.rail_tol_m if t in RAIL_TYPES else cfg.route_tol_m for t in ar["type"]]
    boxes = [_bounds(g, t) for g, t in zip(ar.geometry, targets)]
    geoms = ar.geometry.to_numpy()
    rows = []
    for key, mapped, xy, xy_raw in ours[["route_key", "agency_type", "xy", "xy_raw"]].to_numpy():
        xy = np.asarray(xy, dtype=float).reshape(-1, 2)
        if len(xy) == 0:
            continue
        lo, hi = xy.min(axis=0), xy.max(axis=0)
        points, points_raw = shapely.points(xy), shapely.points(np.asarray(xy_raw, dtype=float))
        for j, akey in enumerate(ar["route_key"]):
            pad = max(tols[j], cfg.stop_tol_m)
            box = boxes[j]
            if not (lo[0] - pad <= box[2] and box[0] <= hi[0] + pad
                    and lo[1] - pad <= box[3] and box[1] <= hi[1] + pad):
                continue
            dist = shapely.distance(points, geoms[j])
            cov_o = float(np.mean(dist <= tols[j]))
            cov_a = _covered_share(targets[j], xy, cfg.stop_tol_m)
            score = 0.0 if cov_o == 0 or cov_a == 0 else 2 * cov_o * cov_a / (cov_o + cov_a)
            if score <= 0 or score < cfg.only_max_score:
                continue
            raw = shapely.distance(points_raw, geoms[j])
            rows.append({
                "our_route_key": key, "agency_route_key": akey, "cov_ours": cov_o,
                "cov_agency": cov_a, "score": score,
                "same_mode": mapped is not None and ar["type"].iat[j] == mapped,
                "median_dist_raw_m": float(np.median(raw)),
                "median_dist_corr_m": float(np.median(dist)),
                "max_dist_corr_m": float(np.max(dist)),
            })
    return rows


def _rank(pair: Mapping[str, Any], other: str) -> tuple:
    """Sort key: score descending (rounded against float noise), then the other side's key."""
    return (-round(pair["score"], 9), pair[other])


def _candidates_text(pairs: list, key_col: str) -> str:
    return "; ".join(f"{p[key_col]} ({p['score']:.2f})" for p in pairs)


# ----------------------------------------------------------------------------------------
# Status
# ----------------------------------------------------------------------------------------


def _both(pair: Mapping[str, Any], threshold: float) -> bool:
    return pair["cov_ours"] >= threshold and pair["cov_agency"] >= threshold


def _status(key, mapped, cands, users, full, cfg) -> tuple[str, dict | None, str]:
    """``(status, chosen pair, reason)`` of one of our routes (spec 4.4, in table order)."""
    if mapped is None:
        return "ours_only", None, "no agency mode"
    same = [p for p in cands if p["same_mode"]]
    cross = [p for p in cands if not p["same_mode"]]
    fulls = [p for p in same if _both(p, cfg.full_cov)]
    if fulls:
        return "matched", fulls[0], ""
    multi = [p for p in same if _both(p, cfg.multi_cov)]
    if len(multi) >= 2:
        return "split_merge", same[0], f"runs over {len(multi)} agency routes"
    if same:
        best = same[0]
        sharing = users.get(best["agency_route_key"], [])
        if (len(sharing) >= 2 and key in sharing
                and not any((k, best["agency_route_key"]) in full for k in sharing)):
            return "split_merge", best, f"agency route shared by {len(sharing)} of our routes"
        if best["score"] >= cfg.match_min_score:
            return "partial", best, ""
        return "weak", best, f"best score below {cfg.match_min_score:g}"
    if cross and cross[0]["score"] >= cfg.match_min_score:
        return "mode_differs", cross[0], "best match is an agency route of another type"
    if cross:
        return "ours_only", None, f"only cross-mode candidates below {cfg.match_min_score:g}"
    return "ours_only", None, "no candidate"


_AGENCY_FIELDS = ("agency_route_key", "agency_name", "agency_line_name", "agency_n_stops",
                  "year_operation", "year_cancel", "source_plan")


def _agency_fields(arow: Mapping[str, Any] | None, labels: Mapping) -> dict[str, Any]:
    if arow is None:
        return dict.fromkeys(_AGENCY_FIELDS)
    plan = arow["source_plan"]
    if isinstance(plan, str):
        plan = labels.get("source_plan", {}).get(plan, plan)
    return {
        "agency_route_key": arow["route_key"], "agency_type": arow["type"],
        "agency_name": arow["name"], "agency_line_name": arow["line_name"],
        "agency_n_stops": int(arow["n_stops"]), "year_operation": arow["year_operation"],
        "year_cancel": arow["year_cancel"], "source_plan": plan,
    }


def match_routes(
    ours: pd.DataFrame,
    agency: AgencyNetwork,
    cfg: CompareConfig,
    report: RunReport | None = None,
) -> RouteComparison:
    """Compare our routes with the agency's routes and give each a status (spec 4.3-4.4).

    Args:
        ours: Output of :func:`build_our_routes`.
        agency: The agency network (routes and stops in EPSG:2039).
        cfg: Tolerances and thresholds.
        report: Optional report; per-status counts are recorded as ``routes_<status>``
            metrics and a summary in section ``routes``.

    Returns:
        The candidate pairs and one status row per route (empty frames keep their columns).
    """
    ar = agency.routes.sort_values("route_key", kind="stable").reset_index(drop=True)
    dropped = int(ours.attrs.get("dropped_nodes", 0))
    ours = ours.sort_values("route_key", kind="stable").reset_index(drop=True)
    mapped = ours["agency_type"].astype(object)
    ours["agency_type"] = mapped.where(mapped.notna(), None)
    targets = _agency_targets(ar, agency.stops)
    pair_rows = _candidate_pairs(ours, ar, targets, cfg) if len(ar) and len(ours) else []

    by_our: dict[str, list] = {}
    by_agency: dict[str, list] = {}
    users: dict[str, list] = {}
    full: set[tuple[str, str]] = set()
    for p in pair_rows:
        by_our.setdefault(p["our_route_key"], []).append(p)
        by_agency.setdefault(p["agency_route_key"], []).append(p)
        if p["same_mode"] and _both(p, cfg.multi_cov):
            users.setdefault(p["agency_route_key"], []).append(p["our_route_key"])
        if p["same_mode"] and _both(p, cfg.full_cov):
            full.add((p["our_route_key"], p["agency_route_key"]))
    for lst in by_our.values():
        lst.sort(key=lambda p: _rank(p, "agency_route_key"))
    for lst in by_agency.values():
        lst.sort(key=lambda p: _rank(p, "our_route_key"))

    arows = {r["route_key"]: r for r in ar.drop(columns="geometry").to_dict("records")}
    rows = []
    for r in ours.to_dict("records"):
        cands = by_our.get(r["route_key"], [])
        status, pair, reason = _status(r["route_key"], r["agency_type"], cands, users, full, cfg)
        akey = pair["agency_route_key"] if pair else None
        rows.append({
            "status": status, "our_route_key": r["route_key"], "our_line_ids": r["line_ids"],
            "our_line_names": r["line_names"], "our_mode": r["mode"],
            "our_n_nodes": r["n_nodes"], "short_route": r["short_route"],
            "agency_type": r["agency_type"],
            **_agency_fields(arows.get(akey), agency.labels),
            "cov_ours": pair["cov_ours"] if pair else None,
            "cov_agency": pair["cov_agency"] if pair else None,
            "score": pair["score"] if pair else None,
            "candidates": _candidates_text(cands, "agency_route_key"),
            "agency_n_our_routes": len(users.get(akey, [])) if akey else None,
            "reason": reason,
        })

    for akey, arow in arows.items():
        on_it = by_agency.get(akey, [])
        same = [p for p in on_it if p["same_mode"]]
        if any(p["score"] >= cfg.match_min_score for p in same):
            continue
        if same:
            reason = f"best score of ours {same[0]['score']:.2f} below {cfg.match_min_score:g}"
        elif on_it:
            reason = "only cross-mode candidates"
        else:
            reason = "no candidate"
        rows.append({
            "status": "agency_only", "our_route_key": None, "our_line_ids": [],
            "our_line_names": [], "our_mode": None, "our_n_nodes": None, "short_route": None,
            **_agency_fields(arow, agency.labels),
            "cov_ours": None, "cov_agency": None, "score": None,
            "candidates": _candidates_text(on_it, "our_route_key"),
            "agency_n_our_routes": len(users.get(akey, [])), "reason": reason,
        })

    routes = pd.DataFrame(rows, columns=ROUTE_COMPARISON_COLUMNS)
    for col in ("our_n_nodes", "agency_n_stops", "agency_n_our_routes"):
        routes[col] = routes[col].astype("Int64")
    routes["short_route"] = routes["short_route"].astype("boolean")
    for col in ("cov_ours", "cov_agency", "score"):
        routes[col] = routes[col].astype(float)
    pairs = pd.DataFrame(pair_rows, columns=PAIR_COLUMNS)
    pairs["same_mode"] = pairs["same_mode"].astype(bool)
    for col in PAIR_COLUMNS[2:5] + PAIR_COLUMNS[6:]:
        pairs[col] = pairs[col].astype(float)

    if report is not None:
        _report(report, routes, ours, len(ar), len(pairs), dropped)
    return RouteComparison(pairs=pairs, routes=routes)


def _report(report: RunReport, routes: pd.DataFrame, ours: pd.DataFrame, n_agency: int,
            n_pairs: int, dropped: int) -> None:
    counts = routes["status"].value_counts()
    for status in STATUSES:
        report.set_metric(f"routes_{status}", int(counts.get(status, 0)))
    n_short = int(ours["short_route"].astype(bool).sum()) if len(ours) else 0
    for name, value in (("routes_ours", len(ours)), ("routes_agency", n_agency),
                        ("route_pairs", n_pairs), ("routes_short", n_short)):
        report.set_metric(name, value)
    if dropped:
        report.warn(SECTION, f"{dropped} node(s) with unparseable coordinates dropped")
    summary = ", ".join(f"{int(counts.get(s, 0))} {s}" for s in STATUSES)
    report.info(
        SECTION,
        f"{len(ours)} routes of ours vs {n_agency} agency routes "
        f"({n_pairs} candidate pairs): {summary}",
        short_routes=n_short,
    )
