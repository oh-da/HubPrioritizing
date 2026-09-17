"""The H3 base layer against the polygon stages it replaces, on synthetic layers."""

import json

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import pytest
import shapely

from src.config import CRS_ISRAEL_TM, CRS_WGS84
from src.pipeline.aggregate import add_influence_area, aggregate_to_groups, tag_bus_terminals
from src.pipeline.base_layer import (
    BASE_LAYER_COLUMNS,
    add_influence_area_from_base,
    allocate_taz,
    build_base_layer,
    build_manifest,
    cell_polygons_itm,
    cells_covering,
    grid_disk_radius,
    read_base_layer,
    tag_area_and_location_from_base,
    tag_bus_terminals_from_base,
    terminals_to_cells,
    write_base_layer,
)
from src.pipeline.report import RunReport
from src.pipeline.spatial_tags import tag_area_and_location

RES = 10
X0, Y0 = 180_000.0, 665_000.0  # ITM, central Israel


def _box(x0, y0, x1, y1):
    return shapely.box(x0, y0, x1, y1)


@pytest.fixture(scope="module")
def layers():
    metro = gpd.GeoDataFrame(
        {"METRO_NAME": ["תל אביב", "תל אביב"], "ZONE_NAME": ["גלעין", "טבעת פנימית"]},
        geometry=[_box(X0, Y0, X0 + 2000, Y0 + 2000), _box(X0 + 2000, Y0 - 2000, X0 + 6000, Y0 + 4000)],
        crs=CRS_ISRAEL_TM,
    )
    districts = gpd.GeoDataFrame({"MACHOZ": ["מחוז מרכז"]}, geometry=[_box(X0 - 6000, Y0 - 6000, X0 + 10000, Y0 + 10000)], crs=CRS_ISRAEL_TM)
    terminals = gpd.GeoDataFrame(
        {"id": [7, 8], "term_type": ["מסוף גדול", "חניון לילה"]},
        geometry=[_box(X0 + 900, Y0 + 900, X0 + 950, Y0 + 950), _box(X0 + 4000, Y0 + 1000, X0 + 4050, Y0 + 1050)],
        crs=CRS_ISRAEL_TM,
    )
    taz = gpd.GeoDataFrame(
        {"POP_2050": [8000.0, 2000.0, 500.0], "EMPL_2050": [3000.0, 9000.0, 100.0]},
        geometry=[_box(X0 - 3000, Y0 - 3000, X0 + 1000, Y0 + 3000), _box(X0 + 1000, Y0 - 3000, X0 + 5000, Y0 + 3000), _box(X0 + 5000, Y0 - 3000, X0 + 9000, Y0 + 3000)],
        crs=CRS_ISRAEL_TM,
    )
    return metro, districts, terminals, taz


@pytest.fixture(scope="module")
def base(layers):
    metro, districts, terminals, taz = layers
    report = RunReport()
    df = build_base_layer(metro, districts, terminals, taz, RES, 200.0, report)
    return df.set_index("h3_index")


def _hexes_at(points_itm, groups):
    """A hexagon table like network.aggregate_to_hexes produces (WGS84 cell polygons)."""
    pts = gpd.GeoSeries([shapely.Point(x, y) for x, y in points_itm], crs=CRS_ISRAEL_TM).to_crs(CRS_WGS84)
    cells = [h3.latlng_to_cell(p.y, p.x, RES) for p in pts]
    polys = [shapely.Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)]) for c in cells]
    return gpd.GeoDataFrame(
        {"h3_index": cells, "group": groups, "node": [[i] for i in range(len(cells))], "Mode_Planned": [["LRT"]] * len(cells), "Line_Unique": [["l"]] * len(cells), "Line_Nunique": [1] * len(cells), "TotalDemand": [1000.0] * len(cells), "TotalTransfers": [0.0] * len(cells), "area": ["x"] * len(cells), "location": [["x"]] * len(cells), "LRT Lines": [1.0] * len(cells)},
        geometry=polys,
        crs=CRS_WGS84,
    )


@pytest.fixture(scope="module")
def hexes():
    # well inside the core, well inside the inner ring, outside the metro (district only),
    # next to the big terminal, and two neighbouring cells forming one group
    pts = [(X0 + 1000, Y0 + 1000), (X0 + 4000, Y0 + 1000), (X0 - 3000, Y0 + 5000), (X0 + 1000, Y0 + 1000 + 120), (X0 + 3000, Y0 - 1000), (X0 + 3000, Y0 - 1000 + 130)]
    return _hexes_at(pts, [0, 1, 2, 0, 3, 3])


def test_build_base_layer_schema_and_totals(base, layers):
    assert list(base.reset_index().columns) == list(BASE_LAYER_COLUMNS)
    assert base.index.is_unique
    taz = layers[3]
    assert base["pop_2050"].sum() == pytest.approx(taz["POP_2050"].sum())
    assert base["emp_2050"].sum() == pytest.approx(taz["EMPL_2050"].sum())
    assert set(base["area"].unique()) <= {"תל אביב", "מרכז", "Unknown"}  # district name folded like the notebook
    assert set(base["bus_terminal"].unique()) == {0, 1, 3}


def test_allocate_taz_uniform_density(layers):
    taz = layers[3]
    alloc = allocate_taz(taz, RES)
    # zone 1: 8000 people over 4 km x 6 km; every cell fully inside it carries density x its area
    zone = gpd.GeoSeries([taz.geometry.iloc[0]], crs=CRS_ISRAEL_TM)
    polys = cell_polygons_itm(alloc["h3_index"].tolist())
    inside = shapely.contains_properly(zone.iloc[0], polys)
    density = alloc.loc[inside, "pop_2050"].to_numpy() / shapely.area(polys[inside])
    assert inside.sum() > 1000
    np.testing.assert_allclose(density, 8000.0 / (4000 * 6000), rtol=1e-6)


def test_terminal_cells_reproduce_hub_buffer_test(base, hexes, layers):
    terminals = layers[2]
    groups = aggregate_to_groups(hexes)
    ref = tag_bus_terminals(groups, terminals, 200.0)
    new = tag_bus_terminals_from_base(groups, hexes, base)
    assert list(ref["bus_terminal"]) == list(new["bus_terminal"])
    assert list(ref["term_type"]) == list(new["term_type"])
    assert new.set_index("group").loc[0, "bus_terminal"] == 3  # the big terminal within 200 m


def test_terminals_to_cells_keeps_highest_class(layers):
    terminals = layers[2].copy()
    terminals.loc[1, "geometry"] = terminals.loc[0, "geometry"]  # both terminals on the same spot
    cells = terminals_to_cells(terminals, RES, 200.0)
    assert cells["h3_index"].is_unique
    assert (cells["bus_terminal"] == 3).all()


def test_area_and_location_match_polygon_stage_away_from_boundaries(base, hexes, layers):
    metro, districts = layers[0], layers[1]
    ref = tag_area_and_location(hexes, metro, districts)
    new = tag_area_and_location_from_base(hexes, base)
    assert list(ref["area"]) == list(new["area"])
    assert [str(v) for v in ref["location"]] == [str(v) for v in new["location"]]
    assert new.loc[2, "area"] == "מרכז" and new.loc[2, "location"] == ["מרכז"]


def test_unknown_cell_is_reported(base, hexes):
    far = _hexes_at([(X0 + 60_000, Y0 + 60_000)], [9])
    report = RunReport()
    out = tag_area_and_location_from_base(pd.concat([hexes, far], ignore_index=True), base, report)
    assert out.loc[len(hexes), "area"] == "Unknown"
    assert any("not in the base layer" in e.message for e in report.warnings)


@pytest.mark.parametrize("rule, tol", [("fraction", 0.02), ("center", 0.15)])
def test_influence_area_close_to_polygon_overlay(base, hexes, layers, rule, tol):
    taz = layers[3]
    groups = aggregate_to_groups(hexes)
    rings = (500, 1000, 1500)
    ref = add_influence_area(groups, taz, rings)
    new = add_influence_area_from_base(groups, base, rings, RES, rule)
    for col in ("pop_0_500", "emp_0_500", "pop_500_1000", "emp_500_1000", "pop_1000_1500", "emp_1000_1500"):
        a, b = ref[col].to_numpy(), new[col].to_numpy()
        assert np.all(np.abs(b - a) <= tol * np.maximum(a, 1.0) + 1e-9), (col, a, b)


def test_influence_area_rules_and_errors(base, hexes):
    groups = aggregate_to_groups(hexes)
    with pytest.raises(ValueError):
        add_influence_area_from_base(groups, base, (1000, 500), RES)
    with pytest.raises(ValueError):
        add_influence_area_from_base(groups, base, (500,), RES, "nearest")
    assert grid_disk_radius(1500, 10) >= 12


def test_cells_covering_small_and_large_polygons():
    small = gpd.GeoSeries([_box(X0, Y0, X0 + 300, Y0 + 300)], crs=CRS_ISRAEL_TM).to_crs(CRS_WGS84)
    large = gpd.GeoSeries([_box(X0, Y0, X0 + 12_000, Y0 + 12_000)], crs=CRS_ISRAEL_TM).to_crs(CRS_WGS84)
    s = cells_covering(small.geometry, RES)
    l = set(cells_covering(large.geometry, RES))
    assert 0 < len(s) < 40
    assert set(s) <= l  # the coarse fill over-covers, never under-covers
    assert len(l) > 144e6 / h3.average_hexagon_area(RES, unit="m^2") * 0.95


def test_parquet_round_trip_and_manifest(base, tmp_path, layers):
    path = tmp_path / "h3_base.parquet"
    shp = tmp_path / "taz.shp"
    layers[3].to_file(shp)
    manifest = build_manifest({"taz": shp, "metro": None}, RES, 200.0, len(base))
    write_base_layer(base.reset_index(), path, manifest)
    back, mf = read_base_layer(path)
    fill = {"term_type": "", "term_id": -1.0}
    pd.testing.assert_frame_equal(back.sort_index().fillna(fill), base.sort_index().fillna(fill), check_dtype=False)
    assert mf["resolution"] == RES and mf["rows"] == len(base)
    assert "taz" in mf["sources"] and "metro" not in mf["sources"]
    assert len(mf["sources"]["taz"]["sha256"]) == 64 and "taz.dbf" in mf["sources"]["taz"]["sidecars"]
    assert json.loads((tmp_path / "h3_base.manifest.json").read_text(encoding="utf-8")) == mf

    bad = base.reset_index().drop(columns=["pop_2050"])
    bad.to_parquet(tmp_path / "bad.parquet", index=False)
    with pytest.raises(ValueError):
        read_base_layer(tmp_path / "bad.parquet")
