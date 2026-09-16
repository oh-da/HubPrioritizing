"""Input discovery, validation and encoding-aware readers."""

from pathlib import Path

import pandas as pd
import pytest

from src.pipeline.inputs import (
    InputError,
    discover_inputs,
    parse_date_from_name,
    pick_latest,
    read_csv_auto,
    read_shapefile,
    require_valid_inputs,
    validate_inputs,
)

REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"


# ---------------------------------------------------------------------------- dates / picking
@pytest.mark.parametrize(
    "name, expected",
    [
        ("All_nodeslines_18062026.csv", "2026-06-18"),
        ("Lines_and_Planned_Mode_18-06-2026.csv", "2026-06-18"),
        ("Nodes_w_results_04022026.xlsx", "2026-02-04"),
        ("Routes_and_Nodes_07-04-2025.xlsx", "2025-04-07"),
        ("hubs_final_results_20260618_1140.csv", "2026-06-18"),
        ("linesNames_noDuplicates.csv", None),
    ],
)
def test_parse_date_from_name(name, expected):
    assert parse_date_from_name(name) == expected


def test_pick_latest_prefers_name_date_over_mtime(tmp_path):
    old = tmp_path / "All_nodeslines_01012025.csv"
    new = tmp_path / "All_nodeslines_18062026.csv"
    new.write_text("a")
    old.write_text("a")  # written later -> newer mtime, but older name date
    chosen, ignored = pick_latest([old, new])
    assert chosen == new and ignored == (old,)


def test_pick_latest_falls_back_to_mtime(tmp_path):
    import os, time

    a = tmp_path / "linesNames_a.csv"
    b = tmp_path / "linesNames_b.csv"
    a.write_text("a")
    b.write_text("b")
    os.utime(a, (time.time() - 100, time.time() - 100))
    chosen, _ = pick_latest([a, b])
    assert chosen == b


# ---------------------------------------------------------------------------- discovery
def _write_minimal_inputs(d: Path) -> None:
    (d / "All_nodeslines_18062026.csv").write_text("node,LINE_ID,X,Y\n1,L1,180000,665000\n", encoding="utf-8")
    (d / "Lines_and_Planned_Mode_18-06-2026.csv").write_text(
        "Line_ModelName,Mode_Planned,Area\nL1,LRT,Tel Aviv\n", encoding="utf-8"
    )
    pd.DataFrame({"Node": [1], "TotalBoardings": [10], "TotalAlight": [5]}).to_excel(
        d / "Nodes_w_results_04022026.xlsx", sheet_name="Daily_5087", index=False
    )


def test_discover_uses_input_dir_then_reference(tmp_path):
    _write_minimal_inputs(tmp_path)
    inputs = discover_inputs(tmp_path, REFERENCE_DIR)
    assert inputs.path("nodeslines").name == "All_nodeslines_18062026.csv"
    assert inputs.files["metro"].source == "reference"
    assert inputs.files["hub_names"].source == "reference"
    # bus terminals and TAZ are not in the repo yet
    missing = {s.key for s in inputs.missing_required()}
    assert missing == {"bus_terminals", "taz"}


def test_input_dir_overrides_reference_copy(tmp_path):
    _write_minimal_inputs(tmp_path)
    (tmp_path / "is_same_group.csv").write_text("Nodes in group\n\"1, 2\"\n", encoding="utf-8")
    inputs = discover_inputs(tmp_path, REFERENCE_DIR)
    assert inputs.files["is_same_group"].source == "input"
    assert inputs.path("is_same_group").parent == tmp_path


def test_explicit_file_override(tmp_path):
    _write_minimal_inputs(tmp_path)
    pinned = tmp_path / "custom_names.csv"
    pinned.write_text("h3_index,HubNameHE\n8a2db0a52227fff,x\n", encoding="utf-8")
    inputs = discover_inputs(tmp_path, REFERENCE_DIR, {"hub_names": pinned})
    assert inputs.files["hub_names"].source == "override"
    with pytest.raises(InputError):
        discover_inputs(tmp_path, REFERENCE_DIR, {"nope": pinned})


# ---------------------------------------------------------------------------- validation
def test_validate_lists_every_problem_at_once(tmp_path):
    (tmp_path / "All_nodeslines_18062026.csv").write_text("foo,bar\n1,2\n", encoding="utf-8")
    inputs = discover_inputs(tmp_path, tmp_path / "no_reference")
    problems = validate_inputs(inputs)
    text = "\n".join(problems)
    assert "missing required columns ['node', 'LINE_ID']" in text
    assert "'lines_mode'" in text and "'demand'" in text
    assert "'metro'" in text and "'taz'" in text
    assert "nodeslines" in text  # column problem reported alongside missing files
    with pytest.raises(InputError) as exc:
        require_valid_inputs(inputs)
    assert len(exc.value.problems) == len(problems)


def test_validate_passes_for_complete_set(tmp_path):
    _write_minimal_inputs(tmp_path)
    inputs = discover_inputs(tmp_path, REFERENCE_DIR)
    problems = validate_inputs(inputs)
    # only the two layers not yet shipped should be reported
    assert len(problems) == 2
    assert all(("bus_terminals" in p) or ("taz" in p) for p in problems)


# ---------------------------------------------------------------------------- readers
def test_read_csv_auto_detects_cp1255_and_utf8(tmp_path):
    heb = tmp_path / "heb.csv"
    heb.write_bytes("Line_ModelName,Line_Name\nL1,רכבלית\n".encode("cp1255"))
    df, enc = read_csv_auto(heb, hebrew_columns=["Line_Name"])
    assert enc == "cp1255" and df.loc[0, "Line_Name"] == "רכבלית"

    utf = tmp_path / "utf.csv"
    utf.write_text("Line_ModelName,Line_Name\nL1,רכבלית\n", encoding="utf-8-sig")
    df, enc = read_csv_auto(utf, hebrew_columns=["Line_Name"])
    assert enc == "utf-8-sig" and df.loc[0, "Line_Name"] == "רכבלית"


def test_read_shapefile_returns_full_hebrew():
    metro, enc = read_shapefile(REFERENCE_DIR / "metro_2008.shp", hebrew_columns=["METRO_NAME", "ZONE_NAME"])
    assert enc == "cp1255"
    assert set(metro["METRO_NAME"]) == {"באר שבע", "חיפה", "ירושלים", "תל אביב"}
    assert set(metro["ZONE_NAME"]) == {"גלעין", "טבעת פנימית", "טבעת תיכונה", "טבעת חיצונית"}
    assert metro.crs is not None and metro.crs.to_epsg() == 4326

    districts, enc = read_shapefile(REFERENCE_DIR / "Districts.shp", hebrew_columns=["MACHOZ"])
    assert enc == "utf-8"
    assert "מחוז ירושלים" in set(districts["MACHOZ"])


def test_read_shapefile_ignores_wrong_cpg_hint(tmp_path):
    import shutil

    for ext in (".shp", ".shx", ".dbf", ".prj"):
        shutil.copy(REFERENCE_DIR / f"metro_2008{ext}", tmp_path / f"m{ext}")
    (tmp_path / "m.cpg").write_text("UTF-8")  # wrong on purpose: bytes are cp1255
    metro, enc = read_shapefile(tmp_path / "m.shp", hebrew_columns=["METRO_NAME"])
    assert enc == "cp1255" and "תל אביב" in set(metro["METRO_NAME"])


# ---------------------------------------------------------------------------- real samples
def test_real_samples_discover_and_validate(real_fixtures_dir):
    inputs = discover_inputs(real_fixtures_dir, REFERENCE_DIR)
    for key in ("nodeslines", "lines_mode", "demand", "line_names", "line_status", "line_corrections", "routes"):
        assert inputs.has(key), key
    problems = validate_inputs(inputs)
    assert all(("bus_terminals" in p) or ("taz" in p) for p in problems), problems
    df, enc = read_csv_auto(inputs.path("lines_mode"), hebrew_columns=["Line_Name"])
    assert enc == "cp1255" and "Line_ModelName" in df.columns
