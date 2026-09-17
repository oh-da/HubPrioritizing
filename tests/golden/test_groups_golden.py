"""Group-level aggregates (lines, modes, per-mode line counts) must match the golden workbook."""

import pandas as pd
import pytest

from src.pipeline.aggregate import aggregate_to_groups
from src.pipeline.demand import apply_manual_demand, assign_demand, load_demand_workbook
from src.pipeline.grouping import apply_manual_groups, assign_hub_ids, group_hexes
from src.pipeline.inputs import read_csv_auto, read_excel_sheets, read_shapefile
from src.pipeline.network import add_mode_line_columns, aggregate_to_hexes, attach_modes, load_nodeslines
from src.pipeline.report import RunReport
from src.pipeline.settings import PipelineConfig
from src.pipeline.spatial_tags import tag_area_and_location
from tests.golden.conftest import parse_listish

MODE_LINE_COLS = ["BRT Lines", "Cable Line Lines", "Funicular Lines", "HighSpeed Rail Lines", "Interurban Rail Lines", "LRT Lines", "Metro Lines", "Suburban Rail Lines"]


@pytest.fixture(scope="module")
def groups_real(real_inputs, real_nodeslines, real_lines_mode):
    cfg = PipelineConfig()
    report = RunReport()
    nodes = attach_modes(load_nodeslines(real_nodeslines), real_lines_mode, cfg.drop_line_rules, report)
    hexes = add_mode_line_columns(aggregate_to_hexes(nodes, cfg.h3_resolution), cfg.per_mode_lines_method)
    hexes = group_hexes(hexes, cfg.merge_threshold_m, cfg.merge_tolerance_m)
    manual_groups = read_csv_auto(real_inputs.path("is_same_group"))[0] if real_inputs.has("is_same_group") else None
    hexes = assign_hub_ids(apply_manual_groups(hexes, manual_groups, report))
    metro, _ = read_shapefile(real_inputs.path("metro"), hebrew_columns=["METRO_NAME", "ZONE_NAME"])
    districts, _ = read_shapefile(real_inputs.path("districts"), hebrew_columns=["MACHOZ"])
    hexes = tag_area_and_location(hexes, metro, districts, report)
    by_region = load_demand_workbook(read_excel_sheets(real_inputs.path("demand")), report)
    hexes = assign_demand(hexes, by_region, cfg.overlay_regions, report)
    manual = read_csv_auto(real_inputs.path("manual_demand"))[0] if real_inputs.has("manual_demand") else None
    hexes = apply_manual_demand(hexes, manual, report)
    return aggregate_to_groups(hexes)


def test_group_aggregates_match_golden(groups_real, golden, golden_groups):
    ours = {frozenset(n): row for n, (_, row) in zip(groups_real["node"], groups_real.iterrows())}
    g = golden.set_index("group")
    diffs = {"Line_Nunique": [], "modes": [], "lines": [], "Num_Modes": [], "mode_cols": [], "location": []}
    for grp, nodes in golden_groups.items():
        mine = ours[nodes]
        gr = g.loc[grp]
        if int(mine["Line_Nunique"]) != int(gr["Line_Nunique"]):
            diffs["Line_Nunique"].append((grp, int(mine["Line_Nunique"]), int(gr["Line_Nunique"])))
        if set(mine["Mode_Planned"]) != set(parse_listish(gr["Mode_Planned"])):
            diffs["modes"].append((grp, mine["Mode_Planned"], gr["Mode_Planned"]))
        if set(mine["Line_Unique"]) != set(parse_listish(gr["Line_Unique"])):
            diffs["lines"].append((grp, sorted(set(mine["Line_Unique"]) ^ set(parse_listish(gr["Line_Unique"])))))
        if int(mine["Num_Modes"]) != int(gr["Num_Modes"]):
            diffs["Num_Modes"].append((grp, int(mine["Num_Modes"]), int(gr["Num_Modes"])))
        for c in MODE_LINE_COLS:
            if abs(float(mine[c]) - float(gr[c])) > 1e-6:
                diffs["mode_cols"].append((grp, c, float(mine[c]), float(gr[c])))
        if mine["location"] != parse_listish(gr["location"]) and mine["location"][0] not in str(gr["location"]):
            diffs["location"].append((grp, mine["location"], gr["location"]))
    for k, v in diffs.items():
        print(f"\n[groups] {k}: {len(v)} mismatches {v[:6]}")
    assert all(len(v) == 0 for v in diffs.values()), {k: len(v) for k, v in diffs.items()}


def test_group_ids_match_golden(groups_real, golden_groups):
    """The display page keys on `group`; sorted-h3 hexagon order should reproduce the notebook's IDs."""
    ours = {frozenset(n): int(g) for n, g in zip(groups_real["node"], groups_real["group"])}
    mismatched = [(grp, ours.get(nodes)) for grp, nodes in golden_groups.items() if ours.get(nodes) != grp]
    print(f"\n[group ids] mismatched: {len(mismatched)} of {len(golden_groups)} {mismatched[:10]}")
    assert not mismatched
