"""Fixtures over the real sample inputs and the golden workbook (skipped when absent)."""

import ast
import re
from pathlib import Path

import pandas as pd
import pytest

from src.pipeline.inputs import discover_inputs, read_csv_auto

REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"


@pytest.fixture(scope="session")
def real_inputs(request):
    real_dir = Path(__file__).resolve().parents[1] / "fixtures" / "real"
    if not real_dir.exists() or not any(real_dir.glob("All_nodeslines*.csv")):
        pytest.skip("real fixtures not present")
    return discover_inputs(real_dir, REFERENCE_DIR)


@pytest.fixture(scope="session")
def golden(real_inputs) -> pd.DataFrame:
    path = real_inputs.input_dir / "golden_hub_prioritization_results.xlsx"
    if not path.exists():
        pytest.skip("golden workbook not present")
    return pd.read_excel(path)


_QUOTED = re.compile(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"")


def parse_listish(value) -> list:
    """Parse the notebook's stringified (possibly nested) lists into a flat list of tokens.

    Handles ``"['Metro', 'HighSpeed Rail']"`` (tokens with spaces) and the CSV round-trip
    artifact ``'["[\\'a\\' \\'b\\']", "[\\'c\\']"]'`` (a list of stringified lists).
    """
    if isinstance(value, list):
        return value
    if pd.isna(value):
        return []
    try:
        outer = ast.literal_eval(str(value))
    except (ValueError, SyntaxError):
        outer = [value]
    if not isinstance(outer, list):
        outer = [outer]
    out: list[str] = []
    for el in outer:
        s = str(el)
        if s.startswith("[") and ("'" in s or '"' in s):
            out.extend(a or b for a, b in _QUOTED.findall(s))
        else:
            out.append(s.strip())
    return [t for t in out if t]


@pytest.fixture(scope="session")
def golden_groups(golden) -> dict[int, frozenset[int]]:
    """group -> frozenset of node ids as in the golden workbook."""
    return {int(g): frozenset(int(n) for n in parse_listish(nodes)) for g, nodes in zip(golden["group"], golden["node"])}


@pytest.fixture(scope="session")
def real_lines_mode(real_inputs):
    df, _ = read_csv_auto(real_inputs.path("lines_mode"), hebrew_columns=["Line_Name"])
    return df


@pytest.fixture(scope="session")
def real_nodeslines(real_inputs):
    df, _ = read_csv_auto(real_inputs.path("nodeslines"))
    return df
