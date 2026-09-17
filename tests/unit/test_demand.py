import pandas as pd
import pytest

from src.pipeline.demand import (
    apply_manual_demand,
    assign_demand,
    load_demand_workbook,
    process_sheet,
    region_for_sheet,
)
from src.pipeline.report import RunReport


@pytest.fixture
def sheets():
    return {
        "Daily_5087": pd.DataFrame(
            {"Node": [1, 1, 2, "x"], "TotalBoardings": [10, 5, 7, 1], "TotalAlight": [4, 1, 3, 1], "TransferBoardings": [2, 1, 0, 0], "TransferAlight": [1, 0, 0, 0]}
        ),
        "Daily_Hadera": pd.DataFrame({"NodeID": [2], "On": [100], "Off": [50]}),
        "Daily_BS": pd.DataFrame({"NODE_ID": [3], "Boardings_Daily": [30], "Alightings_Daily": [20]}),
        "Params": pd.DataFrame({"TLV": ["am"], "ini": [1]}),
    }


def test_region_for_sheet_is_case_insensitive():
    assert region_for_sheet("Daily_5087") == "Tel Aviv"
    assert region_for_sheet("daily_bs") == "Beer Sheva"
    assert region_for_sheet("Whatever") is None


def test_process_sheet_sums_per_node_and_skips_bad_ids(sheets):
    out = process_sheet(sheets["Daily_5087"], "Tel Aviv").set_index("node")
    assert out.loc[1, "demand"] == 20 and out.loc[1, "transfers"] == 4
    assert out.loc[2, "demand"] == 10 and out.loc[2, "transfers"] == 0
    assert "x" not in out.index and len(out) == 2


def test_load_demand_workbook_ignores_unknown_sheets(sheets):
    report = RunReport()
    by_region = load_demand_workbook(sheets, report)
    assert set(by_region) == {"Tel Aviv", "Hadera", "Beer Sheva"}
    assert any("Params" in e.message for e in report.entries)


def test_assign_demand_uses_area_models_and_overlay_override(sheets):
    by_region = load_demand_workbook(sheets)
    hexes = pd.DataFrame({"node": [[1, 2], [3], [9]], "area": ["תל אביב", "מחוז דרום", "תל אביב"]})
    report = RunReport()
    out = assign_demand(hexes, by_region, ("Hadera", "Haifa Metronit"), report)
    # node 1 from Tel Aviv (20); node 2 is in the Hadera overlay -> 150 replaces the Tel Aviv value (10)
    assert out.loc[0, "TotalDemand"] == 170 and out.loc[0, "TotalTransfers"] == 4
    # south district: Beer Sheva model first
    assert out.loc[1, "TotalDemand"] == 50
    assert out.loc[2, "TotalDemand"] == 0
    assert report.metrics["demand_nodes_matched"] == 3
    assert any("no demand" in w.message for w in report.warnings)


def test_apply_manual_demand_overrides_and_keeps_transfers_when_blank():
    hexes = pd.DataFrame({"node": [[400424], [511248, 7], [1]], "TotalDemand": [1.0, 2.0, 3.0], "TotalTransfers": [0.5, 9.0, 0.0]})
    updates = pd.DataFrame(
        {"node": [400424, 511248, 12345], "total_demand": [64985, 255.3, 1], "total_transfers": [43032, None, 1], "station_name": ["a", "b", "c"]}
    )
    report = RunReport()
    out = apply_manual_demand(hexes, updates, report)
    assert out.loc[0, "TotalDemand"] == 64985 and out.loc[0, "TotalTransfers"] == 43032
    assert out.loc[1, "TotalDemand"] == 255.3 and out.loc[1, "TotalTransfers"] == 9.0
    assert out.loc[2, "TotalDemand"] == 3.0
    assert report.metrics["manual_demand_rows_applied"] == 2
    assert any("12345" in w.message for w in report.warnings)
