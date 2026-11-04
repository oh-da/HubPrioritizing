"""Orchestrator of ``hubs compare-network``: a finished run against the agency's network.

Reads the run's ``hub_groups_all.csv`` and ``network_nodes.csv`` and the agency GeoPackage,
corrects our node positions by the estimated local offset, compares the routes (step 1) and the
hubs (step 2) and writes the workbook, GeoPackage, two map pages, ``compare_config.json`` and
``compare_report.md`` / ``.json``. The stages are the pure functions of :mod:`src.compare`; this
module only reads the run files, wires the stages and writes the results.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

from ..pipeline.report import RunReport
from .agency import AgencyNetwork, read_agency_network, read_tod_hubs
from .export import build_layers, build_sheets, write_gpkg, write_workbook
from .hubs import RELATIONS, HubComparison, build_our_hubs, match_hubs
from .maps import write_hubs_map, write_routes_map
from .modes import load_mode_map
from .offset import apply_shift, estimate_shift
from .routes import STATUSES, RouteComparison, build_our_routes, line_route_map, match_routes
from .settings import CompareConfig

SECTION = "compare"
GROUPS_FILE = "hub_groups_all.csv"
NODES_FILE = "network_nodes.csv"
RERUN_HINT = "re-run `hubs run` with this version"
LIST_SEP = ";"
GROUP_TEXT_COLUMNS = ("hub_id", "HubNameHE", "area", "Mode_Planned", "Line_Unique",
                      "exclusion_reason", "HubType")
NODE_TEXT_COLUMNS = ("node", "LINE_ID", "line_name", "Mode_Planned", "hub_id")
OUTPUT_NAMES = {
    "workbook": "network_comparison.xlsx",
    "gpkg": "network_comparison.gpkg",
    "routes_map": "network_comparison_routes.html",
    "hubs_map": "network_comparison_hubs.html",
    "config": "compare_config.json",
}
REPORT_STEM = "compare_report"


class MissingRunFiles(FileNotFoundError):
    """The run directory lacks the files ``hubs compare-network`` reads (an older run)."""

    def __init__(self, run_dir: Path, missing: list[str]):
        self.run_dir = Path(run_dir)
        self.missing = list(missing)
        super().__init__(
            f"{self.run_dir} has no {', '.join(self.missing)}: {RERUN_HINT} "
            "(runs made before the network comparison do not write these files)"
        )


@dataclass
class OurNetwork:
    """Our side of the comparison.

    Attributes:
        nodes: ``network_nodes.csv`` rows with ``x_corr`` / ``y_corr`` when the offset is applied.
        groups: ``hub_groups_all.csv`` rows (list columns as lists).
        routes: :func:`routes.build_our_routes` output.
        hubs: :func:`hubs.build_our_hubs` output.
    """

    nodes: pd.DataFrame
    groups: pd.DataFrame
    routes: pd.DataFrame
    hubs: gpd.GeoDataFrame


@dataclass
class NetworkComparison:
    """Everything :func:`write_comparison` needs.

    Attributes:
        routes: Step-1 result.
        hubs: Step-2 result.
        agency: The agency network.
        ours: Our routes, hubs and (corrected) nodes.
        report: Findings and metrics (written as ``compare_report``).
        cfg: The effective configuration.
        inputs: Input name -> file name, SHA-256 and counts, plus ``run`` (version, dir).
        global_shift: The global median offset ``(dx, dy)`` added to our nodes (zero when the
            offset is not applied).
    """

    routes: RouteComparison
    hubs: HubComparison
    agency: AgencyNetwork
    ours: OurNetwork
    report: RunReport
    cfg: CompareConfig
    inputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    global_shift: tuple[float, float] = (0.0, 0.0)




def _sha256(path: Path) -> str:
    with Path(path).open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def _split(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [s.strip() for s in value.split(LIST_SEP) if s.strip()]


def read_run_tables(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read ``hub_groups_all.csv`` and ``network_nodes.csv`` of a finished run.

    Args:
        run_dir: Output directory of ``hubs run``.

    Returns:
        ``(groups, nodes)``. Identifier and text columns are strings, ``Mode_Planned`` /
        ``Line_Unique`` of the groups are lists (split on ``;``), an empty
        ``exclusion_reason`` is ``""``.

    Raises:
        MissingRunFiles: If either file is absent.
    """
    run_dir = Path(run_dir)
    missing = [name for name in (GROUPS_FILE, NODES_FILE) if not (run_dir / name).exists()]
    if missing:
        raise MissingRunFiles(run_dir, missing)
    groups = pd.read_csv(run_dir / GROUPS_FILE, encoding="utf-8-sig",
                         dtype={c: str for c in GROUP_TEXT_COLUMNS})
    nodes = pd.read_csv(run_dir / NODES_FILE, encoding="utf-8-sig",
                        dtype={c: str for c in NODE_TEXT_COLUMNS})
    for col in ("Mode_Planned", "Line_Unique"):
        if col in groups.columns:
            groups[col] = [_split(v) for v in groups[col]]
    if "exclusion_reason" in groups.columns:
        groups["exclusion_reason"] = groups["exclusion_reason"].fillna("")
    if "line_name" not in nodes.columns:
        nodes["line_name"] = ""
    return groups, nodes


def _run_version(run_dir: Path) -> str:
    from ..pipeline.versioning import read_run_manifest

    try:
        manifest = read_run_manifest(run_dir) or {}
    except (OSError, ValueError):
        manifest = {}
    return str(manifest.get("version") or Path(run_dir).resolve().name)




def correct_positions(
    nodes: pd.DataFrame, agency: AgencyNetwork, cfg: CompareConfig, report: RunReport
) -> tuple[pd.DataFrame, np.ndarray]:
    """Add ``x_corr`` / ``y_corr``: our node positions moved by the estimated local offset.

    The shift is estimated once per distinct node against every agency stop of any mode
    (``stop_tol_m``, ``offset_radius_m``, ``offset_passes``). Non-finite coordinates on either
    side are left out of the estimate; such nodes get the global shift.

    Args:
        nodes: ``network_nodes.csv`` rows (``node``, ``x_itm``, ``y_itm``).
        agency: The agency network (its ``stops`` are used).
        cfg: Comparison settings.
        report: Receives the global shift as metrics and an info entry.

    Returns:
        ``(nodes with x_corr / y_corr, global shift (2,))``.
    """
    out = nodes.copy()
    x = pd.to_numeric(out["x_itm"], errors="coerce")
    y = pd.to_numeric(out["y_itm"], errors="coerce")
    finite = np.isfinite(x.to_numpy(float)) & np.isfinite(y.to_numpy(float))
    distinct = out.loc[finite, ["node"]].assign(_x=x[finite], _y=y[finite])
    distinct = distinct.drop_duplicates("node").reset_index(drop=True)
    stops = agency.stops
    stops_xy = np.empty((0, 2))
    if len(stops):
        geoms = stops.geometry
        ok = geoms.notna() & ~geoms.is_empty
        stops_xy = np.column_stack([geoms[ok].x, geoms[ok].y]) if ok.any() else stops_xy
        stops_xy = stops_xy[np.isfinite(stops_xy).all(axis=1)]
    node_xy = distinct[["_x", "_y"]].to_numpy(float)
    shift, glob = estimate_shift(node_xy, stops_xy, cfg.stop_tol_m, cfg.offset_radius_m,
                                 cfg.offset_passes)
    moved = apply_shift(node_xy, shift)
    corr_x = dict(zip(distinct["node"], moved[:, 0]))
    corr_y = dict(zip(distinct["node"], moved[:, 1]))
    out["x_corr"] = [corr_x.get(n, xv + glob[0]) for n, xv in zip(out["node"], x)]
    out["y_corr"] = [corr_y.get(n, yv + glob[1]) for n, yv in zip(out["node"], y)]

    dist = np.hypot(shift[:, 0], shift[:, 1]) if len(shift) else np.zeros(1)
    report.set_metric("offset_global_dx_m", round(float(glob[0]), 3))
    report.set_metric("offset_global_dy_m", round(float(glob[1]), 3))
    report.set_metric("offset_max_shift_m", round(float(dist.max()), 3))
    report.info(
        "offset",
        f"global shift ({glob[0]:.1f}, {glob[1]:.1f}) m from {len(node_xy)} nodes and "
        f"{len(stops_xy)} agency stops; local shifts up to {dist.max():.1f} m",
        nodes_left_out=int(len(out.loc[~finite, "node"].unique())),
    )
    return out, glob




def _file_entry(path: Path, **counts: Any) -> dict[str, Any]:
    return {"file": Path(path).name, "sha256": _sha256(path), **counts}


def compare_networks(
    run_dir: Path,
    agency_gpkg: Path,
    cfg: CompareConfig,
    agency_meta: Path | None = None,
    tod_gpkg: Path | None = None,
    report: RunReport | None = None,
) -> NetworkComparison:
    """Compare a finished run with the agency's network (steps 1 and 2).

    Args:
        run_dir: Output directory of ``hubs run`` (with ``hub_groups_all.csv`` and
            ``network_nodes.csv``).
        agency_gpkg: ``MT_Network.gpkg``.
        cfg: Comparison settings.
        agency_meta: Optional ``MT_Network_MetaData.xlsx`` (code labels).
        tod_gpkg: Optional scraped TOD map for the agency-hub cross-check.
        report: Report to record findings on (a new one when omitted).

    Returns:
        The comparison with everything :func:`write_comparison` writes.

    Raises:
        MissingRunFiles: If the run directory lacks either CSV.
        InputError: If the agency GeoPackage, the workbook or the TOD map is invalid.
    """
    report = report if report is not None else RunReport()
    run_dir = Path(run_dir)
    groups, nodes = read_run_tables(run_dir)
    agency = read_agency_network(Path(agency_gpkg), agency_meta, cfg, report)
    tod = read_tod_hubs(Path(tod_gpkg)) if tod_gpkg is not None else None

    inputs: dict[str, dict[str, Any]] = {
        "run": {"version": _run_version(run_dir), "dir": str(run_dir)},
        "hub_groups_all": _file_entry(run_dir / GROUPS_FILE, rows=len(groups)),
        "network_nodes": _file_entry(run_dir / NODES_FILE, rows=len(nodes)),
        "agency_gpkg": _file_entry(agency_gpkg, routes=len(agency.routes),
                                   stops=len(agency.stops), hubs=len(agency.hubs)),
    }
    if agency_meta is not None:
        inputs["agency_meta"] = _file_entry(agency_meta, labels=len(agency.labels))
    if tod_gpkg is not None:
        inputs["tod_gpkg"] = _file_entry(tod_gpkg, hubs=len(tod))
    sources = {"run": run_dir, "hub_groups_all": run_dir / GROUPS_FILE,
               "network_nodes": run_dir / NODES_FILE, "agency_gpkg": agency_gpkg,
               "agency_meta": agency_meta, "tod_gpkg": tod_gpkg}
    for key, entry in inputs.items():
        report.record_input(key, Path(sources[key]), **{k: v for k, v in entry.items()
                                                        if k != "dir"})

    glob = np.zeros(2)
    if cfg.apply_offset:
        nodes, glob = correct_positions(nodes, agency, cfg, report)
    else:
        report.info("offset", "offset not applied (apply_offset = false)")

    mode_map = load_mode_map()
    our_routes = build_our_routes(nodes, mode_map)  # attrs carry the dropped-node count
    routes = match_routes(our_routes, agency, cfg, report)
    our_hubs = build_our_hubs(groups, nodes, mode_map, line_route_map(our_routes))
    hubs = match_hubs(our_hubs, agency, routes, cfg, tod=tod, report=report)
    unmapped = sorted({m for m in nodes["Mode_Planned"].dropna() if mode_map.get(m) is None})
    if unmapped:
        report.warn(SECTION, f"mode(s) without an agency counterpart: {', '.join(unmapped)}")
    ours = OurNetwork(nodes=nodes, groups=groups, routes=our_routes, hubs=our_hubs)
    return NetworkComparison(routes=routes, hubs=hubs, agency=agency, ours=ours, report=report,
                             cfg=cfg, inputs=inputs,
                             global_shift=(float(glob[0]), float(glob[1])))


def write_comparison(result: NetworkComparison, out_dir: Path) -> dict[str, Path]:
    """Write every output of ``hubs compare-network`` to ``out_dir``.

    Args:
        result: :func:`compare_networks` output.
        out_dir: Target directory (created when missing).

    Returns:
        Output name -> path: ``workbook``, ``gpkg``, ``routes_map``, ``hubs_map``, ``config``,
        ``report_md``, ``report_json``.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {key: out / name for key, name in OUTPUT_NAMES.items()}
    sheets = build_sheets(result.routes, result.hubs, result.agency, result.cfg, result.inputs)
    write_workbook(paths["workbook"], sheets)
    layers = build_layers(result.routes, result.ours.routes, result.hubs, result.agency,
                          result.ours.hubs)
    write_gpkg(paths["gpkg"], layers)
    write_routes_map(paths["routes_map"], layers)
    write_hubs_map(paths["hubs_map"], layers)
    paths["config"].write_text(result.cfg.to_json() + "\n", encoding="utf-8")
    paths["report_md"], paths["report_json"] = result.report.write(out, stem=REPORT_STEM)
    return paths


def _print_summary(result: NetworkComparison, paths: dict[str, Path]) -> None:
    status = result.routes.routes["status"].value_counts()
    relation = result.hubs.hubs["relation"].value_counts()
    dx, dy = result.global_shift
    run = result.inputs.get("run", {})
    print(f"✓ network comparison of run {run.get('version')}")
    print(f"  offset : {'applied' if result.cfg.apply_offset else 'not applied'}"
          f" (global shift {dx:.1f}, {dy:.1f} m)")
    print("  routes : " + ", ".join(f"{s} {int(status.get(s, 0))}" for s in STATUSES))
    print("  hubs   : " + ", ".join(f"{r} {int(relation.get(r, 0))}" for r in RELATIONS))
    n_warn = len(result.report.warnings)
    print(f"  report : {n_warn} warning(s)")
    print("  files  :")
    for path in paths.values():
        print(f"    {path}")


def compare_network_from_cli(args: Any) -> int:
    """Entry point used by ``hubs compare-network``.

    Returns:
        ``0`` on success, ``1`` when the run files are missing or an input is invalid.

    Raises:
        SystemExit: On a configuration error (bad ``--set`` value or YAML file).
    """
    from ..pipeline.inputs import InputError
    from ..pipeline.settings import ConfigError, parse_set_overrides
    from .settings import load_compare_config

    try:
        cfg = load_compare_config(args.config, parse_set_overrides(args.set))
    except (ConfigError, FileNotFoundError) as exc:
        raise SystemExit(f"configuration error: {exc}")
    try:
        result = compare_networks(args.run, args.agency_gpkg, cfg, agency_meta=args.agency_meta,
                                  tod_gpkg=args.tod_gpkg)
    except MissingRunFiles as exc:
        print(f"✗ {exc}")
        return 1
    except InputError as exc:
        print(f"✗ {len(exc.problems)} input problem(s):")
        for problem in exc.problems:
            print(f"  - {problem}")
        return 1
    paths = write_comparison(result, Path(args.out) if args.out else Path(args.run))
    _print_summary(result, paths)
    return 0
