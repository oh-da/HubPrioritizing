"""Leaflet pages of ``hubs compare-network``: embedded data, safety, empty layers."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, MultiPoint, Point

from src.compare.export import LAYER_NAMES
from src.compare.maps import LEAFLET_CSS, LEAFLET_JS, write_hubs_map, write_routes_map
from tests.compare_helpers import CRS_ITM, X0, Y0

HEBREW = "תחנה מרכזית – קו 1 \"ירושלים\""
EVIL = "</script><script>window.pwned=1</script><!--"


def _gdf(rows: list[dict[str, Any]], geoms: list, columns: list[str]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(pd.DataFrame(rows, columns=columns), geometry=geoms, crs=CRS_ITM)


def _line(x0: float, y: float, n: int = 3) -> LineString:
    return LineString([(X0 + x0 + 250 * i, Y0 + y) for i in range(n)])


def _layers(name: str = HEBREW) -> dict[str, gpd.GeoDataFrame]:
    pair_cols = ["status", "our_route_key", "our_mode", "agency_route_key", "agency_type",
                 "agency_name", "score", "cov_ours", "year_operation", "source_plan"]
    pairs = _gdf(
        [{"status": "matched", "our_route_key": "L1", "our_mode": "LRT",
          "agency_route_key": "LRT:1", "agency_type": "LRT", "agency_name": name, "score": 0.97,
          "cov_ours": 1.0, "year_operation": 2040.0, "source_plan": "מפורטת"},
         {"status": "agency_only", "our_route_key": None, "our_mode": None,
          "agency_route_key": "LRT:2", "agency_type": "LRT", "agency_name": "two",
          "score": float("nan"), "cov_ours": float("nan"), "year_operation": 2040.0,
          "source_plan": None},
         {"status": "weak", "our_route_key": "L5", "our_mode": "BRT",
          "agency_route_key": "LRT:2", "agency_type": "LRT", "agency_name": "two", "score": 0.3,
          "cov_ours": 0.4, "year_operation": 2040.0, "source_plan": None}],
        [_line(0, 0), _line(0, 8000), _line(0, 8000)], pair_cols)
    our_cols = ["route_key", "line_names", "mode", "n_nodes", "visual_aid", "status"]
    rows = [{"route_key": "L1", "line_names": name, "mode": "LRT", "n_nodes": 3,
             "visual_aid": True, "status": "matched"},
            {"route_key": "L9", "line_names": "x", "mode": "Cable Line", "n_nodes": 1,
             "visual_aid": True, "status": "ours_only"}]
    ours = _gdf(rows, [_line(0, 10), Point(X0, Y0 - 8000)], our_cols)
    raw = _gdf(rows, [_line(0, 20), Point(X0, Y0 - 7990)], our_cols)
    ahub_cols = ["agency_hub_id", "name", "modes", "n_modes", "rail_hub", "agency_type",
                 "relation", "paired_groups"]
    agency_hubs = _gdf(
        [{"agency_hub_id": 1, "name": name, "modes": "LRT", "n_modes": 1, "rail_hub": False,
          "agency_type": "1 mode: LRT", "relation": "1:1", "paired_groups": "1"},
         {"agency_hub_id": 2, "name": "hub two", "modes": "LRT; BRT", "n_modes": 2,
          "rail_hub": True, "agency_type": "2 modes", "relation": "agency_only",
          "paired_groups": ""}],
        [MultiPoint([(X0, Y0 + 50), (X0 + 250, Y0 + 50)]), MultiPoint([(X0, Y0 + 8000)])],
        ahub_cols)
    group_cols = ["hub_id", "group", "HubNameHE", "Mode_Planned", "n_modes", "eligible",
                  "exclusion_reason", "HubType", "TotalDemand", "relation"]
    groups = _gdf(
        [{"hub_id": "H1", "group": 1, "HubNameHE": name, "Mode_Planned": "LRT", "n_modes": 1,
          "eligible": True, "exclusion_reason": "", "HubType": "מטרופוליני",
          "TotalDemand": 5000.0, "relation": "1:1"},
         {"hub_id": "H3", "group": 3, "HubNameHE": EVIL, "Mode_Planned": "LRT; BRT",
          "n_modes": 2, "eligible": False, "exclusion_reason": "single mode", "HubType": "",
          "TotalDemand": 10.0, "relation": "ours_only"}],
        [MultiPoint([(X0, Y0)]), MultiPoint([(X0 + 3000, Y0 + 3000)])], group_cols)
    tie_cols = ["agency_hub_id", "group", "hub_id", "relation", "distance_m", "agency_name",
                "HubNameHE", "eligible"]
    ties = _gdf(
        [{"agency_hub_id": 1, "group": 1, "hub_id": "H1", "relation": "1:1", "distance_m": 50.0,
          "agency_name": name, "HubNameHE": name, "eligible": True},
         {"agency_hub_id": 2, "group": 3, "hub_id": "H3", "relation": "many_to_many",
          "distance_m": 0.0, "agency_name": "hub two", "HubNameHE": "z", "eligible": False}],
        [LineString([(X0, Y0 + 50), (X0, Y0)]), LineString([(X0, Y0), (X0, Y0)])], tie_cols)
    return {"route_pairs": pairs, "our_routes": ours, "our_routes_raw": raw,
            "agency_hubs": agency_hubs, "our_groups": groups, "hub_ties": ties}


def _empty_layers() -> dict[str, gpd.GeoDataFrame]:
    return {n: gpd.GeoDataFrame({"a": []}, geometry=gpd.GeoSeries([], crs=CRS_ITM), crs=CRS_ITM)
            for n in LAYER_NAMES}


def _data(html: str) -> dict[str, Any]:
    match = re.search(r'<script type="application/json" id="page-data">(.*?)</script>', html,
                      re.S)
    assert match, "no embedded data block"
    return json.loads(match.group(1))


def _write(tmp_path: Path, layers: dict) -> tuple[str, str]:
    routes = write_routes_map(tmp_path / "routes.html", layers)
    hubs = write_hubs_map(tmp_path / "hubs.html", layers)
    return routes.read_text(encoding="utf-8"), hubs.read_text(encoding="utf-8")


def _coords(geometry: dict | None):
    if geometry is None:
        return
    stack = [geometry["coordinates"]]
    while stack:
        item = stack.pop()
        if item and isinstance(item[0], (int, float)):
            yield item
        else:
            stack.extend(item)


def test_pages_embed_json_with_expected_counts(tmp_path: Path):
    layers = _layers()
    routes, hubs = _write(tmp_path, layers)
    r, h = _data(routes), _data(hubs)
    assert set(r) == {"route_pairs", "our_routes", "our_routes_raw"}
    assert set(h) == {"agency_hubs", "our_groups", "hub_ties"}
    for page in (r, h):
        for name, collection in page.items():
            assert collection["type"] == "FeatureCollection"
            assert len(collection["features"]) == len(layers[name]), name
    assert "leaflet/1.9.4/leaflet.min.js" in LEAFLET_JS and routes.count(LEAFLET_JS) == 1
    assert "leaflet/1.9.4/leaflet.min.css" in LEAFLET_CSS and hubs.count(LEAFLET_CSS) == 1
    # a row of route_pairs is a feature of its own: the shared agency key is not a feature key
    statuses = [f["properties"]["status"] for f in r["route_pairs"]["features"]]
    assert statuses == ["matched", "agency_only", "weak"]
    only = r["route_pairs"]["features"][1]["properties"]
    assert "our_route_key" not in only and "score" not in only  # nulls are not embedded
    # the legends carry the visual-aid and derived-type notes
    assert "visual aid" in routes
    assert "agency demand" in hubs.lower() and "derived" in hubs


def test_coordinates_are_wgs84(tmp_path: Path):
    routes, hubs = _write(tmp_path, _layers())
    seen = 0
    for page in (_data(routes), _data(hubs)):
        for collection in page.values():
            for feature in collection["features"]:
                for lon, lat in _coords(feature["geometry"]):
                    assert 34 < lon < 36 and 29 < lat < 34
                    assert round(lon, 6) == lon and round(lat, 6) == lat
                    seen += 1
    assert seen > 20


def test_hebrew_not_escaped_into_garbage(tmp_path: Path):
    routes, hubs = _write(tmp_path, _layers())
    assert "תחנה מרכזית" in routes and "תחנה מרכזית" in hubs  # UTF-8 as is, no \uXXXX
    assert "\\u05" not in routes and "\\u05" not in hubs
    first = _data(routes)["route_pairs"]["features"][0]["properties"]
    assert first["agency_name"] == HEBREW and first["source_plan"] == "מפורטת"
    assert _data(hubs)["our_groups"]["features"][0]["properties"]["HubNameHE"] == HEBREW
    assert (tmp_path / "routes.html").read_bytes().decode("utf-8") == routes


def test_script_closing_tag_in_data_is_escaped(tmp_path: Path):
    routes, hubs = _write(tmp_path, _layers(name=EVIL))
    for html in (routes, hubs):
        assert html.count("</script>") == html.count("<script"), "data ended a script block"
        assert "<script>window.pwned" not in html and "<!--" not in html
    assert _data(routes)["route_pairs"]["features"][0]["properties"]["agency_name"] == EVIL
    assert _data(hubs)["our_groups"]["features"][1]["properties"]["HubNameHE"] == EVIL
    assert "eval(" not in routes and "eval(" not in hubs and "innerHTML" not in routes


def test_empty_layers_render(tmp_path: Path):
    routes, hubs = _write(tmp_path, _empty_layers())
    for html in (routes, hubs):
        for collection in _data(html).values():
            assert collection == {"type": "FeatureCollection", "features": []}
        assert "Leaflet" in html or "leaflet" in html
    # a mapping without the layers at all renders the same way
    assert _data(write_routes_map(tmp_path / "none.html", {}).read_text("utf-8"))["route_pairs"][
        "features"] == []


def test_same_layers_give_identical_bytes(tmp_path: Path):
    layers = _layers()
    a = write_routes_map(tmp_path / "a.html", layers).read_bytes()
    b = write_routes_map(tmp_path / "b.html", layers).read_bytes()
    assert a == b
    assert write_hubs_map(tmp_path / "c.html", layers).read_bytes() == write_hubs_map(
        tmp_path / "d.html", layers).read_bytes()


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_page_scripts_parse_and_run_against_a_stub(tmp_path: Path):
    """Run each page's own script against a minimal DOM/Leaflet stub, with data and without."""
    runner = Path(__file__).with_name("compare_maps_stub.js")
    # features drawn at start: 3 agency + 2 ours routes; 2 + 2 hubs and the one tie that is not
    # degenerate (the zero-length tie of agency hub 2 is hidden)
    for layers, shown in ((_layers(), 5), (_empty_layers(), 0)):
        _write(tmp_path, layers)
        for name in ("routes", "hubs"):
            out = subprocess.run(
                ["node", str(runner), str(tmp_path / f"{name}.html")],
                capture_output=True, text=True, check=False,
            )
            assert out.returncode == 0, out.stderr
            assert f"shown={shown} " in out.stdout, out.stdout


def test_zoom_control_is_not_under_the_panel(tmp_path: Path):
    routes, hubs = _write(tmp_path, _layers())
    for html in (routes, hubs):
        assert "zoomControl: false" in html
        assert "L.control.zoom({position: 'topright'})" in html


def test_mode_filter_values_cover_both_vocabularies(tmp_path: Path):
    layers = _layers()
    ours = layers["our_routes"].copy()
    ours["agency_type"] = ["LRT", None]
    ours.loc[0, "mode"] = "Suburban Rail"
    ours.loc[0, "agency_type"] = "Rail"
    layers["our_routes"] = ours
    groups = layers["our_groups"].copy()
    groups["common_modes"] = ["Rail; LRT", "LRT; BRT"]
    groups.loc[0, "Mode_Planned"] = "Suburban Rail; LRT"
    layers["our_groups"] = groups
    routes, hubs = _write(tmp_path, layers)
    r, h = _data(routes), _data(hubs)
    first = r["our_routes"]["features"][0]
    assert first["properties"]["mode"] == "Suburban Rail"
    assert "Rail" in first["modes"] and "Suburban Rail" in first["modes"]
    assert r["our_routes"]["features"][1]["modes"] == ["Cable Line"]
    pair = r["route_pairs"]["features"][0]  # agency side: the agency type and our mode
    assert pair["modes"] == ["LRT"]
    group = h["our_groups"]["features"][0]
    assert {"Suburban Rail", "Rail", "LRT"} <= set(group["modes"])
    assert set(h["agency_hubs"]["features"][1]["modes"]) == {"LRT", "BRT"}
    assert "f.modes" in routes and "f.modes" in hubs  # the filters read these arrays


def test_routes_page_knows_every_status(tmp_path: Path):
    from src.compare.routes import STATUSES

    routes, _ = _write(tmp_path, _layers())
    colors = re.search(r"const COLORS = \{(.*?)\};", routes, re.S).group(1)
    meaning = re.search(r"const MEANING = \{(.*?)\};", routes, re.S).group(1)
    for status in STATUSES:
        assert f"{status}:" in colors and f"{status}:" in meaning, status
