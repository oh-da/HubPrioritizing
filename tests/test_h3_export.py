"""The shareable H3 cell layer (h3_export) on the synthetic run."""

import geopandas as gpd
import pandas as pd
import pytest

from src.pipeline.h3_export import LAYER_COLUMNS, build_h3_layer, hub_cell_table, influence_cells, write_h3_layer
from src.pipeline.inputs import discover_inputs
from src.pipeline.run import run_pipeline
from src.pipeline.settings import load_config
from tests.synthetic import make_synthetic_dirs


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    input_dir, ref_dir = make_synthetic_dirs(tmp_path_factory.mktemp("syn"))
    cfg = load_config(None, {"mc_iterations": 50, "apply_eligibility_filter": False, "h3_layer_format": "none"})
    return run_pipeline(cfg, discover_inputs(input_dir, ref_dir))


def test_hub_cell_table_joins_results(run):
    t = hub_cell_table(run.hexes, run.results)
    assert len(t) == len(run.hexes) and t["scored"].all()
    assert set(t["HubType"].dropna()) <= {"מטרופוליני", "עירוני", "Not Hub", "Train Station", "ארצי"}
    assert t["nodes"].str.contains(";").any()  # a hexagon with two nodes
    unscored = hub_cell_table(run.hexes, None)
    assert not unscored["scored"].any() and unscored["HubType"].isna().all()


def test_influence_cells_geometry(run):
    infl = influence_cells(run.groups, run.results, 1500.0, 10)
    assert infl["h3_index"].is_unique
    assert (infl["dist_nearest_hub_m"] <= 1500).all()
    assert (infl["n_hubs_within"] >= 1).all()
    # hubs A and B are 2 km apart: cells between them see both
    assert (infl["n_hubs_within"] >= 2).any()


@pytest.mark.parametrize("extent", ["hubs", "influence", "all"])
def test_build_layer_extents(run, extent):
    layer = build_h3_layer(run.base, run.hexes, run.results, run.groups, (500, 1000, 1500), 10, extent)
    assert list(layer.columns) == list(LAYER_COLUMNS) + ["geometry"]
    assert layer.crs.to_epsg() == 2039 and layer["h3_index"].is_unique
    roles = set(layer["role"])
    if extent == "hubs":
        assert roles == {"hub"} and len(layer) == len(run.hexes)
    elif extent == "influence":
        assert roles == {"hub", "influence"}
    else:
        assert roles == {"hub", "influence", "base"} and len(layer) == len(run.base)
    hub_rows = layer[layer["role"] == "hub"]
    assert (hub_rows["area"] == "תל אביב").sum() >= 2 and hub_rows["group"].notna().all()
    assert layer["bus_terminal"].isin([0, 1, 2, 3]).all()


@pytest.mark.parametrize("fmt", ["gpkg", "geojson", "parquet", "csv"])
def test_write_formats_round_trip(run, tmp_path, fmt):
    layer = build_h3_layer(run.base, run.hexes, run.results, run.groups, extent="hubs")
    path = write_h3_layer(layer, tmp_path / "cells", fmt)
    assert path.exists() and path.suffix == {"gpkg": ".gpkg", "geojson": ".geojson", "parquet": ".parquet", "csv": ".csv"}[fmt]
    if fmt == "csv":
        back = pd.read_csv(path)
        assert back["geometry_wkt"].str.startswith("POLYGON").all()
    elif fmt == "parquet":
        back = gpd.read_parquet(path)
        assert back.crs.to_epsg() == 2039
    else:
        back = gpd.read_file(path)
        assert back.crs.to_epsg() == (4326 if fmt == "geojson" else 2039)
    assert len(back) == len(layer)
    assert set(back["h3_index"]) == set(layer["h3_index"])
    assert (back["HubType"].dropna().astype(str) == layer["HubType"].dropna().astype(str).to_numpy()).all()


def test_write_rejects_unknown_format(run, tmp_path):
    layer = build_h3_layer(run.base, run.hexes, run.results, run.groups, extent="hubs")
    with pytest.raises(ValueError):
        write_h3_layer(layer, tmp_path / "x", "shp")
    with pytest.raises(ValueError):
        build_h3_layer(run.base, extent="country")
