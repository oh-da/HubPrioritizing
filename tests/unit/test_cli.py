from pathlib import Path

import pandas as pd

from src.cli import main

REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"


def test_show_config_defaults(capsys):
    assert main(["show-config", "--defaults"]) == 0
    out = capsys.readouterr().out
    assert "mc_iterations: 10000" in out


def test_show_config_with_set(capsys):
    assert main(["show-config", "--set", "mc_iterations=5"]) == 0
    assert '"mc_iterations": 5' in capsys.readouterr().out


def test_validate_reports_problems_and_exit_code(tmp_path, capsys):
    (tmp_path / "All_nodeslines_18062026.csv").write_text("node,LINE_ID,X,Y\n1,L1,1,1\n")
    code = main(["validate", "--input-dir", str(tmp_path), "--reference-dir", str(REFERENCE_DIR)])
    out = capsys.readouterr().out
    assert code == 1
    assert "lines_mode" in out and "(not found)" in out
    assert "problem(s)" in out


def test_validate_bad_set_value_exits(tmp_path):
    import pytest

    with pytest.raises(SystemExit):
        main(["validate", "--input-dir", str(tmp_path), "--set", "mc_iterations=abc"])


def test_cli_parser_has_compare_network():
    from src.cli import build_parser
    from src.compare.settings import COMPARE_KEYS

    parser = build_parser()
    args = parser.parse_args(["compare-network", "--run", "R", "--agency-gpkg", "A.gpkg"])
    assert args.command == "compare-network"
    assert args.run == Path("R") and args.agency_gpkg == Path("A.gpkg")
    assert args.out is None and args.agency_meta is None and args.tod_gpkg is None
    assert args.set == [] and args.config is None
    sub = next(a for a in parser._actions if a.dest == "command").choices["compare-network"]
    help_text = sub.format_help()
    assert all(key in help_text for key in COMPARE_KEYS)


def test_missing_run_files_exit_1_with_message(tmp_path, capsys):
    gpkg = tmp_path / "MT_Network.gpkg"
    gpkg.write_bytes(b"")
    code = main(["compare-network", "--run", str(tmp_path), "--agency-gpkg", str(gpkg)])
    out = capsys.readouterr().out
    assert code == 1
    assert "re-run `hubs run` with this version" in out
    assert "hub_groups_all.csv" in out and "network_nodes.csv" in out


def test_bad_gpkg_exits_1_with_problems(tmp_path, capsys):
    (tmp_path / "hub_groups_all.csv").write_text("group\n1\n", encoding="utf-8-sig")
    (tmp_path / "network_nodes.csv").write_text("node,LINE_ID\n", encoding="utf-8-sig")
    code = main(["compare-network", "--run", str(tmp_path), "--agency-gpkg",
                 str(tmp_path / "missing.gpkg")])
    out = capsys.readouterr().out
    assert code == 1 and "missing.gpkg" in out


def test_bad_set_value_exits(tmp_path):
    import pytest

    with pytest.raises(SystemExit):
        main(["compare-network", "--run", str(tmp_path), "--agency-gpkg", "x.gpkg",
              "--set", "route_tol_m=abc"])
