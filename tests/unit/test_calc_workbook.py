"""The calculation workbook: structure always, formula values when LibreOffice is available."""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest
from openpyxl import load_workbook

from src.config import MODE_LINE_COLS, TIER_NATIONAL
from src.pipeline.calc_workbook import FIRST_ROW, mc_blocks, write_calculation_workbook
from src.pipeline.postprocess import rank_by_hubtype_metro
from src.pipeline.scoring import draw_weight_matrix, score_hubs
from src.pipeline.settings import load_config

SHEETS = ["README", "Parameters", "1_Eligibility", "2_Location", "3_Service", "4_Demand", "5_PopJobs", "6_BusTerminal",
          "7_MC_Weights", "8_FinalScore", "9_Ranking", "Hub_Explorer", "Checks", "7b_MC_Draws"]


def _groups(n: int = 60, seed: int = 3) -> pd.DataFrame:
    rs = np.random.RandomState(seed)
    modes_all = ["HighSpeed Rail", "Interurban Rail", "Suburban Rail", "Metro", "LRT", "BRT"]
    rows = []
    for g in range(n):
        modes = list(rs.choice(modes_all, rs.randint(1, 4), replace=False))
        r = {"group": g, "Mode_Planned": modes, "area": rs.choice(["תל אביב", "חיפה", "באר שבע"]),
             "location": [rs.choice(["גלעין", "טבעת", "חוץ"])], "TotalDemand": float(10 ** rs.uniform(2.5, 5.3)),
             "bus_terminal": int(rs.randint(0, 4))}
        total = 0.0
        for c in MODE_LINE_COLS:
            v = float(rs.randint(1, 5) * 2) if c[: -len(" Lines")] in modes else 0.0
            r[c] = v
            total += v
        r["Line_Unique"] = [f"L{g}_{i}" for i in range(int(total))]
        for a, b in ((0, 500), (500, 1000), (1000, 1500)):
            r[f"pop_{a}_{b}"] = float(rs.uniform(0, 3e4))
            r[f"emp_{a}_{b}"] = float(rs.uniform(0, 5e4))
        rows.append(r)
    return pd.DataFrame(rows)


@pytest.fixture
def run(tmp_path):
    groups = _groups()
    cfg = load_config(None, {"mc_iterations": 200})
    scored = score_hubs(groups, n_iter=cfg.mc_iterations, seed=cfg.mc_seed, scope=cfg.mc_scope)
    results = scored.assign(TotalScore_MC=scored["Average_Simulated_Score"], Metro=scored["area"], HubNameHE=[f"מתחם {g}" for g in scored["group"]])
    results["RankByHubTypeMetro"] = rank_by_hubtype_metro(results)
    path = write_calculation_workbook(groups, scored, results, cfg, tmp_path / "calc.xlsx", "test")
    return groups, scored, results, cfg, path


def test_mc_blocks_reproduce_the_run_weights():
    groups = _groups(30)
    cfg = load_config(None, {"mc_iterations": 50})
    scored = score_hubs(groups, n_iter=50, seed=cfg.mc_seed)
    rng = np.random.RandomState(cfg.mc_seed)
    for name, raw in mc_blocks(scored, cfg):
        expected = draw_weight_matrix(rng, 50)
        np.testing.assert_allclose(raw / raw.sum(axis=1, keepdims=True), expected)
        assert raw.max() <= 0.5
    # the average-weight shortcut equals the Monte Carlo mean
    blocks = dict(mc_blocks(scored, cfg))
    for t, sub in scored.groupby("HubType"):
        w = blocks[str(t)]
        w = (w / w.sum(axis=1, keepdims=True)).mean(axis=0)
        x = sub[["RegionLocation_Norm", "bus_terminal_Norm", "score_Norm", "TotalDemand_Norm", "PopEmp_Score_Norm"]].to_numpy()
        np.testing.assert_allclose(x @ w, sub["Average_Simulated_Score"].to_numpy(), rtol=1e-12)


def test_workbook_structure(run):
    groups, scored, _, cfg, path = run
    wb = load_workbook(path)
    assert wb.sheetnames == SHEETS
    for name in ("MinPassengers", "NationalMinDemand", "ModeAlpha", "DecayBeta", "CenterKeywords", "MC_WeightTable"):
        assert name in wb.defined_names
    assert wb["1_Eligibility"].max_row == FIRST_ROW - 1 + len(groups)
    assert wb["8_FinalScore"].max_row == FIRST_ROW - 1 + len(scored)
    assert wb["7b_MC_Draws"].max_row == 4 + cfg.mc_iterations
    # derived values are formulas, not numbers
    fs = wb["8_FinalScore"]
    header = {c.value: c.column for c in fs[FIRST_ROW - 1]}
    assert str(fs.cell(FIRST_ROW, header["TOTAL SCORE (TotalScore_MC)"]).value).startswith("=SUM(")
    assert TIER_NATIONAL in str(fs.cell(FIRST_ROW, header["RANK (RankByHubTypeMetro)"]).value)
    assert str(wb["2_Location"].cell(FIRST_ROW, 11).value).startswith("=IF(")
    assert "MINIFS" in str(wb["4_Demand"].cell(FIRST_ROW, 6).value)


def test_settings_switch_off(tmp_path):
    cfg = load_config(None, {"calc_workbook_basename": ""})
    assert cfg.calc_workbook_basename == ""


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice not installed")
def test_formulas_reproduce_pipeline_values(run, tmp_path):
    _, scored, results, _, path = run
    out = tmp_path / "recalc"
    subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(out), str(path)],
                   check=True, capture_output=True, timeout=300)
    wb = load_workbook(out / path.name, data_only=True)
    ck = wb["Checks"]
    assert ck["K3"].value < 1e-9  # largest score difference
    assert ck["O3"].value == 0  # rank mismatches
    assert ck["S3"].value == 0  # hub type mismatches
    fs = wb["8_FinalScore"]
    header = {c.value: c.column for c in fs[FIRST_ROW - 1]}
    book = pd.DataFrame({
        "group": [fs.cell(r, 1).value for r in range(FIRST_ROW, FIRST_ROW + len(scored))],
        "overall": [fs.cell(r, header["Overall rank (Rank_TS_MC)"]).value for r in range(FIRST_ROW, FIRST_ROW + len(scored))],
        "by_type": [fs.cell(r, header["Rank within hub type"]).value for r in range(FIRST_ROW, FIRST_ROW + len(scored))],
    }).merge(scored[["group", "Overall_Rank", "Rank_within_HubType"]], on="group")
    assert (book["overall"] == book["Overall_Rank"]).all()
    assert (book["by_type"] == book["Rank_within_HubType"]).all()
    el = wb["1_Eligibility"]
    eligible = [el.cell(r, 1).value for r in range(FIRST_ROW, el.max_row + 1) if el.cell(r, 17).value is True]
    assert sorted(eligible) == sorted(scored["group"])
