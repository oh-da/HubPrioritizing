"""Build one self-contained HTML map of the MISSING LINES and MISSING HUBS between our network
(the hub prioritization pipeline) and the planning agency's (``MT_Network.gpkg``), with an
evaluation verdict for every feature.

Everything about the matching is read from a finished ``hubs compare-network`` run; this script
only evaluates and draws (see "Map of the missing lines and hubs" in docs/NETWORK_COMPARISON.md).

    hubs run --input-dir DIR --output-dir RUN
    hubs compare-network --run RUN --agency-gpkg MT_Network.gpkg --out CMP
    python scripts/build_missing_map.py --compare-dir CMP --run-dir RUN \\
        --agency-gpkg MT_Network.gpkg [--agency-meta MT_Network_MetaData.xlsx] \\
        [--leaflet-dir leaflet/dist] [--out-dir OUT] [--run-note TEXT]

Writes ``missing_lines_hubs_map.html`` and ``missing_map_summary.md`` to ``--out-dir``
(default: ``--compare-dir``). The output is deterministic.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely import STRtree, unary_union
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.compare.agency import read_agency_network  # noqa: E402
from src.compare.map_assets import (  # noqa: E402
    AGENCY_HE,
    BASEMAP_HTML,
    LABELS,
    basemap_js,
    label,
    plain_reason,
)
from src.compare.settings import CompareConfig  # noqa: E402

# ----------------------------------------------------------------------------------------
# Inputs and outputs
# ----------------------------------------------------------------------------------------
HTML_NAME = "missing_lines_hubs_map.html"
SUMMARY_NAME = "missing_map_summary.md"
LEAFLET_VERSION = "1.9.4"
LEAFLET_CDN = f"https://cdnjs.cloudflare.com/ajax/libs/leaflet/{LEAFLET_VERSION}"

# ----------------------------------------------------------------------------------------
# Evaluation rules (all distances in metres, ITM)
# ----------------------------------------------------------------------------------------
STOP_NEAR_NODE_M = 150.0  # an agency stop is "served" when a node of ours is this close
RAIL_STOP_NEAR_NODE_M = 250.0  # same, for our rail nodes vs agency stops (coarser rail data)
ROUTE_NEAR_M = 100.0  # a point is "on" a route (ours or agency) within this distance
RAIL_ROUTE_NEAR_M = 250.0  # same for the rail types (compare-network's rail_tol_m)
SAMPLE_STEP_M = 100.0  # vertices every 100 m stand in for the stops of a route without stops
COVERED_SHARE = 0.5  # >= this share near the other network -> covered_elsewhere
GAP_SHARE = 0.2  # < this share near the other network -> real_gap
FULL_COV = (
    0.8  # compare-network full_cov: mode_differs with both coverages >= -> definition_difference
)
NO_HUB_AROUND_M = 800.0  # nearest hub/group of the other side farther than this -> nothing around
HUB_MATCH_M = 400.0  # compare-network hub_match_tol_m (for the notes)
MIN_DEMAND = 1000.0  # ELIGIBILITY_MIN_PASSENGERS of the pipeline
TOP_NAMED = 3  # name up to this many covering routes in a sentence
SIMPLIFY_M = 2.0  # geometry simplification tolerance (ITM)
COORD_DECIMALS = 5  # ~1 m in WGS84

RAIL_AGENCY_TYPES = {"Rail", "Rail fast"}
RAIL_OUR_MODES = {"Suburban Rail", "Interurban Rail", "HighSpeed Rail", "Rail"}
# Step-1 statuses that mean "this route exists on the other side"
REAL_MATCH = {"matched", "split_merge", "partial", "ours_within_agency", "agency_within_ours"}
AGENCY_COVERED = REAL_MATCH | {"covered"}
CONTEXT_STATUSES = sorted(AGENCY_COVERED)
DOUBT_STATUSES = ("weak", "mode_differs")

VERDICTS = ("real_gap", "covered_elsewhere", "definition_difference", "check", "present")
VERDICT_LABEL = {v: LABELS["verdict"][v][0] for v in VERDICTS}  # the shared label map
AG = AGENCY_HE  # the planning agency, as every visible text names it

SETS = [  # id, label (the page template has the same order)
    ("ag_line", f"{AG} lines we don't have"),
    ("our_line", f"Our lines {AG} doesn't have"),
    ("doubt", "Unclear lines"),
    ("both_line", "Lines in both"),
    ("ag_hub", f"{AG} hubs with no hub of ours"),
    ("ag_hub_filt", f"{AG} hubs we filtered out"),
    ("our_hub", f"Our hubs {AG} doesn't have"),
    ("both_hub", "Hubs in both"),
]

TO_WGS = Transformer.from_crs("EPSG:2039", "EPSG:4326", always_xy=True)


# ----------------------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------------------
def blank(v) -> bool:
    return (
        v is None
        or (isinstance(v, float) and math.isnan(v))
        or (isinstance(v, str) and not v.strip())
    )


def txt(v) -> str:
    if blank(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def num(v, default=None):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(f) else f


def truthy(v) -> bool:
    """eligible / rail_hub columns come back as 1.0 / 0.0 / NaN / bool / 'True'."""
    if isinstance(v, str):
        return v.strip().lower() in {"true", "1", "yes"}
    f = num(v)
    return bool(f) if f is not None else False


def fmt_int(v) -> str:
    f = num(v)
    return "" if f is None else f"{int(round(f)):,}"


def fmt_m(v) -> str:
    f = num(v)
    return "" if f is None else f"{int(round(f)):,} m"


def pct(x: float) -> str:
    return f"{round(100 * x):d}%"


def split_list(v, sep=";") -> list[str]:
    return [p.strip() for p in txt(v).split(sep) if p.strip()]


def reasons_text(v) -> str:
    """Exclusion reasons (``"a;b"`` or a list) in plain words, joined with ``", "``."""
    items = v if isinstance(v, (list, tuple, set)) else split_list(v)
    return ", ".join(label("exclusion", x) for x in items)


def latlng(x: float, y: float) -> list[float]:
    lon, lat = TO_WGS.transform(x, y)
    return [round(lat, COORD_DECIMALS), round(lon, COORD_DECIMALS)]


def lines_of(geom) -> list[list[list[float]]]:
    """(Multi)LineString in ITM -> list of [[lat,lng], ...], lightly simplified."""
    if geom is None or geom.is_empty:
        return []
    g = geom.simplify(SIMPLIFY_M, preserve_topology=False)
    parts = list(g.geoms) if hasattr(g, "geoms") else [g]
    out = []
    for part in parts:
        if isinstance(part, LineString) and len(part.coords) >= 2:
            out.append([latlng(x, y) for x, y, *_ in part.coords])
    return out


def point_of(geom) -> list[float]:
    c = geom.centroid
    return latlng(c.x, c.y)


def sample_line(geom, step=SAMPLE_STEP_M) -> list[Point]:
    parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    pts = []
    for part in parts:
        n = max(1, int(part.length // step))
        pts.extend(part.interpolate(i * part.length / n) for i in range(n + 1))
    return pts


def first_names(counter: Counter, k=TOP_NAMED) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:k]


# ----------------------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------------------
def load(paths: dict) -> dict:
    """Read the comparison workbook and layers, the run's group table and the agency network."""
    routes = pd.read_excel(paths["workbook"], sheet_name="routes")
    hubs = pd.read_excel(paths["workbook"], sheet_name="hubs")
    gpkg = paths["gpkg"]
    pairs = gpd.read_file(gpkg, layer="route_pairs")
    our_routes = gpd.read_file(gpkg, layer="our_routes")
    agency_hubs = gpd.read_file(gpkg, layer="agency_hubs")
    our_groups = gpd.read_file(gpkg, layer="our_groups")
    ties = gpd.read_file(gpkg, layer="hub_ties")
    groups_csv = pd.read_csv(paths["groups_csv"], encoding="utf-8-sig")
    net = read_agency_network(paths["agency_gpkg"], paths["agency_meta"], CompareConfig())
    return dict(
        routes=routes,
        hubs=hubs,
        pairs=pairs,
        our_routes=our_routes,
        agency_hubs=agency_hubs,
        our_groups=our_groups,
        ties=ties,
        groups_csv=groups_csv,
        net=net,
    )


class Index:
    """Spatial lookups shared by the evaluations."""

    def __init__(self, d):
        net = d["net"]
        # our nodes = the vertices of our_routes (offset-corrected positions), one per route x node
        self.node_pts, self.node_route = [], []
        for key, mode, geom in zip(
            d["our_routes"]["route_key"], d["our_routes"]["mode"], d["our_routes"].geometry
        ):
            coords = [geom.coords[0]] if geom.geom_type == "Point" else list(geom.coords)
            for x, y, *_ in coords:
                self.node_pts.append(Point(x, y))
                self.node_route.append(key)
        self.our_mode = dict(zip(d["our_routes"]["route_key"], d["our_routes"]["mode"]))
        self.our_names = {}
        for _, r in d["routes"].iterrows():
            if r["status"] not in ("agency_only", "covered") and not blank(r["our_route_key"]):
                self.our_names[r["our_route_key"]] = txt(r["our_line_names"]).strip("; ")
        self.node_tree = STRtree(self.node_pts)
        # our node chains (visual aid) buffered: a point of an agency route is "on" ours when inside
        lines = [g for g in d["our_routes"].geometry if g.geom_type == "LineString"]
        pts = [g for g in d["our_routes"].geometry if g.geom_type == "Point"]
        self.our_buf = unary_union([g.buffer(ROUTE_NEAR_M) for g in lines + pts])
        self.our_buf_rail = unary_union([g.buffer(RAIL_ROUTE_NEAR_M) for g in lines + pts])
        # agency stops and route geometry
        self.stops = net.stops
        self.stop_tree = STRtree(list(net.stops.geometry))
        self.ag_routes = net.routes.set_index("route_key")
        self.ag_route_keys = list(net.routes["route_key"])
        self.ag_route_geoms = list(net.routes.geometry)
        self.ag_route_tree = STRtree(self.ag_route_geoms)
        self.labels = net.labels
        # agency hubs and our groups
        self.ag_hub_geom = dict(
            zip(d["agency_hubs"]["agency_hub_id"].astype(int), d["agency_hubs"].geometry)
        )
        self.group_geom = dict(zip(d["our_groups"]["group"].astype(int), d["our_groups"].geometry))
        hub_ids = sorted(self.ag_hub_geom)
        self.ag_hub_ids = hub_ids
        self.ag_hub_tree = STRtree([self.ag_hub_geom[h] for h in hub_ids])
        # route step-1 statuses per key
        self.status_ours = {}
        self.status_agency = defaultdict(set)
        for _, r in d["routes"].iterrows():
            if r["status"] not in ("agency_only", "covered") and not blank(r["our_route_key"]):
                self.status_ours[r["our_route_key"]] = r["status"]
            if not blank(r["agency_route_key"]):
                self.status_agency[r["agency_route_key"]].add(r["status"])

    def agency_type_label(self, t: str) -> str:
        he = self.labels.get("type", {}).get(t)
        return f"{t} ({he})" if he else t


# ----------------------------------------------------------------------------------------
# Feature builders, one per set
# ----------------------------------------------------------------------------------------
def feature(fid, set_id, verdict, why, title, facts, geom, tip):
    return {
        "id": fid,
        "s": set_id,
        "v": verdict,
        "why": why,
        "t": title,
        "f": [[k, v] for k, v in facts if not blank(v)],
        "g": geom,
        "tip": tip,
    }


def agency_route_facts(ix: Index, r) -> list:
    key = r["agency_route_key"]
    geom = ix.ag_routes.loc[key, "geometry"] if key in ix.ag_routes.index else None
    t = txt(r["agency_type"])
    facts = [
        (f"line of {AG}", key),
        ("mode", ix.agency_type_label(t)),
        ("name", txt(r["agency_name"])),
        ("line name", txt(r["agency_line_name"])),
        ("stops", fmt_int(r["agency_n_stops"])),
        ("length", f"{geom.length / 1000:.1f} km" if geom is not None else ""),
        ("opens", txt(r["year_operation"])),
        ("ends", txt(r["year_cancel"])),
        ("plan", txt(r["source_plan"])),
    ]
    if t in RAIL_AGENCY_TYPES:
        facts.append(("note", f"{AG} draws rail in short pieces, so rail results are rough"))
    return facts


def eval_agency_route(ix: Index, key: str):
    """Stops (or 100 m vertices) of an agency route against ANY node / chain of ours."""
    geom = ix.ag_routes.loc[key, "geometry"]
    t = ix.ag_routes.loc[key, "type"]
    st = ix.stops[ix.stops["route_key"] == key]
    has_stops = len(st) > 0
    pts = list(st.geometry) if has_stops else sample_line(geom)
    idx, dist = ix.node_tree.query_nearest(pts, return_distance=True, all_matches=False)
    near_d = np.full(len(pts), np.inf)
    near_d[idx[0]] = dist
    served = near_d <= STOP_NEAR_NODE_M
    share = float(served.mean()) if len(pts) else 0.0
    # which of our routes serve the covered stops
    by_route = Counter()
    hit_pt, hit_node = ix.node_tree.query(pts, predicate="dwithin", distance=STOP_NEAR_NODE_M)
    seen = set()
    for p, n in zip(hit_pt, hit_node):
        k = (int(p), ix.node_route[n])
        if k not in seen:
            seen.add(k)
            by_route[ix.node_route[n]] += 1
    buf = ix.our_buf_rail if t in RAIL_AGENCY_TYPES else ix.our_buf
    len_share = geom.intersection(buf).length / geom.length if geom.length else 0.0
    return dict(
        n=len(pts),
        served=int(served.sum()),
        share=share,
        far=float(near_d.max()),
        len_share=len_share,
        by_route=by_route,
        has_stops=has_stops,
        tol=RAIL_ROUTE_NEAR_M if t in RAIL_AGENCY_TYPES else ROUTE_NEAR_M,
    )


def build_agency_lines(d, ix: Index) -> list:
    out = []
    rows = d["routes"][d["routes"]["status"] == "agency_only"].sort_values("agency_route_key")
    for _, r in rows.iterrows():
        key = r["agency_route_key"]
        ev = eval_agency_route(ix, key)
        what = "stops" if ev["has_stops"] else "points every 100 m (it has no stops)"
        top = first_names(ev["by_route"])
        named = ", ".join(f"{k} ({ix.our_mode.get(k, '')}, {c})" for k, c in top)
        if ev["share"] >= COVERED_SHARE:
            v = "covered_elsewhere"
            why = (
                f"{ev['served']} of {ev['n']} {what} have a stop of ours within "
                f"{STOP_NEAR_NODE_M:g} m, mostly on our lines {named} "
                "(another mode or path, so the comparison did not pair them)."
            )
        elif ev["share"] < GAP_SHARE:
            v = "real_gap"
            why = (
                f"No stop of ours within {STOP_NEAR_NODE_M:g} m of {ev['n'] - ev['served']} of "
                f"{ev['n']} {what}; the farthest is {fmt_m(ev['far'])} from our nearest stop."
            )
        else:
            v = "check"
            why = (
                f"{ev['served']} of {ev['n']} {what} ({pct(ev['share'])}) have a stop of ours "
                "within "
                f"{STOP_NEAR_NODE_M:g} m: partly served" + (f", by {named}" if named else "") + "."
            )
        facts = agency_route_facts(ix, r) + [
            (f"{what} near our stops", f"{ev['served']} / {ev['n']} ({pct(ev['share'])})"),
            ("farthest stop from our stops", fmt_m(ev["far"])),
            (f"length within {ev['tol']:g} m of our lines", pct(ev["len_share"])),
            ("our lines nearby", named),
            ("comparison note", plain_reason(r["reason"])),
            ("close lines of ours", txt(r["candidates"])),
        ]
        geom = {"a": lines_of(ix.ag_routes.loc[key, "geometry"])}
        title = txt(r["agency_name"]) or key
        out.append(
            feature(
                f"ag_line:{key}",
                "ag_line",
                v,
                why,
                title,
                facts,
                geom,
                f"{title} · only in {AG} · {VERDICT_LABEL[v]}",
            )
        )
    return out


def eval_our_route(ix: Index, key: str, geom, mapped: str):
    rail = ix.our_mode.get(key) in RAIL_OUR_MODES
    coords = [geom.coords[0]] if geom.geom_type == "Point" else list(geom.coords)
    pts = [Point(x, y) for x, y, *_ in coords]
    stop_tol = RAIL_STOP_NEAR_NODE_M if rail else STOP_NEAR_NODE_M
    route_tol = RAIL_ROUTE_NEAR_M if rail else ROUTE_NEAR_M
    idx, dist = ix.stop_tree.query_nearest(pts, return_distance=True, all_matches=False)
    near_stop = np.full(len(pts), np.inf)
    near_stop[idx[0]] = dist
    hit_pt, hit_route = ix.ag_route_tree.query(pts, predicate="dwithin", distance=route_tol)
    any_near, other_near = set(), set()
    by_route = Counter()
    seen = set()
    for p, a in zip(hit_pt, hit_route):
        akey = ix.ag_route_keys[a]
        atype = ix.ag_routes.loc[akey, "type"]
        any_near.add(int(p))
        if atype != mapped:
            other_near.add(int(p))
        if (int(p), akey) not in seen:
            seen.add((int(p), akey))
            by_route[akey] += 1
    n = len(pts)
    return dict(
        n=n,
        stop_share=float((near_stop <= stop_tol).mean()),
        stop_tol=stop_tol,
        route_tol=route_tol,
        any_share=len(any_near) / n,
        other_share=len(other_near) / n,
        by_route=by_route,
        nearest_stop=float(near_stop.min()),
    )


def build_our_lines(d, ix: Index) -> list:
    out = []
    geoms = dict(zip(d["our_routes"]["route_key"], d["our_routes"].geometry))
    rows = d["routes"][d["routes"]["status"] == "ours_only"].sort_values("our_route_key")
    for _, r in rows.iterrows():
        key = r["our_route_key"]
        mapped = txt(r["agency_type"])
        ev = eval_our_route(ix, key, geoms[key], mapped)
        top = first_names(ev["by_route"])
        named = ", ".join(f"{k} ({ix.ag_routes.loc[k, 'type']}, {c})" for k, c in top)
        reason = txt(r["reason"])
        if reason == "no agency mode":
            v = "definition_difference"
            why = (
                f"Our mode {r['our_mode']} has no counterpart at {AG}, so it cannot match"
                + (f"; their lines nearby: {named}" if named else "") + "."
            )
        elif ev["other_share"] >= COVERED_SHARE:
            v = "covered_elsewhere"
            why = (
                f"{pct(ev['other_share'])} of its stops lie within {ev['route_tol']:g} m of a "
                f"line of {AG} of another mode: {named}."
            )
        elif max(ev["any_share"], ev["stop_share"]) < GAP_SHARE:
            v = "real_gap"
            why = (
                f"Only {pct(ev['any_share'])} of its stops are within {ev['route_tol']:g} m of "
                f"any line of {AG} and {pct(ev['stop_share'])} within {ev['stop_tol']:g} m of "
                f"one of their stops: {AG} has no line here."
            )
        else:
            v = "check"
            why = (
                f"{pct(ev['any_share'])} of its stops are near a line of {AG} "
                f"({named or 'none'}), but not enough to match: partly on their lines."
            )
        facts = [
            ("our line", key),
            ("mode", txt(r["our_mode"])),
            ("line ids", txt(r["our_line_ids"])),
            ("line names", txt(r["our_line_names"]).strip("; ")),
            ("stops", fmt_int(r["our_n_nodes"])),
            (f"stops within {ev['stop_tol']:g} m of a stop of {AG}", pct(ev["stop_share"])),
            (f"stops within {ev['route_tol']:g} m of a line of {AG}", pct(ev["any_share"])),
            ("… of another mode", pct(ev["other_share"])),
            (f"lines of {AG} nearby", named),
            ("comparison note", plain_reason(reason)),
            ("close lines", txt(r["candidates"])),
            ("shape", "drawn through the stops in order"),
        ]
        geom = geoms[key]
        g = {"op": point_of(geom)} if geom.geom_type == "Point" else {"o": lines_of(geom)}
        out.append(
            feature(
                f"our_line:{key}",
                "our_line",
                v,
                why,
                key,
                facts,
                g,
                f"{key} ({r['our_mode']}) · only in Hubs project · {VERDICT_LABEL[v]}",
            )
        )
    return out


def build_doubtful(d, ix: Index) -> list:
    out = []
    geoms = dict(zip(d["our_routes"]["route_key"], d["our_routes"].geometry))
    pairs = d["pairs"]
    rows = d["routes"][d["routes"]["status"].isin(DOUBT_STATUSES)].sort_values("our_route_key")
    for _, r in rows.iterrows():
        key, akey = r["our_route_key"], r["agency_route_key"]
        co, ca, sc = num(r["cov_ours"], 0), num(r["cov_agency"], 0), num(r["score"], 0)
        if r["status"] == "mode_differs" and co >= FULL_COV and ca >= FULL_COV:
            v = "definition_difference"
            why = (
                f"Same path (overlap {co:.2f} / {ca:.2f}), but ours is {r['our_mode']} and "
                f"their {akey} is {r['agency_type']}: the two sides name the mode differently."
            )
        elif r["status"] == "mode_differs":
            v = "check"
            why = (
                f"Runs on their line {akey} ({r['agency_type']}) with overlap score {sc:.2f}, "
                f"but ours is {r['our_mode']} and the overlap shares ({co:.2f} / {ca:.2f}) are "
                f"not both ≥ {FULL_COV}."
            )
        else:
            v = "check"
            why = (
                f"Their closest line of the same mode, {akey}, only partly overlaps (ours on it "
                f"{co:.2f}, its stops near ours {ca:.2f}, overlap score {sc:.2f} < 0.5): a "
                "different path or length."
            )
        prow = pairs[(pairs["status"] == r["status"]) & (pairs["our_route_key"] == key)]
        g = {"a": lines_of(prow.geometry.iloc[0]) if len(prow) else []}
        geom = geoms.get(key)
        if geom is not None:
            if geom.geom_type == "Point":
                g["op"] = point_of(geom)
            else:
                g["o"] = lines_of(geom)
        facts = [
            ("result", label("route_status", r["status"])),
            ("our line", key),
            ("our mode", txt(r["our_mode"])),
            ("our stops", fmt_int(r["our_n_nodes"])),
            (f"closest line of {AG}", akey),
            ("its mode", ix.agency_type_label(txt(r["agency_type"]))),
            ("its name", txt(r["agency_name"])),
            ("its stops", fmt_int(r["agency_n_stops"])),
            ("share of our line on theirs", f"{co:.2f}"),
            ("share of their line on ours", f"{ca:.2f}"),
            ("overlap score", f"{sc:.2f}"),
            ("close lines", txt(r["candidates"])),
            (
                "other results for their line",
                "; ".join(label("route_status", x) for x in
                          sorted(ix.status_agency.get(akey, set()) - {r["status"]})),
            ),
            ("drawing", f"dashed green = ours (through the stops in order), dashed orange = {AG}"),
        ]
        out.append(
            feature(
                f"doubt:{key}",
                "doubt",
                v,
                why,
                key,
                facts,
                g,
                f"{key} ↔ {akey} · {label('route_status', r['status'])} · {VERDICT_LABEL[v]}",
            )
        )
    return out


def build_both_lines(d, ix: Index) -> list:
    out = []
    pairs = d["pairs"]
    rows = d["routes"][d["routes"]["status"].isin(CONTEXT_STATUSES)]
    for akey, grp in sorted(rows.groupby("agency_route_key"), key=lambda kv: kv[0]):
        r0 = grp.iloc[0]
        ours = sorted(f"{k} ({label('route_status', s)})"
                      for k, s in zip(grp["our_route_key"].map(txt), grp["status"]))
        best = grp["score"].max()
        prow = pairs[pairs["agency_route_key"] == akey]
        g = {
            "a": (
                lines_of(ix.ag_routes.loc[akey, "geometry"])
                if akey in ix.ag_routes.index
                else lines_of(prow.geometry.iloc[0])
            )
        }
        facts = agency_route_facts(ix, r0)[:5] + [
            ("our lines on it", "; ".join(ours)),
            ("best overlap score", f"{num(best, 0):.2f}"),
        ]
        why = (
            f"Their line has {len(grp)} line(s) of ours on it "
            f"({', '.join(sorted({label('route_status', x) for x in grp['status']}))}): "
            "in both, shown for context."
        )
        title = txt(r0["agency_name"]) or akey
        out.append(
            feature(
                f"both_line:{akey}",
                "both_line",
                "present",
                why,
                title,
                facts,
                g,
                f"{title} · in both",
            )
        )
    return out


def agency_hub_facts(r) -> list:
    return [
        ("hub id", txt(r["agency_hub_id"])),
        ("type (worked out from its modes)", txt(r["agency_type"])),
        ("modes", txt(r["agency_modes"])),
        ("lines", fmt_int(r["agency_n_routes"])),
        ("at a rail station", "yes" if truthy(r["agency_rail_hub"]) else "no"),
    ]


def build_agency_hubs_missing(d, ix: Index) -> list:
    out = []
    rows = d["hubs"][d["hubs"]["relation"] == "agency_only"].sort_values("agency_hub_id")
    for _, r in rows.iterrows():
        hid = int(r["agency_hub_id"])
        dist = num(r["distance_m"], float("inf"))
        aroutes = split_list(r["routes_only_agency"])
        present = sorted(k for k in aroutes if ix.status_agency.get(k, set()) & AGENCY_COVERED)
        ng = int(r["nearest_group"]) if num(r["nearest_group"]) is not None else None
        n_el = truthy(r["nearest_eligible"])
        n_reason = reasons_text(r["nearest_exclusion_reason"]) or ("—" if n_el else "")
        if dist > NO_HUB_AROUND_M and not present:
            v = "real_gap"
            why = (
                f"No stop of ours within {NO_HUB_AROUND_M:g} m (nearest group {fmt_m(dist)} away) "
                f"and none of its {len(aroutes)} line(s) is in our network."
            )
        elif dist > NO_HUB_AROUND_M:
            v = "check"
            why = (
                f"Its line(s) {', '.join(present)} exist in our network, but no stop of ours is "
                f"within {NO_HUB_AROUND_M:g} m ({fmt_m(dist)}): the stops or the path differ."
            )
        else:
            state = "a scored hub" if n_el else f"not scored ({n_reason})"
            v = "check"
            why = (
                f"Our group {ng} is {fmt_m(dist)} away (farther than the {HUB_MATCH_M:g} m used "
                f"to match hubs) and is {state}."
                + (f" Its lines {', '.join(present)} are in our network." if present else "")
            )
        facts = agency_hub_facts(r) + [
            ("its lines", "; ".join(aroutes)),
            ("of them in our network", "; ".join(present) or "none"),
            ("nearest group of ours", txt(ng)),
            ("nearest group name", txt(r["nearest_HubNameHE"])),
            ("distance to it", fmt_m(dist)),
            ("nearest group scored", "yes" if n_el else "no"),
            ("why it is not scored", reasons_text(r["nearest_exclusion_reason"])),
        ]
        hgeom = ix.ag_hub_geom[hid]
        g = {"p": point_of(hgeom)}
        if ng is not None and ng in ix.group_geom:
            a, b = nearest_points(hgeom, ix.group_geom[ng])
            g["near"] = point_of(ix.group_geom[ng])
            g["ties"] = [[latlng(a.x, a.y), latlng(b.x, b.y)]]
        title = txt(r["agency_name"]) or f"hub {hid}"
        out.append(
            feature(
                f"ag_hub:{hid}",
                "ag_hub",
                v,
                why,
                title,
                facts,
                g,
                f"{title} · hub only in {AG} · {VERDICT_LABEL[v]}",
            )
        )
    return out


def paired(d):
    p = d["hubs"][~d["hubs"]["relation"].isin(["agency_only", "ours_only"])].copy()
    p["agency_hub_id"] = p["agency_hub_id"].astype(int)
    p["group"] = p["group"].astype(int)
    p["el"] = p["eligible"].map(truthy)
    return p


def ties_for(d, hid: int, groups: list[int]) -> list:
    t = d["ties"]
    sel = t[(t["agency_hub_id"].astype(int) == hid) & (t["group"].astype(int).isin(groups))]
    sel = sel.sort_values("group")
    out = []
    for geom in sel.geometry:
        out.extend(lines_of(geom) or [[latlng(*geom.coords[0][:2]), latlng(*geom.coords[-1][:2])]])
    return out


def build_agency_hubs_filtered(d, ix: Index) -> list:
    out = []
    p = paired(d)
    for hid, grp in sorted(p.groupby("agency_hub_id"), key=lambda kv: kv[0]):
        if grp["el"].any():
            continue
        grp = grp.sort_values("group")
        reasons = sorted({x for v in grp["exclusion_reason"] for x in split_list(v)})
        modes = sorted({m for v in grp["Mode_Planned"] for m in split_list(v)})
        demand = sum(num(x, 0) for x in grp["TotalDemand"])
        max_dem = max(num(x, 0) for x in grp["TotalDemand"])
        r0 = grp.iloc[0]
        needs = []
        if "demand < min" in reasons:
            needs.append(
                f"{fmt_int(MIN_DEMAND - max_dem)} more passengers a day on the busiest group "
                f"({fmt_int(max_dem)} of {fmt_int(MIN_DEMAND)})"
            )
        if "single mode" in reasons:
            needs.append("a second mass-transit mode in the group")
        if "rail only" in reasons:
            needs.append("a mode that is not rail")
        merged = (
            f" Together its {len(grp)} groups have {len(modes)} mode(s) and {fmt_int(demand)} "
            "passengers a day."
            if len(grp) > 1
            else ""
        )
        if "demand < min" in reasons:
            v = "check"
            why = (
                f"Our group(s) exist but are not scored ({reasons_text(reasons)}): the busiest "
                f"has {fmt_int(max_dem)} passengers a day, the minimum is "
                f"{fmt_int(MIN_DEMAND)}.{merged}"
            )
        else:
            v = "definition_difference"
            what = []
            if "single mode" in reasons:
                what.append(
                    f"{AG} counts changes within one mode as hubs, our rule needs 2 or more modes"
                )
            if "rail only" in reasons:
                what.append("our rule needs a mode that is not rail")
            why = f"Not scored ({reasons_text(reasons)}): {'; '.join(what)}.{merged}"
        gl = [
            " · ".join(
                x
                for x in (f"group {int(g)}", txt(n), txt(m), f"{fmt_int(dm)} a day",
                          reasons_text(e))
                if x
            )
            for g, n, m, dm, e in zip(
                grp["group"],
                grp["HubNameHE"],
                grp["Mode_Planned"],
                grp["TotalDemand"],
                grp["exclusion_reason"],
            )
        ]
        facts = agency_hub_facts(r0) + [
            (f"our groups within {HUB_MATCH_M:g} m (none scored)", " | ".join(gl)),
            ("why not scored", reasons_text(reasons)),
            (
                "modes at both",
                "; ".join(sorted({m for v in grp["modes_shared"] for m in split_list(v)})),
            ),
            (
                "lines at both",
                "; ".join(sorted({m for v in grp["routes_shared"] for m in split_list(v)})),
            ),
            ("needed to be scored", "; ".join(needs)),
        ]
        hgeom = ix.ag_hub_geom[hid]
        groups = [int(x) for x in grp["group"]]
        g = {
            "p": point_of(hgeom),
            "grp": [point_of(ix.group_geom[x]) for x in groups],
            "ties": ties_for(d, hid, groups),
        }
        title = txt(r0["agency_name"]) or f"hub {hid}"
        out.append(
            feature(
                f"ag_hub_filt:{hid}",
                "ag_hub_filt",
                v,
                why,
                title,
                facts,
                g,
                f"{title} · our group not scored · {VERDICT_LABEL[v]}",
            )
        )
    return out


def build_our_hubs_missing(d, ix: Index) -> list:
    out = []
    h = d["hubs"]
    rows = h[(h["relation"] == "ours_only") & h["eligible"].map(truthy)].copy()
    rows["group"] = rows["group"].astype(int)
    for _, r in rows.sort_values("group").iterrows():
        gid = int(r["group"])
        geom = ix.group_geom[gid]
        idx, dist = ix.ag_hub_tree.query_nearest([geom], return_distance=True, all_matches=False)
        nh = ix.ag_hub_ids[int(idx[1][0])]
        nd = float(dist[0])
        aname = txt(d["agency_hubs"].set_index("agency_hub_id").loc[nh, "name"])
        oroutes = split_list(r["routes_only_ours"])
        matched = sorted(k for k in oroutes if ix.status_ours.get(k) in REAL_MATCH)
        if nd > NO_HUB_AROUND_M and not matched:
            v = "real_gap"
            why = (
                f"No hub of {AG} within {NO_HUB_AROUND_M:g} m (nearest {fmt_m(nd)}) and none of "
                f"its {len(oroutes)} line(s) matches one of theirs: {AG} does not have this hub."
            )
        elif nd > NO_HUB_AROUND_M:
            v = "check"
            why = (
                f"No hub of {AG} within {NO_HUB_AROUND_M:g} m (nearest {fmt_m(nd)}), but its "
                f"lines {', '.join(matched)} match lines of {AG}: they have the lines, not a hub "
                "here."
            )
        else:
            v = "check"
            why = (
                f"The nearest hub of {AG}, {nh}, is {fmt_m(nd)} away, farther than the "
                f"{HUB_MATCH_M:g} m used to match hubs"
                + (f"; lines {', '.join(matched)} match lines of {AG}." if matched else ".")
            )
        facts = [
            ("group", str(gid)),
            ("hub id", txt(r["hub_id"])),
            ("hub type", label("hub_type", txt(r["HubType"])) if txt(r["HubType"]) else ""),
            ("rank in its type and area", txt(r["RankByHubTypeMetro"])),
            (
                "score",
                f"{num(r['TotalScore_MC'], 0):.2f}" if num(r["TotalScore_MC"]) is not None else "",
            ),
            ("passengers a day", fmt_int(r["TotalDemand"])),
            ("modes", txt(r["Mode_Planned"])),
            ("lines", fmt_int(r["n_lines"])),
            ("our lines", "; ".join(oroutes)),
            (f"of them matching a line of {AG}", "; ".join(matched) or "none"),
            (f"nearest hub of {AG}", " · ".join(x for x in (f"hub {nh}", aname) if x)),
            ("distance to it", fmt_m(nd)),
        ]
        g = {"p": point_of(geom)}
        title = txt(r["HubNameHE"]) or f"group {gid}"
        out.append(
            feature(
                f"our_hub:{gid}",
                "our_hub",
                v,
                why,
                title,
                facts,
                g,
                f"{title} · only in Hubs project · {VERDICT_LABEL[v]}",
            )
        )
    return out


def build_both_hubs(d, ix: Index) -> list:
    out = []
    p = paired(d)
    for hid, grp in sorted(p.groupby("agency_hub_id"), key=lambda kv: kv[0]):
        if not grp["el"].any():
            continue
        el = grp[grp["el"]].sort_values("group")
        r0 = grp.iloc[0]
        gl = [
            " · ".join(
                x
                for x in (f"group {int(g)}", txt(n), label("hub_type", txt(t)) if txt(t) else "",
                          f"rank {txt(k)}")
                if x
            )
            for g, n, t, k in zip(
                el["group"], el["HubNameHE"], el["HubType"], el["RankByHubTypeMetro"]
            )
        ]
        facts = agency_hub_facts(r0) + [
            ("match", label("hub_relation", txt(r0["relation"]))),
            ("our scored hubs", " | ".join(gl)),
            (
                "modes at both",
                "; ".join(sorted({m for v in el["modes_shared"] for m in split_list(v)})),
            ),
            (
                f"modes only at {AG}",
                "; ".join(sorted({m for v in el["modes_only_agency"] for m in split_list(v)})),
            ),
            (
                "modes only in ours",
                "; ".join(sorted({m for v in el["modes_only_ours"] for m in split_list(v)})),
            ),
            ("distance", fmt_m(el["distance_m"].min())),
        ]
        hgeom = ix.ag_hub_geom[int(hid)]
        groups = [int(x) for x in el["group"]]
        g = {
            "p": point_of(hgeom),
            "grp": [point_of(ix.group_geom[x]) for x in groups],
            "ties": ties_for(d, int(hid), groups),
        }
        title = txt(r0["agency_name"]) or f"hub {hid}"
        why = f"Matched with {len(el)} scored hub(s) of ours within {HUB_MATCH_M:g} m: in both."
        out.append(
            feature(
                f"both_hub:{int(hid)}",
                "both_hub",
                "present",
                why,
                title,
                facts,
                g,
                f"{title} · in both",
            )
        )
    return out


# ----------------------------------------------------------------------------------------
# Summary markdown
# ----------------------------------------------------------------------------------------
def counts_table(features) -> dict:
    c = {s: Counter() for s, _ in SETS}
    for f in features:
        c[f["s"]][f["v"]] += 1
    return c


def fact(f, key):
    for k, v in f["f"]:
        if k == key:
            return v
    return ""


def verdict_rules() -> list[tuple[str, str]]:
    """How each set's verdict is decided, in plain words (the page and the summary share it)."""
    m = {v: VERDICT_LABEL[v] for v in VERDICTS}
    return [
        (f"{AG} lines we don't have",
         f"we count how many of its stops (or points every 100 m when it has no stops) have a "
         f"stop of ours, of any mode, within {STOP_NEAR_NODE_M:g} m. Half or more: "
         f"{m['covered_elsewhere']}; under a fifth: {m['real_gap']}; in between: {m['check']}."),
        (f"Our lines {AG} doesn't have",
         f"a mode {AG} does not have (Cable Line): {m['definition_difference']}; half or more of "
         f"its stops within {ROUTE_NEAR_M:g} m (rail {RAIL_ROUTE_NEAR_M:g} m) of a line of "
         f"{AG} of another mode: {m['covered_elsewhere']}; under a fifth near any of their lines "
         f"and stops ({STOP_NEAR_NODE_M:g} m, rail {RAIL_STOP_NEAR_NODE_M:g} m): "
         f"{m['real_gap']}; otherwise {m['check']}."),
        ("Unclear lines",
         f"{m['check']}, except a line of another mode on the same path (both overlap shares "
         f"{FULL_COV} or more): {m['definition_difference']}."),
        (f"{AG} hubs with no hub of ours",
         f"no stop of ours within {NO_HUB_AROUND_M:g} m and none of the hub's lines in our "
         f"network: {m['real_gap']}; otherwise {m['check']}."),
        (f"{AG} hubs we filtered out",
         f"a nearby group of ours with under {fmt_int(MIN_DEMAND)} passengers a day: "
         f"{m['check']}; only one mode or only rail lines: {m['definition_difference']} "
         f"({AG} counts changes within one mode, our rule needs 2 or more modes and a mode "
         "that is not rail)."),
        (f"Our hubs {AG} doesn't have",
         f"no hub of {AG} within {NO_HUB_AROUND_M:g} m and none of the hub's lines matches one "
         f"of theirs: {m['real_gap']}; otherwise {m['check']}."),
        ("Lines and hubs in both", f"shown for context: {m['present']}."),
    ]


def write_summary(features, run_note: str) -> str:
    c = counts_table(features)
    L = [
        f"# Missing lines and hubs: Hubs project vs {AG}",
        "",
        f"Data: {run_note}, "
        "compared with `hubs compare-network` (our stops shifted by the local offset, hubs "
        f"matched within {HUB_MATCH_M:g} m). Generated by `build_missing_map.py`.",
        "",
        "## Counts per set and verdict",
        "",
        "| set | features | " + " | ".join(VERDICT_LABEL[v] for v in VERDICTS) + " |",
        "|---|---:|" + "---:|" * len(VERDICTS),
    ]
    for s, name in SETS:
        L.append(
            f"| {name} | {sum(c[s].values())} | "
            + " | ".join(str(c[s][v]) for v in VERDICTS)
            + " |"
        )
    L += ["", "## How the verdicts are decided", ""]
    L += [f"- **{name}**: {text}" for name, text in verdict_rules()]
    L += ["", "## 15 most important findings", ""]
    by = defaultdict(list)
    for f in features:
        by[f["s"]].append(f)
    km = lambda f: float((fact(f, "length") or "0 km").split()[0])
    stops = lambda f: int((fact(f, "stops") or "0").replace(",", ""))
    items = []
    gaps = sorted(
        [f for f in by["ag_line"] if f["v"] == "real_gap"], key=lambda f: (-km(f), f["id"])
    )
    for f in gaps[:5]:
        items.append(
            f"Line of {AG} we don't have ({VERDICT_LABEL['real_gap']}): "
            f"`{fact(f, f'line of {AG}')}` {f['t']} "
            f"({fact(f, 'mode')}), {fact(f, 'length')}, {fact(f, 'stops') or '0'} stops, "
            f"opens {fact(f, 'opens') or 'n/a'}. {f['why']}"
        )
    chk = sorted(
        [f for f in by["ag_line"] if f["v"] == "check"], key=lambda f: (-stops(f), f["id"])
    )
    for f in chk[:2]:
        items.append(
            f"Line of {AG} partly served by ours ({VERDICT_LABEL['check']}): "
            f"`{fact(f, f'line of {AG}')}` {f['t']}, {fact(f, 'stops')} stops. {f['why']}"
        )
    nr = lambda f: int(fact(f, "lines") or 0)
    ah = sorted(by["ag_hub"], key=lambda f: (-nr(f), f["id"]))
    for f in ah[:3]:
        items.append(
            f"Hub of {AG} with no hub of ours: {f['id'].split(':')[1]} {f['t']} "
            f"({fact(f, 'type (worked out from its modes)')}, {fact(f, 'lines')} lines), "
            f"verdict {VERDICT_LABEL[f['v']]}. {f['why']}"
        )
    sc = lambda f: float(fact(f, "score") or 0)
    oh = sorted(by["our_hub"], key=lambda f: (-sc(f), f["id"]))
    for f in oh[:3]:
        name = "" if f["t"].startswith("group ") else f" {f['t']}"
        items.append(
            f"Our scored hub that {AG} doesn't have: group {fact(f, 'group')}{name} "
            f"({fact(f, 'hub type')}, score {fact(f, 'score')}, rank "
            f"{fact(f, 'rank in its type and area')}), "
            f"verdict {VERDICT_LABEL[f['v']]}. {f['why']}"
        )
    ol = sorted(
        by["our_line"], key=lambda f: (f["v"] != "real_gap", -int(fact(f, "stops") or 0), f["id"])
    )
    for f in ol[:2]:
        items.append(
            f"Our line that {AG} doesn't have: `{f['t']}` ({fact(f, 'mode')}, "
            f"{fact(f, 'stops')} stops), "
            f"verdict {VERDICT_LABEL[f['v']]}. {f['why']}"
        )
    for i, s in enumerate(items[:15], 1):
        L.append(f"{i}. {s}")
    L.append("")
    return "\n".join(L)


# ----------------------------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------------------------
def safe_json(obj) -> str:
    s = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return (
        s.replace("</", "<\\/")
        .replace("<!--", "<\\!--")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


class InputError(Exception):
    """A missing or unusable input; ``main`` prints it and exits with 1."""


def leaflet_assets(leaflet_dir: Path) -> tuple[str, str]:
    """leaflet.css and leaflet.js from a folder such as ``package/dist`` of ``leaflet@1.9.4``."""
    parts = []
    for name in ("leaflet.css", "leaflet.js"):
        path = leaflet_dir / name
        if not path.is_file():
            raise InputError(
                f"{path} not found: --leaflet-dir must hold leaflet.js and leaflet.css "
                f"(e.g. `npm pack leaflet@{LEAFLET_VERSION}`, then package/dist)"
            )
        parts.append(path.read_text(encoding="utf-8"))
    css, js = parts
    js = re.sub(r"//# sourceMappingURL=\S+\s*$", "", js)
    if re.search(r"</script", js, re.I) or re.search(r"</style", css, re.I):
        raise InputError("the Leaflet files contain a closing tag and cannot be inlined")
    return css, js


STYLE_SLOT = "<style>\n/*__LEAFLET_CSS__*/\n</style>"
SCRIPT_SLOT = "<script>\n/*__LEAFLET_JS__*/\n</script>"


def build_html(features, meta, run_note: str, leaflet_dir: Path | None) -> str:
    """The page: Leaflet inlined from ``leaflet_dir`` or loaded from the pinned cdnjs files."""
    page = PAGE_TEMPLATE
    assert STYLE_SLOT in page and SCRIPT_SLOT in page
    if leaflet_dir is not None:
        css, js = leaflet_assets(leaflet_dir)
        page = page.replace("/*__LEAFLET_CSS__*/", css).replace("/*__LEAFLET_JS__*/", js)
    else:
        page = page.replace(STYLE_SLOT, f'<link rel="stylesheet" href="{LEAFLET_CDN}/leaflet.css">')
        page = page.replace(SCRIPT_SLOT, f'<script src="{LEAFLET_CDN}/leaflet.js"></script>')
    data = {"features": features, "meta": meta}
    rules = "\n".join(
        f"      <li><b>{html.escape(name)}</b>: {html.escape(text)}</li>"
        for name, text in verdict_rules()
    ).replace(AGENCY_HE, f"<bdi>{AGENCY_HE}</bdi>")
    page = (
        page.replace("/*__BASEMAP_HTML__*/", BASEMAP_HTML)
        .replace("/*__RULES__*/", rules)
        .replace("/*__VLABEL__*/null", safe_json(VERDICT_LABEL))
        .replace("/*__BASEMAP_JS__*/", basemap_js())
    )
    return page.replace("/*__RUN_NOTE__*/", html.escape(run_note)).replace(
        "/*__DATA__*/null", safe_json(data)
    )


def default_run_note(run_dir: Path, compare_dir: Path) -> str:
    """Describe the data from the run's ``run_manifest.json``; the directory names otherwise."""
    manifest = run_dir / "run_manifest.json"
    if manifest.is_file():
        try:
            m = json.loads(manifest.read_text(encoding="utf-8"))
            version = str(m.get("version") or run_dir.name)
            # the run's own data exports; the reference layers shipped with the repo are not news
            files = sorted(
                str(i.get("file") or "")
                for i in (m.get("inputs") or {}).values()
                if isinstance(i, dict) and i.get("source") != "reference"
            )
            files = [f for f in files if f]
            return f"run {version}" + (f" (inputs: {', '.join(files)})" if files else "")
        except (OSError, ValueError, AttributeError):
            pass
    return f"run {run_dir.name}, comparison {compare_dir.name}"


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="build_missing_map.py",
        description="Map of the lines and hubs missing between our network and the agency's, "
        "with a verdict per feature, from a finished `hubs compare-network` run.",
    )
    ap.add_argument(
        "--compare-dir",
        type=Path,
        required=True,
        help="output of `hubs compare-network` (network_comparison.xlsx + .gpkg)",
    )
    ap.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="output of `hubs run` (hub_groups_all.csv, network_nodes.csv)",
    )
    ap.add_argument(
        "--agency-gpkg",
        type=Path,
        required=True,
        help="the agency's MT_Network.gpkg (the one given to compare-network)",
    )
    ap.add_argument(
        "--agency-meta",
        type=Path,
        default=None,
        help="MT_Network_MetaData.xlsx (optional, as in compare-network)",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="where the page and summary are written (default: --compare-dir)",
    )
    ap.add_argument(
        "--leaflet-dir",
        type=Path,
        default=None,
        help="folder with leaflet.js and leaflet.css to inline (default: pinned cdnjs)",
    )
    ap.add_argument(
        "--run-note",
        default=None,
        help="the data note shown on the page (default: from run_manifest.json)",
    )
    return ap.parse_args(argv)


def resolve_inputs(args: argparse.Namespace) -> dict:
    """Check that every input exists; the message names the file and what produces it."""
    cmp_cmd = "hubs compare-network --run RUN --agency-gpkg MT_Network.gpkg --out DIR"
    run_cmd = "hubs run --input-dir DIR --output-dir RUN"
    wanted = [
        ("workbook", args.compare_dir / "network_comparison.xlsx", cmp_cmd),
        ("gpkg", args.compare_dir / "network_comparison.gpkg", cmp_cmd),
        ("groups_csv", args.run_dir / "hub_groups_all.csv", run_cmd),
        ("network_nodes", args.run_dir / "network_nodes.csv", run_cmd),
        ("agency_gpkg", args.agency_gpkg, "the agency's MT_Network.gpkg"),
    ]
    if args.agency_meta is not None:
        wanted.append(("agency_meta", args.agency_meta, "the agency's MT_Network_MetaData.xlsx"))
    paths = {}
    for key, path, producer in wanted:
        if not path.is_file():
            raise InputError(f"{path} not found (produced by: {producer})")
        paths[key] = path
    paths.setdefault("agency_meta", None)
    return paths


def build_features(d, ix: Index) -> list:
    features = (
        build_agency_lines(d, ix)
        + build_our_lines(d, ix)
        + build_doubtful(d, ix)
        + build_both_lines(d, ix)
        + build_agency_hubs_missing(d, ix)
        + build_agency_hubs_filtered(d, ix)
        + build_our_hubs_missing(d, ix)
        + build_both_hubs(d, ix)
    )
    ids = [f["id"] for f in features]
    assert len(ids) == len(set(ids)), "feature ids must be unique"
    return features


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        paths = resolve_inputs(args)
        out_dir = args.out_dir if args.out_dir is not None else args.compare_dir
        run_note = args.run_note or default_run_note(args.run_dir, args.compare_dir)
        d = load(paths)
        ix = Index(d)
        features = build_features(d, ix)
        meta = {
            "n_agency_routes": int(len(ix.ag_routes)),
            "n_our_routes": int(len(d["our_routes"])),
            "n_agency_hubs": int(len(ix.ag_hub_geom)),
            "n_our_scored": int(d["groups_csv"]["eligible"].map(truthy).sum()),
            "n_groups": int(len(d["groups_csv"])),
        }
        page = build_html(features, meta, run_note, args.leaflet_dir)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.leaflet_dir is None:
        print(
            f"note: Leaflet {LEAFLET_VERSION} is loaded from cdnjs; pass --leaflet-dir to inline it"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_html, out_summary = out_dir / HTML_NAME, out_dir / SUMMARY_NAME
    out_html.write_text(page, encoding="utf-8")
    out_summary.write_text(write_summary(features, run_note), encoding="utf-8")
    c = counts_table(features)
    for s, _ in SETS:
        counts = "  ".join(f"{v}={c[s][v]}" for v in VERDICTS if c[s][v])
        print(f"{s:12s} {sum(c[s].values()):4d}  {counts}")
    print(f"{out_html} {out_html.stat().st_size / 1e6:.2f} MB")
    print(f"{out_summary}")
    return 0


PAGE_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Missing Lines and Hubs</title>
<meta name="description" content="Transit lines and hubs missing between the Hubs project network (פרויקט תעדוף מתחמים) and the network of מנהל התכנון, each marked missing, covered by another line, defined differently or needs a look.">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&display=swap">
<style>
/*__LEAFLET_CSS__*/
</style>
<style>
:root {
  color-scheme: light;
  --bg: #f4f3ef; --panel: #fffefb; --panel-border: #dcd9d0; --ink: #1c1b18; --ink-2: #5b5950; --ink-3: #807d72;
  --map-bg: #e9e9e9; --shadow: 0 4px 18px rgba(30,28,20,.16); --accent: #2a78d6; --focus: #2a78d6; --ring: #ffffff;
  --agency: #eb6834; --ours: #1baf7a; --both: #2a78d6; --ctx: #77746b; --tie: #2a78d6;
  --v-gap-bg: #fde8df; --v-gap-ink: #9a3412; --v-cov-bg: #e2f4ec; --v-cov-ink: #11603f;
  --v-def-bg: #ebe8fb; --v-def-ink: #4532a0; --v-chk-bg: #f1efe8; --v-chk-ink: #4d4b43;
  --v-pre-bg: #e3eefb; --v-pre-ink: #1d5aa6;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #17171a; --panel: #212125; --panel-border: #3a3a40; --ink: #f2f1ea; --ink-2: #c3c2b7; --ink-3: #9a998f;
    --map-bg: #e9e9e9; --shadow: 0 4px 18px rgba(0,0,0,.5); --accent: #3987e5; --focus: #3987e5; --ring: #ffffff;
    --agency: #d95926; --ours: #199e70; --both: #2a78d6; --ctx: #6b685f; --tie: #2a78d6;
    --v-gap-bg: #4a2314; --v-gap-ink: #ffc6ad; --v-cov-bg: #15392a; --v-cov-ink: #a6e8c9;
    --v-def-bg: #2c2552; --v-def-ink: #d2c9ff; --v-chk-bg: #2d2d31; --v-chk-ink: #dddcd2;
    --v-pre-bg: #17304f; --v-pre-ink: #b9d6fb;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #17171a; --panel: #212125; --panel-border: #3a3a40; --ink: #f2f1ea; --ink-2: #c3c2b7; --ink-3: #9a998f;
  --map-bg: #e9e9e9; --shadow: 0 4px 18px rgba(0,0,0,.5); --accent: #3987e5; --focus: #3987e5; --ring: #ffffff;
  --agency: #d95926; --ours: #199e70; --both: #2a78d6; --ctx: #6b685f; --tie: #2a78d6;
  --v-gap-bg: #4a2314; --v-gap-ink: #ffc6ad; --v-cov-bg: #15392a; --v-cov-ink: #a6e8c9;
  --v-def-bg: #2c2552; --v-def-ink: #d2c9ff; --v-chk-bg: #2d2d31; --v-chk-ink: #dddcd2;
  --v-pre-bg: #17304f; --v-pre-ink: #b9d6fb;
}
html, body { height: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.4 "Heebo", "Segoe UI", system-ui, sans-serif; }
#map { position: absolute; inset: 0; background: var(--map-bg); }
.leaflet-container { background: var(--map-bg); font: inherit; }
.osm-gray { filter: grayscale(1) brightness(1.06) contrast(0.88); }
.leaflet-bar { box-shadow: var(--shadow); border: 1px solid var(--panel-border); }
.leaflet-bar a { background: var(--panel); color: var(--ink); border-bottom-color: var(--panel-border); }
.leaflet-bar a:hover, .leaflet-bar a:focus-visible { background: var(--bg); }
.leaflet-control-attribution { background: color-mix(in srgb, var(--panel) 85%, transparent); color: var(--ink-3); font-size: 11px; }
.leaflet-control-attribution a { color: var(--ink-2); }
.leaflet-popup-content-wrapper, .leaflet-popup-tip { background: var(--panel); color: var(--ink); box-shadow: var(--shadow); }
.leaflet-popup-content-wrapper { border-radius: 8px; border: 1px solid var(--panel-border); }
.leaflet-popup-content { margin: 12px 14px; font-size: 13px; min-width: 240px; }
.leaflet-container a.leaflet-popup-close-button { color: var(--ink-3); }
.leaflet-container :focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.leaflet-tooltip { background: var(--panel); color: var(--ink); border-color: var(--panel-border); box-shadow: var(--shadow); font-size: 12px; }
.panel { position: absolute; z-index: 1000; top: calc(12px + env(safe-area-inset-top, 0px)); left: 12px; width: 344px; max-width: calc(100% - 24px);
  max-height: calc(100% - 24px - env(safe-area-inset-top, 0px)); overflow: auto; overscroll-behavior: contain;
  background: var(--panel); border: 1px solid var(--panel-border); border-radius: 10px; box-shadow: var(--shadow); padding: 14px 16px 12px; box-sizing: border-box; }
.panel h1 { margin: 0; font-size: 17px; font-weight: 700; letter-spacing: -.01em; text-wrap: balance; }
.panel .sub { margin: 2px 0 0; color: var(--ink-2); font-size: 12.5px; }
.eyebrow { margin: 14px 0 6px; font-size: 11px; font-weight: 500; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-3); }
.sets { display: grid; gap: 2px; margin: 0; padding: 0; list-style: none; }
.sets label { display: grid; grid-template-columns: 18px 26px 1fr auto; align-items: center; gap: 8px; padding: 5px 6px; border-radius: 6px; cursor: pointer; }
.sets label:hover { background: var(--bg); }
.sets input, .filter input { margin: 0; width: 15px; height: 15px; accent-color: var(--accent); }
.sets input:focus-visible, .filter input:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
.sets .lbl { font-weight: 500; line-height: 1.2; }
.sets .lbl small { display: block; font-weight: 400; color: var(--ink-3); font-size: 11.5px; }
.sets .cnt { color: var(--ink-2); font-variant-numeric: tabular-nums; font-size: 13px; text-align: right; white-space: nowrap; }
.sets .cnt small { color: var(--ink-3); font-size: 11px; }
.sym { justify-self: center; width: 22px; height: 16px; }
.filter { display: flex; align-items: center; gap: 8px; margin-top: 12px; padding: 6px 8px; border: 1px solid var(--panel-border); border-radius: 6px; background: var(--bg); cursor: pointer; font-weight: 500; }
.filter small { font-weight: 400; color: var(--ink-3); }
.actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.actions button { flex: 1 1 auto; white-space: nowrap; font: inherit; font-size: 12.5px; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--ink); cursor: pointer; }
.actions button:hover { border-color: var(--ink-3); }
.actions button:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
.note { margin: 10px 0 0; font-size: 11.5px; color: var(--ink-3); }
.note b { color: var(--ink-2); font-weight: 500; }
details.more { margin-top: 10px; font-size: 11.5px; color: var(--ink-3); }
details.more summary { cursor: pointer; color: var(--ink-2); font-weight: 500; }
details.more summary:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
details.more ul { margin: 6px 0 0; padding-left: 16px; }
details.more li { margin: 2px 0; }
table.summary { width: 100%; border-collapse: collapse; font-size: 11.5px; font-variant-numeric: tabular-nums; }
table.summary th, table.summary td { padding: 3px 4px; border-bottom: 1px solid var(--panel-border); text-align: right; }
table.summary th:first-child, table.summary td:first-child { text-align: left; }
table.summary th { color: var(--ink-3); font-weight: 500; font-size: 10.5px; vertical-align: bottom; }
table.summary td.zero { color: var(--ink-3); }
.chip { display: inline-flex; align-items: center; gap: 4px; font-size: 11.5px; font-weight: 600; padding: 1px 8px; border-radius: 99px; border: 1px solid currentColor; white-space: nowrap; }
.chip::before { font-weight: 700; }
.v-real_gap { background: var(--v-gap-bg); color: var(--v-gap-ink); } .v-real_gap::before { content: "▲"; }
.v-covered_elsewhere { background: var(--v-cov-bg); color: var(--v-cov-ink); } .v-covered_elsewhere::before { content: "◆"; }
.v-definition_difference { background: var(--v-def-bg); color: var(--v-def-ink); } .v-definition_difference::before { content: "≠"; }
.v-check { background: var(--v-chk-bg); color: var(--v-chk-ink); } .v-check::before { content: "?"; }
.v-present { background: var(--v-pre-bg); color: var(--v-pre-ink); } .v-present::before { content: "✓"; }
.pp h2 { margin: 0 0 6px; font-size: 14px; font-weight: 700; line-height: 1.25; }
.pp .tag { display: inline-block; font-size: 11px; font-weight: 500; letter-spacing: .04em; padding: 1px 7px; border-radius: 99px; color: #fff; margin-bottom: 6px; }
.pp .kv { display: grid; grid-template-columns: minmax(0, 42%) 1fr; gap: 2px 8px; font-size: 12.5px; margin: 8px 0 0; }
.pp .kv dt { color: var(--ink-3); } .pp .kv dd { margin: 0; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.pp .eval { margin-top: 2px; border: 1px solid var(--panel-border); border-radius: 6px; padding: 6px 8px; background: var(--bg); }
.pp .eval h3 { margin: 0 0 4px; font-size: 11px; letter-spacing: .04em; text-transform: uppercase; color: var(--ink-3); font-weight: 500; }
.pp .eval p { margin: 5px 0 0; font-size: 12.5px; }
@media (max-width: 560px) {
  .panel { top: auto; bottom: calc(12px + env(safe-area-inset-bottom, 0px)); left: 12px; right: 12px; width: auto; max-height: 48%; }
  .leaflet-top.leaflet-right { top: env(safe-area-inset-top, 0px); }
  .leaflet-popup-content { min-width: 0; }
}
.pick { display: grid; grid-template-columns: 1fr; gap: 6px; margin-top: 6px; }
.pick select { font: inherit; font-size: 12.5px; padding: 5px 6px; border-radius: 6px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--ink); min-width: 0; }
.pick select:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
.bm-note { color: var(--ink-2); }
.bm-note:empty { display: none; }
.panel bdi { white-space: nowrap; }
@media (prefers-reduced-motion: reduce) { .leaflet-zoom-anim .leaflet-zoom-animated, .leaflet-fade-anim .leaflet-popup { transition: none; } }
</style>
</head>
<body>
<div id="map" role="application" aria-label="Map of the transit lines and hubs missing between the Hubs project network and the network of מנהל התכנון"></div>

<section class="panel" id="panel" aria-label="Sets, filter, summary and notes">
  <h1>Missing lines and hubs</h1>
  <p class="sub"><bdi>פרויקט תעדוף מתחמים</bdi> (ours) vs <bdi>מנהל התכנון</bdi> · <span id="sub-counts"></span></p>

  <label class="filter"><input type="checkbox" id="only-gaps"><span>Show only what is missing <small>(▲ Missing)</small></span></label>

  <p class="eyebrow">Lines</p>
  <ul class="sets">
    <li><label><input type="checkbox" id="set-ag_line" data-set="ag_line" checked>
      <svg class="sym" viewBox="0 0 22 16" aria-hidden="true"><line x1="1" y1="8" x2="21" y2="8" stroke="var(--agency)" stroke-width="4" stroke-linecap="round"/></svg>
      <span class="lbl"><bdi>מנהל התכנון</bdi> lines we don't have<small>no line of ours follows it · drawn on their line</small></span><span class="cnt" id="cnt-ag_line"></span></label></li>
    <li><label><input type="checkbox" id="set-our_line" data-set="our_line" checked>
      <svg class="sym" viewBox="0 0 22 16" aria-hidden="true"><polyline points="1,12 8,5 14,10 21,4" fill="none" stroke="var(--ours)" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/></svg>
      <span class="lbl">Our lines <bdi>מנהל התכנון</bdi> doesn't have<small>drawn through our stops in order</small></span><span class="cnt" id="cnt-our_line"></span></label></li>
    <li><label><input type="checkbox" id="set-doubt" data-set="doubt">
      <svg class="sym" viewBox="0 0 22 16" aria-hidden="true"><line x1="1" y1="5" x2="21" y2="5" stroke="var(--agency)" stroke-width="3" stroke-dasharray="6 3"/><line x1="1" y1="11" x2="21" y2="11" stroke="var(--ours)" stroke-width="3" stroke-dasharray="2 3"/></svg>
      <span class="lbl">Unclear lines<small>barely overlaps or other mode · both sides dashed</small></span><span class="cnt" id="cnt-doubt"></span></label></li>
    <li><label><input type="checkbox" id="set-both_line" data-set="both_line">
      <svg class="sym" viewBox="0 0 22 16" aria-hidden="true"><line x1="1" y1="8" x2="21" y2="8" stroke="var(--ctx)" stroke-width="2"/></svg>
      <span class="lbl">Lines in both (context)<small>same line, partly the same, split or joined, part of a longer line</small></span><span class="cnt" id="cnt-both_line"></span></label></li>
  </ul>

  <p class="eyebrow">Hubs</p>
  <ul class="sets">
    <li><label><input type="checkbox" id="set-ag_hub" data-set="ag_hub" checked>
      <svg class="sym" viewBox="0 0 22 16" aria-hidden="true"><circle cx="11" cy="8" r="6" fill="var(--agency)" fill-opacity=".15" stroke="var(--agency)" stroke-width="2.4"/></svg>
      <span class="lbl"><bdi>מנהל התכנון</bdi> hubs with no hub of ours<small>none within 400 m · grey line = our nearest group</small></span><span class="cnt" id="cnt-ag_hub"></span></label></li>
    <li><label><input type="checkbox" id="set-ag_hub_filt" data-set="ag_hub_filt" checked>
      <svg class="sym" viewBox="0 0 22 16" aria-hidden="true"><circle cx="11" cy="8" r="6" fill="none" stroke="var(--agency)" stroke-width="2.2" stroke-dasharray="3 2.4"/></svg>
      <span class="lbl"><bdi>מנהל התכנון</bdi> hubs we filtered out<small>our groups there are not scored</small></span><span class="cnt" id="cnt-ag_hub_filt"></span></label></li>
    <li><label><input type="checkbox" id="set-our_hub" data-set="our_hub" checked>
      <svg class="sym" viewBox="0 0 22 16" aria-hidden="true"><circle cx="11" cy="8" r="6" fill="var(--ours)" stroke="var(--ring)" stroke-width="1.5"/></svg>
      <span class="lbl">Our hubs <bdi>מנהל התכנון</bdi> doesn't have<small>scored hubs of ours, none of theirs within 400 m</small></span><span class="cnt" id="cnt-our_hub"></span></label></li>
    <li><label><input type="checkbox" id="set-both_hub" data-set="both_hub">
      <svg class="sym" viewBox="0 0 22 16" aria-hidden="true"><line x1="7" y1="8" x2="18" y2="8" stroke="var(--tie)" stroke-width="1.5"/><circle cx="7" cy="8" r="5.5" fill="none" stroke="var(--both)" stroke-width="2.2"/><circle cx="18" cy="8" r="3" fill="var(--both)"/></svg>
      <span class="lbl">Hubs in both (context)<small>ring = <bdi>מנהל התכנון</bdi> hub · dot = our scored hub</small></span><span class="cnt" id="cnt-both_hub"></span></label></li>
  </ul>

  <div class="actions">
    <button type="button" id="btn-fit">Zoom to all</button>
    <button type="button" id="btn-tlv">Tel Aviv</button>
    <button type="button" id="btn-hfa">Haifa</button>
    <button type="button" id="btn-jlm">Jerusalem</button>
    <button type="button" id="btn-bsh">Be'er Sheva</button>
  </div>
  /*__BASEMAP_HTML__*/

  <p class="eyebrow">Summary</p>
  <table class="summary" id="summary" aria-label="Features per set and verdict"></table>

  <details class="more">
    <summary>How the verdicts are decided</summary>
    <ul>
/*__RULES__*/
    </ul>
  </details>
  <p class="note"><b>Data</b>: /*__RUN_NOTE__*/, compared with <code>hubs compare-network</code>; our stops are shifted by the local offset.</p>
  <p class="note">Our lines are drawn through their stops in order, so their shape is approximate.</p>
  <p class="note"><bdi>מנהל התכנון</bdi> draws rail in short pieces, so rail results are rough.</p>
  <p class="note">Passenger numbers of <bdi>מנהל התכנון</bdi> are not available.</p>
  <p class="note">Hubs match when a stop of each is within 400 m; <bdi>מנהל התכנון</bdi> also counts changes within one mode as hubs.</p>
</section>

<script>
/*__LEAFLET_JS__*/
</script>
<script>
/*__BASEMAP_JS__*/
(function () {
  'use strict';
  var DATA = /*__DATA__*/null;
  var SETS = [
    {id: 'ag_line', label: 'מנהל התכנון line we don\'t have', kind: 'line'},
    {id: 'our_line', label: 'Our line מנהל התכנון doesn\'t have', kind: 'line'},
    {id: 'doubt', label: 'Unclear line', kind: 'line'},
    {id: 'both_line', label: 'Line in both', kind: 'line'},
    {id: 'ag_hub', label: 'מנהל התכנון hub with no hub of ours', kind: 'hub'},
    {id: 'ag_hub_filt', label: 'מנהל התכנון hub we filtered out', kind: 'hub'},
    {id: 'our_hub', label: 'Our hub מנהל התכנון doesn\'t have', kind: 'hub'},
    {id: 'both_hub', label: 'Hub in both', kind: 'hub'}
  ];
  var VERDICTS = ['real_gap', 'covered_elsewhere', 'definition_difference', 'check', 'present'];
  var VLABEL = /*__VLABEL__*/null;
  var VSHORT = {real_gap: '▲ Missing', covered_elsewhere: '◆ Covered', definition_difference: '≠ Differs', check: '? Look', present: '✓ Both'};
  var TAGVAR = {ag_line: '--agency', our_line: '--ours', doubt: '--ctx', both_line: '--ctx', ag_hub: '--agency', ag_hub_filt: '--agency', our_hub: '--ours', both_hub: '--both'};

  var css = getComputedStyle(document.documentElement);
  var tok = function (n) { return css.getPropertyValue(n).trim(); };
  var esc = function (t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); };
  var el = function (tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; };
  var bdi = function (text) { return el('bdi', null, text); };

  var renderer = L.canvas({tolerance: 6});
  var map = L.map('map', {zoomControl: false, preferCanvas: true, renderer: renderer});
  L.control.zoom({position: 'topright'}).addTo(map);
  map.attributionControl.setPrefix('');
  map.fitBounds([[29.4, 34.2], [33.4, 35.9]]);
  var basemap = hubsBasemap(map, document.getElementById('basemap'), document.getElementById('basemap-note'));

  var features = DATA.features;
  var bySet = {}, groups = {}, drawn = {}, layerById = {};
  SETS.forEach(function (s) { bySet[s.id] = []; groups[s.id] = L.layerGroup(); drawn[s.id] = 0; });
  features.forEach(function (f) { bySet[f.s].push(f); });

  function popupFor(f) {
    var root = el('div', 'pp');
    var tag = el('span', 'tag'); tag.style.background = 'var(' + TAGVAR[f.s] + ')';
    tag.textContent = SETS.filter(function (s) { return s.id === f.s; })[0].label;
    root.appendChild(tag);
    var h = el('h2'); h.appendChild(bdi(f.t)); root.appendChild(h);
    // the verdict first, so it is visible without scrolling; the facts below
    var ev = el('div', 'eval'); ev.appendChild(el('h3', null, 'Evaluation'));
    ev.appendChild(el('span', 'chip v-' + f.v, VLABEL[f.v]));
    var p = el('p'); p.appendChild(bdi(f.why)); ev.appendChild(p);
    root.appendChild(ev);
    var dl = el('dl', 'kv');
    f.f.forEach(function (kv) { dl.appendChild(el('dt', null, kv[0])); var dd = el('dd'); dd.appendChild(bdi(kv[1])); dl.appendChild(dd); });
    root.appendChild(dl);
    return root;
  }
  function tipFor(f) { var s = el('span'); s.appendChild(bdi(f.tip)); return s; }

  function line(coords, o) { return L.polyline(coords, o); }
  function build(f) {
    var g = f.g, parts = [], C = {ag: tok('--agency'), ours: tok('--ours'), both: tok('--both'), ctx: tok('--ctx'), ring: tok('--ring'), tie: tok('--tie')};
    if (f.s === 'ag_line') parts.push(line(g.a, {color: C.ag, weight: 4.5, opacity: .9}));
    else if (f.s === 'our_line') {
      if (g.o) parts.push(line(g.o, {color: C.ours, weight: 4.5, opacity: .9}));
      if (g.op) parts.push(L.circleMarker(g.op, {radius: 5, color: C.ours, weight: 3, fillColor: C.ours, fillOpacity: .9}));
    } else if (f.s === 'doubt') {
      if (g.a && g.a.length) parts.push(line(g.a, {color: C.ag, weight: 3.5, opacity: .85, dashArray: '10 6'}));
      if (g.o) parts.push(line(g.o, {color: C.ours, weight: 3.5, opacity: .95, dashArray: '3 6'}));
      if (g.op) parts.push(L.circleMarker(g.op, {radius: 5, color: C.ours, weight: 2, dashArray: '3 3', fillOpacity: 0}));
    } else if (f.s === 'both_line') parts.push(line(g.a, {color: C.ctx, weight: 2, opacity: .7}));
    else {
      (g.ties || []).forEach(function (t) {
        parts.push(line(t, {color: f.s === 'both_hub' ? C.tie : C.ctx, weight: 1.5, opacity: .9, dashArray: f.s === 'ag_hub' ? '4 4' : null, interactive: false}));
      });
      if (g.near) parts.push(L.circleMarker(g.near, {radius: 3, color: C.ctx, weight: 1.5, fillColor: C.ctx, fillOpacity: .6, interactive: false}));
      (g.grp || []).forEach(function (pt) {
        parts.push(f.s === 'both_hub'
          ? L.circleMarker(pt, {radius: 4, color: C.ring, weight: 1, fillColor: C.both, fillOpacity: .95, interactive: false})
          : L.circleMarker(pt, {radius: 3.5, color: C.ctx, weight: 1.5, fillColor: C.ctx, fillOpacity: 0, interactive: false}));
      });
      if (f.s === 'ag_hub') parts.push(L.circleMarker(g.p, {radius: 9, color: C.ag, weight: 2.6, fillColor: C.ag, fillOpacity: .15}));
      else if (f.s === 'ag_hub_filt') parts.push(L.circleMarker(g.p, {radius: 9, color: C.ag, weight: 2.4, dashArray: '4 3', fillColor: C.ag, fillOpacity: .04}));
      else if (f.s === 'our_hub') parts.push(L.circleMarker(g.p, {radius: 7.5, color: C.ring, weight: 1.5, fillColor: C.ours, fillOpacity: .95}));
      else parts.push(L.circleMarker(g.p, {radius: 9, color: C.both, weight: 2.4, fillColor: C.both, fillOpacity: .06}));
    }
    parts.forEach(function (l) { if (l.setRadius) l.baseRadius = l.options.radius; });
    var fg = L.featureGroup(parts);
    fg.featureId = f.id;
    fg.bindPopup(function () { return popupFor(f); }, {maxWidth: 380, maxHeight: 380, autoPanPadding: [20, 20]});
    fg.bindTooltip(function () { return tipFor(f); }, {sticky: true, direction: 'top', offset: [0, -6]});
    return fg;
  }

  var onlyGaps = document.getElementById('only-gaps');
  function render() {
    map.closePopup();
    SETS.forEach(function (s) {
      var grp = groups[s.id]; grp.clearLayers(); drawn[s.id] = 0;
      bySet[s.id].forEach(function (f) {
        if (onlyGaps.checked && f.v !== 'real_gap') return;
        var fg = layerById[f.id] || (layerById[f.id] = build(f));
        grp.addLayer(fg); drawn[s.id] += 1;
      });
      var c = document.getElementById('cnt-' + s.id);
      c.textContent = '';
      c.dataset.n = String(drawn[s.id]);
      c.appendChild(document.createTextNode(drawn[s.id].toLocaleString('en')));
      if (onlyGaps.checked) c.appendChild(el('small', null, ' of ' + bySet[s.id].length));
    });
  }
  function sync() {
    SETS.forEach(function (s) { map.removeLayer(groups[s.id]); });
    SETS.forEach(function (s) { if (document.getElementById('set-' + s.id).checked) groups[s.id].addTo(map); });
  }
  SETS.forEach(function (s) { document.getElementById('set-' + s.id).addEventListener('change', sync); });
  onlyGaps.addEventListener('change', function () { render(); sync(); });

  // evaluation summary, computed from the data
  (function () {
    var t = document.getElementById('summary');
    var head = el('tr'); head.appendChild(el('th', null, 'Set'));
    var used = VERDICTS;
    used.forEach(function (v) { var th = el('th', null, VSHORT[v]); th.title = VLABEL[v]; head.appendChild(th); });
    var thead = el('thead'); thead.appendChild(head); t.appendChild(thead);
    var tb = el('tbody');
    SETS.forEach(function (s) {
      var tr = el('tr'); tr.appendChild(el('td', null, s.label));
      used.forEach(function (v) {
        var n = bySet[s.id].filter(function (f) { return f.v === v; }).length;
        tr.appendChild(el('td', n ? null : 'zero', n ? n : '·'));
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    var m = DATA.meta;
    document.getElementById('sub-counts').textContent = m.n_our_routes + ' / ' + m.n_agency_routes + ' lines · ' + m.n_our_scored + ' scored hubs of ' + m.n_groups + ' groups / ' + m.n_agency_hubs + ' hubs';
  })();

  var pts = [];
  features.forEach(function (f) {
    var g = f.g;
    if (g.p) pts.push(g.p);
    if (g.op) pts.push(g.op);
    [g.a, g.o].forEach(function (ls) { (ls || []).forEach(function (l) { l.forEach(function (c) { pts.push(c); }); }); });
  });
  var bounds = L.latLngBounds(pts);
  var panel = document.getElementById('panel');
  // keep the data clear of the panel: beside it on a wide screen, above the bottom sheet on a phone
  function fitAll() {
    var wide = window.innerWidth > 560;
    map.fitBounds(bounds, wide
      ? {paddingTopLeft: [panel.offsetWidth + 36, 24], paddingBottomRight: [64, 24]}
      : {paddingTopLeft: [24, 24], paddingBottomRight: [24, panel.offsetHeight + 24]});
  }
  document.getElementById('btn-fit').addEventListener('click', fitAll);
  document.getElementById('btn-tlv').addEventListener('click', function () { map.setView([32.08, 34.82], 12); });
  document.getElementById('btn-hfa').addEventListener('click', function () { map.setView([32.80, 35.02], 12); });
  document.getElementById('btn-jlm').addEventListener('click', function () { map.setView([31.78, 35.21], 12); });
  document.getElementById('btn-bsh').addEventListener('click', function () { map.setView([31.25, 34.79], 12); });
  L.DomEvent.disableClickPropagation(panel); L.DomEvent.disableScrollPropagation(panel);

  // smaller hub symbols at the national zoom levels, where hundreds of them overlap
  function radiusScale() { var z = map.getZoom(); return z < 9 ? 0.55 : z < 11 ? 0.75 : 1; }
  function rescale() {
    var k = radiusScale();
    Object.keys(layerById).forEach(function (id) { layerById[id].eachLayer(function (l) { if (l.baseRadius) l.setRadius(l.baseRadius * k); }); });
  }
  map.on('zoomend', rescale);
  onlyGaps.addEventListener('change', rescale);

  render(); sync();
  fitAll(); rescale();

  // test / debugging hook: stable ids -> layers, drawn counts per set
  window.missingMap = {
    map: map, groups: groups, layerById: layerById, features: features, basemap: basemap,
    drawnCount: function (id) { return drawn[id]; },
    layersOnMap: function (id) { var n = 0; if (map.hasLayer(groups[id])) groups[id].eachLayer(function () { n += 1; }); return n; }
  };
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
