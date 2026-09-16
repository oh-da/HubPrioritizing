"""Post-processing on the golden workbook's own upstream columns must reproduce its display columns."""

import pandas as pd
import pytest

from src.pipeline.inputs import read_csv_auto
from src.pipeline.postprocess import finalize_columns, load_line_corrections, load_line_names, load_line_status
from src.pipeline.report import RunReport
from tests.golden.conftest import REFERENCE_DIR, parse_listish

UPSTREAM = [
    "group", "x", "y", "h3_index", "node", "Mode_Planned", "Line_Unique", "Line_Nunique", "address", "area", "location",
    "TotalDemand", "TotalTransfers", "BRT Lines", "Cable Line Lines", "Funicular Lines", "HighSpeed Rail Lines",
    "Interurban Rail Lines", "LRT Lines", "Metro Lines", "Suburban Rail Lines", "pop_0_500", "emp_0_500", "pop_500_1000",
    "emp_500_1000", "pop_1000_1500", "emp_1000_1500", "Region_category", "Location_category", "RegionLocation", "Num_Modes",
    "score", "bus_terminal", "HubType", "RegionLocation_Norm", "score_Norm", "bus_terminal_Norm", "TotalDemand_Norm",
    "PopEmp_Score_Norm", "Average_Simulated_Score", "Overall_Rank", "Rank_within_HubType", "LogDemand",
]


@pytest.fixture(scope="module")
def lookups(real_inputs):
    report = RunReport()
    names = load_line_names(read_csv_auto(real_inputs.path("line_names"), header=None)[0], report)
    extra, _ = read_csv_auto(REFERENCE_DIR / "line_names_extra.csv")
    for k, v in zip(extra["LineName"], extra["Line_n_Mode"]):
        names.setdefault(str(k).strip(), str(v).strip())
    status = load_line_status(read_csv_auto(real_inputs.path("line_status"))[0], report)
    corrections = load_line_corrections(read_csv_auto(real_inputs.path("line_corrections"))[0])
    hub_names, _ = read_csv_auto(real_inputs.path("hub_names"), hebrew_columns=["HubNameHE"])
    return names, status, corrections, hub_names, report


@pytest.fixture(scope="module")
def upstream(golden) -> pd.DataFrame:
    g = golden[UPSTREAM].copy()
    for col in ("h3_index", "node", "Mode_Planned", "Line_Unique", "location"):
        g[col] = g[col].map(parse_listish)
    g["node"] = g["node"].map(lambda ns: [int(n) for n in ns])
    g["Total_Unique_Lines"] = g["Line_Unique"].map(len)
    return g


@pytest.fixture(scope="module")
def final(upstream, lookups):
    names, status, corrections, hub_names, report = lookups
    return finalize_columns(upstream, line_names=names, line_status=status, line_corrections=corrections, hub_names=hub_names, report=report), report


def test_derived_columns_match_golden(final, golden):
    out, _ = final
    o = out.set_index("group")
    g = golden.set_index("group").loc[o.index]
    for col in ("Metro", "LocationForChart", "HubTypeHE", "HubType_Filtered", "BusTERMINAL_Clone", "TotalNumLines", "TotalPop_2050", "TotalEmp_2050", "TransferRate", "PopEmp_Score"):
        left, right = o[col], g[col]
        if pd.api.types.is_numeric_dtype(right):
            pd.testing.assert_series_equal(left.astype(float), right.astype(float), check_names=False, rtol=1e-9, atol=1e-9, check_dtype=False)
        else:
            assert (left.astype(str) == right.astype(str)).all(), col


def test_score_renames_are_consistent(final, golden):
    """TotalScore_MC etc. are copies of the Monte Carlo columns.

    In the golden workbook group 25 (Netanya) carries a TotalScore_MC / Rank_TS_MC that
    differs from its own Average_Simulated_Score / Overall_Rank (hand-edited after the
    run); the port cannot and should not reproduce that.
    """
    out, _ = final
    o = out.set_index("group")
    g = golden.set_index("group").loc[o.index]
    stale = g.index[(g["TotalScore_MC"] - g["Average_Simulated_Score"]).abs() > 1e-9].tolist()
    print(f"\n[renames] golden rows where TotalScore_MC != Average_Simulated_Score: {stale}")
    for dst, src in (("TotalScore_MC", "Average_Simulated_Score"), ("Rank_TS_MC", "Overall_Rank"), ("Rank_By_TS_MC_By_Metro", "Rank_within_HubType")):
        pd.testing.assert_series_equal(o[dst].astype(float), g[src].astype(float), check_names=False)
        consistent = g.index.difference(stale)
        pd.testing.assert_series_equal(o.loc[consistent, dst].astype(float), g.loc[consistent, dst].astype(float), check_names=False)


def test_modes_for_plot_matches_golden_except_cable_fix(final, golden):
    out, _ = final
    o = out.set_index("group")
    g = golden.set_index("group").loc[o.index]
    # order of modes may differ (set order in the notebook); compare as sets; 'Cable Line' is now translated
    ours = o["Modes_ForPlot"].map(lambda s: {x.strip() for x in s.split(",")})
    theirs = g["Modes_ForPlot"].map(lambda s: {("רכבל" if x.strip() == "Cable Line" else x.strip()) for x in str(s).split(",")})
    assert (ours == theirs).all()


def test_line_names_and_status_columns_match_golden(final, golden):
    out, report = final
    o = out.set_index("group")
    g = golden.set_index("group").loc[o.index]
    # The notebook stripped apostrophes from line IDs before the status lookup, so hubs
    # served by lines such as 4.4_Bee'rSheva-Rahat_Main got no status counts in the golden.
    # The port looks the IDs up correctly; exclude those hubs from the comparison.
    has_apostrophe = o["Line_Unique"].map(lambda ls: any("'" in str(l) for l in ls))
    print(f"\n[status] hubs excluded for apostrophe line IDs: {o.index[has_apostrophe].tolist()}")
    oo, gg = o[~has_apostrophe], g[~has_apostrophe]
    for sid in range(8):
        col = f"NumLinesStatus_{sid}"
        pd.testing.assert_series_equal(oo[col].astype(int), gg[col].astype(int), check_names=False)
    pd.testing.assert_series_equal(oo["TotalLinesAllStatuses"].astype(int), gg["TotalLinesAllStatuses"].astype(int), check_names=False)
    # and the excluded hubs now do get their statuses counted
    assert (o.loc[has_apostrophe, "TotalLinesAllStatuses"] >= g.loc[has_apostrophe, "TotalLinesAllStatuses"]).all()
    # Same number of lines named per hub (the names themselves drift with the names table:
    # the current file names LRT51/52 and renames LRT31/32, the golden run's file did not).
    n_ours = o["Line_Names_forPlot"].map(lambda s: len(s.split(", ")))
    n_gold = g["Line_Names_forPlot"].map(lambda s: len(str(s).split(", ")))
    pd.testing.assert_series_equal(n_ours, n_gold, check_names=False)
    unnamed = [w for w in report.warnings if "no Hebrew name" in w.message]
    print("\n[unnamed lines]", unnamed[0].data["lines"] if unnamed else [])


def test_line_names_for_plot_formula(golden, lookups):
    """The former Excel formula: strip brackets/quotes, join with ', ', substitute the M1 IDs.

    Applied to the golden's own Line_Names list it must reproduce the golden column
    (apostrophes and the '\\' escape artifact removed on both sides, as the formula did).
    """
    import ast

    from src.pipeline.postprocess import line_names_for_plot

    extra, _ = read_csv_auto(REFERENCE_DIR / "line_names_extra.csv")
    m1 = dict(zip(extra["LineName"], extra["Line_n_Mode"]))
    norm = lambda s: s.replace("\\", "").replace("'", "")
    mism = []
    for grp, names, expected in zip(golden["group"], golden["Line_Names"], golden["Line_Names_forPlot"]):
        rendered = line_names_for_plot([m1.get(n, n) for n in ast.literal_eval(names)])
        if norm(rendered) != norm(str(expected)):
            mism.append(grp)
    print(f"\n[Line_Names_forPlot formula] mismatches: {len(mism)} {mism[:5]}")
    assert not mism


def test_hub_names_and_rank_formula_match_golden(final, golden):
    out, _ = final
    o = out.set_index("group")
    g = golden.set_index("group").loc[o.index]
    name_mism = o.index[o["HubNameHE"].astype(str) != g["HubNameHE"].astype(str)].tolist()
    print(f"\n[HubNameHE] mismatches: {len(name_mism)} {[(i, o.loc[i, 'HubNameHE'], g.loc[i, 'HubNameHE']) for i in name_mism[:5]]}")
    assert not name_mism
    pd.testing.assert_series_equal(o["RankByHubTypeMetro"].astype(int), g["RankByHubTypeMetro"].astype(int), check_names=False)


def test_global_renormalisation_reproduces_golden_norm_columns(upstream, lookups, golden):
    names, status, corrections, hub_names, _ = lookups
    out = finalize_columns(upstream, line_names=names, line_status=status, line_corrections=corrections, hub_names=hub_names, renormalize_globally=True)
    o = out.set_index("group")
    g = golden.set_index("group").loc[o.index]
    for col in ("RegionLocation_Norm", "score_Norm", "bus_terminal_Norm", "PopEmp_Score_Norm", "TotalDemand_Norm"):
        pd.testing.assert_series_equal(o[col].astype(float), g[col].astype(float), check_names=False, rtol=1e-9, atol=1e-9)
