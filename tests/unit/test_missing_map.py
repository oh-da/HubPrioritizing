"""``scripts/build_missing_map.py`` on the synthetic run and agency network.

The script is not part of a package, so it is loaded by path. The scenario is the one of
``test_compare_run.py``: a synthetic ``hubs run``, the synthetic agency files and a
``hubs compare-network`` output, from which the map and the summary are built.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest

from src.cli import main as hubs_main
from src.pipeline.inputs import discover_inputs
from src.pipeline.run import run_pipeline, write_outputs
from src.pipeline.settings import load_config
from tests.synthetic import make_synthetic_dirs
from tests.synthetic_agency import make_agency_gpkg, make_metadata_xlsx

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_missing_map.py"
VERDICTS = {"real_gap", "covered_elsewhere", "definition_difference", "check", "present"}
TRUE_TEXT = {"true", "1", "1.0"}  # how the workbook's eligible column reads back
SETS = {"ag_line", "our_line", "doubt", "both_line", "ag_hub", "ag_hub_filt", "our_hub", "both_hub"}


def _load_script():
    spec = importlib.util.spec_from_file_location("build_missing_map", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bmm():
    return _load_script()


def _without_hub_b(src: Path, dst: Path) -> Path:
    """Copy of the synthetic agency file without hub B (BRT 3001 and LRT 1002).

    Our hub B and its two routes then exist on our side only.
    """
    gone = (3001, 1002)
    for layer in ("lines", "stations"):
        frame = gpd.read_file(src, layer=layer)
        frame[~frame["line_id"].isin(gone)].to_file(dst, layer=layer, driver="GPKG")
    return dst


@pytest.fixture(scope="module", params=["full", "trimmed"])
def scenario(request, tmp_path_factory):
    """The synthetic run compared with the full agency network and with one without hub B."""
    root = tmp_path_factory.mktemp(f"missing_map_{request.param}")
    input_dir, ref_dir = make_synthetic_dirs(root)
    run_dir = root / "run"
    cfg = load_config(None, {"mc_iterations": 50})
    write_outputs(run_pipeline(cfg, discover_inputs(input_dir, ref_dir)), run_dir)
    gpkg = make_agency_gpkg(root / "MT_Network.gpkg")
    if request.param == "trimmed":
        gpkg = _without_hub_b(gpkg, root / "MT_Network_trimmed.gpkg")
    meta = make_metadata_xlsx(root / "MT_Network_MetaData.xlsx")
    compare_dir = root / "compare"
    assert hubs_main([
        "compare-network", "--run", str(run_dir), "--agency-gpkg", str(gpkg),
        "--agency-meta", str(meta), "--out", str(compare_dir),
    ]) == 0
    return {"root": root, "run": run_dir, "compare": compare_dir, "gpkg": gpkg, "meta": meta,
            "kind": request.param}


def _argv(sc, out, *extra):
    return [
        "--compare-dir", str(sc["compare"]), "--run-dir", str(sc["run"]),
        "--agency-gpkg", str(sc["gpkg"]), "--agency-meta", str(sc["meta"]),
        "--out-dir", str(out), *extra,
    ]


def _data(html_path: Path) -> dict:
    page = html_path.read_text(encoding="utf-8")
    m = re.search(r"var DATA = (.*);\n  var SETS", page)
    assert m, "embedded data not found"
    return json.loads(m.group(1))


@pytest.fixture(scope="module")
def built(bmm, scenario):
    out = scenario["root"] / "map"
    assert bmm.main(_argv(scenario, out)) == 0
    return out


def test_builds_page_and_summary(built):
    assert (built / "missing_lines_hubs_map.html").stat().st_size > 0
    summary = (built / "missing_map_summary.md").read_text(encoding="utf-8")
    assert summary.startswith("# Missing lines and hubs")
    assert "## Counts per set and verdict" in summary


def test_feature_counts_match_the_comparison_workbook(built, scenario):
    sheets = pd.read_excel(scenario["compare"] / "network_comparison.xlsx", sheet_name=None)
    routes, hubs = sheets["routes"], sheets["hubs"]
    ours_only = hubs[hubs["relation"] == "ours_only"]
    expected = {
        "ag_line": int((routes["status"] == "agency_only").sum()),
        "our_line": int((routes["status"] == "ours_only").sum()),
        "ag_hub": int((hubs["relation"] == "agency_only").sum()),
        "our_hub": int(ours_only["eligible"].map(lambda v: str(v).lower() in TRUE_TEXT).sum()),
    }
    if scenario["kind"] == "trimmed":  # this scenario fills all four sets
        assert min(expected.values()) > 0, expected
    feats = _data(built / "missing_lines_hubs_map.html")["features"]
    got = {s: sum(f["s"] == s for f in feats) for s in SETS}
    for name, n in expected.items():
        assert got[name] == n, (name, got, expected)
    assert set(got) == SETS


def test_every_feature_has_a_verdict_geometry_and_unique_id(built):
    feats = _data(built / "missing_lines_hubs_map.html")["features"]
    assert feats
    assert len({f["id"] for f in feats}) == len(feats)
    for f in feats:
        assert f["v"] in VERDICTS, f
        assert f["s"] in SETS and f["why"] and f["g"], f
    present_sets = {"both_line", "both_hub"}
    assert all((f["v"] == "present") == (f["s"] in present_sets) for f in feats)


def test_output_is_deterministic(bmm, scenario, built):
    again = scenario["root"] / "map_again"
    assert bmm.main(_argv(scenario, again)) == 0
    for name in ("missing_lines_hubs_map.html", "missing_map_summary.md"):
        assert (built / name).read_bytes() == (again / name).read_bytes(), name


def test_run_note_is_shown_and_escaped(bmm, scenario, built):
    note = "run X <b>bold</b> </script><script>alert(1)</script> & more"
    out = scenario["root"] / "map_note"
    assert bmm.main(_argv(scenario, out, "--run-note", note)) == 0
    page = (out / "missing_lines_hubs_map.html").read_text(encoding="utf-8")
    base = (built / "missing_lines_hubs_map.html").read_text(encoding="utf-8")
    assert "run X &lt;b&gt;bold&lt;/b&gt; &lt;/script&gt;&lt;script&gt;alert(1)" in page
    assert "<script>alert(1)" not in page
    assert page.count("</script>") == base.count("</script>")
    summary = (out / "missing_map_summary.md").read_text(encoding="utf-8")
    assert f"Data: {note}," in summary


def test_default_run_note_comes_from_the_manifest_not_a_fixed_text(built, scenario):
    manifest = json.loads((scenario["run"] / "run_manifest.json").read_text(encoding="utf-8"))
    page = (built / "missing_lines_hubs_map.html").read_text(encoding="utf-8")
    assert f"run {manifest['version']}" in page
    assert "V1.1" not in page and "rail_13" not in page and "51179" not in page


def test_default_run_note_without_manifest_names_the_directories(bmm, tmp_path):
    run, cmp_ = tmp_path / "myrun", tmp_path / "mycmp"
    run.mkdir(), cmp_.mkdir()
    assert bmm.default_run_note(run, cmp_) == "run myrun, comparison mycmp"


def test_out_dir_defaults_to_the_compare_dir(bmm, scenario, tmp_path):
    import shutil

    cmp_copy = tmp_path / "compare"
    shutil.copytree(scenario["compare"], cmp_copy)
    argv = _argv(scenario, tmp_path / "unused")
    argv[argv.index("--compare-dir") + 1] = str(cmp_copy)
    del argv[argv.index("--out-dir"):argv.index("--out-dir") + 2]
    assert bmm.main(argv) == 0
    assert (cmp_copy / "missing_lines_hubs_map.html").is_file()
    assert (cmp_copy / "missing_map_summary.md").is_file()


def test_leaflet_dir_is_inlined_and_cdn_is_the_fallback(bmm, scenario, built, tmp_path, capsys):
    leaflet = tmp_path / "dist"
    leaflet.mkdir()
    (leaflet / "leaflet.js").write_text("window.L = {fake: 'LEAFLET_JS_MARK'};\n", encoding="utf-8")
    (leaflet / "leaflet.css").write_text(".fake-leaflet { LEAFLET_CSS_MARK: 1; }\n",
                                         encoding="utf-8")
    out = tmp_path / "inlined"
    assert bmm.main(_argv(scenario, out, "--leaflet-dir", str(leaflet))) == 0
    page = (out / "missing_lines_hubs_map.html").read_text(encoding="utf-8")
    assert "LEAFLET_JS_MARK" in page and "LEAFLET_CSS_MARK" in page
    assert "cdnjs" not in page
    assert "notice" not in capsys.readouterr().out

    capsys.readouterr()
    cdn = (built / "missing_lines_hubs_map.html").read_text(encoding="utf-8")
    assert "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js" in cdn
    assert "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" in cdn
    assert "LEAFLET_JS_MARK" not in cdn


def test_cdn_fallback_prints_a_one_line_notice(bmm, scenario, tmp_path, capsys):
    assert bmm.main(_argv(scenario, tmp_path / "o")) == 0
    notices = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("note:")]
    assert len(notices) == 1 and "cdnjs" in notices[0] and "--leaflet-dir" in notices[0]


def test_incomplete_leaflet_dir_is_an_error_not_a_traceback(bmm, scenario, tmp_path, capsys):
    leaflet = tmp_path / "dist"
    leaflet.mkdir()
    (leaflet / "leaflet.css").write_text("x{}", encoding="utf-8")
    code = bmm.main(_argv(scenario, tmp_path / "o", "--leaflet-dir", str(leaflet)))
    assert code == 1
    assert "leaflet.js" in capsys.readouterr().err
    assert not (tmp_path / "o").exists()


@pytest.mark.parametrize("where, name, producer", [
    ("compare", "network_comparison.xlsx", "hubs compare-network"),
    ("compare", "network_comparison.gpkg", "hubs compare-network"),
    ("run", "hub_groups_all.csv", "hubs run"),
    ("run", "network_nodes.csv", "hubs run"),
])
def test_missing_input_file_exits_1_and_names_it(bmm, scenario, tmp_path, capsys,
                                                 where, name, producer):
    import shutil

    broken = {**scenario, where: tmp_path / where}
    shutil.copytree(scenario[where], broken[where])
    (broken[where] / name).unlink()
    out = tmp_path / "out"
    assert bmm.main(_argv(broken, out)) == 1
    err = capsys.readouterr().err
    assert name in err and producer in err and "Traceback" not in err
    assert not out.exists()


def test_missing_agency_file_exits_1(bmm, scenario, tmp_path, capsys):
    sc = {**scenario, "gpkg": tmp_path / "nope.gpkg"}
    assert bmm.main(_argv(sc, tmp_path / "o")) == 1
    assert "nope.gpkg" in capsys.readouterr().err


def test_compare_dir_and_run_dir_and_agency_gpkg_are_required(bmm, scenario, capsys):
    for flag in ("--compare-dir", "--run-dir", "--agency-gpkg"):
        argv = _argv(scenario, scenario["root"] / "o")
        i = argv.index(flag)
        del argv[i:i + 2]
        with pytest.raises(SystemExit) as e:
            bmm.main(argv)
        assert e.value.code == 2
        assert flag in capsys.readouterr().err


def test_importing_the_script_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _load_script()
    assert not list(tmp_path.iterdir())


# ----------------------------------------------------------------------------------------
# Wording and basemap (shared with the compare-network pages, src/compare/map_assets.py)
# ----------------------------------------------------------------------------------------

from src.compare.map_assets import BASEMAPS, LABELS  # noqa: E402

RAW_CODES = sorted({c for kind in ("route_status", "hub_relation", "verdict")
                    for c in LABELS[kind] if "_" in c or ":" in c})
FORBIDDEN = re.compile(r"\bagency\b|\bminhal\b|visual aid|containment|\brelation\b|candidate|"
                       r"\bcoverage\b|" + "|".join(rf"(?<![\w:]){re.escape(c)}(?![\w:])"
                                                    for c in RAW_CODES), re.I)


def _static_text(page: str) -> str:
    import html as html_lib

    body = re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S)
    attrs = " ".join(re.findall(r'(?:aria-label|title|content)="([^"]*)"', body))
    return html_lib.unescape(re.sub(r"<[^>]+>", " ", body) + " " + attrs)


def test_verdicts_come_from_the_shared_label_map(bmm):
    assert set(VERDICTS) == set(LABELS["verdict"])
    assert bmm.VERDICT_LABEL == {v: LABELS["verdict"][v][0] for v in VERDICTS}
    assert bmm.VERDICT_LABEL["real_gap"] == "Missing"


def test_visible_text_is_plain_and_names_the_agency_in_hebrew(built):
    page = (built / "missing_lines_hubs_map.html").read_text(encoding="utf-8")
    static = _static_text(page)
    assert not FORBIDDEN.search(static), FORBIDDEN.search(static).group(0)
    assert "<bdi>מנהל התכנון</bdi>" in page
    for f in _data(built / "missing_lines_hubs_map.html")["features"]:
        for text in [f["why"], f["t"], f["tip"], *(f"{k} {v}" for k, v in f["f"])]:
            assert not FORBIDDEN.search(text), (f["id"], text)
    summary = (built / "missing_map_summary.md").read_text(encoding="utf-8")
    assert not FORBIDDEN.search(summary), FORBIDDEN.search(summary).group(0)
    assert "Hubs project vs מנהל התכנון" in summary and "Needs a look" in summary


def test_page_offers_the_four_basemaps(built):
    page = (built / "missing_lines_hubs_map.html").read_text(encoding="utf-8")
    for provider in BASEMAPS:
        if provider["url"]:
            assert provider["url"] in page, provider["id"]
    assert 'id="basemap"' in page and 'role="status"' in page and "hubsBasemap(map" in page
    assert "tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom" not in page  # no fixed OSM


def test_popups_are_plain_in_a_browser(built):
    from tests.unit.test_compare_maps import PLAYWRIGHT_ENV, _browse

    if PLAYWRIGHT_ENV is None:
        pytest.skip("node + playwright or the Leaflet files are missing")
    seen = _browse(built / "missing_lines_hubs_map.html", "--check")
    assert seen["errors"] == [] and seen["basemap"] == "none"
    assert seen["counts"] == {k: str(v) for k, v in seen["drawn"].items()}
    assert seen["popups"], "no popup opened"
    for text in [seen["panel"], seen["title"], *seen["popups"].values(),
                 *seen["tooltips"].values()]:
        assert text and not FORBIDDEN.search(text), (text, FORBIDDEN.search(text or ""))
