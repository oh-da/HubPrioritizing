"""Unit tests of the hub comparison (``src/compare/hubs.py``) on hand-built frames."""

from __future__ import annotations

from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import MultiPoint, Point

from src.compare.agency import HUB_COLUMNS, ROUTE_COLUMNS, STOP_COLUMNS, AgencyNetwork
from src.compare.hubs import (
    HUB_COMPARISON_COLUMNS,
    HUB_ROUTE_COLUMNS,
    build_our_hubs,
    match_hubs,
)
from src.compare.modes import load_mode_map
from src.compare.routes import PAIR_COLUMNS, ROUTE_COMPARISON_COLUMNS, RouteComparison
from src.compare.settings import CompareConfig
from src.pipeline.all_groups import ALL_GROUPS_COLUMNS, NETWORK_NODES_COLUMNS
from src.pipeline.report import RunReport

CRS_ITM = "EPSG:2039"
X0, Y0 = 200000.0, 600000.0
CFG = CompareConfig()


def _group(group: int, **kw: Any) -> dict[str, Any]:
    row = {c: None for c in ALL_GROUPS_COLUMNS}
    row.update(
        hub_id=f"H{group}", group=group, HubNameHE=f"מתחם {group}", x=35.0, y=32.0,
        x_itm=X0, y_itm=Y0, area="TA", Mode_Planned=["LRT", "BRT"], n_modes=2,
        Line_Unique=[], n_lines=0, TotalDemand=5000.0, TotalTransfers=100.0, eligible=True,
        exclusion_reason="", HubType="Metropolitan", TotalScore_MC=6.0, Rank_TS_MC=1.0,
        RankByHubTypeMetro=1.0,
    )
    row.update(kw)
    return row


def make_groups(*rows: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=list(ALL_GROUPS_COLUMNS))


def make_nodes(points: dict[int, list[tuple[float, float]]]) -> pd.DataFrame:
    """``group -> relative node positions`` as a ``network_nodes`` frame."""
    rows = []
    for group, coords in points.items():
        for i, (x, y) in enumerate(coords):
            rows.append({
                "node": f"g{group}n{i}", "LINE_ID": "L1", "line_name": "", "Mode_Planned": "LRT",
                "x_itm": X0 + x, "y_itm": Y0 + y, "group": group, "hub_id": f"H{group}",
            })
    return pd.DataFrame(rows, columns=list(NETWORK_NODES_COLUMNS))


def make_agency(hubs: dict[int, dict[str, Any]]) -> AgencyNetwork:
    """``agency_hub_id -> {"stops": [...], "modes": [...], "route_keys": [...]}``."""
    rows = []
    for hub_id, spec in hubs.items():
        modes = sorted(spec.get("modes", ["LRT"]))
        keys = sorted(spec.get("route_keys", []))
        rows.append({
            "agency_hub_id": hub_id, "name": f"hub {hub_id}", "modes": modes,
            "n_modes": len(modes), "rail_hub": spec.get("rail_hub", False),
            "agency_type": f"{len(modes)} modes", "route_keys": keys, "n_routes": len(keys),
            "geometry": MultiPoint([(X0 + x, Y0 + y) for x, y in spec["stops"]]),
        })
    frame = pd.DataFrame(rows, columns=HUB_COLUMNS)
    frame["agency_hub_id"] = frame["agency_hub_id"].astype("int64")
    empty_routes = gpd.GeoDataFrame(pd.DataFrame(columns=ROUTE_COLUMNS), geometry="geometry",
                                    crs=CRS_ITM)
    empty_stops = gpd.GeoDataFrame(pd.DataFrame(columns=STOP_COLUMNS), geometry="geometry",
                                   crs=CRS_ITM)
    return AgencyNetwork(
        routes=empty_routes, stops=empty_stops,
        hubs=gpd.GeoDataFrame(frame, geometry="geometry", crs=CRS_ITM),
    )


def make_routes(pairs: list[dict[str, Any]] | None = None,
                routes: list[dict[str, Any]] | None = None) -> RouteComparison:
    return RouteComparison(
        pairs=pd.DataFrame(pairs or [], columns=PAIR_COLUMNS),
        routes=pd.DataFrame(routes or [], columns=ROUTE_COMPARISON_COLUMNS),
    )


def run(groups: pd.DataFrame, nodes: pd.DataFrame, agency: AgencyNetwork,
        routes: RouteComparison | None = None, line_map: dict[str, str] | None = None,
        tod: gpd.GeoDataFrame | None = None, report: RunReport | None = None):
    ours = build_our_hubs(groups, nodes, load_mode_map(), line_map or {})
    return match_hubs(ours, agency, routes or make_routes(), CFG, tod=tod, report=report)


def rows_of(result, relation: str) -> pd.DataFrame:
    return result.hubs[result.hubs["relation"] == relation].reset_index(drop=True)


# ----------------------------------------------------------------------------------------


def test_one_to_one():
    report = RunReport()
    res = run(make_groups(_group(10)), make_nodes({10: [(100, 0)]}),
              make_agency({1: {"stops": [(0, 0)]}}), report=report)
    assert list(res.hubs.columns) == HUB_COMPARISON_COLUMNS
    assert len(res.hubs) == 1
    row = res.hubs.iloc[0]
    assert row["relation"] == "1:1"
    assert row["agency_hub_id"] == 1 and row["group"] == 10
    assert row["distance_m"] == pytest.approx(100.0)
    assert report.metrics["hubs_1:1"] == 1
    assert any(e.section == "hubs" for e in report.entries)


def test_agency_splits():
    res = run(make_groups(_group(10), _group(11)),
              make_nodes({10: [(300, 0)], 11: [(-300, 0)]}),
              make_agency({1: {"stops": [(0, 0)]}}))
    assert list(res.hubs["relation"]) == ["agency_splits", "agency_splits"]
    assert list(res.hubs["group"]) == [10, 11]


def test_ours_merges():
    res = run(make_groups(_group(10)), make_nodes({10: [(200, 0), (400, 0)]}),
              make_agency({1: {"stops": [(0, 0)]}, 2: {"stops": [(600, 0)]}}))
    assert list(res.hubs["relation"]) == ["ours_merges", "ours_merges"]
    assert list(res.hubs["agency_hub_id"]) == [1, 2]


def test_many_to_many():
    res = run(make_groups(_group(10), _group(11)),
              make_nodes({10: [(300, 0), (650, 0)], 11: [(700, 0)]}),
              make_agency({1: {"stops": [(0, 0)]}, 2: {"stops": [(1000, 0)]}}))
    assert set(res.hubs["relation"]) == {"many_to_many"}
    pairs = list(zip(res.hubs["agency_hub_id"], res.hubs["group"]))
    assert pairs == [(1, 10), (2, 10), (2, 11)]


def test_pair_distance_is_nearest_point_not_centroid():
    # Agency hub 700 m wide (centroid at 350), group whose centroid is 800 m away but whose
    # nearest node is 100 m from the agency's nearest stop.
    res = run(make_groups(_group(10)), make_nodes({10: [(800, 0), (1500, 0)]}),
              make_agency({1: {"stops": [(0, 0), (700, 0)]}}))
    assert list(res.hubs["relation"]) == ["1:1"]
    assert res.hubs["distance_m"].iloc[0] == pytest.approx(100.0)


def test_agency_only_reports_nearest_group_and_exclusion_reason():
    groups = make_groups(
        _group(10, eligible=False, exclusion_reason="demand < min"), _group(11),
    )
    res = run(groups, make_nodes({10: [(1000, 0)], 11: [(2000, 0)]}),
              make_agency({1: {"stops": [(0, 0)]}}))
    row = rows_of(res, "agency_only").iloc[0]
    assert row["agency_hub_id"] == 1
    assert row["group"] == 10
    assert row["distance_m"] == pytest.approx(1000.0)
    assert not bool(row["eligible"])
    assert row["exclusion_reason"] == "demand < min"


def test_ours_only_split_by_eligible():
    groups = make_groups(
        _group(10), _group(11, eligible=False, exclusion_reason="single mode",
                           TotalScore_MC=np.nan),
    )
    res = run(groups, make_nodes({10: [(5000, 0)], 11: [(6000, 0)]}),
              make_agency({1: {"stops": [(0, 0)]}}))
    ours = rows_of(res, "ours_only")
    assert list(ours["group"]) == [10, 11]
    assert [bool(v) for v in ours["eligible"]] == [True, False]
    assert ours["agency_hub_id"].isna().all()


def test_routes_shared_only_agency_only_ours():
    groups = make_groups(_group(10, Line_Unique=["L1", "L2", "L3"], n_lines=3))
    line_map = {"L1": "L1+L2", "L2": "L1+L2", "L3": "L3"}
    routes = make_routes(
        pairs=[
            {"our_route_key": "L1+L2", "agency_route_key": "LRT:1", "score": 0.9,
             "same_mode": True, "cov_ours": 0.9, "cov_agency": 0.9},
            {"our_route_key": "L3", "agency_route_key": "BRT:2", "score": 0.3,
             "same_mode": True, "cov_ours": 0.3, "cov_agency": 0.3},
        ],
        routes=[
            {"status": "matched", "our_route_key": "L1+L2", "agency_route_key": "LRT:1"},
            {"status": "ours_only", "our_route_key": "L3", "agency_route_key": None},
            {"status": "agency_only", "our_route_key": None, "agency_route_key": "BRT:2"},
        ],
    )
    res = run(groups, make_nodes({10: [(50, 0)]}),
              make_agency({1: {"stops": [(0, 0)], "route_keys": ["LRT:1", "BRT:2"]}}),
              routes=routes, line_map=line_map)
    row = res.hubs.iloc[0]
    assert row["routes_shared"] == "LRT:1=L1+L2"
    assert row["routes_only_agency"] == "BRT:2"
    assert row["routes_only_ours"] == "L3"
    hr = res.hub_routes
    assert list(hr.columns) == HUB_ROUTE_COLUMNS
    got = {(s, o, a, st) for s, o, a, st in
           zip(hr["side"], hr["our_route_key"], hr["agency_route_key"], hr["route_status"])}
    assert got == {
        ("shared", "L1+L2", "LRT:1", "matched"),
        ("only_agency", None, "BRT:2", "agency_only"),
        ("only_ours", "L3", None, "ours_only"),
    }
    assert set(hr["agency_hub_id"]) == {1} and set(hr["group"]) == {10}


def test_modes_difference_columns():
    groups = make_groups(_group(10, Mode_Planned=["Light Rail", "Metro"]))
    res = run(groups, make_nodes({10: [(50, 0)]}),
              make_agency({1: {"stops": [(0, 0)], "modes": ["LRT", "Rail", "BRT"]}}))
    row = res.hubs.iloc[0]
    assert row["modes_shared"] == "LRT"
    assert row["modes_only_agency"] == "BRT;Rail"
    assert row["modes_only_ours"] == "Metro"
    assert row["n_modes_diff"] == 1


def test_agency_demand_column_is_empty():
    res = run(make_groups(_group(10)), make_nodes({10: [(100, 0)]}),
              make_agency({1: {"stops": [(0, 0)]}, 2: {"stops": [(9000, 0)]}}))
    assert "agency_total_demand" in res.hubs.columns
    assert res.hubs["agency_total_demand"].isna().all()


def test_tod_type_sum_and_disagreement_flag():
    agency = make_agency({
        1: {"stops": [(0, 0)], "modes": ["LRT", "Rail", "BRT"]},
        2: {"stops": [(5000, 0)], "modes": ["LRT", "BRT"]},
        3: {"stops": [(10000, 0)], "modes": ["LRT", "BRT"]},
    })
    tod = gpd.GeoDataFrame(
        pd.DataFrame({"tod_hub_id": pd.array([7, 8, 9], dtype="Int64"),
                      "n_modes": pd.array([2, 2, 2], dtype="Int64"),
                      "type_sum": pd.array([2, 2, 2], dtype="Int64")}),
        geometry=[Point(X0 + 50, Y0), Point(X0 + 5100, Y0), Point(X0 + 10300, Y0)],
        crs=CRS_ITM,
    )
    res = run(make_groups(), make_nodes({}), agency, tod=tod)
    by_hub = res.hubs.set_index("agency_hub_id")
    assert by_hub.loc[1, "tod_type_sum"] == 2 and bool(by_hub.loc[1, "tod_disagrees"])
    assert by_hub.loc[2, "tod_type_sum"] == 2 and not bool(by_hub.loc[2, "tod_disagrees"])
    assert pd.isna(by_hub.loc[3, "tod_type_sum"]) and pd.isna(by_hub.loc[3, "tod_disagrees"])


def test_no_eligible_hubs_and_no_agency_hubs():
    ours = build_our_hubs(make_groups(), make_nodes({}), load_mode_map(), {})
    assert {"common_modes", "route_keys", "geometry"} <= set(ours.columns)
    res = match_hubs(ours, make_agency({}), make_routes(), CFG)
    assert list(res.hubs.columns) == HUB_COMPARISON_COLUMNS and res.hubs.empty
    assert list(res.hub_routes.columns) == HUB_ROUTE_COLUMNS and res.hub_routes.empty

    only_agency = run(make_groups(), make_nodes({}), make_agency({1: {"stops": [(0, 0)]}}))
    assert list(only_agency.hubs["relation"]) == ["agency_only"]
    assert only_agency.hubs["group"].isna().all()

    only_ours = run(make_groups(_group(10, eligible=False)), make_nodes({10: [(0, 0)]}),
                    make_agency({}))
    assert list(only_ours.hubs["relation"]) == ["ours_only"]


def test_group_without_nodes():
    groups = make_groups(_group(10, Mode_Planned="LRT;BRT", Line_Unique="L1;L2"), _group(11))
    ours = build_our_hubs(groups, make_nodes({11: [(0, 0)]}), load_mode_map(),
                          {"L1": "L1", "L2": "L2"})
    by_group = ours.set_index("group")
    assert by_group.loc[10, "geometry"].is_empty
    assert by_group.loc[10, "common_modes"] == ["BRT", "LRT"]
    assert by_group.loc[10, "route_keys"] == ["L1", "L2"]
    res = match_hubs(ours, make_agency({1: {"stops": [(0, 0)]}}), make_routes(), CFG)
    row = res.hubs[res.hubs["group"] == 10].iloc[0]
    assert row["relation"] == "ours_only"
    assert pd.isna(row["distance_m"])
    assert rows_of(res, "1:1")["group"].tolist() == [11]
