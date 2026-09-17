"""Compare the ported network + grouping stages against the golden workbook's hub node sets.

Informational: the golden was produced with the same June 2026 exports, so the
overlap should be high, but manual merges and any input drift make exact equality
unlikely. The assertions guard against gross regressions only.
"""

import pandas as pd
import pytest

from src.pipeline.grouping import apply_manual_groups, group_hexes
from src.pipeline.inputs import read_csv_auto
from src.pipeline.network import add_mode_line_columns, aggregate_to_hexes, attach_modes, load_nodeslines
from src.pipeline.report import RunReport
from src.pipeline.settings import PipelineConfig


@pytest.fixture(scope="module")
def grouped_real(real_inputs, real_nodeslines, real_lines_mode):
    cfg = PipelineConfig()
    report = RunReport()
    nodes = attach_modes(load_nodeslines(real_nodeslines), real_lines_mode, cfg.drop_line_rules, report)
    hexes = add_mode_line_columns(aggregate_to_hexes(nodes, cfg.h3_resolution), cfg.per_mode_lines_method)
    grouped = group_hexes(hexes, cfg.merge_threshold_m, cfg.merge_tolerance_m)
    manual = None
    if real_inputs.has("is_same_group"):
        manual, _ = read_csv_auto(real_inputs.path("is_same_group"))
    grouped = apply_manual_groups(grouped, manual, report)
    return grouped, report


def test_network_report_lists_known_data_issues(grouped_real):
    _, report = grouped_real
    messages = " | ".join(w.message for w in report.warnings)
    assert "duplicated Line_ModelName" in messages
    unmatched = [w for w in report.warnings if "no row" in w.message][0]
    assert set(unmatched.data["lines"]) == {"BluRT1", "BluRT2", "LRT9", "LRT10"}


def test_group_node_sets_overlap_golden(grouped_real, golden_groups):
    grouped, _ = grouped_real
    ours = {}
    for g, grp in grouped.groupby("group"):
        ours[int(g)] = frozenset(int(n) for ns in grp["node"] for n in ns)
    our_sets = set(ours.values())
    golden_sets = set(golden_groups.values())

    exact = len(our_sets & golden_sets)
    # golden groups whose nodes are all inside one of our groups (we merged more)
    contained = sum(1 for gs in golden_sets if gs not in our_sets and any(gs <= o for o in our_sets))
    print(
        f"\n[golden groups] total={len(golden_sets)} exact={exact} contained_in_ours={contained} "
        f"ours_total={len(our_sets)}"
    )
    missing = [sorted(gs) for gs in golden_sets if not any(gs <= o for o in our_sets)]
    print(f"[golden groups] not reproduced (first 10): {missing[:10]}")
    assert exact + contained >= 0.9 * len(golden_sets)
