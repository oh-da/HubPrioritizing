"""Scoring recomputed from the golden workbook's raw columns must reproduce its scores and ranks."""

import numpy as np
import pandas as pd
import pytest

from src.pipeline.scoring import add_mode_score, classify, filter_eligible, monte_carlo, normalize_scores, prepare_scoring_frame
from tests.golden.conftest import parse_listish

MODE_LINE_COLS = ["BRT Lines", "Cable Line Lines", "Funicular Lines", "HighSpeed Rail Lines", "Interurban Rail Lines", "LRT Lines", "Metro Lines", "Suburban Rail Lines"]
RING_COLS = ["pop_0_500", "emp_0_500", "pop_500_1000", "emp_500_1000", "pop_1000_1500", "emp_1000_1500"]


@pytest.fixture(scope="module")
def golden_raw(golden) -> pd.DataFrame:
    g = golden.copy()
    g["Mode_Planned"] = g["Mode_Planned"].map(parse_listish)
    g["Line_Unique"] = g["Line_Unique"].map(parse_listish)
    g["location"] = g["location"].map(parse_listish)
    keep = ["group", "TotalDemand", "TotalTransfers", "Mode_Planned", "Line_Unique", "area", "location", "Num_Modes", "bus_terminal", *MODE_LINE_COLS, *RING_COLS]
    return g[keep].sort_values("group").reset_index(drop=True)


@pytest.fixture(scope="module")
def scored(golden_raw) -> pd.DataFrame:
    df = classify(add_mode_score(prepare_scoring_frame(golden_raw)))
    df = filter_eligible(df, enabled=True)
    df = normalize_scores(df)
    return monte_carlo(df, n_iter=10000, seed=42, scope="per_hubtype")


def test_all_golden_hubs_pass_eligibility(golden_raw, scored):
    assert len(scored) == len(golden_raw) == 142


def test_categories_and_mode_score_match(scored, golden):
    g = golden.set_index("group")
    s = scored.set_index("group")
    for col in ("Region_category", "Location_category", "RegionLocation", "Num_Modes"):
        pd.testing.assert_series_equal(s[col].astype(int), g.loc[s.index, col].astype(int), check_names=False)
    np.testing.assert_allclose(s["score"], g.loc[s.index, "score"], rtol=1e-9)


def test_hub_types_match(scored, golden):
    g = golden.set_index("group")
    s = scored.set_index("group")
    mism = s.index[s["HubType"] != g.loc[s.index, "HubType"]].tolist()
    print(f"\n[HubType] mismatches: {len(mism)} {mism[:10]}")
    assert not mism


def test_monte_carlo_scores_and_ranks_match(scored, golden):
    g = golden.set_index("group")
    s = scored.set_index("group")
    diff = (s["Average_Simulated_Score"] - g.loc[s.index, "Average_Simulated_Score"]).abs()
    print(f"\n[MC] max |diff| = {diff.max():.3e}; worst groups {diff.sort_values(ascending=False).head(5).to_dict()}")
    assert diff.max() < 1e-6

    # The golden ranks were computed on a larger table (max Overall_Rank 147 for 142 rows),
    # so compare the ORDER the ranks induce, not their raw values.
    gold = g.loc[s.index]
    print(f"[ranks] golden Overall_Rank max = {int(gold['Overall_Rank'].max())} on {len(gold)} rows")
    for col in ("Overall_Rank", "Rank_within_HubType"):
        ours_order = s[col].rank(method="dense")
        gold_order = gold[col].rank(method="dense")
        if col == "Rank_within_HubType":
            ours_order = s.groupby("HubType")[col].rank(method="dense")
            gold_order = gold.groupby("HubType")[col].rank(method="dense")
        mism = s.index[(ours_order != gold_order).to_numpy()].tolist()
        print(f"[ranks] {col}: {len(mism)} order mismatches {mism[:10]}")
        assert not mism, col
