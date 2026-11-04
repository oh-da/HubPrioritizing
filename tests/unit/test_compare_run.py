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


def _base_nodes():
    base = [(180000.0 + 500 * i, 665000.0 + 300 * (i % 3)) for i in range(8)]
    return base, pd.DataFrame({
        "node": [str(i) for i in range(8)],
        "x_itm": [x for x, _ in base], "y_itm": [y for _, y in base],
    })


def test_correct_positions_counts_only_nodes_without_any_finite_row():
    from types import SimpleNamespace

    from shapely.geometry import Point

    from src.compare.run import correct_positions
    from src.compare.settings import CompareConfig
    from src.pipeline.report import RunReport

    base, nodes = _base_nodes()
    extra = pd.DataFrame({"node": ["3", "8"], "x_itm": [float("nan")] * 2,
                          "y_itm": [float("nan")] * 2})
    nodes = pd.concat([nodes, extra], ignore_index=True)
    agency = SimpleNamespace(stops=gpd.GeoDataFrame(
        geometry=[Point(x + 40.0, y - 30.0) for x, y in base], crs="EPSG:2039"))
    report = RunReport()
    out, _ = correct_positions(nodes, agency, CompareConfig(), report)
    # the NaN row of node 3 takes node 3's corrected position; node 8 has none and stays NaN
    assert out["x_corr"].iloc[8] == pytest.approx(base[3][0] + 40.0)
    assert pd.isna(out["x_corr"].iloc[9])
    entry = next(e for e in report.entries if e.section == "offset")
    assert entry.data["nodes_left_out"] == 1
    assert report.metrics["offset_estimated"] is True
    assert not [e for e in report.warnings if e.section == "offset"]


def test_offset_that_cannot_be_estimated_is_reported():
    from types import SimpleNamespace

    from shapely.geometry import Point

    from src.compare.run import correct_positions
    from src.compare.settings import CompareConfig
    from src.pipeline.report import RunReport

    _, nodes = _base_nodes()
    # stops in degrees (a CRS mix-up): no node has a stop within stop_tol_m
    agency = SimpleNamespace(stops=gpd.GeoDataFrame(
        geometry=[Point(34.8 + 0.01 * i, 32.0) for i in range(8)], crs="EPSG:2039"))
    report = RunReport()
    out, glob = correct_positions(nodes, agency, CompareConfig(), report)
    assert list(glob) == [0.0, 0.0]
    assert report.metrics["offset_estimated"] is False
    warned = [e for e in report.warnings if e.section == "offset"]
    assert len(warned) == 1 and "not estimated" in warned[0].message
    assert "0 node-stop pair(s)" in warned[0].message


def test_run_table_checks_warn_on_missing_modes_and_empty_tables():
    from src.compare.run import check_run_tables
    from src.pipeline.report import RunReport

    nodes = pd.DataFrame({"node": ["1", "2", "3"], "LINE_ID": ["A", "A", "B"],
                          "Mode_Planned": ["LRT", None, "  "]})
    report = RunReport()
    check_run_tables(pd.DataFrame({"group": [1]}), nodes, report)
    msgs = [e.message for e in report.warnings]
    assert any("2 node x line row(s) without a mode" in m for m in msgs), msgs

    report = RunReport()
    check_run_tables(pd.DataFrame(columns=["group"]), nodes.iloc[:0], report)
    msgs = " | ".join(e.message for e in report.warnings)
    assert "hub_groups_all.csv has no rows" in msgs and "network_nodes.csv has no rows" in msgs


def test_console_summary_says_when_the_offset_was_not_estimated(capsys):
    from types import SimpleNamespace

    from src.compare.run import _print_summary
    from src.compare.settings import CompareConfig
    from src.pipeline.report import RunReport

    def result(estimated):
        return SimpleNamespace(
            routes=SimpleNamespace(routes=pd.DataFrame({"status": []})),
            hubs=SimpleNamespace(hubs=pd.DataFrame({"relation": []})),
            global_shift=(0.0, 0.0), inputs={"run": {"version": "v"}}, report=RunReport(),
            cfg=CompareConfig(), offset_estimated=estimated)

    _print_summary(result(False), {})
    assert "offset : not estimated" in capsys.readouterr().out
    _print_summary(result(True), {})
    assert "offset : applied" in capsys.readouterr().out


def test_agency_types_missing_from_the_mode_map_are_reported():
    from src.compare.modes import load_mode_map
    from src.compare.run import check_agency_types
    from src.pipeline.report import RunReport

    routes = pd.DataFrame({"type": ["LRT", "Tram", "Tram", "rail", "BRT"]})
    report = RunReport()
    check_agency_types(routes, load_mode_map(), report)
    warned = [e for e in report.warnings if e.section == "modes"]
    assert len(warned) == 1
    # exact, case-sensitive compare: 'rail' is not 'Rail'
    assert "Tram (2 routes)" in warned[0].message and "rail (1 route)" in warned[0].message
    assert "LRT" not in warned[0].message and "BRT" not in warned[0].message

    report = RunReport()
    check_agency_types(pd.DataFrame({"type": ["LRT", "Rail fast", "FUNI"]}), load_mode_map(),
                       report)
    assert not report.warnings
