"""Unit tests of the comparison writers (``src/compare/export.py``) on hand-built inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import openpyxl
import pandas as pd
import pytest
from shapely.geometry import MultiPoint, Point

from src.compare.agency import HUB_COLUMNS, AgencyNetwork
from src.compare.export import build_layers, build_sheets, write_gpkg, write_workbook
from src.compare.hubs import (
    HUB_COMPARISON_COLUMNS,
    HUB_ROUTE_COLUMNS,
    HubComparison,
    build_our_hubs,
    match_hubs,
)
from src.compare.modes import load_mode_map
from src.compare.routes import (
    PAIR_COLUMNS,
    ROUTE_COMPARISON_COLUMNS,
    RouteComparison,
    build_our_routes,
    line_route_map,
    match_routes,
)
from src.compare.settings import CompareConfig
from src.pipeline.all_groups import ALL_GROUPS_COLUMNS
from tests.compare_helpers import (
    CRS_ITM,
    X0,
    Y0,
    make_agency_network,
    make_network_nodes,
    pts,
)

CFG = CompareConfig()
SHEETS = [
    "summary", "routes", "routes_only_ours", "routes_only_agency", "mode_summary", "hubs",
    "hubs_agency_only", "hubs_ours_only", "hub_routes", "settings", "inputs",
]
INPUTS = {
    "agency_gpkg": {"file": "MT_Network.gpkg", "sha256": "ab" * 32, "rows": 2},
    "run": {"version": "28-10", "dir": "/runs/28-10"},
}


def _scenario() -> dict[str, Any]:
    """One matched LRT route, one single-node LRT route, one Cable Line route; two agency hubs.

    * L1 (LRT, raw positions 10 m north of the corrected ones) runs over ``LRT:1`` -> matched
    * L5 (LRT, one node far away)                                       -> ours_only
    * L9 (Cable Line, no agency mode)                                   -> ours_only
    * ``LRT:2`` far away has no route of ours                           -> agency_only
    * agency hub 1 is 50 m from group 1 (1:1); hub 2 (8 km south of nothing) has no partner and
      its nearest group is group 1
    """
    coords = pts(0, 2000, 250)
    nodes = make_network_nodes({
        "L1": {"mode": "LRT", "coords": [(x, y + 10) for x, y in coords], "corr": coords,
               "name": "קו אחד"},
        "L5": {"mode": "LRT", "coords": [(0, 20010)], "corr": [(0, 20000)], "name": "קו חמש"},
        "L9": {"mode": "Cable Line", "coords": pts(0, 500, 250, y=-7990),
               "corr": pts(0, 500, 250, y=-8000), "name": "רכבל"},
    })
    nodes["group"] = nodes["LINE_ID"].map({"L1": 1, "L9": 2, "L5": 3})
    mode_map = load_mode_map()
    ours = build_our_routes(nodes, mode_map)
    agency = make_agency_network({
        "LRT:1": {"coords": coords, "stops": coords},
        "LRT:2": {"coords": pts(0, 1000, 250, y=8000), "stops": pts(0, 1000, 500, y=8000)},
    })
    agency.hubs = gpd.GeoDataFrame(
        pd.DataFrame([
            {"agency_hub_id": 1, "name": "תחנה מרכזית", "modes": ["LRT"], "n_modes": 1,
             "rail_hub": False, "agency_type": "1 mode: LRT", "route_keys": ["LRT:1"],
             "n_routes": 1, "geometry": MultiPoint([(X0, Y0 + 50), (X0 + 250, Y0 + 50)])},
            {"agency_hub_id": 2, "name": "hub two", "modes": ["LRT", "BRT"], "n_modes": 2,
             "rail_hub": True, "agency_type": "2 modes, rail hub: BRT+LRT",
             "route_keys": ["LRT:2"], "n_routes": 1,
             "geometry": MultiPoint([(X0, Y0 + 8000)])},
        ], columns=HUB_COLUMNS),
        geometry="geometry", crs=CRS_ITM,
    )
    routes = match_routes(ours, agency, CFG)
    groups = pd.DataFrame([
        _group(1, ["LRT"], ["L1"]), _group(2, ["Cable Line"], ["L9"]),
        _group(3, ["LRT"], ["L5"], eligible=False, exclusion_reason="single mode"),
    ], columns=list(ALL_GROUPS_COLUMNS))
    our_hubs = build_our_hubs(groups, nodes, mode_map, line_route_map(ours))
    hubs = match_hubs(our_hubs, agency, routes, CFG)
    return {"ours": ours, "agency": agency, "routes": routes, "our_hubs": our_hubs, "hubs": hubs}


def _group(group: int, modes: list[str], lines: list[str], **kw: Any) -> dict[str, Any]:
    row = {c: None for c in ALL_GROUPS_COLUMNS}
    row.update(
        hub_id=f"H{group}", group=group, HubNameHE=f"מתחם {group}", x_itm=X0, y_itm=Y0,
        area="TA", Mode_Planned=modes, n_modes=len(modes), Line_Unique=lines,
        n_lines=len(lines), TotalDemand=5000.0, TotalTransfers=100.0, eligible=True,
        exclusion_reason="", HubType="Metropolitan", TotalScore_MC=6.0, RankByHubTypeMetro=1.0,
    )
    row.update(kw)
    return row


def _empty() -> dict[str, Any]:
    agency = make_agency_network({})
    agency.hubs = gpd.GeoDataFrame(
        pd.DataFrame(columns=HUB_COLUMNS), geometry="geometry", crs=CRS_ITM
    )
    ours = build_our_routes(pd.DataFrame(), load_mode_map())
    return {
        "ours": ours, "agency": agency,
        "routes": RouteComparison(pd.DataFrame(columns=PAIR_COLUMNS),
                                  pd.DataFrame(columns=ROUTE_COMPARISON_COLUMNS)),
        "hubs": HubComparison(pd.DataFrame(columns=HUB_COMPARISON_COLUMNS),
                              pd.DataFrame(columns=HUB_ROUTE_COLUMNS)),
        "our_hubs": gpd.GeoDataFrame(
            pd.DataFrame(columns=list(ALL_GROUPS_COLUMNS) + ["common_modes", "route_keys"]),
            geometry=gpd.GeoSeries([], crs=CRS_ITM), crs=CRS_ITM),
    }


def _sheets(s: dict[str, Any]) -> dict[str, pd.DataFrame]:
    return build_sheets(s["routes"], s["hubs"], s["agency"], CFG, INPUTS)


def _layers(s: dict[str, Any]) -> dict[str, gpd.GeoDataFrame]:
    return build_layers(s["routes"], s["ours"], s["hubs"], s["agency"], s["our_hubs"])


@pytest.fixture(scope="module")
def scenario() -> dict[str, Any]:
    return _scenario()


def test_sheet_names_and_order(scenario):
    sheets = _sheets(scenario)
    assert list(sheets) == SHEETS
    assert all(len(name) <= 31 for name in sheets)
    routes = sheets["routes"]
    # the best pair's distance statistics are on the routes sheet (corrected < raw here)
    matched = routes[routes["status"] == "matched"].iloc[0]
    assert matched["median_dist_corr_m"] == pytest.approx(0.0, abs=1e-6)
    assert matched["median_dist_raw_m"] == pytest.approx(10.0)
    assert matched["max_dist_corr_m"] == pytest.approx(0.0, abs=1e-6)
    assert routes[routes["status"] == "agency_only"]["median_dist_corr_m"].isna().all()
    assert sheets["routes_only_ours"]["status"].eq("ours_only").all()
    assert len(sheets["routes_only_ours"]) == 2
    assert sheets["routes_only_agency"]["agency_route_key"].tolist() == ["LRT:2"]
    assert sheets["settings"].set_index("key")["value"]["hub_match_tol_m"] == 400.0
    assert sheets["inputs"].set_index("input").loc["agency_gpkg", "file"] == "MT_Network.gpkg"


def test_mode_summary_counts(scenario):
    ms = _sheets(scenario)["mode_summary"].set_index(["side", "mode"])
    status_cols = ["matched", "split_merge", "partial", "weak", "mode_differs", "ours_only",
                   "agency_only", "other"]
    # our side groups by our mode: LRT (matched + single-node ours_only) and the unmapped Cable Line
    assert ms.loc[("ours", "LRT"), "n_routes"] == 2
    assert ms.loc[("ours", "LRT"), "matched"] == 1
    assert ms.loc[("ours", "LRT"), "ours_only"] == 1
    assert ms.loc[("ours", "Cable Line"), "n_routes"] == 1
    assert ms.loc[("ours", "Cable Line"), "ours_only"] == 1
    # the agency side groups by the agency route type (LRT:1 matched, LRT:2 agency_only)
    assert ms.loc[("agency", "LRT"), "n_routes"] == 2
    assert ms.loc[("agency", "LRT"), "matched"] == 1
    assert ms.loc[("agency", "LRT"), "agency_only"] == 1
    assert ("agency", "Cable Line") not in ms.index
    for _, row in ms.iterrows():
        assert row[status_cols].sum() == row["n_routes"]


def test_hubs_only_sheets_are_filters_of_hubs(scenario):
    sheets = _sheets(scenario)
    hubs = sheets["hubs"]
    assert len(hubs) == len(scenario["hubs"].hubs)
    agency_only = hubs[hubs["relation"] == "agency_only"].reset_index(drop=True)
    ours_only = hubs[hubs["relation"] == "ours_only"].reset_index(drop=True)
    pd.testing.assert_frame_equal(sheets["hubs_agency_only"], agency_only)
    pd.testing.assert_frame_equal(sheets["hubs_ours_only"], ours_only)
    # an agency_only row carries the nearest group's identity, so it must still be listed there
    assert agency_only["group"].notna().all()
    assert sorted(ours_only["group"]) == [2, 3]
    assert (hubs["relation"] == "1:1").sum() == 1  # paired rows stay only in the full table
    assert set(sheets["hubs_agency_only"]["agency_hub_id"]) == {2}


def test_summary_states_derived_type_and_empty_demand(scenario):
    summary = _sheets(scenario)["summary"]
    text = " ".join(summary.astype(str).to_numpy().ravel()).lower()
    assert "agency_total_demand" in text and "empty" in text
    assert "derived" in text and "not an agency classification" in text
    assert "28-10" in text and "/runs/28-10" in text
    assert "settings" in text
    items = dict(zip(summary["item"], summary["value"]))
    assert items["routes: matched"] == 1
    assert items["routes: ours_only"] == 2
    assert items["routes: agency_only"] == 1
    assert items["hubs: agency hubs"] == 2
    assert items["hubs: groups of ours"] == 3
    assert items["hubs: relation 1:1"] == 1
    assert items["hubs: relation agency_only"] == 1
    assert items["hubs: relation ours_only"] == 2


def test_sheets_are_deterministic(scenario):
    a, b = _sheets(scenario), _sheets(scenario)
    for name in SHEETS:
        pd.testing.assert_frame_equal(a[name], b[name])


def test_lists_are_joined_and_hebrew_survives_roundtrip(tmp_path: Path):
    frame = pd.DataFrame({
        "name": ["תחנה מרכזית", "=SUM(A1)", None],
        "lines": [["L1", "L2"], [], ("a",)],
        "n": pd.array([3, pd.NA, 7], dtype="Int64"),
        "x": [1.5, np.nan, 2.0],
        "flag": pd.array([True, pd.NA, False], dtype="boolean"),
        "geometry": [Point(0, 0)] * 3,
    })
    wide = pd.DataFrame({"long": ["x" * 200]})
    path = write_workbook(
        tmp_path / "out.xlsx", {"Hebrew": frame, "a very long sheet name over thirty one": wide}
    )
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames[0] == "Hebrew"
    assert all(len(n) <= 31 for n in wb.sheetnames)
    ws = wb["Hebrew"]
    assert [c.value for c in ws[1]] == ["name", "lines", "n", "x", "flag"]  # no geometry
    assert ws["A2"].value == "תחנה מרכזית"
    assert ws["A3"].value == "=SUM(A1)" and ws["A3"].data_type == "s"  # text, not a formula
    assert ws["A4"].value is None
    assert ws["B2"].value == "L1; L2" and ws["B3"].value in (None, "") and ws["B4"].value == "a"
    assert ws["C2"].value == 3 and isinstance(ws["C2"].value, int)
    assert ws["C3"].value is None and ws["D3"].value is None and ws["E3"].value is None
    assert ws["E2"].value is True and ws["E4"].value is False
    assert ws["D2"].value == 1.5
    assert ws.freeze_panes == "A2"
    assert all(c.font.bold for c in ws[1])
    assert ws.auto_filter.ref == "A1:E4"
    assert wb[wb.sheetnames[1]].column_dimensions["A"].width <= 60


def test_gpkg_layers_crs_and_counts(scenario, tmp_path: Path):
    layers = _layers(scenario)
    assert set(layers) == {
        "route_pairs", "our_routes", "our_routes_raw", "agency_hubs", "our_groups", "hub_ties",
    }
    path = write_gpkg(tmp_path / "cmp.gpkg", layers)
    names = set(gpd.list_layers(path)["name"])
    assert names == set(layers)
    expected = {"route_pairs": 1, "our_routes": 3, "our_routes_raw": 3, "agency_hubs": 2,
                "our_groups": 3, "hub_ties": 1}
    for name, count in expected.items():
        back = gpd.read_file(path, layer=name)
        assert len(back) == count, name
        assert back.crs.to_epsg() == 2039, name
    pairs = gpd.read_file(path, layer="route_pairs").iloc[0]
    assert pairs["status"] == "matched" and pairs["agency_route_key"] == "LRT:1"
    assert pairs.geometry.geom_type in ("MultiLineString", "LineString")
    tie = gpd.read_file(path, layer="hub_ties").iloc[0]
    assert tie.geometry.length == pytest.approx(50.0)
    assert tie["agency_hub_id"] == 1 and tie["group"] == 1
    groups = gpd.read_file(path, layer="our_groups").set_index("group")
    assert groups.loc[1, "relation"] == "1:1" and groups.loc[2, "relation"] == "ours_only"
    assert groups.loc[1, "HubNameHE"] == "מתחם 1"


def test_our_routes_layer_survives_single_node_route(scenario, tmp_path: Path):
    layers = _layers(scenario)
    routes = layers["our_routes"].set_index("route_key")
    assert routes["visual_aid"].all()
    assert routes.loc["L5"].geometry.geom_type == "Point"
    assert routes.loc["L1"].geometry.geom_type == "LineString"
    assert routes.loc["L1"].geometry.length == pytest.approx(2000.0)
    assert bool(routes.loc["L5", "short_route"]) is True
    # the raw layer has the raw positions: 10 m north of the corrected ones
    raw = layers["our_routes_raw"].set_index("route_key")
    assert raw.loc["L5"].geometry.y - routes.loc["L5"].geometry.y == pytest.approx(10.0)
    shift = raw.loc["L1"].geometry.bounds[1] - routes.loc["L1"].geometry.bounds[1]
    assert shift == pytest.approx(10.0)
    assert layers["our_routes"].crs.to_epsg() == 2039
    write_gpkg(tmp_path / "mixed.gpkg", layers)  # mixed Point / LineString geometries write


def test_empty_comparison_still_writes_all_sheets(tmp_path: Path):
    empty = _empty()
    sheets = _sheets(empty)
    assert list(sheets) == SHEETS
    path = write_workbook(tmp_path / "empty.xlsx", sheets)
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == SHEETS
    for name in ("routes", "hubs", "hub_routes", "mode_summary", "routes_only_ours"):
        assert wb[name].max_row == 1 and wb[name].max_column > 1, name
    layers = _layers(empty)
    assert all(len(layer) == 0 for layer in layers.values())
    gpkg = write_gpkg(tmp_path / "empty.gpkg", layers)
    assert set(gpd.list_layers(gpkg)["name"]) == set(layers)
