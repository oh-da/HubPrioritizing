"""A base layer older than its source shapefiles is detected before a run."""

import json

import geopandas as gpd
import pytest
from shapely.geometry import box

from src.pipeline.base_layer import manifest_path, stale_sources
from src.pipeline.inputs import InputError, base_layer_staleness, discover_inputs, validate_inputs
from src.pipeline.report import RunReport
from src.pipeline.run import run_pipeline
from src.pipeline.settings import load_config
from tests.synthetic import make_synthetic_dirs


@pytest.fixture
def dirs(tmp_path):
    return make_synthetic_dirs(tmp_path)


def _replace_taz(ref_dir):
    """Rewrite the TAZ layer with a different population: same file names, new bytes."""
    taz = gpd.GeoDataFrame(
        {"POP_2050": [9000.0, 1000.0, 300.0], "EMPL_2050": [2000.0, 500.0, 100.0]},
        geometry=[box(179000, 664000, 181000, 666000), box(181000, 664000, 183000, 666000), box(189000, 664000, 191000, 666000)],
        crs="EPSG:2039",
    )
    taz.to_file(ref_dir / "TAZ_1270.shp")


def test_fresh_layer_is_current(dirs):
    input_dir, ref_dir = dirs
    inputs = discover_inputs(input_dir, ref_dir)
    assert base_layer_staleness(inputs) == []
    assert validate_inputs(inputs) == []


def test_changed_source_is_reported_and_stops_the_run(dirs):
    input_dir, ref_dir = dirs
    _replace_taz(ref_dir)
    inputs = discover_inputs(input_dir, ref_dir)
    msgs = base_layer_staleness(inputs)
    assert len(msgs) == 1 and "'taz'" in msgs[0] and "prepare-base" in msgs[0]

    problems = validate_inputs(inputs)  # default: a problem
    assert any("stale" in p for p in problems)
    with pytest.raises(InputError) as exc:
        run_pipeline(load_config(None, {"mc_iterations": 20}), inputs)
    assert any("stale" in p for p in exc.value.problems)

    # 'warn' lets the run continue and records the finding
    report = RunReport()
    result = run_pipeline(load_config(None, {"mc_iterations": 20, "on_stale_base_layer": "warn"}), inputs, report)
    assert len(result.results) >= 1
    assert any("stale" in w.message for w in report.warnings)

    # the shapefile path does not use the layer, so it is not checked
    assert validate_inputs(inputs, spatial_source="shapefiles") == []


def test_absent_source_is_not_a_problem(dirs):
    input_dir, ref_dir = dirs
    for p in ref_dir.glob("TAZ_1270.*"):
        p.unlink()
    inputs = discover_inputs(input_dir, ref_dir)
    assert base_layer_staleness(inputs) == []


def test_renamed_or_manifestless_layer(dirs):
    input_dir, ref_dir = dirs
    inputs = discover_inputs(input_dir, ref_dir)
    mp = manifest_path(inputs.path("h3_base"))
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    assert stale_sources(manifest, {"taz": ref_dir / "TAZ_1270.shp"}) == []
    renamed = ref_dir / "TAZ_1280.shp"
    (ref_dir / "TAZ_1270.shp").rename(renamed)
    msgs = stale_sources(manifest, {"taz": renamed})
    assert len(msgs) == 1 and "TAZ_1280.shp" in msgs[0]
    assert stale_sources(None, {"taz": renamed})[0].startswith("h3_base has no manifest")
    mp.unlink()
    assert base_layer_staleness(discover_inputs(input_dir, ref_dir))[0].startswith("h3_base has no manifest")
