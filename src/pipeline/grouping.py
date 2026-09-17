"""
Part 1 (continued): group hexagons into hubs.

Ports cells 17-21 of ``COMPLETE_TRANSIT_PIPELINE.ipynb``:

- :func:`group_hexes`          union-find over hexagons within 120 m edge-to-edge
- :func:`apply_manual_groups`  merges forced by ``is_same_group.csv``, then sequential renumbering
- :func:`assign_hub_ids`       a stable ``hub_id`` derived from the group's node set
- :func:`hub_identity_table`   group -> hub_id -> nodes lookup for the output folder
"""

from __future__ import annotations

import hashlib
from typing import Iterable

import geopandas as gpd
import pandas as pd

from ..config import HUB_MERGE_THRESHOLD_M, HUB_MERGE_TOLERANCE_M
from ..spatial.merging import create_proximity_groups
from .report import RunReport
from .spatial_tags import get_regions_for_area

MANUAL_GROUP_COLUMN = "Nodes in group"


def group_hexes(
    hexes: gpd.GeoDataFrame,
    threshold_m: float = HUB_MERGE_THRESHOLD_M,
    tolerance_m: float = HUB_MERGE_TOLERANCE_M,
) -> gpd.GeoDataFrame:
    """Add a ``group`` column: transitive clusters of hexagons within ``threshold_m``.

    Distances are edge-to-edge in EPSG:2039. Group IDs are assigned in order of first
    appearance, like the notebook.
    """
    out = hexes.copy().reset_index(drop=True)
    return create_proximity_groups(out, distance_threshold=threshold_m, tolerance=tolerance_m)


def parse_manual_group_rows(is_same_group: pd.DataFrame) -> list[tuple[list[int], str | None]]:
    """``(node ids, model)`` per row of the manual group file (rows with < 2 nodes skipped).

    ``model`` comes from an optional ``model`` column (blank = any) and restricts the
    merge to hexagons whose location belongs to that demand model.
    """
    if MANUAL_GROUP_COLUMN not in is_same_group.columns:
        raise ValueError(f"manual group file needs a '{MANUAL_GROUP_COLUMN}' column")
    rows: list[tuple[list[int], str | None]] = []
    has_model = "model" in is_same_group.columns
    for _, r in is_same_group.iterrows():
        raw = r[MANUAL_GROUP_COLUMN]
        if pd.isna(raw):
            continue
        ids = []
        for tok in str(raw).replace(";", ",").split(","):
            tok = tok.strip()
            if tok:
                ids.append(int(float(tok)))
        if len(ids) < 2:
            continue
        model = None
        if has_model and pd.notna(r["model"]) and str(r["model"]).strip():
            model = str(r["model"]).strip()
        rows.append((ids, model))
    return rows


def parse_manual_groups(is_same_group: pd.DataFrame) -> list[list[int]]:
    """Parse the ``Nodes in group`` column into lists of node IDs (rows with < 2 nodes skipped)."""
    return [ids for ids, _ in parse_manual_group_rows(is_same_group)]


def apply_manual_groups(
    hexes: gpd.GeoDataFrame,
    is_same_group: pd.DataFrame | None,
    report: RunReport | None = None,
    renumber: bool = True,
) -> gpd.GeoDataFrame:
    """Force the hexagons holding the listed nodes into one group, then renumber.

    Mirrors notebook cell 21: every group touched by a row is merged into the
    smallest group ID among them; afterwards group IDs are renumbered to
    0..n-1 in ascending order of the old IDs (only when a manual file was given,
    as in the notebook).
    """
    out = hexes.copy()
    if is_same_group is None:
        if report is not None:
            report.info("grouping", "no manual group corrections file; groups unchanged")
        return out

    node_to_idx: dict[int, list[int]] = {}
    for idx, nodes in zip(out.index, out["node"]):
        for n in nodes if isinstance(nodes, list) else [nodes]:
            node_to_idx.setdefault(int(n), []).append(idx)
    areas = out["area"] if "area" in out.columns else None

    applied = merged = 0
    for row_num, (node_ids, model) in enumerate(parse_manual_group_rows(is_same_group)):
        idxs, missing, wrong_model = [], [], []
        for n in node_ids:
            if n not in node_to_idx:
                missing.append(n)
                continue
            for idx in node_to_idx[n]:
                if model is not None and (areas is None or model not in get_regions_for_area(areas.loc[idx])):
                    wrong_model.append(n)
                    continue
                idxs.append(idx)
        if missing and report is not None:
            report.warn("grouping", f"manual group row {row_num}: nodes not found in network", nodes=missing)
        if wrong_model and report is not None:
            report.warn("grouping", f"manual group row {row_num}: nodes present but not in model '{model}'; ignored for this row", nodes=sorted(set(wrong_model)))
        if len(idxs) < 2:
            if report is not None:
                report.warn("grouping", f"manual group row {row_num}: fewer than 2 hexagons matched; skipped", nodes=node_ids)
            continue
        current = set(int(g) for g in out.loc[idxs, "group"])
        if len(current) > 1:
            target = min(current)
            out.loc[out["group"].isin(current - {target}), "group"] = target
            merged += len(current) - 1
            applied += 1
            if report is not None:
                report.info("grouping", f"manual merge of groups {sorted(current)} -> {target}", nodes=node_ids)
        elif report is not None:
            report.info("grouping", f"manual group row {row_num}: nodes already in one group", nodes=node_ids)

    if renumber:
        mapping = {old: new for new, old in enumerate(sorted(out["group"].unique()))}
        out["group"] = out["group"].map(mapping).astype(int)

    if report is not None:
        report.set_metric("manual_group_rows_applied", applied)
        report.set_metric("groups_merged_manually", merged)
    return out


def stable_hub_id(nodes: Iterable[int]) -> str:
    """``'H' + sha1(sorted node ids)[:10]``: unchanged as long as the group's nodes are."""
    key = ",".join(str(int(n)) for n in sorted(set(int(x) for x in nodes)))
    return "H" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def assign_hub_ids(hexes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add ``hub_id`` per group from the union of the group's node IDs."""
    out = hexes.copy()
    nodes_by_group: dict[int, set[int]] = {}
    for g, nodes in zip(out["group"], out["node"]):
        nodes_by_group.setdefault(int(g), set()).update(int(n) for n in (nodes if isinstance(nodes, list) else [nodes]))
    ids = {g: stable_hub_id(ns) for g, ns in nodes_by_group.items()}
    out["hub_id"] = out["group"].map(lambda g: ids[int(g)])
    return out


def hub_identity_table(hexes: gpd.GeoDataFrame) -> pd.DataFrame:
    """``group, hub_id, n_hexes, nodes, demand_models`` (nodes as a comma-separated sorted
    string; ``demand_models`` the models that supplied the nodes' demand, when known)."""
    rows = []
    has_models = "DemandModels" in hexes.columns
    for g, grp in hexes.groupby("group", sort=True):
        nodes = sorted({int(n) for ns in grp["node"] for n in (ns if isinstance(ns, list) else [ns])})
        row = {"group": int(g), "hub_id": stable_hub_id(nodes), "n_hexes": len(grp), "nodes": ",".join(map(str, nodes))}
        if has_models:
            models = list(dict.fromkeys(m for ms in grp["DemandModels"] for m in (ms if isinstance(ms, list) else [])))
            row["demand_models"] = ";".join(models)
        rows.append(row)
    return pd.DataFrame(rows)
