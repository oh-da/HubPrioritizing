import numpy as np
import pandas as pd
import pytest

from src.config import TIER_LOCAL, TIER_METRO, TIER_NATIONAL
from src.pipeline.scoring import (
    SCORING_COLS,
    add_mode_score,
    classify,
    correct_mode_planned,
    draw_weight_matrix,
    filter_eligible,
    location_category,
    monte_carlo,
    normalize_scores,
    prepare_scoring_frame,
    region_category,
    score_hubs,
)


@pytest.fixture
def groups():
    return pd.DataFrame(
        {
            "group": [2, 0, 1, 3],
            "TotalDemand": [60000.0, 8000.0, 1500.0, 900.0],
            "TotalTransfers": [1000.0, 0.0, 0.0, 0.0],
            "Mode_Planned": [["HighSpeed Rail", "LRT", "Rail"], ["Suburban", "BRT"], ["BRT", "LRT"], ["LRT", "BRT"]],
            "Line_Unique": [["a", "b", "c", "d"], ["e", "f", "g"], ["h", "i", "j"], ["k", "l", "m"]],
            "area": ["תל אביב", "חיפה", "מחוז דרום", "ירושלים"],
            "location": [["גלעין"], ["טבעת פנימית"], ["מחוז דרום"], ["גלעין"]],
            "HighSpeed Rail Lines": [2.0, 0.0, 0.0, 0.0],
            "LRT Lines": [2.0, 0.0, 1.5, 1.5],
            "Suburban Rail Lines": [0.0, 1.5, 0.0, 0.0],
            "BRT Lines": [0.0, 1.5, 1.5, 1.5],
            "Num_Modes": [2, 2, 2, 2],
            "bus_terminal": [3, 0, 2, 0],
            "pop_0_500": [1000.0, 500.0, 200.0, 100.0],
            "emp_0_500": [5000.0, 200.0, 100.0, 50.0],
            "pop_500_1000": [2000.0, 800.0, 300.0, 100.0],
            "emp_500_1000": [6000.0, 300.0, 100.0, 50.0],
            "pop_1000_1500": [3000.0, 900.0, 400.0, 100.0],
            "emp_1000_1500": [7000.0, 400.0, 100.0, 50.0],
        }
    )


def test_correct_mode_planned_drops_generic_rail_and_expands_aliases():
    assert correct_mode_planned(["HighSpeed", "Rail", "Suburban,", "LRT"]) == ["HighSpeed Rail", "Suburban Rail", "LRT"]
    assert correct_mode_planned("not a list") == []


@pytest.mark.parametrize("area, cat", [("תל אביב", 0), ("מחוז מרכז", 0), ("Tel Aviv", 0), ("חיפה", 1), (None, 1), (["חיפה", "מרכז"], 0)])
def test_region_category(area, cat):
    assert region_category(area) == cat


@pytest.mark.parametrize("loc, cat", [(["גלעין"], 3), (["טבעת חיצונית"], 2), (["מחוז דרום"], 1), (["טבעת", "גלעין"], 3), (None, 1)])
def test_location_category(loc, cat):
    assert location_category(loc) == cat


def test_prepare_and_mode_score(groups):
    df = add_mode_score(prepare_scoring_frame(groups))
    row = df[df["group"] == 2].iloc[0]
    assert row["Total_Unique_Lines"] == 4 and row["RegionLocation"] == 0  # Tel Aviv core: 0 * 3
    assert row["Mode_Planned"] == ["HighSpeed Rail", "LRT"]
    # score = (2*8 + 2*5) * (1 + 0.1*(2-1)) with config MODE_WEIGHTS
    assert row["score"] == pytest.approx((2 * 8 + 2 * 5) * 1.1)
    assert df[df["group"] == 0].iloc[0]["RegionLocation"] == 2  # Haifa inner ring: 1 * 2


def test_classify_and_filter(groups):
    df = classify(add_mode_score(prepare_scoring_frame(groups)))
    by = df.set_index("group")
    assert by.loc[2, "HubType"] == TIER_NATIONAL
    assert by.loc[0, "HubType"] == TIER_METRO
    assert by.loc[1, "HubType"] == TIER_LOCAL
    assert by.loc[3, "HubType"] == "Not Hub"  # < 1000 demand
    assert list(by["eligible"]) == [True, True, True, False]
    kept = filter_eligible(df, True)
    assert set(kept["group"]) == {0, 1, 2}
    assert len(filter_eligible(df, False)) == 4


def test_rail_only_hubs_are_excluded_when_required():
    df = pd.DataFrame(
        {"group": [0], "TotalDemand": [70000.0], "Mode_Planned": [["Suburban Rail", "Interurban Rail"]], "Line_Unique": [["a", "b", "c"]], "area": ["חיפה"], "location": [["גלעין"]], "Num_Modes": [2], "bus_terminal": [0]}
    )
    out = classify(add_mode_score(prepare_scoring_frame(df)), require_non_rail=True)
    assert out.loc[0, "is_rail_only"] and not out.loc[0, "eligible"]
    assert classify(add_mode_score(prepare_scoring_frame(df)), require_non_rail=False).loc[0, "eligible"]


def test_normalize_scores_per_type(groups):
    df = classify(add_mode_score(prepare_scoring_frame(groups)))
    df = filter_eligible(df, False)
    out = normalize_scores(df)
    # every hub type here has a single member -> constant -> 5.5 for min-max columns
    assert (out["RegionLocation_Norm"] == 5.5).all()
    assert (out["TotalDemand_Norm"] == 5.5).all()
    for col in SCORING_COLS:
        assert out[col].between(1, 10).all()
    # national/metro weight jobs 80 %
    nat = out[out["HubType"] == TIER_NATIONAL].iloc[0]
    mids = np.array([250.0, 750.0, 1250.0]) ** 1.5
    expected = ((0.2 * np.array([1000, 2000, 3000]) + 0.8 * np.array([5000, 6000, 7000])) / mids).sum()
    assert nat["PopEmp_Score_Raw"] == pytest.approx(expected)


def test_normalize_scores_type_with_two_members():
    df = pd.DataFrame({"HubType": ["x", "x", "y"], "RegionLocation": [1, 3, 2], "score": [0, 10, 5], "bus_terminal": [0, 3, 3], "TotalDemand": [1000.0, 10000.0, 0.0]})
    out = normalize_scores(df)
    assert list(out["RegionLocation_Norm"][:2]) == [1.0, 10.0]
    assert list(out["TotalDemand_Norm"][:2]) == [1.0, 10.0]
    assert out["TotalDemand_Norm"].iloc[2] == 1.0  # a type with no non-zero demand
    assert out["PopEmp_Score_Norm"].iloc[0] == 5.0  # no ring columns


def test_draw_weight_matrix_matches_legacy_loop():
    legacy = []
    np.random.seed(42)
    for _ in range(50):
        w = np.random.rand(5)
        while any(w > 0.5):
            w = np.random.rand(5)
        legacy.append(w / w.sum())
    ours = draw_weight_matrix(np.random.RandomState(42), 50, 5)
    np.testing.assert_allclose(ours, np.array(legacy), rtol=0, atol=1e-15)
    # the 0.5 cap applies to the raw draws; after normalisation a weight may exceed 0.5
    assert np.allclose(ours.sum(axis=1), 1)


def test_monte_carlo_matches_notebook_loop(groups):
    df = normalize_scores(filter_eligible(classify(add_mode_score(prepare_scoring_frame(groups))), False))
    df = df.sort_values("group").reset_index(drop=True)
    n_iter = 300
    ours = monte_carlo(df, n_iter=n_iter, seed=42)

    # straight port of notebook cell 88
    np.random.seed(42)
    cols = list(SCORING_COLS)
    parts = []
    for hub_type in df["HubType"].unique():
        hub_df = df[df["HubType"] == hub_type].copy()
        hub_df["Sum"] = 0.0
        for _ in range(n_iter):
            w = np.random.rand(len(cols))
            while any(w > 0.5):
                w = np.random.rand(len(cols))
            w /= w.sum()
            hub_df["Sum"] += (hub_df[cols] * w).sum(axis=1)
        hub_df["Average_Simulated_Score"] = hub_df["Sum"] / n_iter
        parts.append(hub_df)
    legacy = pd.concat(parts).sort_index()
    np.testing.assert_allclose(ours["Average_Simulated_Score"], legacy["Average_Simulated_Score"], atol=1e-10)
    assert ours["Overall_Rank"].min() == 1 and ours["Rank_within_HubType"].max() >= 1


def test_score_hubs_is_deterministic(groups):
    a = score_hubs(groups, n_iter=200)
    b = score_hubs(groups, n_iter=200)
    pd.testing.assert_frame_equal(a, b)
    assert set(a.columns) >= {"Average_Simulated_Score", "Overall_Rank", "Rank_within_HubType", "HubType", *SCORING_COLS}
    with pytest.raises(ValueError):
        monte_carlo(a.drop(columns=["score_Norm"]), n_iter=10)
