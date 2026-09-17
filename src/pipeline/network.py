"""
Part 1 of the pipeline: transit network -> H3 hexagons.

Ports cells 13, 15 and 25 of ``COMPLETE_TRANSIT_PIPELINE.ipynb``:

1. :func:`load_nodeslines`   node x line rows with ITM coordinates -> GeoDataFrame
2. :func:`attach_modes`      join the planned 2050 mode per line, apply drop rules
3. :func:`aggregate_to_hexes` one row per H3 hexagon with node / mode / line lists
4. :func:`add_mode_line_columns` per-mode line-count columns used by the service score

All functions are pure (frame in, frame out) and record data-quality findings on a
:class:`~src.pipeline.report.RunReport`.
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence

import geopandas as gpd
import h3
import pandas as pd
from shapely import wkt
from shapely.geometry import Point

from ..config import CRS_ISRAEL_TM, CRS_WGS84, H3_RESOLUTION, MODE_LINE_COLS, MODE_TO_COLUMN
from ..spatial.h3_operations import h3_to_polygon
from .report import RunReport
from .settings import LineDropRule

NODE_COL = "node"
LINE_COL = "LINE_ID"
LINE_KEY_COL = "Line_ModelName"
MODE_COL = "Mode_Planned"
AREA_COL = "Area"

# columns that GIS exports add and the pipeline ignores
_INDEX_LIKE_COLUMNS = ("עמודה1", "Index", "index", "Unnamed: 0", "OBJECTID", "FID")


# ----------------------------------------------------------------------------------------
# 1. nodes x lines
# ----------------------------------------------------------------------------------------


def load_nodeslines(df: pd.DataFrame, crs: str = CRS_ISRAEL_TM) -> gpd.GeoDataFrame:
    """Turn the raw ``All_nodeslines`` frame into points.

    Accepts a WKT ``geometry`` column or ``X``/``Y`` columns (metres, EPSG:2039).
    ``node`` becomes int, ``LINE_ID`` is stripped of whitespace, index-like columns
    from the GIS export are dropped. Rows without coordinates or node are removed.
    """
    missing = [c for c in (NODE_COL, LINE_COL) if c not in df.columns]
    if missing:
        raise ValueError(f"nodeslines is missing required columns {missing}")

    out = df.drop(columns=[c for c in _INDEX_LIKE_COLUMNS if c in df.columns]).copy()

    if "geometry" in out.columns:
        geoms = out["geometry"].map(lambda v: wkt.loads(v) if isinstance(v, str) and v.strip() else None)
    elif {"X", "Y"} <= set(out.columns):
        xy = out[["X", "Y"]].apply(pd.to_numeric, errors="coerce")
        geoms = [Point(x, y) if pd.notna(x) and pd.notna(y) else None for x, y in zip(xy["X"], xy["Y"])]
    else:
        raise ValueError("nodeslines needs a WKT 'geometry' column or 'X' and 'Y' columns")

    out = out.drop(columns=[c for c in ("geometry",) if c in out.columns])
    gdf = gpd.GeoDataFrame(out, geometry=list(geoms), crs=crs)

    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    gdf[NODE_COL] = pd.to_numeric(gdf[NODE_COL], errors="coerce")
    gdf = gdf[gdf[NODE_COL].notna()].copy()
    gdf[NODE_COL] = gdf[NODE_COL].astype(int)
    gdf[LINE_COL] = gdf[LINE_COL].astype(str).str.strip()
    gdf = gdf[gdf[LINE_COL] != ""].reset_index(drop=True)
    return gdf


# ----------------------------------------------------------------------------------------
# 1b. node positions: one coordinate per node
# ----------------------------------------------------------------------------------------

NODE_POSITION_TOLERANCE_M = 150.0  # about one resolution-10 cell across


def apply_node_position_overrides(
    nodes: gpd.GeoDataFrame, overrides: pd.DataFrame | None, report: RunReport | None = None
) -> gpd.GeoDataFrame:
    """Move every row of a listed node to the ``X`` / ``Y`` (EPSG:2039) of
    ``node_position_overrides.csv``. Rows for nodes absent from the network are reported."""
    out = nodes.copy()
    if overrides is None or overrides.empty:
        return out
    required = {"node", "X", "Y"}
    if not required <= set(overrides.columns):
        raise ValueError(f"node position overrides need columns {sorted(required)}; got {list(overrides.columns)}")
    applied = 0
    for _, row in overrides.iterrows():
        try:
            node = int(row["node"])
            x, y = float(row["X"]), float(row["Y"])
        except (TypeError, ValueError):
            if report is not None:
                report.warn("network", f"node position override with invalid values skipped: {row.to_dict()}")
            continue
        mask = out[NODE_COL] == node
        if not mask.any():
            if report is not None:
                report.warn("network", f"node position override: node {node} not found in the network; skipped")
            continue
        out.loc[mask, out.geometry.name] = [Point(x, y)] * int(mask.sum())
        applied += 1
        if report is not None:
            report.info("network", f"node {node} moved to ({x:.1f}, {y:.1f}) by node_position_overrides.csv", rows=int(mask.sum()), notes=str(row.get("notes", "") or ""))
    if report is not None:
        report.set_metric("node_position_overrides_applied", applied)
    return out


def node_position_table(nodes: gpd.GeoDataFrame) -> pd.DataFrame:
    """One row per node whose rows disagree on position.

    Columns: ``node, n_positions, spread_m, positions`` where ``positions`` is a list of
    ``{"x", "y", "rows", "lines"}`` in order of first appearance.
    """
    df = pd.DataFrame(
        {
            NODE_COL: nodes[NODE_COL].to_numpy(),
            LINE_COL: nodes[LINE_COL].to_numpy(),
            "x": nodes.geometry.x.round(2).to_numpy(),
            "y": nodes.geometry.y.round(2).to_numpy(),
        }
    )
    rows = []
    for node, grp in df.groupby(NODE_COL, sort=True):
        positions = grp.groupby(["x", "y"], sort=False).agg(rows=(LINE_COL, "size"), lines=(LINE_COL, lambda s: sorted(set(s)))).reset_index()
        if len(positions) < 2:
            continue
        xs, ys = positions["x"].to_numpy(), positions["y"].to_numpy()
        spread = max(float(((xs - xs[i]) ** 2 + (ys - ys[i]) ** 2).max() ** 0.5) for i in range(len(xs)))
        rows.append(
            {
                NODE_COL: int(node),
                "n_positions": int(len(positions)),
                "spread_m": round(spread, 1),
                "positions": [{"x": float(r.x), "y": float(r.y), "rows": int(r.rows), "lines": list(r.lines)} for r in positions.itertuples()],
            }
        )
    return pd.DataFrame(rows, columns=[NODE_COL, "n_positions", "spread_m", "positions"])


def check_node_positions(
    nodes: gpd.GeoDataFrame,
    tolerance_m: float = NODE_POSITION_TOLERANCE_M,
    on_conflict: str = "warn",
    report: RunReport | None = None,
) -> tuple[gpd.GeoDataFrame, list[str]]:
    """Give every node one position.

    A node whose rows disagree by at most ``tolerance_m`` is snapped to the position
    carried by most of its rows (first in file order on a tie); all rows are kept. A
    larger spread is a conflict between network sources that the pipeline will not
    guess: the rows stay where they are, the node is reported, and with
    ``on_conflict='error'`` the problem is returned for the caller to stop on.
    Resolve conflicts with ``node_position_overrides.csv``.
    """
    if on_conflict not in ("warn", "error"):
        raise ValueError("on_conflict must be 'warn' or 'error'")
    out = nodes.copy()
    table = node_position_table(out)
    problems: list[str] = []
    snapped = 0
    for row in table.itertuples():
        positions = row.positions
        lines_by_pos = "; ".join(f"({p['x']:.1f}, {p['y']:.1f}) {p['rows']} rows: {', '.join(p['lines'])}" for p in positions)
        if row.spread_m <= tolerance_m:
            best = max(positions, key=lambda p: p["rows"])  # first on a tie (max keeps the first maximum)
            mask = out[NODE_COL] == row.node
            out.loc[mask, out.geometry.name] = [Point(best["x"], best["y"])] * int(mask.sum())
            snapped += 1
            if report is not None:
                report.warn("network", f"node {row.node}: {row.n_positions} positions {row.spread_m:.0f} m apart; snapped to ({best['x']:.1f}, {best['y']:.1f})", positions=lines_by_pos)
        else:
            msg = f"node {row.node}: {row.n_positions} positions {row.spread_m:.0f} m apart (more than {tolerance_m:.0f} m); the rows stay in different cells until node_position_overrides.csv fixes it"
            problems.append(msg + " [" + lines_by_pos + "]")
            if report is not None:
                report.warn("network", msg, positions=lines_by_pos)
    if report is not None:
        report.set_metric("nodes_with_inconsistent_position", int(len(table)))
        report.set_metric("nodes_snapped", snapped)
        report.set_metric("node_position_conflicts", len(problems))
    return out, problems


# ----------------------------------------------------------------------------------------
# 2. planned modes
# ----------------------------------------------------------------------------------------


def clean_lines_mode(lines_mode: pd.DataFrame, report: RunReport | None = None) -> pd.DataFrame:
    """Strip keys and drop duplicated ``Line_ModelName`` rows (first wins, warning)."""
    lm = lines_mode.copy()
    lm[LINE_KEY_COL] = lm[LINE_KEY_COL].astype(str).str.strip()
    lm[MODE_COL] = lm[MODE_COL].astype(str).str.strip()
    dup_mask = lm.duplicated(subset=[LINE_KEY_COL], keep="first")
    if dup_mask.any():
        dups = lm.loc[dup_mask, LINE_KEY_COL].tolist()
        if report is not None:
            report.warn(
                "network",
                f"{len(dups)} duplicated Line_ModelName rows in the lines/mode file; keeping the first of each",
                lines=sorted(set(dups)),
            )
        lm = lm[~dup_mask]
    return lm.reset_index(drop=True)


def lines_matching_rules(lines_mode: pd.DataFrame, rules: Iterable[LineDropRule]) -> list[str]:
    """Line keys removed by the configured drop rules (old Metronit, Netanya LRT151/152 ...)."""
    drop: list[str] = []
    for rule in rules:
        pat = re.compile(rule.pattern)
        subset = lines_mode
        if rule.area is not None and AREA_COL in lines_mode.columns:
            subset = lines_mode[lines_mode[AREA_COL].astype(str).str.strip() == rule.area]
        drop.extend(k for k in subset[LINE_KEY_COL].astype(str) if pat.search(k))
    return sorted(set(drop))


def attach_modes(
    nodes: gpd.GeoDataFrame,
    lines_mode: pd.DataFrame,
    drop_rules: Sequence[LineDropRule] = (),
    report: RunReport | None = None,
) -> gpd.GeoDataFrame:
    """Join ``Mode_Planned`` onto each node x line row.

    - duplicated line keys are collapsed (see :func:`clean_lines_mode`)
    - lines matching a drop rule are removed before the join
    - rows whose line has no mode are dropped, exactly as the notebook's
      ``groupby(..., dropna=True)`` did implicitly, but reported.
    """
    lm = clean_lines_mode(lines_mode, report)

    to_drop = lines_matching_rules(lm, drop_rules)
    if to_drop:
        before = len(nodes)
        nodes = nodes[~nodes[LINE_COL].isin(to_drop)]
        if report is not None:
            report.info(
                "network",
                f"dropped {before - len(nodes)} node x line rows for {len(to_drop)} lines matching drop rules",
                lines=to_drop,
            )

    merged = nodes.merge(
        lm[[LINE_KEY_COL, MODE_COL] + ([AREA_COL] if AREA_COL in lm.columns else [])],
        left_on=LINE_COL,
        right_on=LINE_KEY_COL,
        how="left",
        validate="many_to_one",
    )

    no_mode = merged[MODE_COL].isna() | (merged[MODE_COL].astype(str).str.lower() == "nan")
    if no_mode.any():
        lost = sorted(merged.loc[no_mode, LINE_COL].unique())
        if report is not None:
            report.warn(
                "network",
                f"{len(lost)} lines have no row in the lines/mode file and are excluded",
                lines=lost,
                rows=int(no_mode.sum()),
            )
        merged = merged[~no_mode]

    return gpd.GeoDataFrame(merged.reset_index(drop=True), geometry="geometry", crs=nodes.crs)


# ----------------------------------------------------------------------------------------
# 3. H3 aggregation
# ----------------------------------------------------------------------------------------


def _unique_in_order(values: Iterable) -> list:
    seen: set = set()
    out: list = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def aggregate_to_hexes(nodes: gpd.GeoDataFrame, resolution: int = H3_RESOLUTION) -> gpd.GeoDataFrame:
    """One row per H3 hexagon (WGS84 polygon) with node / mode / line aggregates.

    Reproduces notebook cell 15: lines are first counted per (hexagon, node, mode)
    and then summed per hexagon, so a line serving two nodes inside one hexagon counts
    twice in ``Line_Nunique`` (kept for fidelity). ``Line_Unique`` is the sorted set of
    line IDs; ``Lines_by_Mode`` maps each mode to its line count (used by the ``exact``
    per-mode method).

    Output columns: ``h3_index, node, Mode_Planned, Line_Nunique, Line_Unique,
    Lines_by_Mode, geometry``.
    """
    pts = nodes.to_crs(CRS_WGS84)
    lat = pts.geometry.y.to_numpy()
    lon = pts.geometry.x.to_numpy()
    df = pd.DataFrame(
        {
            "h3_index": [h3.latlng_to_cell(a, b, resolution) for a, b in zip(lat, lon)],
            NODE_COL: pts[NODE_COL].to_numpy(),
            MODE_COL: pts[MODE_COL].to_numpy(),
            LINE_COL: pts[LINE_COL].to_numpy(),
        }
    )

    # sort=True on purpose: the notebook's default groupby ordering (by h3_index, node,
    # mode) fixes the hexagon order, which in turn fixes group numbering and which
    # hexagon's area/location a group inherits. Keeping it reproduces the golden IDs.
    per_node_mode = (
        df.groupby(["h3_index", NODE_COL, MODE_COL], sort=True)[LINE_COL]
        .agg(Line_Nunique="nunique", lines=lambda s: sorted(set(s)))
        .reset_index()
    )

    rows = []
    for h3_index, grp in per_node_mode.groupby("h3_index", sort=True):
        lines_by_mode: dict[str, int] = {}
        for mode, n in zip(grp[MODE_COL], grp["Line_Nunique"]):
            lines_by_mode[mode] = lines_by_mode.get(mode, 0) + int(n)
        rows.append(
            {
                "h3_index": h3_index,
                NODE_COL: [int(n) for n in _unique_in_order(grp[NODE_COL])],
                MODE_COL: _unique_in_order(grp[MODE_COL]),
                "Line_Nunique": int(grp["Line_Nunique"].sum()),
                "Line_Unique": sorted({l for ls in grp["lines"] for l in ls}),
                "Lines_by_Mode": lines_by_mode,
            }
        )

    hexes = pd.DataFrame(rows)
    hexes["geometry"] = hexes["h3_index"].map(h3_to_polygon)
    return gpd.GeoDataFrame(hexes, geometry="geometry", crs=CRS_WGS84)


# ----------------------------------------------------------------------------------------
# 4. per-mode line counts
# ----------------------------------------------------------------------------------------


def add_mode_line_columns(hexes: gpd.GeoDataFrame, method: str = "even") -> gpd.GeoDataFrame:
    """Add the eight ``<Mode> Lines`` columns.

    ``method='even'`` reproduces the notebook workaround: ``Line_Nunique`` is split
    evenly across the (non-bus) modes present. ``method='exact'`` uses the true per-mode
    counts from ``Lines_by_Mode``.
    """
    if method not in ("even", "exact"):
        raise ValueError("method must be 'even' or 'exact'")

    out = hexes.copy()
    for col in MODE_LINE_COLS:
        out[col] = 0.0

    values = {col: [] for col in MODE_LINE_COLS}
    for modes, total, by_mode in zip(out[MODE_COL], out["Line_Nunique"], out.get("Lines_by_Mode", [None] * len(out))):
        counts = {col: 0.0 for col in MODE_LINE_COLS}
        mode_list = modes if isinstance(modes, list) else ([m.strip() for m in str(modes).split(",")] if pd.notna(modes) else [])
        valid = [m for m in mode_list if MODE_TO_COLUMN.get(m) is not None]
        if valid:
            if method == "even":
                share = float(total) / len(valid) if total else 0.0
                for m in valid:
                    counts[MODE_TO_COLUMN[m]] = share
            else:
                for m in valid:
                    counts[MODE_TO_COLUMN[m]] += float((by_mode or {}).get(m, 0))
        for col in MODE_LINE_COLS:
            values[col].append(counts[col])
    for col in MODE_LINE_COLS:
        out[col] = values[col]
    return out
