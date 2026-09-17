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
