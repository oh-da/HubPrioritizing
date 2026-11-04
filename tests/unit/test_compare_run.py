"""End-to-end test of ``hubs compare-network`` on the synthetic run and agency network."""

from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd
import pytest

from src.cli import main
from src.compare.export import LAYER_NAMES, SHEET_NAMES
from src.pipeline.inputs import discover_inputs
from src.pipeline.run import run_pipeline, write_outputs
from src.pipeline.settings import load_config
from tests.synthetic import make_synthetic_dirs
from tests.synthetic_agency import make_agency_gpkg, make_metadata_xlsx

OUTPUTS = (
    "network_comparison.xlsx", "network_comparison.gpkg", "network_comparison_routes.html",
    "network_comparison_hubs.html", "compare_config.json", "compare_report.md",
    "compare_report.json",
)


@pytest.fixture(scope="module")
def compared(tmp_path_factory):
    root = tmp_path_factory.mktemp("compare_run")
    input_dir, ref_dir = make_synthetic_dirs(root)
    cfg = load_config(None, {"mc_iterations": 50})
    run_dir = root / "run"
    write_outputs(run_pipeline(cfg, discover_inputs(input_dir, ref_dir)), run_dir)
    gpkg = make_agency_gpkg(root / "MT_Network.gpkg")
    meta = make_metadata_xlsx(root / "MT_Network_MetaData.xlsx")
    codes = []
    for out in ("out1", "out2"):
        codes.append(main([
            "compare-network", "--run", str(run_dir), "--agency-gpkg", str(gpkg),
            "--agency-meta", str(meta), "--out", str(root / out),
        ]))
    return codes, run_dir, root / "out1", root / "out2"


def _sheets(path):
    return pd.read_excel(path, sheet_name=None, dtype=object)


def _node9_group(run_dir) -> int:
    nn = pd.read_csv(run_dir / "network_nodes.csv", encoding="utf-8-sig")
    return int(nn.loc[nn["node"] == 9, "group"].iloc[0])


def test_compare_network_end_to_end(compared, capsys):
    codes, run_dir, out1, out2 = compared
    assert codes == [0, 0]
    for name in OUTPUTS:
        assert (out1 / name).exists(), name

    sheets = _sheets(out1 / "network_comparison.xlsx")
    assert list(sheets) == list(SHEET_NAMES)

    routes = sheets["routes"]
    red = routes[routes["our_route_key"] == "Red-N+Red-S"].iloc[0]
    assert red["status"] == "matched" and red["agency_route_key"] == "LRT:1001"

    agency_only = sheets["hubs_agency_only"]
    assert len(agency_only) == 1 and int(agency_only["agency_hub_id"].iloc[0]) == 7

    hubs = sheets["hubs"]
    b = hubs[hubs["agency_hub_id"].astype(float) == 102]
    assert len(b) == 1 and b["relation"].iloc[0] == "1:1"
    assert str(b["eligible"].iloc[0]).lower() == "true"
    assert pd.notna(b["TotalScore_MC"].iloc[0])
    assert hubs["agency_total_demand"].isna().all()

    ours_only = sheets["hubs_ours_only"]
    rail = ours_only[ours_only["group"].astype(int) == _node9_group(run_dir)]
    assert len(rail) == 1
    assert str(rail["eligible"].iloc[0]).lower() == "false"
    assert isinstance(rail["exclusion_reason"].iloc[0], str) and rail["exclusion_reason"].iloc[0]

    run_row = sheets["inputs"][sheets["inputs"]["input"] == "run"]
    assert len(run_row) == 1
    files = sheets["inputs"].set_index("input")
    assert len(str(files.loc["hub_groups_all", "sha256"])) == 64

    cfg = json.loads((out1 / "compare_config.json").read_text(encoding="utf-8"))
    assert cfg["apply_offset"] is True and cfg["hub_match_tol_m"] == 400.0
    report = json.loads((out1 / "compare_report.json").read_text(encoding="utf-8"))
    assert "offset_global_dx_m" in report["metrics"]


def test_compare_network_is_deterministic(compared):
    _, _, out1, out2 = compared
    for name in ("compare_config.json", "network_comparison_routes.html",
                 "network_comparison_hubs.html"):
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes(), name
    s1, s2 = _sheets(out1 / "network_comparison.xlsx"), _sheets(out2 / "network_comparison.xlsx")
    for name in SHEET_NAMES:
        pd.testing.assert_frame_equal(s1[name], s2[name], obj=name)
    for layer in LAYER_NAMES:
        a = gpd.read_file(out1 / "network_comparison.gpkg", layer=layer)
        b = gpd.read_file(out2 / "network_comparison.gpkg", layer=layer)
        pd.testing.assert_frame_equal(pd.DataFrame(a), pd.DataFrame(b), obj=layer)
    r1 = json.loads((out1 / "compare_report.json").read_text(encoding="utf-8"))
    r2 = json.loads((out2 / "compare_report.json").read_text(encoding="utf-8"))
    r1.pop("started_at"), r2.pop("started_at")
    assert r1 == r2


def test_out_defaults_to_run_dir(tmp_path):
    from src.compare.run import compare_networks, write_comparison
    from src.compare.settings import CompareConfig

    input_dir, ref_dir = make_synthetic_dirs(tmp_path)
    run_dir = tmp_path / "run"
    write_outputs(run_pipeline(load_config(None, {"mc_iterations": 50}),
                               discover_inputs(input_dir, ref_dir)), run_dir)
    gpkg = make_agency_gpkg(tmp_path / "MT_Network.gpkg")
    assert main(["compare-network", "--run", str(run_dir), "--agency-gpkg", str(gpkg),
                 "--set", "apply_offset=false"]) == 0
    assert (run_dir / "network_comparison.xlsx").exists()
    cfg = json.loads((run_dir / "compare_config.json").read_text(encoding="utf-8"))
    assert cfg["apply_offset"] is False

    result = compare_networks(run_dir, gpkg, CompareConfig(apply_offset=False))
    nodes = result.ours.nodes
    assert "x_corr" not in nodes.columns or nodes["x_corr"].equals(nodes["x_itm"])
    paths = write_comparison(result, tmp_path / "direct")
    assert {p.name for p in paths.values()} >= set(OUTPUTS)


def test_correct_positions_skips_non_finite_points():
    from types import SimpleNamespace

    from shapely.geometry import Point

    from src.compare.run import correct_positions
    from src.compare.settings import CompareConfig
    from src.pipeline.report import RunReport

    base = [(180000.0 + 500 * i, 665000.0 + 300 * (i % 3)) for i in range(8)]
    nodes = pd.DataFrame({
        "node": [str(i) for i in range(8)] + ["8", "8"],
        "x_itm": [x for x, _ in base] + [float("nan"), float("nan")],
        "y_itm": [y for _, y in base] + [float("nan"), float("nan")],
    })
    stops = [Point(x + 40.0, y - 30.0) for x, y in base] + [Point(float("nan"), float("nan"))]
    agency = SimpleNamespace(stops=gpd.GeoDataFrame(geometry=stops, crs="EPSG:2039"))
    report = RunReport()
    out, glob = correct_positions(nodes, agency, CompareConfig(), report)
    assert glob == pytest.approx([40.0, -30.0])
    assert (out["x_corr"].iloc[:8] - out["x_itm"].iloc[:8]).tolist() == pytest.approx([40.0] * 8)
    assert out["x_corr"].iloc[8:].isna().all()
    assert report.metrics["offset_global_dx_m"] == 40.0
