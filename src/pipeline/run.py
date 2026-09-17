"""
Orchestrator: input directory -> ``hub_prioritization_results.xlsx``.

:func:`run_pipeline` chains the stage modules in the notebook's order and returns
everything in memory; :func:`write_outputs` persists the workbook, its CSV twin, the
hub identity table, the run report and the effective configuration.
"""

from __future__ import annotations

import logging
import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from ..config import CRS_WGS84
from ..utils.logging import setup_logger
from .aggregate import add_influence_area, aggregate_to_groups, tag_bus_terminals
from .base_layer import add_influence_area_from_base, read_base_layer, tag_area_and_location_from_base, tag_bus_terminals_from_base
from .demand import apply_manual_demand, assign_demand, load_demand_workbook
from .export import write_results_csv, write_results_xlsx
from .grouping import apply_manual_groups, assign_hub_ids, group_hexes, hub_identity_table
from .inputs import InputError, InputSet, read_csv_auto, read_excel_sheets, read_shapefile, validate_inputs
from .network import (
    add_mode_line_columns,
    aggregate_to_hexes,
    apply_node_position_overrides,
    attach_modes,
    check_node_positions,
    load_nodeslines,
)
from .postprocess import finalize_columns, load_line_corrections, load_line_names, load_line_status
from .report import RunReport
from .scoring import score_hubs
from .settings import PipelineConfig
from .spatial_tags import tag_area_and_location

OPTIONAL_LAYER_KEYS = ("bus_terminals", "taz")
ALLOW_MISSING_LAYERS_ENV = "HUBS_ALLOW_MISSING_LAYERS"


@dataclass
class RunResult:
    results: pd.DataFrame  # final display table (70 columns + extras)
    groups: gpd.GeoDataFrame  # aggregated hubs with geometry
    scored: pd.DataFrame
    hexes: gpd.GeoDataFrame
    report: RunReport
    config: PipelineConfig
    base: pd.DataFrame | None = None  # the H3 base layer the run used (indexed by h3_index)
    inputs: InputSet | None = None
    outputs: dict[str, Path] = field(default_factory=dict)


def _read_optional_csv(inputs: InputSet, key: str, report: RunReport, **kwargs) -> pd.DataFrame | None:
    path = inputs.path(key)
    if path is None:
        report.info("inputs", f"optional input '{key}' not provided")
        return None
    df, enc = read_csv_auto(path, **kwargs)
    report.record_input(key, path, encoding=enc, source=inputs.files[key].source, date=inputs.files[key].date)
    return df


def _read_optional_layer(inputs: InputSet, key: str, report: RunReport, hebrew_columns=()) -> gpd.GeoDataFrame | None:
    path = inputs.path(key)
    if path is None:
        return None
    gdf, enc = read_shapefile(path, hebrew_columns=hebrew_columns)
    report.record_input(key, path, encoding=enc, source=inputs.files[key].source, rows=len(gdf))
    return gdf


def run_pipeline(
    cfg: PipelineConfig,
    inputs: InputSet,
    report: RunReport | None = None,
    allow_missing_layers: bool = False,
) -> RunResult:
    """Run every stage on the discovered inputs. Raises :class:`InputError` on invalid inputs.

    ``allow_missing_layers`` lets the bus-terminal and TAZ layers be absent (their scores
    become 0); it exists for tests and dry runs and is refused by the CLI unless the
    ``HUBS_ALLOW_MISSING_LAYERS=1`` environment variable is set.
    """
    report = report or RunReport()
    log = logging.getLogger("hubs.run")

    problems = validate_inputs(inputs, report, cfg.spatial_source, cfg.on_stale_base_layer)
    if allow_missing_layers and cfg.spatial_source == "shapefiles":
        problems = [p for p in problems if not any(f"'{k}'" in p for k in OPTIONAL_LAYER_KEYS)]
        for k in OPTIONAL_LAYER_KEYS:
            if not inputs.has(k):
                report.warn("inputs", f"layer '{k}' missing and allowed to be missing: its score is 0 for every hub")
    if problems:
        raise InputError(problems)
    report.info("config", "effective configuration", **cfg.to_dict())

    # --- Part 1: network -> hexagons -> groups ------------------------------------------
    log.info("Part 1: network and grouping")
    nodes_df, enc = read_csv_auto(inputs.path("nodeslines"))
    report.record_input("nodeslines", inputs.path("nodeslines"), encoding=enc, rows=len(nodes_df))
    lines_df, enc = read_csv_auto(inputs.path("lines_mode"), hebrew_columns=["Line_Name", "Line_Description"])
    report.record_input("lines_mode", inputs.path("lines_mode"), encoding=enc, rows=len(lines_df))

    nodes = load_nodeslines(nodes_df)
    nodes = apply_node_position_overrides(nodes, _read_optional_csv(inputs, "node_positions", report), report)
    nodes, position_problems = check_node_positions(nodes, cfg.node_position_tolerance_m, cfg.on_node_position_conflict, report)
    if position_problems and cfg.on_node_position_conflict == "error":
        raise InputError(position_problems)
    nodes = attach_modes(nodes, lines_df, cfg.drop_line_rules, report)
    hexes = aggregate_to_hexes(nodes, cfg.h3_resolution)
    hexes = add_mode_line_columns(hexes, cfg.per_mode_lines_method)
    report.set_metric("nodes", int(nodes["node"].nunique()))
    report.set_metric("hexagons", len(hexes))

    # area / ring per hexagon comes before the manual merges so a merge row can be
    # restricted to one demand model (its 'model' column is checked against the location)
    base = None
    if cfg.spatial_source == "h3_base":
        base_path = inputs.path("h3_base")
        if base_path is None:
            raise InputError(["spatial_source=h3_base but no h3_base*.parquet was found; run 'hubs prepare-base' first"])
        base, manifest = read_base_layer(base_path)
        provenance = {}
        if manifest:
            provenance = {
                "built": manifest.get("built"),
                "resolution": manifest.get("resolution"),
                "sources": {k: v.get("sha256", "")[:12] for k, v in manifest.get("sources", {}).items()},
            }
        report.record_input("h3_base", base_path, source=inputs.files["h3_base"].source, rows=len(base), **provenance)
        if manifest and manifest.get("resolution") != cfg.h3_resolution:
            raise InputError([f"h3_base was built at resolution {manifest.get('resolution')}, the run uses {cfg.h3_resolution}"])
        if manifest and float(manifest.get("terminal_buffer_m", cfg.terminal_buffer_m)) != float(cfg.terminal_buffer_m):
            report.warn("inputs", f"h3_base was built with terminal_buffer_m={manifest.get('terminal_buffer_m')}; the run's {cfg.terminal_buffer_m} is ignored")
        hexes = tag_area_and_location_from_base(hexes, base, report)
    else:
        metro = _read_optional_layer(inputs, "metro", report, ["METRO_NAME", "ZONE_NAME"])
        districts = _read_optional_layer(inputs, "districts", report, ["MACHOZ"])
        hexes = tag_area_and_location(hexes, metro, districts, report)

    hexes = group_hexes(hexes, cfg.merge_threshold_m, cfg.merge_tolerance_m)
    hexes = apply_manual_groups(hexes, _read_optional_csv(inputs, "is_same_group", report), report)
    hexes = assign_hub_ids(hexes)
    if cfg.geocode:
        report.warn("grouping", "geocoding is not implemented in the pipeline; address set to 'Not geocoded'")
    hexes["address"] = "Not geocoded"
    report.set_metric("groups", int(hexes["group"].nunique()))

    # --- Part 2: demand ------------------------------------------------------------------
    log.info("Part 2: demand")
    sheets = read_excel_sheets(inputs.path("demand"))
    report.record_input("demand", inputs.path("demand"), sheets=list(sheets))
    by_region = load_demand_workbook(sheets, report)
    hexes = assign_demand(hexes, by_region, cfg.overlay_regions, report)
    hexes = apply_manual_demand(hexes, _read_optional_csv(inputs, "manual_demand", report), report)

    # --- Part 3: groups, terminals, influence area ---------------------------------------
    log.info("Part 3: aggregation, terminals, influence area")
    groups = aggregate_to_groups(hexes)
    if base is not None:
        groups = tag_bus_terminals_from_base(groups, hexes, base, report)
        groups = add_influence_area_from_base(groups, base, cfg.influence_rings, cfg.h3_resolution, cfg.influence_cell_rule, report)
    else:
        terminals = _read_optional_layer(inputs, "bus_terminals", report, ["term_type"])
        groups = tag_bus_terminals(groups, terminals, cfg.terminal_buffer_m, report)
        taz = _read_optional_layer(inputs, "taz", report)
        groups = add_influence_area(groups, taz, cfg.influence_rings, report)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # geographic centroid, as the notebook computed it
        centroids = groups.geometry.to_crs(CRS_WGS84).centroid
    groups["x"] = centroids.x.to_numpy()
    groups["y"] = centroids.y.to_numpy()

    # --- Part 4: scoring -----------------------------------------------------------------
    log.info("Part 4: scoring")
    scored = score_hubs(
        pd.DataFrame(groups.drop(columns=groups.geometry.name)),
        apply_eligibility_filter=cfg.apply_eligibility_filter,
        require_non_rail=cfg.require_non_rail_mode,
        alpha=cfg.mode_diversity_alpha,
        rings=cfg.influence_rings,
        decay_beta=cfg.distance_decay_beta,
        decay_midpoints=cfg.pop_emp_decay_midpoints or None,
        n_iter=cfg.mc_iterations,
        seed=cfg.mc_seed,
        scope=cfg.mc_scope,
        report=report,
    )
    report.set_metric("hubs_scored", len(scored))

    # --- Part 5: display columns ---------------------------------------------------------
    log.info("Part 5: display columns")
    names: dict[str, str] = {}
    if inputs.has("line_names"):
        names_df = _read_optional_csv(inputs, "line_names", report, header=None)
        names = load_line_names(names_df, report)
    extra_df = _read_optional_csv(inputs, "line_names_extra", report, hebrew_columns=["Line_n_Mode"])
    if extra_df is not None:
        for k, v in zip(extra_df["LineName"], extra_df["Line_n_Mode"]):
            names.setdefault(str(k).strip(), str(v).strip())
    status_df = _read_optional_csv(inputs, "line_status", report)
    status = load_line_status(status_df, report) if status_df is not None else {}
    corr_df = _read_optional_csv(inputs, "line_corrections", report)
    corrections = load_line_corrections(corr_df) if corr_df is not None else {}
    hub_names = _read_optional_csv(inputs, "hub_names", report, hebrew_columns=["HubNameHE"])

    results = finalize_columns(
        scored,
        line_names=names,
        line_status=status,
        line_corrections=corrections,
        hub_names=hub_names,
        renormalize_globally=cfg.renormalize_globally,
        report=report,
    )
    report.set_metric("hub_type_counts_final", results["HubType"].value_counts().to_dict())
    top = results.nsmallest(10, "Rank_TS_MC")[["group", "HubNameHE", "HubType", "TotalScore_MC"]]
    report.info("results", "top 10 hubs by TotalScore_MC", top=top.to_dict("records"))
    return RunResult(results=results, groups=groups, scored=scored, hexes=hexes, report=report, config=cfg, base=base, inputs=inputs)


def write_outputs(result: RunResult, output_dir: Path | str, version: str | None = None) -> dict[str, Path]:
    """Write the workbook, CSV, identity table, cell layer, report, config and run manifest
    into ``output_dir``. ``version`` names the run (default: the newest input date)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cfg = result.config
    paths: dict[str, Path] = {}
    paths["xlsx"] = write_results_xlsx(
        result.results, out / f"{cfg.output_basename}.xlsx", sheet_name=cfg.output_sheet_name, table_name=cfg.output_table_name, extra_columns=cfg.extra_columns
    )
    paths["csv"] = write_results_csv(result.results, out / f"{cfg.output_basename}.csv", extra_columns=cfg.extra_columns)

    identity = hub_identity_table(result.hexes).merge(result.results[["group", "HubNameHE", "HubType"]], on="group", how="left")
    paths["hub_identity"] = out / "hub_identity.csv"
    identity.to_csv(paths["hub_identity"], index=False, encoding="utf-8-sig")

    if result.base is not None and cfg.h3_layer_format != "none":
        from .h3_export import build_h3_layer, write_h3_layer

        layer = build_h3_layer(result.base, result.hexes, result.results, result.groups, cfg.influence_rings, cfg.h3_resolution, cfg.h3_layer_extent)
        paths["h3_layer"] = write_h3_layer(layer, out / "h3_layer", cfg.h3_layer_format)
        result.report.set_metric("h3_layer_cells", len(layer))
        result.report.info("outputs", f"H3 cell layer written ({cfg.h3_layer_extent} extent, {len(layer)} cells)", path=str(paths["h3_layer"]))

    paths["run_config"] = out / "run_config.json"
    paths["run_config"].write_text(cfg.to_json(), encoding="utf-8")
    if result.inputs is not None:
        from .versioning import build_run_manifest, write_run_manifest

        manifest = build_run_manifest(result.inputs, cfg, result.results, version, paths)
        result.report.set_metric("version", manifest["version"])
        paths["run_manifest"] = write_run_manifest(manifest, out)
    md, js = result.report.write(out)
    paths["report_md"], paths["report_json"] = md, js

    if cfg.keep_intermediates:
        inter = out / "intermediate"
        inter.mkdir(exist_ok=True)
        _to_geojson(result.hexes, inter / "hexes.geojson")
        _to_geojson(result.groups, inter / "groups.geojson")
        result.scored.to_csv(inter / "scored.csv", index=False, encoding="utf-8-sig")
        paths["intermediate"] = inter
    result.outputs = paths
    return paths


def _to_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    plain = gdf.copy()
    for col in plain.columns:
        if col != plain.geometry.name and plain[col].map(lambda v: isinstance(v, (list, dict))).any():
            plain[col] = plain[col].map(lambda v: str(v) if isinstance(v, (list, dict)) else v)
    plain.to_file(path, driver="GeoJSON")


def prepare_base_layer(
    inputs: InputSet,
    out_path: Path | str,
    resolution: int = 10,
    terminal_buffer_m: float | None = None,
    report: RunReport | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Build ``h3_base.parquet`` (+ manifest) from the four reference shapefiles."""
    from .base_layer import build_base_layer, build_manifest, write_base_layer
    from ..config import TERMINAL_PROXIMITY_DISTANCE_M

    report = report or RunReport()
    buffer_m = TERMINAL_PROXIMITY_DISTANCE_M if terminal_buffer_m is None else terminal_buffer_m
    missing = [k for k in ("metro", "districts", "bus_terminals", "taz") if not inputs.has(k)]
    if missing:
        raise InputError([f"prepare-base needs the reference layers {missing}"])
    metro = _read_optional_layer(inputs, "metro", report, ["METRO_NAME", "ZONE_NAME"])
    districts = _read_optional_layer(inputs, "districts", report, ["MACHOZ"])
    terminals = _read_optional_layer(inputs, "bus_terminals", report, ["term_type"])
    taz = _read_optional_layer(inputs, "taz", report)
    layer = build_base_layer(metro, districts, terminals, taz, resolution, buffer_m, report)
    manifest = build_manifest({k: inputs.path(k) for k in ("metro", "districts", "bus_terminals", "taz")}, resolution, buffer_m, len(layer))
    write_base_layer(layer, out_path, manifest)
    return layer, manifest


def prepare_base_from_cli(args: Any) -> int:
    """Entry point used by ``hubs prepare-base``."""
    from .inputs import discover_inputs

    setup_logger("hubs")
    log = logging.getLogger("hubs.prepare")
    reference_dir = Path(args.reference_dir)
    out_path = Path(args.out) if args.out else reference_dir / "h3_base.parquet"
    inputs = discover_inputs(args.input_dir or reference_dir, reference_dir, _parse_file_overrides_safe(args))
    report = RunReport()
    try:
        layer, manifest = prepare_base_layer(inputs, out_path, args.resolution, args.terminal_buffer_m, report)
    except InputError as exc:
        print(str(exc))
        return 1
    for entry in report.warnings:
        log.warning("%s: %s", entry.section, entry.message)
    print(f"✓ base layer written: {out_path} ({len(layer):,} cells, resolution {manifest['resolution']})")
    print(f"  manifest : {out_path.with_name(out_path.stem + '.manifest.json')}")
    return 0


def export_h3_from_cli(args: Any) -> int:
    """Entry point used by ``hubs export-h3``: the base layer alone, in a shareable format."""
    from .base_layer import read_base_layer
    from .h3_export import build_h3_layer, write_h3_layer
    from .inputs import discover_inputs

    setup_logger("hubs")
    reference_dir = Path(args.reference_dir)
    inputs = discover_inputs(args.input_dir or reference_dir, reference_dir, _parse_file_overrides_safe(args))
    base_path = inputs.path("h3_base")
    if base_path is None:
        print(f"no h3_base*.parquet in {reference_dir}; run 'hubs prepare-base' first")
        return 1
    base, manifest = read_base_layer(base_path)
    resolution = int(manifest.get("resolution", 10)) if manifest else 10
    layer = build_h3_layer(base, extent="all", resolution=resolution)
    path = write_h3_layer(layer, args.out, args.format)
    print(f"✓ {len(layer):,} cells written: {path}")
    return 0


def compare_from_cli(args: Any) -> int:
    """Entry point used by ``hubs compare A B``."""
    from .versioning import compare_runs, write_comparison

    try:
        comp = compare_runs(args.run_a, args.run_b)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1
    out_dir = Path(args.out) if args.out else Path(args.run_b)
    paths = write_comparison(comp, out_dir)
    s = comp["summary"]
    print(f"✓ {s['a']['version']} → {s['b']['version']}: {s['matched_by_hub_id']} hubs unchanged in membership, {s['matched_by_nodes']} changed membership, {s['added']} added, {s['removed']} removed")
    print(f"  tier changes {s['tier_changes']}, score changed {s['score_changed']}, rank changed {s['rank_changed']}, inputs changed {len(s['inputs_changed'])}, settings changed {len(s['config_changed'])}")
    print(f"  report : {paths['md']}")
    print(f"  table  : {paths['csv']}")
    return 0


def runs_from_cli(args: Any) -> int:
    """Entry point used by ``hubs runs DIR``."""
    from .versioning import list_runs

    table = list_runs(args.root)
    if table.empty:
        print(f"no run manifests found under {args.root}")
        return 1
    print(table.to_string(index=False))
    return 0


def _parse_file_overrides_safe(args: Any) -> dict[str, Path]:
    from ..cli import _parse_file_overrides

    return _parse_file_overrides(getattr(args, "file", []) or [])


def run_from_cli(args: Any) -> int:
    """Entry point used by ``hubs run``."""
    from ..cli import _load_config_or_exit, _parse_file_overrides
    from .inputs import discover_inputs

    cfg = _load_config_or_exit(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    setup_logger("hubs", log_file=output_dir / "run.log")
    log = logging.getLogger("hubs.run")

    report = RunReport()
    inputs = discover_inputs(args.input_dir, args.reference_dir, _parse_file_overrides(args.file))
    allow_missing = os.environ.get(ALLOW_MISSING_LAYERS_ENV, "").strip() in ("1", "true", "yes")
    if allow_missing:
        log.warning("%s is set: missing bus terminal / TAZ layers are tolerated (scores of 0)", ALLOW_MISSING_LAYERS_ENV)
    try:
        result = run_pipeline(cfg, inputs, report, allow_missing_layers=allow_missing)
    except InputError as exc:
        print(str(exc))
        print("\nRun 'hubs validate --input-dir ...' for the full input check.")
        return 1

    paths = write_outputs(result, output_dir, getattr(args, "version", None))
    print(f"✓ {len(result.results)} hubs written (version {result.report.metrics.get('version')})")
    print(f"  workbook : {paths['xlsx']}")
    print(f"  csv      : {paths['csv']}")
    print(f"  report   : {paths['report_md']}")
    print(f"  manifest : {paths.get('run_manifest')}")
    n_warn = len(result.report.warnings)
    if n_warn:
        print(f"  {n_warn} warning(s) in the report; review them before publishing.")
    return 0
