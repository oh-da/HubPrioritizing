"""
``hubs`` command line interface.

    hubs validate    --input-dir DIR [--reference-dir DIR]
    hubs show-config [--config pipeline.yaml] [--set key=value ...] [--defaults]
    hubs run         --input-dir DIR --output-dir DIR [--version NAME] [...]
    hubs compare     OUT_A OUT_B [--out DIR]
    hubs runs        [DIR]
    hubs serve       [--root DIR] [--port N]
    hubs prepare-base / export-h3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .config import REFERENCE_DATA_DIR
from .pipeline.inputs import discover_inputs, validate_inputs
from .pipeline.report import RunReport
from .pipeline.settings import CONFIG_KEYS, ConfigError, default_yaml, load_config, parse_set_overrides


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hubs", description="Hub prioritization pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser, with_input: bool = True) -> None:
        if with_input:
            p.add_argument("--input-dir", required=True, type=Path, help="directory with the per-run model exports")
            p.add_argument(
                "--reference-dir",
                type=Path,
                default=REFERENCE_DATA_DIR,
                help=f"directory with stable reference layers (default: {REFERENCE_DATA_DIR})",
            )
            p.add_argument(
                "--file",
                action="append",
                default=[],
                metavar="KEY=PATH",
                help="pin a specific file for an input key (repeatable)",
            )
        p.add_argument("--config", type=Path, help="pipeline.yaml with configuration overrides")
        p.add_argument(
            "--set",
            action="append",
            default=[],
            metavar="KEY=VALUE",
            help=f"override a config value (repeatable). Keys: {', '.join(CONFIG_KEYS)}",
        )

    p_val = sub.add_parser("validate", help="discover and validate inputs without processing")
    add_common(p_val)

    p_cfg = sub.add_parser("show-config", help="print the effective configuration")
    add_common(p_cfg, with_input=False)
    p_cfg.add_argument("--defaults", action="store_true", help="print the built-in defaults as YAML")

    p_run = sub.add_parser("run", help="run the full pipeline")
    add_common(p_run)
    p_run.add_argument("--output-dir", required=True, type=Path)
    p_run.add_argument("--version", default=None, help="name of this run (default: the newest date among the model exports)")

    p_base = sub.add_parser("prepare-base", help="pre-allocate the reference layers to H3 cells (h3_base.parquet)")
    p_base.add_argument("--reference-dir", type=Path, default=REFERENCE_DATA_DIR, help=f"directory with the four shapefiles (default: {REFERENCE_DATA_DIR})")
    p_base.add_argument("--input-dir", type=Path, default=None, help="optional directory whose same-named layers override the reference copies")
    p_base.add_argument("--out", type=Path, default=None, help="output parquet (default: <reference-dir>/h3_base.parquet)")
    p_base.add_argument("--resolution", type=int, default=10, help="H3 resolution (must match the run's h3_resolution)")
    p_base.add_argument("--terminal-buffer-m", type=float, default=None, help="terminal proximity distance (default: config value, 200 m)")
    p_base.add_argument("--file", action="append", default=[], metavar="KEY=PATH", help="pin a specific file for a layer key (repeatable)")

    p_cmp = sub.add_parser("compare", help="compare two run output directories (A = before, B = after)")
    p_cmp.add_argument("run_a", type=Path, help="output directory of the earlier run")
    p_cmp.add_argument("run_b", type=Path, help="output directory of the later run")
    p_cmp.add_argument("--out", type=Path, default=None, help="where to write compare_<A>_vs_<B>.md/.csv/.json (default: run B's directory)")

    p_runs = sub.add_parser("runs", help="list the run versions found under a directory")
    p_runs.add_argument("root", type=Path, nargs="?", default=Path("."), help="directory to search (recursively) for run_manifest.json")

    p_srv = sub.add_parser("serve", help="open the local web page (choose inputs, validate, run, compare versions)")
    p_srv.add_argument("--root", type=Path, default=Path("."), help="folder the page browses and lists runs from (default: current directory)")
    p_srv.add_argument("--reference-dir", type=Path, default=REFERENCE_DATA_DIR, help=f"reference data directory (default: {REFERENCE_DATA_DIR})")
    p_srv.add_argument("--port", type=int, default=8765, help="port on 127.0.0.1 (default 8765; 0 = any free port)")
    p_srv.add_argument("--host", default="127.0.0.1", help=argparse.SUPPRESS)
    p_srv.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")

    p_exp = sub.add_parser("export-h3", help="write the H3 base layer (every cell, all attributes) in a shareable GIS format")
    p_exp.add_argument("--out", required=True, type=Path, help="output file; the extension follows --format")
    p_exp.add_argument("--format", default="gpkg", choices=["gpkg", "geojson", "parquet", "csv"], help="GeoPackage (default), GeoJSON, GeoParquet or CSV with WKT")
    p_exp.add_argument("--reference-dir", type=Path, default=REFERENCE_DATA_DIR, help=f"directory holding h3_base.parquet (default: {REFERENCE_DATA_DIR})")
    p_exp.add_argument("--input-dir", type=Path, default=None, help="optional directory whose h3_base*.parquet overrides the reference copy")
    p_exp.add_argument("--file", action="append", default=[], metavar="KEY=PATH", help="pin a specific file (h3_base=PATH)")

    return parser


def _parse_file_overrides(items: Sequence[str]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--file expects KEY=PATH, got {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = Path(v.strip())
    return out


def _load_config_or_exit(args: argparse.Namespace):
    try:
        return load_config(args.config, parse_set_overrides(args.set))
    except (ConfigError, FileNotFoundError) as exc:
        raise SystemExit(f"configuration error: {exc}")


def cmd_validate(args: argparse.Namespace) -> int:
    cfg = _load_config_or_exit(args)
    report = RunReport()
    inputs = discover_inputs(args.input_dir, args.reference_dir, _parse_file_overrides(args.file))
    problems = validate_inputs(inputs, report, cfg.spatial_source, cfg.on_stale_base_layer)

    print(f"Input directory:     {inputs.input_dir}")
    print(f"Reference directory: {inputs.reference_dir}")
    print()
    print(f"spatial source:      {cfg.spatial_source}" + ("  (the polygon layers are not needed at run time)" if cfg.spatial_source == "h3_base" else ""))
    print()
    print(f"{'key':<18} {'req':<4} {'source':<10} {'date':<11} file")
    for row in inputs.summary_rows(cfg.spatial_source):
        req = "yes" if row["required"] else "opt"
        print(f"{row['key']:<18} {req:<4} {str(row['source'] or '-'):<10} {str(row['date'] or '-'):<11} {row['file'] or '(not found)'}")
        for ign in row["ignored"]:
            print(f"{'':<18} {'':<4} {'':<10} {'':<11}   ignored older: {ign}")
    print()
    for key, info in report.inputs.items():
        if info.get("encoding"):
            print(f"  {key}: encoding {info['encoding']}")
    print()
    if not problems:
        _print_node_position_check(inputs, cfg)
    if problems:
        print(f"✗ {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"✓ inputs are valid (config: {cfg.mc_iterations} MC iterations, rings {list(cfg.influence_rings)})")
    return 0


def cmd_show_config(args: argparse.Namespace) -> int:
    if args.defaults:
        print(default_yaml(), end="")
        return 0
    cfg = _load_config_or_exit(args)
    print(cfg.to_json())
    return 0


def _print_node_position_check(inputs, cfg) -> None:
    """After a clean validation, list nodes whose network rows disagree on position."""
    from .pipeline.inputs import read_csv_auto
    from .pipeline.network import apply_node_position_overrides, load_nodeslines, node_position_table

    try:
        nodes = load_nodeslines(read_csv_auto(inputs.path("nodeslines"))[0])
        overrides = read_csv_auto(inputs.path("node_positions"))[0] if inputs.has("node_positions") else None
        nodes = apply_node_position_overrides(nodes, overrides)
        table = node_position_table(nodes)
    except Exception as exc:  # noqa: BLE001 - the data check must never mask the validation verdict
        print(f"node position check skipped: {exc}\n")
        return
    if table.empty:
        print("node positions:      every node has one coordinate\n")
        return
    print(f"node positions:      {len(table)} node(s) with more than one coordinate (tolerance {cfg.node_position_tolerance_m:.0f} m):")
    for row in table.itertuples():
        verdict = "snapped to the majority position" if row.spread_m <= cfg.node_position_tolerance_m else "CONFLICT: add a row to node_position_overrides.csv"
        print(f"  node {row.node}: {row.n_positions} positions, {row.spread_m:.0f} m apart -> {verdict}")
        for p in row.positions:
            print(f"      ({p['x']:.1f}, {p['y']:.1f})  {p['rows']} rows: {', '.join(p['lines'])}")
    print()


def cmd_prepare_base(args: argparse.Namespace) -> int:
    from .pipeline.run import prepare_base_from_cli

    return prepare_base_from_cli(args)


def cmd_compare(args: argparse.Namespace) -> int:
    from .pipeline.run import compare_from_cli

    return compare_from_cli(args)


def cmd_runs(args: argparse.Namespace) -> int:
    from .pipeline.run import runs_from_cli

    return runs_from_cli(args)


def cmd_serve(args: argparse.Namespace) -> int:
    from .gui.server import serve_from_cli

    return serve_from_cli(args)


def cmd_export_h3(args: argparse.Namespace) -> int:
    from .pipeline.run import export_h3_from_cli

    return export_h3_from_cli(args)


def cmd_run(args: argparse.Namespace) -> int:
    try:
        from .pipeline.run import run_from_cli  # implemented in PR 8
    except ImportError:
        raise SystemExit("'hubs run' is not available yet: the orchestrator lands in PR 8. Use 'hubs validate' for now.")
    return run_from_cli(args)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {"validate": cmd_validate, "show-config": cmd_show_config, "run": cmd_run, "prepare-base": cmd_prepare_base, "export-h3": cmd_export_h3, "compare": cmd_compare, "runs": cmd_runs, "serve": cmd_serve}
    return handlers[args.command](args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
