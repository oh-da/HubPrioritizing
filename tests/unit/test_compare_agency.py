"""Agency network reader: routes, stops, hubs, labels, CRS handling, errors."""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

from src.compare.agency import (
    build_route_key,
    hub_type_label,
    read_agency_network,
    read_tod_hubs,
)
from src.compare.settings import CompareConfig
from src.pipeline.inputs import InputError
from src.pipeline.report import RunReport
from tests.synthetic_agency import (
    HUB_A,
    HUB_B,
    HUB_EAST,
    make_agency_gpkg,
    make_metadata_xlsx,
    make_tod_gpkg,
)


@pytest.fixture()
def gpkg(tmp_path):
    return make_agency_gpkg(tmp_path / "agency.gpkg")


@pytest.fixture()
def net(gpkg):
    return read_agency_network(gpkg, None, CompareConfig(), RunReport())


def test_route_keys(net):
    assert build_route_key("LRT", 3106, "ignored") == "LRT:3106"
    assert build_route_key("Rail", 0, "Haifa Rail 22") == "Rail:0:Haifa Rail 22"
    keys = set(net.routes["route_key"])
    # the two "Rail A" features collapse into one route, "Rail B" is another
    assert {"Rail:0:Rail A", "Rail:0:Rail B"} <= keys
    assert net.routes["route_key"].is_unique
    rail_a = net.routes.set_index("route_key").loc["Rail:0:Rail A"]
    assert rail_a.geometry.length == pytest.approx(300.0)  # 120 m + 180 m, union of both features
    assert rail_a["line_id"] == 0
    assert len(net.routes) == 9  # 10 lines features, two merged
    assert list(net.routes.columns) == [
        "route_key", "type", "line_id", "name", "line_name", "year_operation", "year_cancel",
        "source_plan", "source_name", "n_stops", "has_stops", "geometry",
    ]
    assert str(net.routes.crs.to_epsg()) == "2039"
    lonely = net.routes.set_index("route_key").loc["LRT:5001"]
    assert not lonely["has_stops"] and lonely["n_stops"] == 0
    assert net.routes.set_index("route_key").loc["LRT:1001", "has_stops"]


def test_rail_stations_assigned_to_nearest_feature_within_tol(gpkg):
    report = RunReport()
    net = read_agency_network(gpkg, None, CompareConfig(), report)
    rail = net.stops[net.stops["type"] == "Rail"].set_index("station_name")
    assert rail.loc["תחנה א - 1", "route_key"] == "Rail:0:Rail A"
    assert rail.loc["תחנה ב - 1", "route_key"] == "Rail:0:Rail B"
    assert rail.loc["אליעזר בן יהודה - 3", "route_key"] == "Rail:0:Rail A"
    # the station 300 m from every rail feature is dropped and reported
    assert "תחנה רחוקה - 2" not in rail.index
    warnings = [w for w in report.warnings if w.section == "agency"]
    assert len(warnings) == 1
    assert "1 " in warnings[0].message and "rail" in warnings[0].message.lower()
    # a wider tolerance keeps it
    wide = read_agency_network(gpkg, None, CompareConfig(rail_assign_tol_m=400.0), RunReport())
    far = wide.stops.set_index("station_name").loc["תחנה רחוקה - 2"]
    assert far["route_key"] == "Rail:0:Rail B"
    # stations of other lines take their key directly
    lrt = net.stops[net.stops["line_id"] == 1001]
    assert set(lrt["route_key"]) == {"LRT:1001"}
    assert net.routes.set_index("route_key").loc["Rail:0:Rail B", "n_stops"] == 1


def test_hub_ids_are_ints_and_hubs_have_two_stops(net):
    assert str(net.stops["hub_id"].dtype) == "Int64"
    assert net.stops["rail_hub"].dtype == bool
    assert pd.api.types.is_integer_dtype(net.hubs["agency_hub_id"])
    assert sorted(net.hubs["agency_hub_id"]) == sorted([HUB_A, HUB_B, HUB_EAST])
    counts = net.stops.dropna(subset=["hub_id"]).groupby("hub_id").size()
    assert (counts >= 2).all() and len(counts) == 3
    hubs = net.hubs.set_index("agency_hub_id")
    assert hubs.loc[HUB_A, "modes"] == ["LRT", "Metro", "Rail"]
    assert hubs.loc[HUB_A, "n_modes"] == 3 and bool(hubs.loc[HUB_A, "rail_hub"])
    assert hubs.loc[HUB_B, "modes"] == ["BRT", "LRT"] and not bool(hubs.loc[HUB_B, "rail_hub"])
    assert hubs.loc[HUB_B, "route_keys"] == ["BRT:3001", "LRT:1002"]
    assert hubs.loc[HUB_EAST, "n_routes"] == 2 and hubs.loc[HUB_EAST, "n_modes"] == 1
    assert hubs.loc[HUB_A, "geometry"].geom_type == "MultiPoint"
    assert len(hubs.loc[HUB_A, "geometry"].geoms) == 3
    assert list(net.hubs.columns) == [
        "agency_hub_id", "name", "modes", "n_modes", "rail_hub", "agency_type", "route_keys",
        "n_routes", "geometry",
    ]
    assert list(net.stops.columns) == [
        "stop_id", "route_key", "type", "line_id", "station_name", "hub_id", "rail_hub",
        "hub_stop_id", "geometry",
    ]


def test_hub_name_ignores_placeholder_suffix(net):
    hubs = net.hubs.set_index("agency_hub_id")
    assert hubs.loc[HUB_A, "name"] == "אליעזר בן יהודה"  # " - 471", " - 12", " - 3" stripped
    assert hubs.loc[HUB_B, "name"] == "שדרות הנשיא"
    assert hubs.loc[HUB_EAST, "name"] == f"hub {HUB_EAST}"  # only "- 7" / "- 8" names


def test_agency_type_label(net):
    assert hub_type_label(["LRT"], False) == "1 mode: LRT"
    assert hub_type_label(["Rail", "BRT", "LRT"], True) == "3 modes, rail hub: BRT+LRT+Rail"
    assert hub_type_label(["LRT", "BRT", "LRT"], False) == "2 modes: BRT+LRT"
    hubs = net.hubs.set_index("agency_hub_id")
    assert hubs.loc[HUB_A, "agency_type"] == "3 modes, rail hub: LRT+Metro+Rail"
    assert hubs.loc[HUB_B, "agency_type"] == "2 modes: BRT+LRT"
    assert hubs.loc[HUB_EAST, "agency_type"] == "1 mode: LRT"


def test_other_crs_is_reprojected(tmp_path, net):
    other = make_agency_gpkg(tmp_path / "wgs.gpkg", crs="EPSG:4326")
    assert gpd.read_file(other, layer="stations").crs.to_epsg() == 4326
    again = read_agency_network(other, None, CompareConfig(), RunReport())
    assert str(again.stops.crs.to_epsg()) == "2039"
    a = net.stops.set_index("stop_id").geometry
    b = again.stops.set_index("stop_id").geometry
    assert all(a.loc[i].distance(b.loc[i]) < 1.0 for i in a.index)
    ra = net.routes.set_index("route_key").geometry
    rb = again.routes.set_index("route_key").geometry
    assert all(ra.loc[k].hausdorff_distance(rb.loc[k]) < 1.0 for k in ra.index)
    assert all(net.hubs.geometry.reset_index(drop=True).geom_equals_exact(
        again.hubs.geometry.reset_index(drop=True), tolerance=1.0))


@pytest.mark.filterwarnings("ignore:'crs' was not provided")
def test_missing_layer_raises_input_error_listing_all_problems(tmp_path):
    path = tmp_path / "bad.gpkg"
    lines = gpd.GeoDataFrame(
        {"line_id": [1], "name": ["x"]},  # no `type`
        geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:2039",
    )
    lines.to_file(path, layer="lines", driver="GPKG")  # and no `stations` layer
    with pytest.raises(InputError) as exc:
        read_agency_network(path, None, CompareConfig())
    text = "\n".join(exc.value.problems)
    assert "stations" in text and "type" in text
    assert len(exc.value.problems) >= 2
    # a missing file is an InputError as well; a layer without a CRS is reported
    with pytest.raises(InputError):
        read_agency_network(tmp_path / "nope.gpkg", None, CompareConfig())
    nocrs = tmp_path / "nocrs.gpkg"
    for layer, geom in (("lines", LineString([(0, 0), (1, 1)])), ("stations", Point(0, 0))):
        cols = {"type": ["LRT"], "line_id": [1], "name": ["n"], "station_name": ["s"],
                "stop_id": ["a"], "hub_id": [1.0], "rail_hub": [1.0]}
        gpd.GeoDataFrame(cols, geometry=[geom], crs=None).to_file(nocrs, layer=layer, driver="GPKG")
    with pytest.raises(InputError) as exc:
        read_agency_network(nocrs, None, CompareConfig())
    assert any("CRS" in p for p in exc.value.problems)


def test_labels_from_metadata_are_case_insensitive(gpkg, tmp_path):
    meta = make_metadata_xlsx(tmp_path / "meta.xlsx")
    net = read_agency_network(gpkg, meta, CompareConfig(), RunReport())
    types = net.labels["type"]
    assert types["metro"] == "מטרו"
    assert types["Metro"] == "מטרו"  # the gpkg spells it with a capital
    assert types["Rail fast"] == "רכבת מהירה"
    assert types["BRT"] == 'תאו"מ'
    assert net.labels["source_plan"]["Strategic"] == "תכנית אסטרטגית"
    assert net.labels["source_plan"]["detailed"] == "תכנית מפורטת"
    assert read_agency_network(gpkg, None, CompareConfig()).labels == {}


def test_read_tod_hubs(tmp_path):
    path = make_tod_gpkg(tmp_path / "tod.gpkg", crs="EPSG:4326")
    hubs = read_tod_hubs(path)
    assert list(hubs.columns) == ["tod_hub_id", "n_modes", "type_sum", "geometry"]
    assert sorted(hubs["tod_hub_id"]) == [11, 12]  # one row per hub, non-hubs dropped
    assert str(hubs["tod_hub_id"].dtype) == "Int64"
    assert str(hubs.crs.to_epsg()) == "2039"
    row = hubs.set_index("tod_hub_id")
    assert row.loc[11, "n_modes"] == 3 and row.loc[11, "type_sum"] == 3
    # the mean of the hub's stations, in ITM
    assert row.loc[11, "geometry"].distance(Point(180000, 665010)) < 1.0
    assert row.loc[12, "geometry"].distance(Point(182010, 665000)) < 1.0


def test_read_tod_hubs_non_numeric_hub_id_is_an_input_error(tmp_path):
    path = make_tod_gpkg(tmp_path / "tod.gpkg", crs="EPSG:4326")
    gdf = gpd.read_file(path, layer="stations")
    gdf["hub_id"] = gdf["hub_id"].astype(object)
    gdf.loc[0, "hub_id"] = "eleven"
    path.unlink()
    gdf.to_file(path, layer="stations", driver="GPKG")
    with pytest.raises(InputError) as exc:
        read_tod_hubs(path)
    assert any("hub_id" in p for p in exc.value.problems)
