"""Export a finished ``hubs run`` as shapefiles for GIS: the hubs and the lines.

    hubs run --input-dir DIR --output-dir RUN
    python scripts/export_shapefiles.py --run-dir RUN [--lines-file Lines_and_Planned_Mode_*.csv] \\
        [--out-dir OUT] [--version NAME] [--no-zip]

Reads ``hub_prioritization_results.csv``, ``hub_identity.csv`` and ``network_nodes.csv`` of the
run folder and the run's ``Lines_and_Planned_Mode_*.csv`` (default: the file recorded in
``run_manifest.json``). Writes two packages to ``--out-dir`` (default ``<run-dir>/shapefiles``),
each in ITM (EPSG:2039) and WGS84 (EPSG:4326), and one zip per package unless ``--no-zip``:

* ``pkg_hubs``: every exported hub as a point with its type (``HubTypeHE``) and its attributes,
  ``hub_lines.csv`` (hub x line), ``field_map_hubs.csv``, ``README.txt``;
* ``pkg_lines``: one LineString per line, the node x line points with ``Seq``,
  ``lines_attributes.csv``, ``lines_without_geometry.csv``, ``README.txt``.

The pipeline has no route geometry: a line is drawn through its nodes in shortest-open-path
order, a visual aid only (see docs/EXPORT_SHAPEFILES.md). The output is deterministic.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.compare.routes import order_points  # noqa: E402  (shortest open path through points)
from src.pipeline.inputs import read_csv_auto  # noqa: E402

ITM, WGS = "EPSG:2039", "EPSG:4326"
RESULTS_FILE = "hub_prioritization_results.csv"
IDENTITY_FILE = "hub_identity.csv"
NODES_FILE = "network_nodes.csv"
MANIFEST_FILE = "run_manifest.json"
GROUPS_ALL_FILE = "hub_groups_all.csv"
LINES_COLUMNS = ("Line_ModelName", "Mode_Planned", "Line_Name", "Line_Description", "Area")
NODES_COLUMNS = ("node", "LINE_ID", "Mode_Planned", "x_itm", "y_itm", "group", "hub_id")
ZIP_DATE = (1980, 1, 1, 0, 0, 0)  # fixed, so the zips are byte-identical between runs

_LINES_NOTE = "lines of the mode"
_NORM = "criterion score 1-10 (per hub type): "

# result column -> (shapefile field, description); shapefile field names are <= 10 characters
HUB_FIELDS = {
    "group": ("group", "group number of this run (changes between runs)"),
    "hub_id": ("hub_id", "stable hub id: hash of the node set"),
    "HubNameHE": ("name_he", "hub name (Hebrew)"),
    "HubTypeHE": ("HubTypeHE", "hub type: ארצי / מטרופוליני / עירוני / Not Hub"),
    "area": ("area", "metropolitan area / district"),
    "Metro": ("Metro", "metropolitan area name"),
    "location": ("location", "position in the metropolitan area (core / rings)"),
    "TotalDemand": ("TotDemand", "daily passengers 2050 (boardings + alightings model value)"),
    "TotalTransfers": ("TotTransf", "daily transfers 2050"),
    "TransferRate": ("TransfRate", "TotalTransfers / TotalDemand"),
    "Mode_Planned": ("Modes", "planned modes (English)"),
    "Modes_ForPlot": ("ModesHe", "planned modes (Hebrew)"),
    "Num_Modes": ("NumModes", "number of modes"),
    "_n_lines": ("NumLines", "number of unique lines at the hub (each direction is a line)"),
    "BRT Lines": ("LinesBRT", _LINES_NOTE + " (service-score input)"),
    "Cable Line Lines": ("LinesCable", _LINES_NOTE),
    "Funicular Lines": ("LinesFunic", _LINES_NOTE),
    "HighSpeed Rail Lines": ("LinesHSR", _LINES_NOTE),
    "Interurban Rail Lines": ("LinesInter", _LINES_NOTE),
    "LRT Lines": ("LinesLRT", _LINES_NOTE),
    "Metro Lines": ("LinesMetro", _LINES_NOTE),
    "Suburban Rail Lines": ("LinesSubRl", _LINES_NOTE),
    "TotalPop_2050": ("Pop2050", "population 2050 within the catchment rings "
                                 "(decay-weighted inputs summed)"),
    "TotalEmp_2050": ("Emp2050", "jobs 2050 within the catchment rings"),
    "bus_terminal": ("BusTermCls", "bus terminal class within 200 m "
                                   "(0 none, 1 night parking, 2 small/medium, 3 large)"),
    "RegionLocation_Norm": ("NormLoc", _NORM + "location"),
    "bus_terminal_Norm": ("NormBus", _NORM + "bus terminal"),
    "score_Norm": ("NormServ", _NORM + "service and modes"),
    "TotalDemand_Norm": ("NormDem", _NORM + "passenger activity"),
    "PopEmp_Score_Norm": ("NormPopEmp", _NORM + "population and jobs"),
    "TotalScore_MC": ("ScoreMC", "final Monte Carlo score"),
    "Rank_TS_MC": ("RankAll", "overall rank by ScoreMC"),
    "Rank_within_HubType": ("RankType", "rank within the hub type"),
    "RankByHubTypeMetro": ("RankTypMet", "rank within hub type and metropolitan area "
                                         "(the display rank)"),
}
TEXT_LIST_COLS = ("Mode_Planned", "location")
DERIVED_FIELDS = ("_n_lines", "hub_id")  # not in the results table: counted / from hub_identity


class ExportError(Exception):
    """A missing or unusable input; reported on stderr with exit code 1, no traceback."""


# ----------------------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------------------
def parse_list(value) -> list:
    """A list cell of the results table (``"['a', 'b']"``) as a list; a scalar as a 1-list."""
    if isinstance(value, str) and value.startswith("["):
        return ast.literal_eval(value)
    return [] if pd.isna(value) else [value]


def _require_file(path: Path, what: str, hint: str) -> Path:
    if not path.is_file():
        raise ExportError(f"{what} not found: {path}\n{hint}")
    return path


def _require_columns(frame: pd.DataFrame, columns, name: str) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise ExportError(f"{name} lacks the column(s) {', '.join(missing)}; "
                          "was it written by this version of `hubs run`?")


def read_manifest(run_dir: Path) -> dict:
    """``run_manifest.json`` of the run, or ``{}`` when it is absent or unreadable."""
    path = run_dir / MANIFEST_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _manifest_input(manifest: dict, key: str) -> str | None:
    entry = (manifest.get("inputs") or {}).get(key)
    name = entry.get("file") if isinstance(entry, dict) else None
    return name if isinstance(name, str) and name else None


def resolve_lines_file(arg: str | None, manifest: dict) -> Path:
    """``--lines-file``, else the lines file recorded in the manifest, else an error."""
    if arg:
        return _require_file(Path(arg), "lines file", "Pass the run's "
                             "Lines_and_Planned_Mode_*.csv with --lines-file.")
    name = _manifest_input(manifest, "lines_mode")
    ask = "pass the run's Lines_and_Planned_Mode_*.csv with --lines-file"
    if not name:
        raise ExportError(f"no lines file: the run has no {MANIFEST_FILE} naming it; {ask}.")
    base = Path(str(manifest.get("input_dir") or "."))
    candidates = [base / name] if base.is_absolute() else [Path.cwd() / base / name,
                                                           REPO_ROOT / base / name]
    for cand in candidates:
        if cand.is_file():
            return cand
    raise ExportError(f"the manifest names the lines file {name} (input_dir {base}), "
                      f"but it does not exist at {candidates[0]}; {ask}.")


def _label(text: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", text).strip("_") or "run"


def write_layer(gdf: gpd.GeoDataFrame, stem: str, folder: Path) -> None:
    """ITM and WGS84 copies of one layer as shapefiles (UTF-8, .cpg written)."""
    folder.mkdir(parents=True, exist_ok=True)
    for crs, tag in ((ITM, "itm"), (WGS, "wgs84")):
        gdf.to_crs(crs).to_file(folder / f"{stem}_{tag}.shp", driver="ESRI Shapefile",
                                encoding="utf-8")


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig", lineterminator="\n")


def write_text(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def zip_folder(folder: Path, zip_path: Path) -> None:
    """Zip the files of ``folder`` in name order with fixed timestamps (deterministic)."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(folder.iterdir()):
            info = zipfile.ZipInfo(path.name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


# ----------------------------------------------------------------------------------------
# 1. hubs
# ----------------------------------------------------------------------------------------
def read_lines_meta(lines_file: Path) -> pd.DataFrame:
    """The run's lines file (encoding detected), one row per ``Line_ModelName``."""
    try:
        frame, _ = read_csv_auto(lines_file, hebrew_columns=("Line_Name", "Line_Description"))
    except ValueError as exc:
        raise ExportError(f"cannot read the lines file {lines_file}: {exc}") from exc
    _require_columns(frame, LINES_COLUMNS, f"lines file {lines_file.name}")
    return frame.drop_duplicates("Line_ModelName").set_index("Line_ModelName", drop=False)


def build_hubs(run_dir: Path, meta: pd.DataFrame):
    """Hub points, the hub x line table and the field map."""
    r = pd.read_csv(run_dir / RESULTS_FILE, encoding="utf-8-sig")
    needed = [c for c in HUB_FIELDS if c not in DERIVED_FIELDS] + ["Line_Unique", "x", "y"]
    _require_columns(r, needed, RESULTS_FILE)
    ident = pd.read_csv(run_dir / IDENTITY_FILE, encoding="utf-8-sig")
    _require_columns(ident, ("group", "hub_id"), IDENTITY_FILE)
    r = r.merge(ident[["group", "hub_id"]], on="group", how="left", validate="one_to_one")
    r["_n_lines"] = r["Line_Unique"].map(lambda v: len(parse_list(v)))
    for col in TEXT_LIST_COLS:
        r[col + "_txt"] = r[col].map(lambda v: "; ".join(map(str, parse_list(v))))
    cols = {}
    for src, (dst, _) in HUB_FIELDS.items():
        cols[dst] = r[src + "_txt"] if src in TEXT_LIST_COLS else r[src]
    gdf = gpd.GeoDataFrame(pd.DataFrame(cols), geometry=gpd.points_from_xy(r["x"], r["y"]),
                           crs=WGS)
    # hub x line table (the full line list does not fit a 254-character DBF field)
    rows = []
    for _, hub in r.iterrows():
        for lid in parse_list(hub["Line_Unique"]):
            known = lid in meta.index
            rows.append({
                "group": hub["group"], "hub_id": hub["hub_id"], "HubNameHE": hub["HubNameHE"],
                "HubTypeHE": hub["HubTypeHE"], "LINE_ID": lid,
                "Mode": meta.loc[lid, "Mode_Planned"] if known else None,
                "LineName": meta.loc[lid, "Line_Name"] if known else None,
            })
    hub_lines = pd.DataFrame(rows, columns=["group", "hub_id", "HubNameHE", "HubTypeHE",
                                            "LINE_ID", "Mode", "LineName"])
    fmap = pd.DataFrame([{"shapefile_field": d, "source_column": s, "description": t}
                         for s, (d, t) in HUB_FIELDS.items()])
    return gdf, hub_lines, fmap


# ----------------------------------------------------------------------------------------
# 2. lines and their nodes
# ----------------------------------------------------------------------------------------
def build_lines(run_dir: Path, meta: pd.DataFrame):
    """Line features, node x line points, the attribute table and the single-node lines."""
    nn = pd.read_csv(run_dir / NODES_FILE, encoding="utf-8-sig")
    _require_columns(nn, NODES_COLUMNS, NODES_FILE)
    nn = nn.drop_duplicates(["node", "LINE_ID"])
    seg_rows, node_rows, nogeom = [], [], []
    for lid, grp in nn.groupby("LINE_ID", sort=True):
        grp = grp.reset_index(drop=True)
        order = order_points(grp[["x_itm", "y_itm"]].to_numpy(float))
        grp = grp.iloc[order].reset_index(drop=True)
        xy = grp[["x_itm", "y_itm"]].to_numpy(float)
        known = lid in meta.index
        base = {
            "LINE_ID": lid, "Mode": grp["Mode_Planned"].iloc[0],
            "LineName": meta.loc[lid, "Line_Name"] if known else None,
            "Descr": meta.loc[lid, "Line_Description"] if known else None,
            "Area": meta.loc[lid, "Area"] if known else None, "NumNodes": len(grp),
        }
        for i, n in grp.iterrows():
            node_rows.append({
                "LINE_ID": lid, "Seq": i + 1, "node": int(n["node"]), "Mode": base["Mode"],
                "LineName": base["LineName"], "group": int(n["group"]), "hub_id": n["hub_id"],
                "geometry": Point(n["x_itm"], n["y_itm"]),
            })
        if len(grp) >= 2:
            seg_rows.append({**base, "geometry": LineString(xy)})
        else:
            nogeom.append(base)
    if not seg_rows:
        raise ExportError(f"{NODES_FILE} has no line with two or more nodes; nothing to draw.")
    lines = gpd.GeoDataFrame(seg_rows, geometry="geometry", crs=ITM)
    lines["LengthKm"] = (lines.length / 1000).round(2)
    nodes = gpd.GeoDataFrame(node_rows, geometry="geometry", crs=ITM)
    attrs = pd.DataFrame(lines.drop(columns="geometry"))
    nogeom = pd.DataFrame(nogeom, columns=[c for c in attrs.columns if c != "LengthKm"])
    return lines, nodes, attrs, nogeom


# ----------------------------------------------------------------------------------------
# READMEs (generic: built from the run)
# ----------------------------------------------------------------------------------------
README_HUBS = """HubPrioritizing - hubs (run {v})
================================
hubs_itm.shp / hubs_wgs84.shp   one point per hub the pipeline exported ({n} hubs, all hub types incl. 'Not Hub').
                                ITM = EPSG:2039, WGS84 = EPSG:4326. Point = the hub centroid of the run (x, y of the results table).
HubTypeHE                       ארצי (national) / מטרופוליני (metropolitan) / עירוני (local) / Not Hub (eligible but fewer than 3 lines).
field_map_hubs.csv              shapefile field -> results column -> meaning (field names are limited to 10 characters).
hub_lines.csv                   hub x line table (the full line list does not fit a shapefile field).
Hebrew text is stored as UTF-8 (.cpg sidecar); open with a recent QGIS / ArcGIS Pro.
Source: {results} of `hubs run` (version {v}){inputs}.
Only the hubs the pipeline exported are included: the groups that failed the eligibility filter
are in {groups_all} of the run{groups}.
"""

README_LINES = """HubPrioritizing - lines used by the pipeline (run {v})
=====================================================
lines_itm.shp / lines_wgs84.shp        one line feature per LINE_ID ({n_lines} lines, each direction is a separate line) built from the
                                       nodes of the run ({nodes}) and the lines file ({lines_file}).
line_nodes_itm.shp / _wgs84.shp        the node x line points ({n_nodes} rows) with Seq = position along the drawn line.
lines_attributes.csv                   attribute table of the line features.
lines_without_geometry.csv             {n_nogeom} lines that have a single node in the nodes table (no line can be drawn).
IMPORTANT: the pipeline has NO route geometry - only node points per line. The line features join the nodes of a line in the order of the
shortest open path through them (a visual aid). Long lines (rail, BRT) show as straight chords between distant nodes and branching or loop
lines can zig-zag. Do not use them as route alignments or for lengths (LengthKm is the length of the drawn polyline).
'Used' = the lines present in the pipeline's node x line table after the mode join and the drop rules (lines without a mode row and the
lines the pipeline drops are excluded). {n_unused} lines of the lines file are not in the nodes table and are not exported.
Hebrew text is stored as UTF-8 (.cpg sidecar). Mode = Mode_Planned of the lines file.
"""


def _input_names(manifest: dict) -> str:
    names = [_manifest_input(manifest, k) for k in ("nodeslines", "lines_mode", "demand")]
    names = [n for n in names if n]
    return f"; inputs: {', '.join(names)}" if names else ""


def _count_groups(run_dir: Path) -> str:
    try:
        n = len(pd.read_csv(run_dir / GROUPS_ALL_FILE, usecols=[0], encoding="utf-8-sig"))
    except (OSError, ValueError):
        return ""
    return f" (all {n:,} groups, with `eligible` and `exclusion_reason`)"


# ----------------------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------------------
def export(run_dir: Path, lines_file: Path, out_dir: Path, version: str, manifest: dict,
           zip_packages: bool = True) -> dict:
    """Write both packages (and their zips); return the counts."""
    meta = read_lines_meta(lines_file)
    hubs, hub_lines, fmap = build_hubs(run_dir, meta)
    lines, nodes, attrs, nogeom = build_lines(run_dir, meta)

    hubs_dir, lines_dir = out_dir / "pkg_hubs", out_dir / "pkg_lines"
    for folder in (hubs_dir, lines_dir):
        shutil.rmtree(folder, ignore_errors=True)
    write_layer(hubs, "hubs", hubs_dir)
    write_csv(hub_lines, hubs_dir / "hub_lines.csv")
    write_csv(fmap, hubs_dir / "field_map_hubs.csv")
    write_text(hubs_dir / "README.txt", README_HUBS.format(
        v=version, n=len(hubs), results=RESULTS_FILE, inputs=_input_names(manifest),
        groups=_count_groups(run_dir), groups_all=GROUPS_ALL_FILE))

    write_layer(lines, "lines", lines_dir)
    write_layer(nodes, "line_nodes", lines_dir)
    write_csv(attrs, lines_dir / "lines_attributes.csv")
    write_csv(nogeom, lines_dir / "lines_without_geometry.csv")
    used = set(nodes["LINE_ID"])
    write_text(lines_dir / "README.txt", README_LINES.format(
        v=version, n_lines=len(lines), n_nodes=len(nodes), n_nogeom=len(nogeom),
        n_unused=len(set(meta.index) - used),
        nodes=_manifest_input(manifest, "nodeslines") or NODES_FILE, lines_file=lines_file.name))

    if zip_packages:
        label = _label(version)
        zip_folder(hubs_dir, out_dir / f"hubs_hubprioritizing_{label}_shp.zip")
        zip_folder(lines_dir, out_dir / f"lines_hubprioritizing_{label}_shp.zip")
    return {"hubs": len(hubs), "lines": len(lines), "nodes": len(nodes),
            "lines_without_geometry": len(nogeom)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="export_shapefiles.py", description="Export a finished `hubs run` as shapefiles.")
    parser.add_argument("--run-dir", required=True,
                        help="output folder of `hubs run` (results, hub_identity, network_nodes)")
    parser.add_argument("--lines-file",
                        help="the run's Lines_and_Planned_Mode_*.csv "
                             "(default: the file recorded in run_manifest.json)")
    parser.add_argument("--out-dir", help="output folder (default: <run-dir>/shapefiles)")
    parser.add_argument("--version",
                        help="label for the zip names and READMEs "
                             "(default: version of run_manifest.json, else the run folder name)")
    parser.add_argument("--no-zip", action="store_true", help="do not write the zip files")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = Path(args.run_dir)
    try:
        if not run_dir.is_dir():
            raise ExportError(f"run folder not found: {run_dir}\n"
                              "Produce it with `hubs run --input-dir DIR --output-dir RUN`.")
        for name in (RESULTS_FILE, IDENTITY_FILE, NODES_FILE):
            _require_file(run_dir / name, name, "Produce it with "
                          f"`hubs run --input-dir DIR --output-dir {run_dir}`.")
        manifest = read_manifest(run_dir)
        lines_file = resolve_lines_file(args.lines_file, manifest)
        version = args.version or manifest.get("version") or run_dir.resolve().name
        out_dir = Path(args.out_dir) if args.out_dir else run_dir / "shapefiles"
        out_dir.mkdir(parents=True, exist_ok=True)
        counts = export(run_dir, lines_file, out_dir, str(version), manifest,
                        zip_packages=not args.no_zip)
    except ExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
