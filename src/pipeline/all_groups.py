"""
Tables for comparing the network and its hubs with another source (an agency's hubs).

- :func:`build_all_groups_table`    ``hub_groups_all.csv``: every hub group formed from the H3
  hexagons *before* the eligibility filter, with its eligibility flag, the reasons it was
  excluded and, for scored hubs, the final score and ranks.
- :func:`build_network_nodes_table` ``network_nodes.csv``: one row per node x line with the
  line's mode, the node's ITM position and the group / ``hub_id`` the node belongs to.

Both are pure functions of the in-memory run result; ``run.write_outputs`` writes them.
"""

from __future__ import annotations

import warnings
from typing import Mapping

import geopandas as gpd
import h3
import pandas as pd

from ..config import CRS_ISRAEL_TM, CRS_WGS84, ELIGIBILITY_MIN_MODES, ELIGIBILITY_MIN_PASSENGERS
from .network import LINE_COL, MODE_COL, NODE_COL
from .postprocess import hub_name_lookup
from .scoring import classify, prepare_scoring_frame

SCORE_COLUMNS = ("TotalScore_MC", "Rank_TS_MC", "RankByHubTypeMetro")
ALL_GROUPS_COLUMNS = (
    "hub_id", "group", "HubNameHE", "x", "y", "x_itm", "y_itm", "area", "Mode_Planned", "n_modes",
    "Line_Unique", "n_lines", "TotalDemand", "TotalTransfers", "eligible", "exclusion_reason", "HubType",
    *SCORE_COLUMNS,
)  # fmt: skip
NETWORK_NODES_COLUMNS = ("node", "LINE_ID", "line_name", "Mode_Planned", "x_itm", "y_itm", "group", "hub_id")


def _exclusion_reason(row: pd.Series, require_non_rail: bool) -> str:
    """Why a group is not an eligible hub: reasons joined by ``;``, empty when eligible."""
    reasons = []
    demand = row["TotalDemand"]
    if pd.isna(demand) or demand < ELIGIBILITY_MIN_PASSENGERS:
        reasons.append("demand < min")
    if len(row["Mode_Planned"]) < ELIGIBILITY_MIN_MODES:
        reasons.append("single mode")
    if require_non_rail and row["is_rail_only"]:
        reasons.append("rail only")
    return ";".join(reasons)


def _centroids(groups: pd.DataFrame) -> pd.DataFrame:
    """WGS84 ``x``/``y`` (the run's own columns when present) and ITM ``x_itm``/``y_itm``."""
    gdf = gpd.GeoDataFrame(groups)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # geographic centroid, as the pipeline computes x / y
        wgs = gdf.geometry.to_crs(CRS_WGS84).centroid
    itm = gdf.geometry.to_crs(CRS_ISRAEL_TM).centroid
    out = pd.DataFrame({"x_itm": itm.x.to_numpy(), "y_itm": itm.y.to_numpy()}, index=groups.index)
    out["x"] = groups["x"] if "x" in groups.columns else wgs.x.to_numpy()
    out["y"] = groups["y"] if "y" in groups.columns else wgs.y.to_numpy()
    return out


def build_all_groups_table(
    groups: pd.DataFrame,
    results: pd.DataFrame,
    hub_names: pd.DataFrame | None,
    require_non_rail: bool,
) -> pd.DataFrame:
    """One row per hub group, before any eligibility filter.

    Args:
        groups: the aggregated groups of a run (``RunResult.groups``, with geometry).
        results: the final scored table (``RunResult.results``); its ``TotalScore_MC``,
            ``Rank_TS_MC`` and ``RankByHubTypeMetro`` are joined on ``group`` (NaN for
            groups that were not scored).
        hub_names: the optional ``h3_index -> HubNameHE`` table.
        require_non_rail: the run's ``require_non_rail_mode`` setting.

    Returns:
        The columns of :data:`ALL_GROUPS_COLUMNS`. ``Mode_Planned`` and ``Line_Unique`` stay
        Python lists (the CSV writer joins them with ``;``); ``eligible`` and
        ``exclusion_reason`` come from :func:`scoring.classify` and the thresholds of
        ``src/config.py``.
    """
    coords = _centroids(groups)
    frame = classify(prepare_scoring_frame(pd.DataFrame(groups.drop(columns=groups.geometry.name))), require_non_rail)
    frame = frame.join(coords[["x_itm", "y_itm"]]).assign(x=coords["x"], y=coords["y"])
    frame["HubNameHE"] = hub_name_lookup(frame, hub_names)
    frame["n_modes"] = frame["Mode_Planned"].map(len)
    frame["n_lines"] = frame["Line_Unique"].map(len)
    frame["exclusion_reason"] = frame.apply(_exclusion_reason, axis=1, require_non_rail=require_non_rail) if len(frame) else ""

    scores = results[["group", *[c for c in SCORE_COLUMNS if c in results.columns]]].drop_duplicates("group")
    frame = frame.merge(scores, on="group", how="left")
    for col in SCORE_COLUMNS:
        if col not in frame.columns:
            frame[col] = float("nan")
    return frame[list(ALL_GROUPS_COLUMNS)].reset_index(drop=True)


def build_network_nodes_table(
    nodes: gpd.GeoDataFrame,
    hexes: gpd.GeoDataFrame,
    line_names: Mapping[str, str],
) -> pd.DataFrame:
    """One row per node x line with the line's mode, ITM position and hub group.

    Each row is placed in the hexagon its point falls in (the resolution is read from
    ``hexes``), which carries the ``group`` and ``hub_id``. ``line_name`` is the Hebrew
    display name of the line, empty when the line has none. Duplicate (node, line) rows are
    reduced to the first.
    """
    cols = [NODE_COL, LINE_COL, MODE_COL]
    rows = nodes.drop_duplicates([NODE_COL, LINE_COL])
    itm = rows.to_crs(CRS_ISRAEL_TM)
    wgs = rows.to_crs(CRS_WGS84)
    resolution = h3.get_resolution(hexes["h3_index"].iloc[0])
    out = pd.DataFrame(rows[cols])
    out["x_itm"] = itm.geometry.x.to_numpy()
    out["y_itm"] = itm.geometry.y.to_numpy()
    out["h3_index"] = [h3.latlng_to_cell(y, x, resolution) for x, y in zip(wgs.geometry.x, wgs.geometry.y)]
    out["line_name"] = out[LINE_COL].map(lambda line: line_names.get(str(line).strip().strip("\\").strip(), ""))
    out = out.merge(hexes[["h3_index", "group", "hub_id"]], on="h3_index", how="left", validate="many_to_one")
    return out[list(NETWORK_NODES_COLUMNS)].reset_index(drop=True)


def lists_to_text(table: pd.DataFrame) -> pd.DataFrame:
    """Copy of ``table`` with list-valued columns joined by ``;`` for CSV output."""
    out = table.copy()
    for col in out.columns:
        if out[col].map(lambda v: isinstance(v, (list, tuple))).any():
            out[col] = out[col].map(lambda v: ";".join(str(i) for i in v) if isinstance(v, (list, tuple)) else v)
    return out
