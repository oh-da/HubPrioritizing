"""``scripts/export_shapefiles.py`` on a small hand-written run folder.

The script is not part of a package, so it is loaded by path. The repo's synthetic pipeline run
only has single-node lines, so the run folder is written by hand: three hubs, four lines (two
with several nodes, one with two, one with a single node), Hebrew names, a lines file in CP1255.
"""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from geopandas.testing import assert_geodataframe_equal

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_shapefiles.py"

# line -> nodes (node, group, x_itm, y_itm); file order is scrambled on purpose
NODES = {
    "L1": [(14, 2, 183000.0, 650000.0), (11, 1, 180000.0, 650000.0),
           (13, 2, 182000.0, 650000.0), (12, 1, 181000.0, 650000.0)],
    "L2": [(22, 3, 181000.0, 652000.0), (21, 1, 180000.0, 651000.0),
           (23, 3, 182000.0, 653000.0)],
    "L3": [(31, 2, 183000.0, 651000.0), (32, 2, 183500.0, 651000.0)],
    "L4": [(41, 3, 182000.0, 654000.0)],
}
MODES = {"L1": "LRT", "L2": "BRT", "L3": "Metro", "L4": "BRT"}
HUB_LINES = {1: ["L1", "L2"], 2: ["L1", "L3"], 3: ["L4", "L2"]}
HUB_NAMES = {1: "תחנה מרכזית", 2: "צומת הדרום", 3: "קניון הצפון"}
HUB_TYPES = {1: "ארצי", 2: "מטרופוליני", 3: "Not Hub"}
LINE_NAMES = {"L1": "קו אדום", "L2": "קו 1", "L3": "מטרו דן", "L4": "קו 4", "L9": "קו לא בשימוש"}


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("export_shapefiles", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _results(script) -> pd.DataFrame:
    rows = []
    for g, lines in HUB_LINES.items():
        row = {src: 1.5 for src in script.HUB_FIELDS
               if src not in script.DERIVED_FIELDS}
        row.update({
            "group": g, "x": 34.8 + g / 100, "y": 32.0 + g / 100, "Line_Unique": str(lines),
            "HubNameHE": HUB_NAMES[g], "HubTypeHE": HUB_TYPES[g], "area": "תל אביב",
            "Metro": "גוש דן", "location": "['גלעין']", "Mode_Planned": str(["LRT", "BRT"]),
            "Modes_ForPlot": "רק\"ל, BRT", "Num_Modes": 2, "bus_terminal": 2, "Rank_TS_MC": g,
            "Rank_within_HubType": 1, "RankByHubTypeMetro": 1,
        })
        rows.append(row)
    return pd.DataFrame(rows)


def _nodes() -> pd.DataFrame:
    rows = []
    for lid, nodes in NODES.items():
        for node, group, x, y in nodes:
            rows.append({"node": node, "LINE_ID": lid, "line_name": None,
                         "Mode_Planned": MODES[lid], "x_itm": x, "y_itm": y, "group": group,
                         "hub_id": f"H{group:010d}"})
    rows.append(dict(rows[0]))  # the same node x line twice: counted once
    return pd.DataFrame(rows)


def _write_run(root: Path, script, manifest: dict | None = None) -> Path:
    run = root / "run"
    run.mkdir()
    _results(script).to_csv(run / "hub_prioritization_results.csv", index=False,
                            encoding="utf-8-sig")
    pd.DataFrame({"group": list(HUB_LINES), "hub_id": [f"H{g:010d}" for g in HUB_LINES]}).to_csv(
        run / "hub_identity.csv", index=False, encoding="utf-8-sig")
    _nodes().to_csv(run / "network_nodes.csv", index=False, encoding="utf-8-sig")
    if manifest is not None:
        (run / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run


def _write_lines_file(path: Path) -> Path:
    frame = pd.DataFrame({
        "Line_ModelName": list(LINE_NAMES),
        "Mode_Planned": ["LRT", "BRT", "Metro", "BRT", "BRT"],
        "Line_Name": list(LINE_NAMES.values()),
        "Line_Description": ["א-ב", "ב-ג", "ג-ד", "ד-ה", "ה-ו"],
        "Area": ["Tel Aviv"] * 5,
    })
    frame.to_csv(path, index=False, encoding="cp1255")
    return path


@pytest.fixture(scope="module")
def exported(tmp_path_factory, script):
    root = tmp_path_factory.mktemp("export_shapefiles")
    run = _write_run(root, script)
    lines_file = _write_lines_file(root / "Lines_and_Planned_Mode_T.csv")
    out = root / "out"
    code = script.main(["--run-dir", str(run), "--lines-file", str(lines_file),
                        "--out-dir", str(out), "--version", "T1"])
    return {"code": code, "run": run, "lines_file": lines_file, "out": out, "root": root}


def test_exit_code_and_packages(exported):
    assert exported["code"] == 0
    for pkg in ("pkg_hubs", "pkg_lines"):
        assert (exported["out"] / pkg).is_dir()


@pytest.mark.parametrize("tag,crs", [("itm", 2039), ("wgs84", 4326)])
def test_hubs_layer(exported, script, tag, crs):
    layer = gpd.read_file(exported["out"] / "pkg_hubs" / f"hubs_{tag}.shp", encoding="utf-8")
    res = _results(script)
    assert len(layer) == len(res)
    assert layer.crs.to_epsg() == crs
    assert (layer.geometry.geom_type == "Point").all()
    assert list(layer["HubTypeHE"]) == list(res["HubTypeHE"])
    assert list(layer["name_he"]) == list(res["HubNameHE"])  # Hebrew round-trip
    assert list(layer["NumLines"]) == [2, 2, 2]
    assert list(layer["location"]) == ["גלעין"] * 3


def test_hub_fields_are_all_in_the_dbf(exported):
    pkg = exported["out"] / "pkg_hubs"
    fmap = pd.read_csv(pkg / "field_map_hubs.csv", encoding="utf-8-sig")
    layer = gpd.read_file(pkg / "hubs_itm.shp", encoding="utf-8")
    assert set(fmap["shapefile_field"]) == set(layer.columns) - {"geometry"}
    for tag in ("itm", "wgs84"):
        cols = gpd.read_file(pkg / f"hubs_{tag}.shp", encoding="utf-8").columns
        assert all(len(c) <= 10 for c in cols)
    assert list(fmap.columns) == ["shapefile_field", "source_column", "description"]


def test_hub_lines_csv(exported):
    table = pd.read_csv(exported["out"] / "pkg_hubs" / "hub_lines.csv", encoding="utf-8-sig")
    assert len(table) == sum(len(v) for v in HUB_LINES.values())
    row = table[(table["group"] == 3) & (table["LINE_ID"] == "L4")].iloc[0]
    assert row["LineName"] == "קו 4" and row["Mode"] == "BRT"
    assert row["HubNameHE"] == HUB_NAMES[3]


@pytest.mark.parametrize("tag,crs", [("itm", 2039), ("wgs84", 4326)])
def test_lines_layer(exported, tag, crs):
    pkg = exported["out"] / "pkg_lines"
    lines = gpd.read_file(pkg / f"lines_{tag}.shp", encoding="utf-8")
    assert lines.crs.to_epsg() == crs
    assert sorted(lines["LINE_ID"]) == ["L1", "L2", "L3"]  # L4 has one node
    assert (lines.geometry.geom_type == "LineString").all()
    assert dict(zip(lines["LINE_ID"], lines["NumNodes"])) == {"L1": 4, "L2": 3, "L3": 2}
    assert set(lines["LineName"]) == {"קו אדום", "קו 1", "מטרו דן"}
    assert all(len(c) <= 10 for c in lines.columns)


def test_line_geometry_follows_the_nodes(exported):
    lines = gpd.read_file(exported["out"] / "pkg_lines" / "lines_itm.shp", encoding="utf-8")
    l1 = lines[lines["LINE_ID"] == "L1"].geometry.iloc[0]
    xs = [c[0] for c in l1.coords]
    assert xs == sorted(xs) or xs == sorted(xs, reverse=True)  # scrambled input, ordered path
    assert lines[lines["LINE_ID"] == "L1"]["LengthKm"].iloc[0] == 3.0


def test_lines_without_geometry(exported):
    pkg = exported["out"] / "pkg_lines"
    table = pd.read_csv(pkg / "lines_without_geometry.csv", encoding="utf-8-sig")
    assert list(table["LINE_ID"]) == ["L4"]
    attrs = pd.read_csv(pkg / "lines_attributes.csv", encoding="utf-8-sig")
    assert sorted(attrs["LINE_ID"]) == ["L1", "L2", "L3"]


@pytest.mark.parametrize("tag,crs", [("itm", 2039), ("wgs84", 4326)])
def test_nodes_layer_has_a_sequence_per_line(exported, tag, crs):
    nodes = gpd.read_file(exported["out"] / "pkg_lines" / f"line_nodes_{tag}.shp",
                          encoding="utf-8")
    assert nodes.crs.to_epsg() == crs
    assert len(nodes) == sum(len(v) for v in NODES.values())  # the duplicate row is dropped
    for lid, grp in nodes.groupby("LINE_ID"):
        assert sorted(grp["Seq"]) == list(range(1, len(NODES[lid]) + 1))
    assert all(len(c) <= 10 for c in nodes.columns)


def test_readmes_are_generic(exported):
    hubs = (exported["out"] / "pkg_hubs" / "README.txt").read_text(encoding="utf-8")
    lines = (exported["out"] / "pkg_lines" / "README.txt").read_text(encoding="utf-8")
    assert "T1" in hubs and "T1" in lines
    assert "3 hubs" in hubs and "hub_groups_all.csv" in hubs and "UTF-8" in hubs
    assert "HubTypeHE" in hubs and "ארצי" in hubs
    assert "IMPORTANT" in lines and "visual aid" in lines and "1 lines" in lines
    for text in (hubs, lines):
        assert "V1.1" not in text and "commit" not in text


def test_zips_hold_the_expected_files(exported):
    out = exported["out"]
    for pkg, zname in (("pkg_hubs", "hubs_hubprioritizing_T1_shp.zip"),
                       ("pkg_lines", "lines_hubprioritizing_T1_shp.zip")):
        with zipfile.ZipFile(out / zname) as z:
            assert sorted(z.namelist()) == sorted(p.name for p in (out / pkg).iterdir())
    with zipfile.ZipFile(out / "hubs_hubprioritizing_T1_shp.zip") as z:
        assert {"hubs_itm.shp", "hubs_itm.cpg", "hubs_wgs84.dbf", "hub_lines.csv",
                "field_map_hubs.csv", "README.txt"} <= set(z.namelist())


def test_second_run_is_identical(exported, script, tmp_path):
    again = tmp_path / "again"
    code = script.main(["--run-dir", str(exported["run"]), "--lines-file",
                        str(exported["lines_file"]), "--out-dir", str(again), "--version", "T1"])
    assert code == 0
    first = exported["out"]
    for pkg, stems in (("pkg_hubs", ["hubs_itm", "hubs_wgs84"]),
                       ("pkg_lines", ["lines_itm", "lines_wgs84", "line_nodes_itm",
                                      "line_nodes_wgs84"])):
        for stem in stems:
            a = gpd.read_file(first / pkg / f"{stem}.shp", encoding="utf-8")
            b = gpd.read_file(again / pkg / f"{stem}.shp", encoding="utf-8")
            assert_geodataframe_equal(a, b)
    for pkg, name in (("pkg_hubs", "hub_lines.csv"), ("pkg_hubs", "field_map_hubs.csv"),
                      ("pkg_hubs", "README.txt"), ("pkg_lines", "lines_attributes.csv"),
                      ("pkg_lines", "lines_without_geometry.csv"), ("pkg_lines", "README.txt")):
        assert (first / pkg / name).read_bytes() == (again / pkg / name).read_bytes()


def test_no_zip_writes_no_zip(exported, script, tmp_path):
    out = tmp_path / "nozip"
    code = script.main(["--run-dir", str(exported["run"]), "--lines-file",
                        str(exported["lines_file"]), "--out-dir", str(out), "--no-zip"])
    assert code == 0
    assert list(out.glob("*.zip")) == []
    assert (out / "pkg_hubs" / "hubs_itm.shp").exists()


def test_defaults_come_from_the_manifest(tmp_path, script):
    """No --lines-file / --out-dir / --version: the manifest supplies file and label."""
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    lines_file = _write_lines_file(inputs / "Lines_and_Planned_Mode_M.csv")
    manifest = {"version": "M7", "input_dir": str(inputs),
                "inputs": {"lines_mode": {"file": lines_file.name},
                           "nodeslines": {"file": "All_nodes_M.csv"}}}
    run = _write_run(tmp_path, script, manifest)
    assert script.main(["--run-dir", str(run)]) == 0
    out = run / "shapefiles"
    assert (out / "hubs_hubprioritizing_M7_shp.zip").exists()
    readme = (out / "pkg_hubs" / "README.txt").read_text(encoding="utf-8")
    assert "M7" in readme and "All_nodes_M.csv" in readme


def test_version_falls_back_to_the_run_folder_name(tmp_path, script):
    run = _write_run(tmp_path, script)
    lines_file = _write_lines_file(tmp_path / "lines.csv")
    assert script.main(["--run-dir", str(run), "--lines-file", str(lines_file)]) == 0
    assert (run / "shapefiles" / "hubs_hubprioritizing_run_shp.zip").exists()


@pytest.mark.parametrize("missing", ["hub_prioritization_results.csv", "hub_identity.csv",
                                     "network_nodes.csv"])
def test_missing_run_file_exits_1_and_names_it(tmp_path, script, capsys, missing):
    run = _write_run(tmp_path, script)
    (run / missing).unlink()
    lines_file = _write_lines_file(tmp_path / "lines.csv")
    code = script.main(["--run-dir", str(run), "--lines-file", str(lines_file),
                        "--out-dir", str(tmp_path / "out")])
    err = capsys.readouterr().err
    assert code == 1
    assert missing in err and "hubs run" in err
    assert "Traceback" not in err


def test_missing_run_dir_exits_1(tmp_path, script, capsys):
    code = script.main(["--run-dir", str(tmp_path / "nope")])
    assert code == 1
    assert "hubs run" in capsys.readouterr().err


def test_missing_lines_file_exits_1(tmp_path, script, capsys):
    run = _write_run(tmp_path, script)  # no manifest, no --lines-file
    code = script.main(["--run-dir", str(run), "--out-dir", str(tmp_path / "out")])
    err = capsys.readouterr().err
    assert code == 1
    assert "--lines-file" in err and "Traceback" not in err


def test_manifest_names_a_lines_file_that_is_gone(tmp_path, script, capsys):
    manifest = {"version": "M", "input_dir": str(tmp_path / "gone"),
                "inputs": {"lines_mode": {"file": "Lines_and_Planned_Mode_X.csv"}}}
    run = _write_run(tmp_path, script, manifest)
    code = script.main(["--run-dir", str(run)])
    err = capsys.readouterr().err
    assert code == 1
    assert "Lines_and_Planned_Mode_X.csv" in err and "--lines-file" in err


def test_explicit_missing_lines_file_exits_1(tmp_path, script, capsys):
    run = _write_run(tmp_path, script)
    code = script.main(["--run-dir", str(run), "--lines-file", str(tmp_path / "x.csv")])
    assert code == 1
    assert "x.csv" in capsys.readouterr().err
