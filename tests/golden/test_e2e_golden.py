"""Full pipeline on the real exports vs the golden workbook.

The bus-terminal and TAZ layers are not in the repository yet, so the terminal and
population/jobs criteria (and therefore the Monte Carlo scores) cannot be reproduced
here; everything upstream of them is compared.
"""

import pandas as pd
import pytest

from src.pipeline.report import RunReport
from src.pipeline.run import run_pipeline
from src.pipeline.settings import PipelineConfig
from tests.golden.conftest import parse_listish


@pytest.fixture(scope="module")
def e2e(real_inputs):
    report = RunReport()
    result = run_pipeline(PipelineConfig(), real_inputs, report, allow_missing_layers=True)
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
