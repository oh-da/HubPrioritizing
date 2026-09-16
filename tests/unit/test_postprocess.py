import numpy as np
import pandas as pd
import pytest

from src.pipeline.postprocess import (
    finalize_columns,
    hub_name_lookup,
    line_names_for_plot,
    load_line_corrections,
    load_line_names,
    load_line_status,
    modes_to_hebrew,
    parse_line_unique,
    rank_by_hubtype_metro,
)
from src.pipeline.report import RunReport


def test_parse_line_unique_handles_nested_stringified_lists():
    nested = '["[\'Mgt1-E\', \'Mgt2-E\']", "[\'M1-RA-RE\', \'rail_4_2\']"]'
    assert parse_line_unique(nested) == ["Mgt1-E", "Mgt2-E", "M1-RA-RE", "rail_4_2"]
    assert parse_line_unique("['a', 'b']") == ["a", "b"]
    assert parse_line_unique(["a", "['b' 'c']"]) == ["a", "b", "c"]
    assert parse_line_unique('["4.4_Bee\'rSheva-Rahat_Main"]') == ["4.4_Bee'rSheva-Rahat_Main"]
    assert parse_line_unique(None) == [] and parse_line_unique("[]") == []


def test_load_line_names_headerless_with_stray_header():
    df = pd.DataFrame([["4.1_Arad-BS", 'ערד-באר שבע מערב (רק"ל)'], ["Line_Unique_List", "Line_n_Mode"], [" lrt01 ", "חיפה (רק\"ל)"]])
    report = RunReport()
    names = load_line_names(df, report)
    assert names == {"4.1_Arad-BS": 'ערד-באר שבע מערב (רק"ל)', "lrt01": 'חיפה (רק"ל)'}
    assert any("header-like" in e.message for e in report.entries)


def test_load_line_status_legacy_exploded_with_conflicts():
    df = pd.DataFrame({"Unnamed: 0": [0, 1, 1, 29, 31], "LineName": ["0", "Red-N", " Red-S", "m0810a", "m0810a"], "StatusID": [0, 0, 0, 6, 7]})
    report = RunReport()
    status = load_line_status(df, report)
    assert status == {"Red-N": 0, "Red-S": 0, "m0810a": 7}  # last wins, '0' placeholder dropped
    assert report.warnings and report.warnings[0].data["lines"] == ["m0810a"]
    clean = load_line_status(pd.DataFrame({"LineName": ["A"], "Status Id": [3]}))
    assert clean == {"A": 3}


def test_load_line_corrections_strips_noise():
    df = pd.DataFrame({"ID": [1, 2], "LineName": ["\\4.2_LRT_BRS-Shoket\\", "4.5_BeeSheva-Rahat"], "LineName_Correct": ["4.2_LRT_BRS-Shoket", " 4.5_Bee'rSheva-Rahat"]})
    assert load_line_corrections(df) == {"4.2_LRT_BRS-Shoket": "4.2_LRT_BRS-Shoket", "4.5_BeeSheva-Rahat": "4.5_Bee'rSheva-Rahat"}


def test_hub_name_lookup_by_h3_and_legacy_group():
    hubs = pd.DataFrame({"group": [0, 1, 2], "h3_index": [["a", "b"], ["c"], ["z"]]})
    names = pd.DataFrame({"h3_index": ["b", "c", "a"], "HubNameHE": ["בית", "גג", "אחר"]})
    report = RunReport()
    out = hub_name_lookup(hubs, names, report)
    assert list(out) == ["אחר", "גג", None]  # first hex in the group's list wins
    assert report.metrics["hubs_without_name"] == 1 and report.warnings
    legacy = hub_name_lookup(hubs, pd.DataFrame({"group": [2], "HubNameHE": ["ישן"]}), RunReport())
    assert list(legacy) == [None, None, "ישן"]


def test_modes_and_names_for_plot():
    assert modes_to_hebrew(["Metro", "Cable Line", "BRT"]) == "מטרו, רכבל, BRT"
    assert line_names_for_plot("['א (רק\"ל)', 'ב (BRT)']") == 'א (רק"ל), ב (BRT)'


def test_rank_by_hubtype_metro_competition_rank():
    df = pd.DataFrame(
        {
            "HubType": ["ארצי", "ארצי", "מטרופוליני", "מטרופוליני", "מטרופוליני", "עירוני"],
            "Metro": ["תל אביב", "חיפה", "תל אביב", "תל אביב", "חיפה", "תל אביב"],
            "TotalScore_MC": [7.0, 7.5, 6.0, 6.0, 5.0, 4.0],
        }
    )
    assert list(rank_by_hubtype_metro(df)) == [2, 1, 1, 1, 1, 1]  # national: nationwide; ties share the min rank


@pytest.fixture
def scored():
    return pd.DataFrame(
        {
            "group": [10, 20],
            "x": [34.8, 35.0],
            "y": [32.1, 32.8],
            "h3_index": [["h1", "h2"], ["h3"]],
            "node": [[1, 2], [3]],
            "Mode_Planned": [["Metro", "LRT"], ["BRT", "LRT"]],
            "Line_Unique": [["M1-RA-RE", "Red-N"], ["b1", "Red-S"]],
            "Line_Nunique": [4, 2],
            "Total_Unique_Lines": [2, 2],
            "address": ["Not geocoded"] * 2,
            "area": ["תל אביב", "חיפה"],
            "location": [["גלעין"], ["טבעת פנימית"]],
            "Location_category": [3, 2],
            "Region_category": [0, 1],
            "RegionLocation": [0, 2],
            "TotalDemand": [1000.0, 0.0],
            "TotalTransfers": [500.0, 0.0],
            "BRT Lines": [0.0, 1.0],
            "Cable Line Lines": [0.0, 0.0],
            "Funicular Lines": [0.0, 0.0],
            "HighSpeed Rail Lines": [0.0, 0.0],
            "Interurban Rail Lines": [0.0, 0.0],
            "LRT Lines": [2.0, 1.0],
            "Metro Lines": [2.0, 0.0],
            "Suburban Rail Lines": [0.0, 0.0],
            "pop_0_500": [100.0, 10.0],
            "emp_0_500": [200.0, 20.0],
            "pop_500_1000": [100.0, 10.0],
            "emp_500_1000": [200.0, 20.0],
            "pop_1000_1500": [100.0, 10.0],
            "emp_1000_1500": [200.0, 20.0],
            "Num_Modes": [2, 2],
            "score": [26.4, 9.9],
            "bus_terminal": [3, 0],
            "HubType": ["מטרופוליני", "עירוני"],
            "RegionLocation_Norm": [5.5, 5.5],
            "score_Norm": [5.5, 5.5],
            "bus_terminal_Norm": [5.5, 5.5],
            "TotalDemand_Norm": [5.5, 1.0],
            "PopEmp_Score_Norm": [5.5, 5.5],
            "LogDemand": [3.0, 0.0],
            "PopEmp_Score_Raw": [1.0, 0.1],
            "Average_Simulated_Score": [5.5, 4.6],
            "Rank_within_HubType": [1.0, 1.0],
            "Overall_Rank": [1.0, 2.0],
        }
    )


def test_finalize_columns_end_to_end(scored):
    report = RunReport()
    out = finalize_columns(
        scored,
        line_names={"Red-N": 'אדום צפון (רק"ל)', "M1-KS-LOD": "x"},
        line_status={"Red-N": 0, "Red-S": 6, "M1-RA-RE": 5},
        line_corrections={"b1": "Red-S"},
        hub_names=pd.DataFrame({"h3_index": ["h2", "h3"], "HubNameHE": ["סבידור", "חיפה"]}),
        report=report,
    )
    first = out.iloc[0]
    assert first["group"] == 10 and first["Metro"] == "תל אביב" and first["LocationForChart"] == "גלעין"
    assert first["TransferRate"] == 0.5 and out.iloc[1]["TransferRate"] == 0.0
    assert first["TotalPop_2050"] == 300 and first["TotalEmp_2050"] == 600
    assert first["Modes_ForPlot"] == 'מטרו, רק"ל' and first["HubTypeHE"] == "מטרופוליני"
    assert first["HubType_Filtered"] == 0 and first["BusTERMINAL_Clone"] == 3 and first["TotalNumLines"] == 4
    assert first["PopEmp_Score"] == pytest.approx(0.2 * 300 + 0.8 * 600)
    assert first["TotalScore_MC"] == 5.5 and first["Rank_TS_MC"] == 1 and first["Average_Simulated_Score"] == 5.5
    assert first["Line_Names"] == str(["M1-RA-RE", 'אדום צפון (רק"ל)'])
    assert first["Line_Names_forPlot"] == 'M1-RA-RE, אדום צפון (רק"ל)'
    assert first["NumLinesStatus_0"] == 1 and first["NumLinesStatus_5"] == 1 and first["TotalLinesAllStatuses"] == 2
    second = out.iloc[1]
    assert second["NumLinesStatus_6"] == 2  # b1 corrected to Red-S, plus Red-S itself
    assert list(out["HubNameHE"]) == ["סבידור", "חיפה"]
    assert list(out["RankByHubTypeMetro"]) == [1, 1]
    assert any("no Hebrew name" in w.message for w in report.warnings)


def test_finalize_columns_global_renormalisation_flag(scored):
    out = finalize_columns(scored, renormalize_globally=True, report=RunReport())
    assert set(out["RegionLocation_Norm"]) == {1.0, 10.0}
    assert set(out["PopEmp_Score_Norm"]) == {1.0, 10.0}
