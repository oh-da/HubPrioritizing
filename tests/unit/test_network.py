import geopandas as gpd
import pandas as pd
import pytest

from src.pipeline.network import (
    add_mode_line_columns,
    aggregate_to_hexes,
    attach_modes,
    clean_lines_mode,
    load_nodeslines,
)
from src.pipeline.report import RunReport
from src.pipeline.settings import LineDropRule


@pytest.fixture
def nodeslines_df():
    # two nodes ~20 m apart (same res-10 hex is not guaranteed, so use identical coords for node 2/3)
    return pd.DataFrame(
        {
            "עמודה1": [0, 1, 2, 3, 4, 5],
            "node": [1, 1, 2, 2, 3, 3],
            "LINE_ID": ["L1", " L2", "L1", "M1", "B1", "X9"],
            "X": [180000, 180000, 180000, 180000, 183000, 183000],
            "Y": [665000, 665000, 665000, 665000, 665000, 665000],
        }
    )


@pytest.fixture
def lines_mode_df():
    return pd.DataFrame(
        {
            "Line_ModelName": ["L1", "L2", "M1", "B1", "m0810a", "m0810a", "LRT151"],
            "Mode_Planned": ["LRT", "LRT", "Metro", "BRT", "BRT", "BRT", "LRT"],
            "Area": ["Tel Aviv", "Tel Aviv", "Tel Aviv", "Haifa", "Haifa", "Haifa", "Netanya"],
        }
    )


def test_load_nodeslines_from_xy_and_wkt(nodeslines_df):
    gdf = load_nodeslines(nodeslines_df)
    assert gdf.crs.to_epsg() == 2039 and len(gdf) == 6
    assert "עמודה1" not in gdf.columns
    assert gdf.loc[1, "LINE_ID"] == "L2"  # stripped

    wkt_df = nodeslines_df.drop(columns=["X", "Y"]).assign(geometry="POINT (180000 665000)")
    assert len(load_nodeslines(wkt_df)) == 6


def test_clean_lines_mode_dedupes_with_warning(lines_mode_df):
    report = RunReport()
    lm = clean_lines_mode(lines_mode_df, report)
    assert lm["Line_ModelName"].is_unique
    assert report.warnings[0].data["lines"] == ["m0810a"]


def test_attach_modes_applies_rules_and_reports_unmatched(nodeslines_df, lines_mode_df):
    report = RunReport()
    nodes = load_nodeslines(nodeslines_df)
    rules = [LineDropRule("^m", "Haifa"), LineDropRule("^LRT15[12]$", "Netanya")]
    merged = attach_modes(nodes, lines_mode_df, rules, report)
    assert set(merged["LINE_ID"]) == {"L1", "L2", "M1", "B1"}  # X9 has no mode row -> dropped
    unmatched = [w for w in report.warnings if "no row" in w.message][0]
    assert unmatched.data["lines"] == ["X9"]
    assert list(merged["Mode_Planned"]).count("LRT") == 3


def test_aggregate_to_hexes_counts_lines_per_node_then_sums(nodeslines_df, lines_mode_df):
    nodes = attach_modes(load_nodeslines(nodeslines_df), lines_mode_df)
    hexes = aggregate_to_hexes(nodes, resolution=10)
    assert hexes.crs.to_epsg() == 4326 and len(hexes) == 2

    big = hexes[hexes["node"].map(lambda ns: 1 in ns)].iloc[0]
    assert big["node"] == [1, 2]
    assert big["Mode_Planned"] == ["LRT", "Metro"]  # first appearance order
    assert big["Line_Unique"] == ["L1", "L2", "M1"]  # sorted, deduplicated
    # L1 serves nodes 1 and 2 in the same hex -> counted twice (notebook fidelity)
    assert big["Line_Nunique"] == 4
    assert big["Lines_by_Mode"] == {"LRT": 3, "Metro": 1}


def test_add_mode_line_columns_even_and_exact(nodeslines_df, lines_mode_df):
    nodes = attach_modes(load_nodeslines(nodeslines_df), lines_mode_df)
    hexes = aggregate_to_hexes(nodes)
    big_idx = hexes.index[hexes["node"].map(lambda ns: 1 in ns)][0]

    even = add_mode_line_columns(hexes, "even")
    assert even.loc[big_idx, "LRT Lines"] == 2.0 and even.loc[big_idx, "Metro Lines"] == 2.0
    assert even.loc[big_idx, "BRT Lines"] == 0.0

    exact = add_mode_line_columns(hexes, "exact")
    assert exact.loc[big_idx, "LRT Lines"] == 3.0 and exact.loc[big_idx, "Metro Lines"] == 1.0

    with pytest.raises(ValueError):
        add_mode_line_columns(hexes, "random")


def test_bus_modes_are_excluded_from_mode_lines():
    hexes = gpd.GeoDataFrame(
        {"h3_index": ["x"], "node": [[1]], "Mode_Planned": [["Bus", "BRT"]], "Line_Nunique": [4], "Lines_by_Mode": [{"Bus": 3, "BRT": 1}]},
        geometry=gpd.points_from_xy([34.8], [32.1]),
        crs="EPSG:4326",
    )
    even = add_mode_line_columns(hexes, "even")
    assert even.loc[0, "BRT Lines"] == 4.0  # all lines attributed to the only valid mode
