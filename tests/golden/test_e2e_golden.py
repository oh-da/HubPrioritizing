"""Full pipeline on the real exports vs the golden workbook.

``e2e`` is the default run (the H3 base layer); ``e2e_shp`` overlays the shapefiles,
which is the path that reproduces the June 2026 workbook exactly.
"""

import pandas as pd
import pytest

from src.pipeline.report import RunReport
from src.pipeline.run import run_pipeline
from src.pipeline.settings import PipelineConfig, load_config
from tests.golden.conftest import parse_listish


@pytest.fixture(scope="module")
def e2e(real_inputs):
    report = RunReport()
    result = run_pipeline(PipelineConfig(), real_inputs, report)
    return result, report


@pytest.fixture(scope="module")
def e2e_shp(real_inputs):
    report = RunReport()
    result = run_pipeline(load_config(None, {"spatial_source": "shapefiles"}), real_inputs, report, allow_missing_layers=True)
    return result, report


def test_e2e_reproduces_golden_upstream_columns(e2e, golden):
    result, report = e2e
    res = result.results.set_index("group")
    g = golden.set_index("group")
    assert set(g.index) <= set(res.index), sorted(set(g.index) - set(res.index))
    res = res.loc[g.index]

    pd.testing.assert_series_equal(res["TotalDemand"].astype(float), g["TotalDemand"].astype(float), check_names=False, rtol=1e-9)
    pd.testing.assert_series_equal(res["TotalTransfers"].astype(float), g["TotalTransfers"].astype(float), check_names=False, rtol=1e-9)
    pd.testing.assert_series_equal(res["Line_Nunique"].astype(int), g["Line_Nunique"].astype(int), check_names=False)
    pd.testing.assert_series_equal(res["Num_Modes"].astype(int), g["Num_Modes"].astype(int), check_names=False)
    pd.testing.assert_series_equal(res["score"].astype(float), g["score"].astype(float), check_names=False, rtol=1e-9)
    assert (res["HubType"] == g["HubType"]).all()
    assert (res["area"] == g["area"]).all()
    assert (res["HubNameHE"].astype(str) == g["HubNameHE"].astype(str)).all()
    assert (res["node"].map(set) == g["node"].map(lambda v: set(int(n) for n in parse_listish(v)))).all()
    # centroids of the same dissolved hexagons
    assert (res["x"] - g["x"]).abs().max() < 1e-6 and (res["y"] - g["y"]).abs().max() < 1e-6
    print(f"\n[e2e] {len(res)} golden hubs reproduced; total hubs in run: {len(result.results)}; warnings: {len(report.warnings)}")


def test_e2e_row_count_matches_golden(e2e, golden):
    result, _ = e2e
    assert len(result.results) == len(golden) == 142


def test_e2e_legacy_settings_reproduce_golden_scores(real_inputs, golden):
    """Full run with the notebook's accidental geometry (600/1000/1200 m buffers, 250/750/1250 m
    decay midpoints) reproduces the golden pop/emp columns exactly and the Monte Carlo score for
    every hub except Netanya (group 25: hand-edited score, terminal tie; see DEVIATIONS.md)."""
    if not (real_inputs.has("taz") and real_inputs.has("bus_terminals")):
        pytest.skip("TAZ or bus terminals layer not present")

    cfg = load_config(None, {"spatial_source": "shapefiles", "influence_rings": "600,1000,1200", "pop_emp_decay_midpoints": "250,750,1250"})
    res = run_pipeline(cfg, real_inputs, RunReport()).results.set_index("group").loc[golden["group"]]
    g = golden.set_index("group")
    legacy_cols = {"pop_0_600": "pop_0_500", "emp_0_600": "emp_0_500", "pop_600_1000": "pop_500_1000", "emp_600_1000": "emp_500_1000", "pop_1000_1200": "pop_1000_1500", "emp_1000_1200": "emp_1000_1500"}
    for ours, theirs in legacy_cols.items():
        assert (res[ours].astype(float) - g[theirs].astype(float)).abs().max() < 1e-6, theirs
    diff = (res["TotalScore_MC"] - g["Average_Simulated_Score"]).abs()
    off = diff.index[diff > 1e-6].tolist()
    print(f"\n[legacy e2e] hubs with a different score: {off}; max diff elsewhere {diff.drop(off).max():.2e}")
    assert set(off) <= {25}
    ok = diff.index.difference(off)
    assert (res.loc[ok, "Overall_Rank"].rank(method="dense") == g.loc[ok, "Overall_Rank"].rank(method="dense")).all()


def test_e2e_h3_base_layer_matches_shapefile_path(e2e, e2e_shp, golden, real_inputs):
    """The default run (H3 base layer, fraction rule) against the polygon stages:
    terminals identical, tiers identical, population/jobs within a few percent,
    ring tags differ only for the hexagons the polygon stage tagged by layer order
    (see docs/H3_BASE_LAYER.md)."""
    if not real_inputs.has("h3_base"):
        pytest.skip("h3_base.parquet not present; run 'hubs prepare-base'")
    ref, _ = e2e_shp
    new, _ = e2e
    a = ref.results.set_index("group").loc[golden["group"]]
    b = new.results.set_index("group").loc[golden["group"]]

    assert (a["HubType"] == b["HubType"]).all()
    assert (a["bus_terminal"].astype(int) == b["bus_terminal"].astype(int)).all()
    assert (a["area"] == b["area"]).all()
    ring_differs = a.index[a["location"].map(str) != b["location"].map(str)].tolist()
    print(f"\n[h3_base] hubs whose ring tag differs: {ring_differs}")
    assert set(ring_differs) <= {303, 524, 546, 630}

    pop_cols = ["pop_0_500", "emp_0_500", "pop_500_1000", "emp_500_1000", "pop_1000_1500", "emp_1000_1500"]
    for col in pop_cols:
        rel = (b[col] - a[col]).abs() / a[col].clip(lower=1.0)
        assert rel.median() < 0.01, col
        assert rel.quantile(0.9) < 0.03, col
    total_a, total_b = a[pop_cols].sum().sum(), b[pop_cols].sum().sum()
    assert abs(total_b / total_a - 1) < 0.005

    diff = (b["TotalScore_MC"] - a["TotalScore_MC"]).abs()
    off = diff.index[diff > 0.05].tolist()
    print(f"[h3_base] hubs whose score moved by more than 0.05: {off}; max elsewhere {diff.drop(off).max():.3f}")
    assert set(off) <= set(ring_differs)


def test_e2e_bus_terminal_matches_golden(e2e, golden, real_inputs):
    """With the terminals layer present, bus_terminal matches except where the notebook's
    duplicate-row spatial join picked a lower class (Netanya, group 25; see DEVIATIONS.md)."""
    if not real_inputs.has("bus_terminals"):
        pytest.skip("bus terminals layer not present")
    result, _ = e2e
    res = result.results.set_index("group").loc[golden["group"]]
    g = golden.set_index("group")
    mism = res.index[res["bus_terminal"].astype(int) != g["bus_terminal"].astype(int)].tolist()
    print(f"\n[bus_terminal] mismatches: {mism}")
    assert set(mism) <= {25}
    assert (res.loc[mism, "bus_terminal"] > g.loc[mism, "bus_terminal"]).all()
