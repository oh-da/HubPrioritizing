"""
Part 2, steps 2.4-2.6: 2050 demand per hexagon.

Ports cells 30, 36, 38, 40, 43, 45 and 47 of ``COMPLETE_TRANSIT_PIPELINE.ipynb``:

- :data:`SHEET_NAME_MAPPING` / :data:`SHEET_COLUMN_CONFIG`  workbook layout per regional model
- :func:`load_demand_workbook`  sheets -> region -> (node, demand, transfers)
- :func:`assign_demand`         per hexagon, sum demand of its nodes using the area's
  candidate models; overlay models (Hadera, Haifa Metronit) override the base model
- :func:`apply_manual_demand`   node-level overrides from ``manual_demand_updates.csv``
  (the formerly hardcoded National-Model and Shefaim corrections live there now)
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

import pandas as pd

from .report import RunReport
from .spatial_tags import AREA_COL, get_regions_for_area

DEMAND_COL = "TotalDemand"
TRANSFERS_COL = "TotalTransfers"

SHEET_NAME_MAPPING: dict[str, str] = {
    "5040_Daily": "Haifa",
    "Daily_5087": "Tel Aviv",
    "Daily_BS": "Beer Sheva",
    "Daily_Hadera": "Hadera",
    "Daily_Jerusalem": "Jerusalem",
    "HaifaNewMetronit": "Haifa Metronit",
    "Daily_5093": "Ashdod-Ashkelon",
    "National": "Rail",
    # already-mapped names
    "Haifa": "Haifa",
    "TelAviv": "Tel Aviv",
    "Tel Aviv": "Tel Aviv",
    "BeerSheva": "Beer Sheva",
    "Beer Sheva": "Beer Sheva",
    "Hadera": "Hadera",
    "Jerusalem": "Jerusalem",
    "Ashdod": "Ashdod-Ashkelon",
    "Ashdod-Ashkelon": "Ashdod-Ashkelon",
    "Ashkelon": "Ashdod-Ashkelon",
    "HaifaMetronit": "Haifa Metronit",
    "Haifa Metronit": "Haifa Metronit",
}

SHEET_COLUMN_CONFIG: dict[str, dict[str, list[str]]] = {
    "Beer Sheva": {
        "node_cols": ["NODE_ID", "Node", "node"],
        "boardings_cols": ["Boardings", "Boardings_Daily", "TotalBoardings"],
        "alightings_cols": ["Alightings", "Alightings_Daily", "TotalAlight"],
        "transfer_cols": [],
    },
    "Hadera": {
        "node_cols": ["NodeID", "Node", "node"],
        "boardings_cols": ["On", "Boardings", "Boardings_Daily"],
        "alightings_cols": ["Off", "Alightings", "Alightings_Daily"],
        "transfer_cols": [],
    },
    "Tel Aviv": {
        "node_cols": ["Node", "node"],
        "boardings_cols": ["TotalBoardings", "Boardings", "Boardings_Daily"],
        "alightings_cols": ["TotalAlight", "Alightings", "Alightings_Daily"],
        "transfer_cols": ["TransferBoardings", "TransferAlight"],
    },
    "Ashdod-Ashkelon": {
        "node_cols": ["Node", "node"],
        "boardings_cols": ["InitialBoardings", "Boardings", "TotalBoardings"],
        "alightings_cols": ["FinalAlight", "Alightings", "TotalAlight"],
        "transfer_cols": [],
    },
    "Haifa": {
        "node_cols": ["Node", "node"],
        "boardings_cols": ["TotalBoardings", "Boardings", "Boardings_Daily"],
        "alightings_cols": ["TotalAlight", "Alightings", "Alightings_Daily"],
        "transfer_cols": ["TransferBoardings", "TransferAlight"],
    },
    "Haifa Metronit": {
        "node_cols": ["ModelNode", "Node", "node"],
        "boardings_cols": ["Boardings_Daily", "Boardings", "TotalBoardings"],
        "alightings_cols": ["Alightings_Daily", "Alightings", "TotalAlight"],
        "transfer_cols": [],
    },
    "Jerusalem": {
        "node_cols": ["ID", "Node", "node"],
        "boardings_cols": ["DailyBoard_2050", "Boardings", "Boardings_Daily"],
        "alightings_cols": ["DailyAlight_2050", "Alightings", "Alightings_Daily"],
        "transfer_cols": [],
    },
    "Rail": {
        "node_cols": ["Node", "node", "NODE_ID"],
        "boardings_cols": ["Boardings", "TotalBoardings", "Boardings_Daily"],
        "alightings_cols": ["Alightings", "TotalAlight", "Alightings_Daily"],
        "transfer_cols": [],
    },
}

DEFAULT_COLUMN_CONFIG: dict[str, list[str]] = {
    "node_cols": ["Node", "node", "NODE_ID", "NodeID", "ID", "ModelNode", "N"],
    "boardings_cols": ["Boardings", "TotalBoardings", "Boardings_Daily", "InitialBoardings", "On", "DailyBoard_2050"],
    "alightings_cols": ["Alightings", "TotalAlight", "Alightings_Daily", "FinalAlight", "Off", "DailyAlight_2050"],
    "transfer_cols": ["Transfers", "TotalTransfers", "TransferBoardings", "TransferAlight"],
}

DEFAULT_OVERLAY_REGIONS: tuple[str, ...] = ("Hadera", "Haifa Metronit")


# ----------------------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------------------


def region_for_sheet(sheet_name: str) -> str | None:
    """Map a workbook sheet name to a demand-model region (case-insensitive)."""
    if sheet_name in SHEET_NAME_MAPPING:
        return SHEET_NAME_MAPPING[sheet_name]
    lower = sheet_name.lower()
    for k, v in SHEET_NAME_MAPPING.items():
        if k.lower() == lower:
            return v
    return None


def _find_column(columns: Iterable[str], candidates: Sequence[str]) -> str | None:
    cols = list(columns)
    lower = {str(c).lower(): c for c in cols}
    for name in candidates:
        if name in cols:
            return name
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def process_sheet(df: pd.DataFrame, region: str) -> pd.DataFrame | None:
    """Standardise one sheet to ``node, demand, transfers`` (summed per node).

    demand = boardings + alightings; transfers = sum of the region's transfer columns.
    Returns None when no node column can be found.
    """
    config = SHEET_COLUMN_CONFIG.get(region, DEFAULT_COLUMN_CONFIG)
    node_col = _find_column(df.columns, config["node_cols"])
    if node_col is None:
        return None
    boardings_col = _find_column(df.columns, config["boardings_cols"])
    alightings_col = _find_column(df.columns, config["alightings_cols"])
    transfer_cols = [c for c in (_find_column(df.columns, [t]) for t in config.get("transfer_cols", [])) if c]

    node = pd.to_numeric(df[node_col], errors="coerce")
    keep = node.notna()
    out = pd.DataFrame({"node": node[keep].astype(int)})

    def numeric(col: str | None) -> pd.Series:
        if col is None:
            return pd.Series(0.0, index=out.index)
        return pd.to_numeric(df.loc[keep, col], errors="coerce").fillna(0.0).astype(float).set_axis(out.index)

    out["demand"] = numeric(boardings_col) + numeric(alightings_col)
    out["transfers"] = sum((numeric(c) for c in transfer_cols), pd.Series(0.0, index=out.index))
    return out.groupby("node", as_index=False)[["demand", "transfers"]].sum()


def load_demand_workbook(
    sheets: Mapping[str, pd.DataFrame],
    report: RunReport | None = None,
) -> dict[str, pd.DataFrame]:
    """Sheets -> region -> ``node, demand, transfers``; unknown sheets are ignored with a note."""
    by_region: dict[str, pd.DataFrame] = {}
    for sheet_name, df in sheets.items():
        region = region_for_sheet(sheet_name)
        if region is None:
            if report is not None:
                report.info("demand", f"sheet '{sheet_name}' is not a known demand model; ignored")
            continue
        processed = process_sheet(df, region)
        if processed is None or processed.empty:
            if report is not None:
                report.warn("demand", f"sheet '{sheet_name}' ({region}) has no usable node/demand columns", columns=list(df.columns)[:12])
            continue
        if region in by_region:
            processed = pd.concat([by_region[region], processed]).groupby("node", as_index=False).sum()
        by_region[region] = processed
        if report is not None:
            report.info("demand", f"sheet '{sheet_name}' -> {region}: {len(processed)} nodes, total demand {processed['demand'].sum():,.0f}")
    return by_region


# ----------------------------------------------------------------------------------------
# Matching
# ----------------------------------------------------------------------------------------


def assign_demand(
    hexes: pd.DataFrame,
    demand_by_region: Mapping[str, pd.DataFrame],
    overlay_regions: Sequence[str] = DEFAULT_OVERLAY_REGIONS,
    report: RunReport | None = None,
) -> pd.DataFrame:
    """Sum node demand into ``TotalDemand`` / ``TotalTransfers`` per hexagon.

    For every node of a hexagon: an overlay model containing the node is authoritative
    (its value replaces the base model, never adds); otherwise the first candidate
    region of the hexagon's ``area`` that contains the node is used.
    """
    lookup: dict[str, dict[int, tuple[float, float]]] = {
        region: dict(zip(df["node"].astype(int), zip(df["demand"], df["transfers"]))) for region, df in demand_by_region.items()
    }
    overlays = [r for r in overlay_regions if r in lookup]

    out = hexes.copy()
    demand_vals, transfer_vals = [], []
    unmatched: dict[str, set[int]] = {}
    n_nodes = n_matched = 0

    for nodes, area in zip(out["node"], out[AREA_COL] if AREA_COL in out.columns else [None] * len(out)):
        regions = get_regions_for_area(area)
        total_d = total_t = 0.0
        for node in nodes if isinstance(nodes, list) else [nodes]:
            n_nodes += 1
            try:
                node = int(node)
            except (TypeError, ValueError):
                continue
            hit = None
            for r in overlays:
                if node in lookup[r]:
                    hit = lookup[r][node]
                    break
            if hit is None:
                for r in regions:
                    if r in lookup and node in lookup[r]:
                        hit = lookup[r][node]
                        break
            if hit is None:
                unmatched.setdefault(str(area), set()).add(node)
                continue
            total_d += hit[0]
            total_t += hit[1]
            n_matched += 1
        demand_vals.append(total_d)
        transfer_vals.append(total_t)

    out[DEMAND_COL] = demand_vals
    out[TRANSFERS_COL] = transfer_vals

    if report is not None:
        report.set_metric("demand_nodes_checked", n_nodes)
        report.set_metric("demand_nodes_matched", n_matched)
        report.set_metric("hexes_with_demand", int((out[DEMAND_COL] > 0).sum()))
        for area, nodes in sorted(unmatched.items()):
            report.warn("demand", f"{len(nodes)} nodes in area '{area}' have no demand in models {get_regions_for_area(area)}", nodes=sorted(nodes)[:50])
        if n_matched == 0:
            report.error("demand", "no node matched any demand model; check node IDs and sheet names")
    return out


# ----------------------------------------------------------------------------------------
# Manual overrides
# ----------------------------------------------------------------------------------------


def apply_manual_demand(hexes: pd.DataFrame, updates: pd.DataFrame | None, report: RunReport | None = None) -> pd.DataFrame:
    """Override ``TotalDemand`` / ``TotalTransfers`` for every hexagon containing a listed node.

    ``updates`` columns: ``node``, ``total_demand``, optional ``total_transfers``
    (blank keeps the computed value), optional ``station_name`` / ``notes`` for the report.
    Rows are applied in file order; later rows win.
    """
    out = hexes.copy()
    if updates is None or updates.empty:
        return out
    required = {"node", "total_demand"}
    if not required <= set(updates.columns):
        raise ValueError(f"manual demand updates need columns {sorted(required)}; got {list(updates.columns)}")

    node_sets = [set(int(n) for n in (ns if isinstance(ns, list) else [ns])) for ns in out["node"]]
    applied = 0
    for _, row in updates.iterrows():
        try:
            node = int(row["node"])
        except (TypeError, ValueError):
            if report is not None:
                report.warn("demand", f"manual demand row with invalid node skipped: {row.to_dict()}")
            continue
        label = str(row.get("station_name", "") or "")
        mask = [node in s for s in node_sets]
        if not any(mask):
            if report is not None:
                report.warn("demand", f"manual demand: node {node} ({label}) not found in the network; skipped")
            continue
        out.loc[mask, DEMAND_COL] = float(row["total_demand"])
        transfers = row.get("total_transfers")
        if transfers is not None and pd.notna(transfers) and str(transfers).strip() != "":
            out.loc[mask, TRANSFERS_COL] = float(transfers)
        applied += 1
        if report is not None:
            report.info("demand", f"manual demand applied to node {node} ({label}): {float(row['total_demand']):,.1f}", hexes=int(sum(mask)))
    if report is not None:
        report.set_metric("manual_demand_rows_applied", applied)
    return out
