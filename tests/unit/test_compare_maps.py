"""Leaflet pages of ``hubs compare-network``: embedded data, sets, wording, design, basemap."""

from __future__ import annotations

import html as html_lib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, MultiPoint, Point

from src.compare.export import LAYER_NAMES
from src.compare.hubs import RELATIONS
from src.compare.map_assets import BASEMAPS, LABELS, TOKENS, plain_reason
from src.compare.maps import LEAFLET_CSS, LEAFLET_JS, write_hubs_map, write_routes_map
from src.compare.routes import STATUSES
from tests.compare_helpers import CRS_ITM, X0, Y0

HEBREW = "תחנה מרכזית – קו 1 \"ירושלים\""
EVIL = "</script><script>window.pwned=1</script><!--"
HERE = Path(__file__).parent
REFERENCE_DIR = Path(os.environ.get("HUBS_SCRAPING_DIR", "/home/user/HubsScraping"))
LEAFLET_DIR = Path(os.environ.get("LEAFLET_DIST_DIR", "/tmp/claude-0/leaflet_dl/package/dist"))
# codes that must never reach a visible text (plain-word codes such as "matched" are words)
RAW_CODES = sorted({c for kind in ("route_status", "hub_relation", "verdict")
                    for c in LABELS[kind] if "_" in c or ":" in c})
FORBIDDEN = re.compile(r"\bagency\b|\bminhal\b|visual aid|containment|\brelation\b|candidate|"
                       r"\bcoverage\b|" + "|".join(
    rf"(?<![\w:]){re.escape(c)}(?![\w:])" for c in RAW_CODES), re.I)
EXCLUSION_REASONS = ("demand < min", "single mode", "rail only")  # src/pipeline/all_groups.py


def _gdf(rows: list[dict[str, Any]], geoms: list, columns: list[str]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(pd.DataFrame(rows, columns=columns), geometry=geoms, crs=CRS_ITM)


def _line(x0: float, y: float, n: int = 3) -> LineString:
    return LineString([(X0 + x0 + 250 * i, Y0 + y) for i in range(n)])


def _layers(name: str = HEBREW) -> dict[str, gpd.GeoDataFrame]:
    pair_cols = ["status", "our_route_key", "our_mode", "agency_route_key", "agency_type",
                 "agency_name", "score", "cov_ours", "year_operation", "source_plan", "reason"]
    pairs = _gdf(
        [{"status": "matched", "our_route_key": "L1", "our_mode": "LRT",
          "agency_route_key": "LRT:1", "agency_type": "LRT", "agency_name": name, "score": 0.97,
          "cov_ours": 1.0, "year_operation": 2040.0, "source_plan": "מפורטת", "reason": None},
         {"status": "agency_only", "our_route_key": None, "our_mode": None,
          "agency_route_key": "LRT:2", "agency_type": "LRT", "agency_name": "two",
          "score": float("nan"), "cov_ours": float("nan"), "year_operation": 2040.0,
          "source_plan": None, "reason": "no candidate"},
         {"status": "weak", "our_route_key": "L5", "our_mode": "BRT",
          "agency_route_key": "LRT:2", "agency_type": "LRT", "agency_name": "two", "score": 0.3,
          "cov_ours": 0.4, "year_operation": 2040.0, "source_plan": None,
          "reason": "best match is an agency route of another type"}],
        [_line(0, 0), _line(0, 8000), _line(0, 8000)], pair_cols)
    our_cols = ["route_key", "line_ids", "line_names", "mode", "n_nodes", "visual_aid", "status"]
    rows = [{"route_key": "L1", "line_ids": "L1", "line_names": name, "mode": "LRT",
             "n_nodes": 3, "visual_aid": True, "status": "matched"},
            {"route_key": "L5", "line_ids": "L5a; L5b", "line_names": "five", "mode": "BRT",
             "n_nodes": 3, "visual_aid": True, "status": "weak"},
            {"route_key": "L9", "line_ids": "L9", "line_names": "x", "mode": "Cable Line",
             "n_nodes": 1, "visual_aid": True, "status": "ours_only"}]
    ours = _gdf(rows, [_line(0, 10), _line(0, 8010), Point(X0, Y0 - 8000)], our_cols)
    raw = _gdf(rows, [_line(0, 20), _line(0, 8020), Point(X0, Y0 - 7990)], our_cols)
    ahub_cols = ["agency_hub_id", "name", "modes", "n_modes", "rail_hub", "agency_type",
                 "relation", "paired_groups"]
    agency_hubs = _gdf(
        [{"agency_hub_id": 1, "name": name, "modes": "LRT; BRT", "n_modes": 2, "rail_hub": False,
          "agency_type": "2 modes", "relation": "1:1", "paired_groups": "1"},
         {"agency_hub_id": 2, "name": "hub two", "modes": "LRT; BRT", "n_modes": 2,
          "rail_hub": True, "agency_type": "2 modes", "relation": "many_to_many",
          "paired_groups": "3"},
         {"agency_hub_id": 3, "name": "hub three", "modes": "LRT", "n_modes": 1,
          "rail_hub": False, "agency_type": "1 mode: LRT", "relation": "agency_only",
          "paired_groups": ""}],
        [MultiPoint([(X0, Y0 + 50), (X0 + 250, Y0 + 50)]), MultiPoint([(X0, Y0 + 8000)]),
         MultiPoint([(X0 + 9000, Y0)])],
        ahub_cols)
    group_cols = ["hub_id", "group", "HubNameHE", "Mode_Planned", "n_modes", "eligible",
                  "exclusion_reason", "HubType", "TotalDemand", "relation"]
    groups = _gdf(
        [{"hub_id": "H1", "group": 1, "HubNameHE": name, "Mode_Planned": "LRT; BRT",
          "n_modes": 2, "eligible": True, "exclusion_reason": "", "HubType": "מטרופוליני",
          "TotalDemand": 5000.0, "relation": "1:1"},
         {"hub_id": "H3", "group": 3, "HubNameHE": EVIL, "Mode_Planned": "LRT; BRT",
          "n_modes": 2, "eligible": False, "exclusion_reason": "demand < min;rail only",
          "HubType": "", "TotalDemand": 10.0, "relation": "many_to_many"},
         {"hub_id": "H4", "group": 4, "HubNameHE": "four", "Mode_Planned": "BRT; LRT",
          "n_modes": 2, "eligible": True, "exclusion_reason": "", "HubType": "Not Hub",
          "TotalDemand": 2000.0, "relation": "ours_only"}],
        [MultiPoint([(X0, Y0)]), MultiPoint([(X0, Y0 + 8000)]),
         MultiPoint([(X0 + 3000, Y0 + 3000)])], group_cols)
    tie_cols = ["agency_hub_id", "group", "hub_id", "relation", "distance_m", "agency_name",
                "HubNameHE", "eligible", "modes_only_agency", "routes_shared"]
    ties = _gdf(
        [{"agency_hub_id": 1, "group": 1, "hub_id": "H1", "relation": "1:1", "distance_m": 50.0,
          "agency_name": name, "HubNameHE": name, "eligible": True, "modes_only_agency": "",
          "routes_shared": "LRT:1=L1"},
         {"agency_hub_id": 2, "group": 3, "hub_id": "H3", "relation": "many_to_many",
          "distance_m": 0.0, "agency_name": "hub two", "HubNameHE": "z", "eligible": False,
          "modes_only_agency": "BRT", "routes_shared": ""}],
        [LineString([(X0, Y0 + 50), (X0, Y0)]), LineString([(X0, Y0), (X0, Y0)])], tie_cols)
    return {"route_pairs": pairs, "our_routes": ours, "our_routes_raw": raw,
            "agency_hubs": agency_hubs, "our_groups": groups, "hub_ties": ties}


def _empty_layers() -> dict[str, gpd.GeoDataFrame]:
    return {n: gpd.GeoDataFrame({"a": []}, geometry=gpd.GeoSeries([], crs=CRS_ITM), crs=CRS_ITM)
            for n in LAYER_NAMES}


def _data(html: str) -> dict[str, Any]:
    match = re.search(r'<script type="application/json" id="page-data">(.*?)</script>', html,
                      re.S)
    assert match, "no embedded data block"
    return json.loads(match.group(1))


def _write(tmp_path: Path, layers: dict) -> tuple[str, str]:
    routes = write_routes_map(tmp_path / "routes.html", layers)
    hubs = write_hubs_map(tmp_path / "hubs.html", layers)
    return routes.read_text(encoding="utf-8"), hubs.read_text(encoding="utf-8")


def _visible_text(html: str) -> str:
    """The text a reader sees: the markup without scripts and styles, plus titles and labels."""
    body = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    attrs = " ".join(re.findall(r'(?:aria-label|title|content)="([^"]*)"', body))
    return html_lib.unescape(re.sub(r"<[^>]+>", " ", body) + " " + attrs)


def _coords(geometry: dict | None):
    if geometry is None:
        return
    stack = [geometry["coordinates"]]
    while stack:
        item = stack.pop()
        if item and isinstance(item[0], (int, float)):
            yield item
        else:
            stack.extend(item)


def _sets(collection: dict) -> list:
    return [f.get("sets", f.get("set")) for f in collection["features"]]


# ----------------------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------------------


def test_pages_embed_json_with_expected_counts(tmp_path: Path):
    layers = _layers()
    routes, hubs = _write(tmp_path, layers)
    r, h = _data(routes), _data(hubs)
    assert set(r) == {"labels", "settings", "route_pairs", "our_routes"}
    assert set(h) == {"labels", "settings", "agency_hubs", "our_groups", "hub_ties"}
    for page, names in ((r, ("route_pairs", "our_routes")),
                        (h, ("agency_hubs", "our_groups", "hub_ties"))):
        for name in names:
            assert page[name]["type"] == "FeatureCollection"
            assert len(page[name]["features"]) == len(layers[name]), name
        assert page["labels"] == LABELS and page["settings"]["hub_match_tol_m"] == 400.0
    assert "leaflet/1.9.4/leaflet.min.js" in LEAFLET_JS and routes.count(LEAFLET_JS) == 1
    assert "leaflet/1.9.4/leaflet.min.css" in LEAFLET_CSS and hubs.count(LEAFLET_CSS) == 1
    statuses = [f["properties"]["status"] for f in r["route_pairs"]["features"]]
    assert statuses == ["matched", "agency_only", "weak"]
    only = r["route_pairs"]["features"][1]["properties"]
    assert "our_route_key" not in only and "score" not in only  # nulls are not embedded
    assert only["why"].startswith("no line of") and only["length_m"] == 500


def test_route_sets_follow_the_reference(tmp_path: Path):
    routes, _ = _write(tmp_path, _layers())
    r = _data(routes)
    # matched row: drawn on the agency line, which also counts once as in use; agency_only:
    # a gap; the weak row of the same agency key is neither (its key is a gap)
    assert _sets(r["route_pairs"]) == [["routed", "used"], ["gap"], []]
    assert _sets(r["our_routes"]) == [["routed"], ["diff"], ["off"]]


def test_hub_sets_follow_the_reference(tmp_path: Path):
    _, hubs = _write(tmp_path, _layers())
    h = _data(hubs)
    # agency 1 (2 modes) - group 1 (scored): in both; agency 2 (2 modes) is tied to a group
    # that is not scored: only theirs; agency 3 has one mode; group 4 is scored, alone
    assert _sets(h["agency_hubs"]) == ["both", "onlym", "single"]
    assert _sets(h["our_groups"]) == ["both", "filt", "onlyx"]
    assert [f["both"] for f in h["hub_ties"]["features"]] == [True, False]
    g4 = h["our_groups"]["features"][2]["properties"]
    assert g4["near_hub"] in (1, 2) and g4["near_m"] > 0
    a2 = h["agency_hubs"]["features"][1]["properties"]
    assert a2["near_group"] in (1, 4)
    for f in h["agency_hubs"]["features"] + h["our_groups"]["features"]:
        assert f["geometry"]["type"] == "Point"  # drawn at the centroid


def test_coordinates_are_wgs84(tmp_path: Path):
    routes, hubs = _write(tmp_path, _layers())
    seen = 0
    for page in (_data(routes), _data(hubs)):
        for name, collection in page.items():
            if name in ("labels", "settings"):
                continue
            for feature in collection["features"]:
                for lon, lat in _coords(feature["geometry"]):
                    assert 34 < lon < 36 and 29 < lat < 34
                    assert round(lon, 6) == lon and round(lat, 6) == lat
                    seen += 1
    assert seen > 15


def test_hebrew_not_escaped_into_garbage(tmp_path: Path):
    routes, hubs = _write(tmp_path, _layers())
    assert "תחנה מרכזית" in routes and "תחנה מרכזית" in hubs  # UTF-8 as is, no \uXXXX
    assert "\\u05" not in routes and "\\u05" not in hubs
    first = _data(routes)["route_pairs"]["features"][0]["properties"]
    assert first["agency_name"] == HEBREW and first["source_plan"] == "מפורטת"
    assert _data(hubs)["our_groups"]["features"][0]["properties"]["HubNameHE"] == HEBREW
    assert (tmp_path / "routes.html").read_bytes().decode("utf-8") == routes


def test_script_closing_tag_in_data_is_escaped(tmp_path: Path):
    routes, hubs = _write(tmp_path, _layers(name=EVIL))
    for html in (routes, hubs):
        assert html.count("</script>") == html.count("<script"), "data ended a script block"
        assert "<script>window.pwned" not in html and "<!--" not in html
        assert "eval(" not in html and "innerHTML" not in html
        assert "const esc = " in html  # every data text reaches the markup through esc()
    assert _data(routes)["route_pairs"]["features"][0]["properties"]["agency_name"] == EVIL
    assert _data(hubs)["our_groups"]["features"][1]["properties"]["HubNameHE"] == EVIL


def test_empty_layers_render(tmp_path: Path):
    routes, hubs = _write(tmp_path, _empty_layers())
    for html in (routes, hubs):
        for name, collection in _data(html).items():
            if name not in ("labels", "settings"):
                assert collection == {"type": "FeatureCollection", "features": []}
    assert _data(write_routes_map(tmp_path / "none.html", {}).read_text("utf-8"))["route_pairs"][
        "features"] == []


def test_same_layers_give_identical_bytes(tmp_path: Path):
    layers = _layers()
    a = write_routes_map(tmp_path / "a.html", layers).read_bytes()
    b = write_routes_map(tmp_path / "b.html", layers).read_bytes()
    assert a == b
    assert write_hubs_map(tmp_path / "c.html", layers).read_bytes() == write_hubs_map(
        tmp_path / "d.html", layers).read_bytes()


def test_settings_reach_the_panel(tmp_path: Path):
    settings = {"route_tol_m": 120.0, "hub_match_tol_m": 300.0, "offset_dx_m": -56.0,
                "offset_dy_m": -36.9}
    routes = write_routes_map(tmp_path / "r.html", _layers(), settings).read_text("utf-8")
    hubs = write_hubs_map(tmp_path / "h.html", _layers(), settings).read_text("utf-8")
    assert "within 120 m (rail 250 m)" in routes and "overall -56 m, -37 m" in routes
    assert "matched within 300 m" in hubs and _data(hubs)["settings"]["hub_match_tol_m"] == 300.0


# ----------------------------------------------------------------------------------------
# Wording: plain words, no codes, the agency named מנהל התכנון
# ----------------------------------------------------------------------------------------


def test_label_map_covers_every_code_of_the_data():
    assert set(STATUSES) <= set(LABELS["route_status"])
    assert set(RELATIONS) <= set(LABELS["hub_relation"])
    assert set(EXCLUSION_REASONS) <= set(LABELS["exclusion"])
    assert {"Not Hub"} <= set(LABELS["hub_type"])
    for kind, entries in LABELS.items():
        for code, (text, explanation) in entries.items():
            assert text and not FORBIDDEN.search(text + " " + explanation), (kind, code)


def test_reasons_are_told_in_plain_words():
    for reason in ("no candidate", "agency route shared by 2 of our routes",
                   "best score of ours 0.21 below 0.5", "best score below 0.5",
                   "runs over 3 agency routes", "only cross-mode candidates",
                   "only cross-mode candidates below 0.5",
                   "best match is an agency route of another type",
                   "our route lies on a longer agency route",
                   "candidate of 3 of our routes, never their best",
                   "the agency route lies on a longer route of ours", "no agency mode",
                   "some new agency reason about a candidate route"):
        text = plain_reason(reason)
        assert text and not FORBIDDEN.search(text) and "candidate" not in text, reason
    assert plain_reason(None) == "" and plain_reason(float("nan")) == ""


def test_visible_text_has_no_agency_word_and_no_codes(tmp_path: Path):
    routes, hubs = _write(tmp_path, _layers())
    for html in (routes, hubs):
        text = _visible_text(html)
        assert not FORBIDDEN.search(text), FORBIDDEN.search(text).group(0)
        assert "מנהל התכנון" in text
        assert "<bdi>מנהל התכנון</bdi>" in html and "<bdi>פרויקט תעדוף מתחמים</bdi>" in html
    assert "Hubs project vs <bdi>מנהל התכנון</bdi>: transit lines" in routes
    assert "<h1>Hub list comparison</h1>" in hubs
    for label in ("Same line", "Lines that differ", "Only in Hubs project",
                  "<bdi>מנהל התכנון</bdi> lines in use",
                  "<bdi>מנהל התכנון</bdi> lines without a line of ours"):
        assert label in routes, label
    for label in ("In both", "Only in Hubs project", "Only in <bdi>מנהל התכנון</bdi>",
                  "<bdi>מנהל התכנון</bdi> hubs with one mode", "Hubs project groups not scored"):
        assert label in hubs, label


# ----------------------------------------------------------------------------------------
# Design: the reference tokens, the shared look
# ----------------------------------------------------------------------------------------


def _token_blocks(css: str) -> dict[str, dict[str, str]]:
    """``light`` / ``dark_media`` / ``dark_forced`` custom properties of a page."""
    out = {}
    for name, pattern in (("light", r":root\s*\{([^}]*)\}"),
                          ("dark_media", r':root:not\(\[data-theme="light"\]\)\s*\{([^}]*)\}'),
                          ("dark_forced", r':root\[data-theme="dark"\]\s*\{([^}]*)\}')):
        match = re.search(pattern, css)
        assert match, name
        out[name] = dict(re.findall(r"--([\w-]+)\s*:\s*([^;]+);", match.group(1)))
        out[name] = {k: v.strip() for k, v in out[name].items()}
    return out


@pytest.mark.skipif(not (REFERENCE_DIR / "compare.html").is_file(),
                    reason="the HubsScraping reference pages are not checked out")
def test_design_tokens_match_the_reference_pages(tmp_path: Path):
    reference: dict[str, dict[str, str]] = {"light": {}, "dark_media": {}, "dark_forced": {}}
    for name in ("compare_lines.html", "compare.html"):
        blocks = _token_blocks((REFERENCE_DIR / name).read_text(encoding="utf-8"))
        for scheme, tokens in blocks.items():
            for key, value in tokens.items():
                assert reference[scheme].setdefault(key, value) == value, (name, key)
    for html in _write(tmp_path, _layers()):
        ours = _token_blocks(html)
        for scheme, tokens in ours.items():
            assert tokens, scheme
            for key, value in tokens.items():
                assert key in reference[scheme], f"--{key} is not a reference token"
                assert reference[scheme][key] == value, (scheme, key, value)
    assert TOKENS["light"]["routed"] == "#2a78d6" and TOKENS["dark"]["gap"] == "#a02fb8"


def test_shared_design_pieces(tmp_path: Path):
    routes, hubs = _write(tmp_path, _layers())
    for html in (routes, hubs):
        assert "zoomControl: false" in html
        assert "L.control.zoom({position: 'topright'})" in html
        assert "preferCanvas: true" in html
        assert "family=Heebo" in html and ".osm-gray {" in html and "width: 336px" in html
        for piece in ('class="sets"', 'class="sym"', 'class="actions"', 'id="btn-bsh"',
                      'id="basemap"', 'role="status"', 'class="pp" dir="auto"'):
            assert piece in html, piece
    assert 'id="pick-line"' in routes and 'id="pick-status"' in routes
    assert ".st-match" in routes and "dashArray: '6 5'" in routes


def test_every_page_offers_the_four_basemaps(tmp_path: Path):
    for html in _write(tmp_path, _layers()):
        for provider in BASEMAPS:
            if provider["url"]:
                assert provider["url"] in html, provider["id"]
        assert "No basemap" in html and '"maxNativeZoom":16' in html
        assert '"subdomains":"abcd"' in html and '"className":"osm-gray"' in html


# ----------------------------------------------------------------------------------------
# Running the page scripts
# ----------------------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_page_scripts_run_against_a_stub(tmp_path: Path):
    """Each page's script against a minimal DOM/Leaflet stub: counts equal the drawn layers."""
    runner = HERE / "compare_maps_stub.js"
    expected = {
        "routes": {"used": 1, "gap": 1, "routed": 1, "diff": 1, "off": 1},
        "hubs": {"both": 1, "onlyx": 1, "onlym": 1, "single": 1, "filt": 1},
    }
    for layers, empty in ((_layers(), False), (_empty_layers(), True)):
        _write(tmp_path, layers)
        for name in ("routes", "hubs"):
            out = subprocess.run(["node", str(runner), str(tmp_path / f"{name}.html")],
                                 capture_output=True, text=True, check=False)
            assert out.returncode == 0, out.stderr
            seen = json.loads(out.stdout)
            want = {k: 0 for k in expected[name]} if empty else expected[name]
            assert seen["drawn"] == want, seen
            counts = {k: int(str(v).split()[0]) for k, v in seen["counts"].items()}
            assert counts == want
            if not empty:
                assert seen["popups"] >= len(want)


def _node_playwright() -> dict[str, str] | None:
    """Environment for ``node`` with Playwright resolvable, or None when it is unavailable."""
    if shutil.which("node") is None or not (LEAFLET_DIR / "leaflet.js").is_file():
        return None
    env = dict(os.environ)
    try:
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True,
                              check=False, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        root = ""
    env["NODE_PATH"] = os.pathsep.join(p for p in (env.get("NODE_PATH", ""), root) if p)
    probe = subprocess.run(["node", "-e", "require('playwright')"], env=env,
                           capture_output=True, check=False)
    return env if probe.returncode == 0 else None


PLAYWRIGHT_ENV = _node_playwright()
needs_browser = pytest.mark.skipif(PLAYWRIGHT_ENV is None,
                                   reason="node + playwright or the Leaflet files are missing")


def _browse(page: Path, *extra: str) -> dict[str, Any]:
    out = subprocess.run(
        ["node", str(HERE / "compare_maps_browser.js"), "--leaflet", str(LEAFLET_DIR),
         "--page", str(page), *extra],
        capture_output=True, text=True, check=False, env=PLAYWRIGHT_ENV, timeout=180,
    )
    if out.returncode != 0 and "Executable doesn't exist" in out.stderr:
        pytest.skip("the Playwright browser is not installed")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@needs_browser
@pytest.mark.parametrize("scenario, basemap, notice", [
    ("A", "carto", ""),
    ("B", "esri", "Basemap tiles from CARTO light did not load (blocked or offline); "
                  "switched to Esri light gray."),
    ("C", "none", "No basemap tiles could be loaded; the lines and hubs still draw on the "
                  "gray background."),
    ("D", "osm", ""),
])
def test_basemap_fallback_in_a_browser(tmp_path: Path, scenario, basemap, notice):
    routes = write_routes_map(tmp_path / "routes.html", _layers())
    seen = _browse(routes, "--scenario", scenario)
    assert seen["errors"] == []
    assert seen["basemap"] == basemap and seen["note"] == notice
    assert seen["noteRole"] == "status"
    if scenario == "C":
        assert seen["tiles"]["osm"] > 0 and seen["tiles"]["esri"] > 0
    if scenario == "D":
        assert seen["osmLayer"] and seen["tiles"]["osm"] > 0


@needs_browser
@pytest.mark.parametrize("name", ["routes", "hubs"])
def test_pages_work_in_a_browser(tmp_path: Path, name):
    _write(tmp_path, _layers())
    seen = _browse(tmp_path / f"{name}.html", "--check")
    assert seen["errors"] == []
    counts = {k: int(str(v).split()[0]) for k, v in seen["counts"].items()}
    assert counts == seen["drawn"] and all(seen["toggles"].values())
    assert set(seen["popups"]) == set(seen["drawn"])  # one popup opened per set
    texts = [seen["panel"], seen["title"], *seen["popups"].values(), *seen["tooltips"].values(),
             *seen.get("statusOptions", []), *seen.get("lineOptions", [])]
    for text in texts:
        assert text and not FORBIDDEN.search(text), (text, FORBIDDEN.search(text or ""))
    assert abs(seen["cities"]["btn-tlv"][0] - 32.08) < 0.01
    assert abs(seen["cities"]["btn-bsh"][1] - 34.79) < 0.01
    if name == "routes":
        assert seen["pickOn"] >= 1 and seen["pickDimmed"] >= 1 and seen["pickRestored"]
        assert seen["statusOptions"][0] == "any status"
