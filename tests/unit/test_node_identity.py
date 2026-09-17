"""Node identity: one position per node, the demand model behind every node, and the
optional ``model`` column of the manual tables."""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from src.config import CRS_ISRAEL_TM
from src.pipeline.demand import MODELS_COL, NODE_MODELS_COL, apply_manual_demand, assign_demand, hex_accepts_model
from src.pipeline.grouping import apply_manual_groups, hub_identity_table, parse_manual_group_rows, parse_manual_groups
from src.pipeline.network import apply_node_position_overrides, check_node_positions, load_nodeslines, node_position_table
from src.pipeline.report import RunReport


# ---------------------------------------------------------------------------- positions
def _nodes(rows):
    df = pd.DataFrame(rows, columns=["node", "LINE_ID", "X", "Y"])
    return load_nodeslines(df)


@pytest.fixture
def messy_nodes():
    return _nodes(
        [
            (1, "a", 180000, 665000), (1, "b", 180000, 665000), (1, "c", 180040, 665030),  # 50 m apart: snap to (180000, 665000)
            (2, "d", 182000, 665000), (2, "e", 184500, 665000),  # 2.5 km apart: conflict
            (3, "f", 190000, 665000), (3, "g", 190000, 665000),  # consistent
        ]
    )


def test_node_position_table_lists_only_disagreeing_nodes(messy_nodes):
    t = node_position_table(messy_nodes)
    assert list(t["node"]) == [1, 2]
    one = t.set_index("node").loc[1]
    assert one["n_positions"] == 2 and one["spread_m"] == 50.0
    assert one["positions"][0]["rows"] == 2 and one["positions"][0]["lines"] == ["a", "b"]
    assert t.set_index("node").loc[2, "spread_m"] == 2500.0


def test_check_snaps_small_spreads_and_reports_large_ones(messy_nodes):
    report = RunReport()
    out, problems = check_node_positions(messy_nodes, tolerance_m=150, on_conflict="warn", report=report)
    assert len(out) == len(messy_nodes)  # no row is dropped
    node1 = out[out["node"] == 1]
    assert (node1.geometry.x == 180000).all() and (node1.geometry.y == 665000).all()
    node2 = out[out["node"] == 2]
    assert set(node2.geometry.x) == {182000, 184500}  # untouched
    assert len(problems) == 1 and "node 2" in problems[0] and "2500 m" in problems[0]
    assert report.metrics["nodes_snapped"] == 1 and report.metrics["node_position_conflicts"] == 1
    msgs = " | ".join(w.message for w in report.warnings)
    assert "node 1" in msgs and "snapped" in msgs and "node 2" in msgs
    with pytest.raises(ValueError):
        check_node_positions(messy_nodes, on_conflict="ignore")


def test_overrides_resolve_a_conflict(messy_nodes):
    overrides = pd.DataFrame({"node": [2, 99], "X": [182000, 1], "Y": [665000, 1], "notes": ["LRT row was wrong", "unknown"]})
    report = RunReport()
    fixed = apply_node_position_overrides(messy_nodes, overrides, report)
    node2 = fixed[fixed["node"] == 2]
    assert (node2.geometry.x == 182000).all() and len(node2) == 2
    assert any("node 99 not found" in w.message for w in report.warnings)
    assert report.metrics["node_position_overrides_applied"] == 1
    _, problems = check_node_positions(fixed, tolerance_m=150)
    assert problems == []
    with pytest.raises(ValueError):
        apply_node_position_overrides(messy_nodes, pd.DataFrame({"node": [2]}))


# ---------------------------------------------------------------------------- demand models
@pytest.fixture
def hexes():
    return pd.DataFrame(
        {
            "h3_index": ["h1", "h2", "h3"],
            "node": [[10, 11], [20], [30]],
            "area": ["תל אביב", "מחוז דרום", "חיפה"],
            "group": [0, 1, 2],
        }
    )


@pytest.fixture
def by_region():
    mk = lambda rows: pd.DataFrame(rows, columns=["node", "demand", "transfers"])
    return {
        "Tel Aviv": mk([(10, 100.0, 5.0), (11, 50.0, 0.0), (20, 999.0, 0.0)]),
        "Beer Sheva": mk([(20, 300.0, 10.0)]),
        "Ashdod-Ashkelon": mk([(20, 700.0, 0.0)]),  # same id, different value: collision
        "Haifa": mk([(30, 40.0, 0.0)]),
        "Hadera": mk([(30, 60.0, 1.0)]),  # overlay overrides Haifa
    }


def test_assign_demand_records_models_and_collisions(hexes, by_region):
    report = RunReport()
    out = assign_demand(hexes, by_region, ("Hadera", "Haifa Metronit"), report)
    assert list(out["TotalDemand"]) == [150.0, 300.0, 60.0]
    assert out[NODE_MODELS_COL].tolist() == [{10: "Tel Aviv", 11: "Tel Aviv"}, {20: "Beer Sheva"}, {30: "Hadera"}]
    assert out[MODELS_COL].tolist() == [["Tel Aviv"], ["Beer Sheva"], ["Hadera"]]
    assert report.metrics["demand_nodes_by_model"] == {"Beer Sheva": 1, "Hadera": 1, "Tel Aviv": 2}
    assert report.metrics["demand_node_id_collisions"] == 1
    coll = [w for w in report.warnings if "collision" in w.message]
    assert len(coll) == 1 and "node 20" in coll[0].message and coll[0].data["demand_by_model"] == {"Beer Sheva": 300, "Ashdod-Ashkelon": 700}


def test_hex_accepts_model():
    assert hex_accepts_model("חיפה", {30: "Hadera"}, 30, None)
    assert hex_accepts_model("חיפה", {30: "Hadera"}, 30, "Hadera")  # the model that supplied it
    assert hex_accepts_model("חיפה", {30: "Hadera"}, 30, "Haifa")  # a candidate model of the location
    assert not hex_accepts_model("חיפה", {30: "Hadera"}, 30, "Tel Aviv")
    assert hex_accepts_model("מחוז דרום", None, 20, "Ashdod-Ashkelon")


def test_manual_demand_model_column(hexes, by_region):
    out = assign_demand(hexes, by_region, ("Hadera",))
    updates = pd.DataFrame(
        {
            "node": [20, 20, 10],
            "total_demand": [1.0, 2.0, 3.0],
            "total_transfers": ["", "", ""],
            "model": ["Tel Aviv", "Beer Sheva", None],  # 20 is not a Tel Aviv node here; blank = any
            "station_name": ["x", "y", "z"],
        }
    )
    report = RunReport()
    res = apply_manual_demand(out, updates, report)
    assert list(res["TotalDemand"]) == [3.0, 2.0, 60.0]
    skipped = [w for w in report.warnings if "not in model" in w.message]
    assert len(skipped) == 1 and "Tel Aviv" in skipped[0].message
    assert report.metrics["manual_demand_rows_applied"] == 2


def test_hub_identity_table_carries_demand_models(hexes, by_region):
    out = assign_demand(hexes, by_region, ("Hadera",))
    out = gpd.GeoDataFrame(out, geometry=[Point(0, 0)] * 3, crs=CRS_ISRAEL_TM)
    table = hub_identity_table(out)
    assert list(table["demand_models"]) == ["Tel Aviv", "Beer Sheva", "Hadera"]
    assert "demand_models" not in hub_identity_table(out.drop(columns=[MODELS_COL])).columns


# ---------------------------------------------------------------------------- manual groups
def test_parse_manual_group_rows_with_model():
    df = pd.DataFrame({"Nodes in group": ["1, 2", "3; 4", "5"], "model": ["Tel Aviv", None, "x"]})
    assert parse_manual_group_rows(df) == [([1, 2], "Tel Aviv"), ([3, 4], None)]
    assert parse_manual_groups(df) == [[1, 2], [3, 4]]
    assert parse_manual_group_rows(pd.DataFrame({"Nodes in group": ["1,2"]})) == [([1, 2], None)]


def test_manual_group_restricted_to_model():
    hexes = gpd.GeoDataFrame(
        {
            "h3_index": ["a", "b", "c"],
            "node": [[1], [2], [2]],  # node 2 exists in Tel Aviv and in Beer Sheva
            "area": ["תל אביב", "תל אביב", "באר שבע"],
            "group": [0, 1, 2],
        },
        geometry=[Point(0, 0), Point(1, 1), Point(2, 2)],
        crs=CRS_ISRAEL_TM,
    )
    merged = apply_manual_groups(hexes, pd.DataFrame({"Nodes in group": ["1, 2"], "model": ["Tel Aviv"]}), renumber=False)
    assert merged["group"].tolist() == [0, 0, 2]  # the Beer Sheva copy of node 2 is left alone
    report = RunReport()
    both = apply_manual_groups(hexes, pd.DataFrame({"Nodes in group": ["1, 2"]}), report, renumber=False)
    assert both["group"].tolist() == [0, 0, 0]  # no model: every hexagon holding node 2 is merged
    report = RunReport()
    none = apply_manual_groups(hexes, pd.DataFrame({"Nodes in group": ["1, 2"], "model": ["Haifa"]}), report, renumber=False)
    assert none["group"].tolist() == [0, 1, 2]
    assert any("not in model 'Haifa'" in w.message for w in report.warnings)
