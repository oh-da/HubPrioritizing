"""Area tagging + demand on the real exports must reproduce the golden TotalDemand per hub."""

import pandas as pd
import pytest

from src.pipeline.demand import apply_manual_demand, assign_demand, load_demand_workbook
from src.pipeline.grouping import apply_manual_groups, group_hexes
from src.pipeline.inputs import read_csv_auto, read_excel_sheets, read_shapefile
from src.pipeline.network import add_mode_line_columns, aggregate_to_hexes, attach_modes, load_nodeslines
from src.pipeline.report import RunReport
from src.pipeline.settings import PipelineConfig
from src.pipeline.spatial_tags import tag_area_and_location


@pytest.fixture(scope="module")
def hexes_with_demand(real_inputs, real_nodeslines, real_lines_mode):
    cfg = PipelineConfig()
    report = RunReport()
    nodes = attach_modes(load_nodeslines(real_nodeslines), real_lines_mode, cfg.drop_line_rules, report)
    hexes = add_mode_line_columns(aggregate_to_hexes(nodes, cfg.h3_resolution), cfg.per_mode_lines_method)
    hexes = group_hexes(hexes, cfg.merge_threshold_m, cfg.merge_tolerance_m)
    manual_groups = read_csv_auto(real_inputs.path("is_same_group"))[0] if real_inputs.has("is_same_group") else None
    hexes = apply_manual_groups(hexes, manual_groups, report)

    metro, _ = read_shapefile(real_inputs.path("metro"), hebrew_columns=["METRO_NAME", "ZONE_NAME"])
    districts, _ = read_shapefile(real_inputs.path("districts"), hebrew_columns=["MACHOZ"])
    hexes = tag_area_and_location(hexes, metro, districts, report)

    by_region = load_demand_workbook(read_excel_sheets(real_inputs.path("demand")), report)
    hexes = assign_demand(hexes, by_region, cfg.overlay_regions, report)
    manual = read_csv_auto(real_inputs.path("manual_demand"))[0] if real_inputs.has("manual_demand") else None
    hexes = apply_manual_demand(hexes, manual, report)
    return hexes, report


def _by_nodeset(hexes: pd.DataFrame) -> dict[frozenset, dict]:
    out = {}
    for g, grp in hexes.groupby("group"):
        nodes = frozenset(int(n) for ns in grp["node"] for n in ns)
        out[nodes] = {
            "TotalDemand": float(grp["TotalDemand"].sum()),
            "TotalTransfers": float(grp["TotalTransfers"].sum()),
            "areas": set(grp["area"]),
        }
    return out


def test_area_vocabulary_matches_golden(hexes_with_demand, golden, golden_groups):
    hexes, _ = hexes_with_demand
    ours = _by_nodeset(hexes)
    mismatches = []
    for g, nodes in golden_groups.items():
        golden_area = golden.set_index("group").loc[g, "area"]
        our_areas = ours.get(nodes, {}).get("areas")
        if our_areas is None or golden_area not in our_areas:
            mismatches.append((g, golden_area, our_areas))
    print(f"\n[area] mismatches: {len(mismatches)} of {len(golden_groups)}: {mismatches[:10]}")
    assert len(mismatches) <= 0.05 * len(golden_groups)


def test_total_demand_matches_golden(hexes_with_demand, golden, golden_groups):
    hexes, report = hexes_with_demand
    ours = _by_nodeset(hexes)
    g = golden.set_index("group")
    rows = []
    for grp, nodes in golden_groups.items():
        mine = ours.get(nodes)
        rows.append(
            {
                "group": grp,
                "golden": float(g.loc[grp, "TotalDemand"]),
                "ours": None if mine is None else mine["TotalDemand"],
                "golden_t": float(g.loc[grp, "TotalTransfers"]),
                "ours_t": None if mine is None else mine["TotalTransfers"],
            }
        )
    df = pd.DataFrame(rows)
    df["diff"] = (df["ours"] - df["golden"]).abs()
    bad = df[(df["diff"] > 1.0) | df["ours"].isna()].sort_values("diff", ascending=False)
    print(f"\n[demand] hubs off by >1: {len(bad)} of {len(df)}")
    print(bad.head(15).to_string(index=False))
    print("[demand warnings]", [w.message for w in report.warnings][:8])
    assert len(bad) <= 0.05 * len(df)
