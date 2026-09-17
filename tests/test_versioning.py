"""Run manifests and run-to-run comparison on the synthetic inputs."""

import json

import pandas as pd
import pytest

from src.cli import main
from src.pipeline.inputs import discover_inputs
from src.pipeline.run import run_pipeline, write_outputs
from src.pipeline.settings import load_config
from src.pipeline.versioning import RUN_MANIFEST, compare_runs, default_version, list_runs, match_hubs, read_run_manifest, RunDir
from tests.synthetic import make_synthetic_dirs


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("versions")
    input_dir, ref_dir = make_synthetic_dirs(root / "syn")
    cfg = load_config(None, {"mc_iterations": 100, "apply_eligibility_filter": False, "h3_layer_format": "none"})

    # run A as delivered
    inputs_a = discover_inputs(input_dir, ref_dir)
    write_outputs(run_pipeline(cfg, inputs_a), root / "A", version="A-2030-01-01")

    # run B: hub B's demand doubles, the lone rail node 9 disappears, a new BRT+LRT hub appears
    input_b = root / "syn_b"
    input_b.mkdir()
    for f in input_dir.iterdir():
        (input_b / f.name).write_bytes(f.read_bytes())
    nodes = pd.read_csv(input_b / "All_nodeslines_01012030.csv", encoding="cp1255")
    nodes = nodes[nodes["node"] != 9]
    # inside the synthetic Tel Aviv metro polygon (so its demand model resolves), 600 m from hub B
    extra = pd.DataFrame({"עמודה1": [90, 91, 92, 93], "node": [7, 7, 8, 8], "LINE_ID": ["Yelw-N", "Yelw-S", "Grn1-N", "Grn1-S"], "X": [182600, 182600, 182630, 182630], "Y": [665000, 665000, 665000, 665000]})
    pd.concat([nodes, extra], ignore_index=True).to_csv(input_b / "All_nodeslines_02012030.csv", index=False, encoding="cp1255")
    (input_b / "All_nodeslines_01012030.csv").unlink()
    with pd.ExcelWriter(input_b / "Nodes_w_results_02012030.xlsx") as xw:
        pd.DataFrame(
            {"Node": [1, 2, 3, 4, 5, 7, 8], "TotalBoardings": [30000, 20000, 10000, 1600, 1400, 3000, 3000], "TotalAlight": [30000, 20000, 10000, 1600, 1400, 3000, 3000], "TransferBoardings": [5000, 4000, 0, 0, 0, 0, 0], "TransferAlight": [1000, 0, 0, 0, 0, 0, 0]}
        ).to_excel(xw, sheet_name="Daily_5087", index=False)
    (input_b / "Nodes_w_results_01012030.xlsx").unlink()
    # hub B's manual override must go so the doubled demand shows
    (ref_dir / "manual_demand_updates.csv").write_text("node,total_demand,total_transfers,station_name,notes\n", encoding="utf-8")

    inputs_b = discover_inputs(input_b, ref_dir)
    write_outputs(run_pipeline(cfg, inputs_b), root / "B")  # default version = newest input date
    return root


def test_run_manifest_records_provenance(two_runs):
    m = read_run_manifest(two_runs / "A")
    assert m["version"] == "A-2030-01-01"
    assert set(m["inputs"]) >= {"nodeslines", "lines_mode", "demand", "h3_base"}
    assert len(m["inputs"]["nodeslines"]["sha256"]) == 64
    assert m["base_layer"]["resolution"] == 10 and m["base_layer"]["built"]
    assert m["config"]["mc_iterations"] == 100
    assert m["summary"]["hubs"] == 3 and m["outputs"]["xlsx"] == "hub_prioritization_results.xlsx"
    mb = read_run_manifest(two_runs / "B")
    assert mb["version"] == "2030-01-02"  # newest date among the exports


def test_default_version_from_input_dates(two_runs):
    inputs = discover_inputs(two_runs / "syn" / "input", two_runs / "syn" / "reference")
    assert default_version(inputs) == "2030-01-01"


def test_match_and_compare(two_runs):
    a, b = RunDir(two_runs / "A"), RunDir(two_runs / "B")
    pairs = match_hubs(a, b)
    assert set(pairs["match"]) == {"hub_id", "removed", "added"}
    comp = compare_runs(two_runs / "A", two_runs / "B")
    s = comp["summary"]
    assert s["matched_by_hub_id"] == 2 and s["added"] == 1 and s["removed"] == 1
    assert s["inputs_changed"]["nodeslines"]["status"] == "different file"
    assert s["inputs_changed"]["demand"]["status"] == "different file"
    assert "manual_demand" in s["inputs_changed"]
    assert s["config_changed"] == {}
    t = comp["table"].set_index("match")
    hub_b = comp["table"][(comp["table"]["match"] == "hub_id") & (comp["table"]["TotalDemand_a"] == 2500.0)].iloc[0]
    assert hub_b["TotalDemand_b"] == 6000.0 and hub_b["TotalDemand_delta"] == 3500.0
    assert comp["table"][comp["table"]["match"] == "added"].iloc[0]["TotalDemand_b"] == 12000.0
    assert comp["table"][comp["table"]["match"] == "removed"].iloc[0]["TotalDemand_a"] == 200.0


def test_compare_cli_writes_report_and_list_runs(two_runs, capsys):
    assert main(["compare", str(two_runs / "A"), str(two_runs / "B"), "--out", str(two_runs / "cmp")]) == 0
    out = capsys.readouterr().out
    assert "1 added, 1 removed" in out
    md = (two_runs / "cmp" / "compare_A-2030-01-01_vs_2030-01-02.md").read_text(encoding="utf-8")
    assert "Hubs only in B (added)" in md and "Hubs only in A (removed)" in md and "different file" in md
    table = pd.read_csv(two_runs / "cmp" / "compare_A-2030-01-01_vs_2030-01-02.csv")
    assert {"match", "hub_id_a", "hub_id_b", "TotalScore_MC_delta", "RankByHubTypeMetro_delta"} <= set(table.columns)
    summary = json.loads((two_runs / "cmp" / "compare_A-2030-01-01_vs_2030-01-02.json").read_text(encoding="utf-8"))
    assert summary["added"] == 1

    runs = list_runs(two_runs)
    assert list(runs["version"]) == ["A-2030-01-01", "2030-01-02"]
    assert main(["runs", str(two_runs)]) == 0
    assert "A-2030-01-01" in capsys.readouterr().out
    assert main(["compare", str(two_runs / "nope"), str(two_runs / "B")]) == 1
