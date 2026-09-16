"""
``hubs`` command line interface.

    hubs validate    --input-dir DIR [--reference-dir DIR]
    hubs show-config [--config pipeline.yaml] [--set key=value ...] [--defaults]
    hubs run         --input-dir DIR --output-dir DIR [...]   (available from PR 8)
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
    problems = validate_inputs(inputs, report)

    print(f"Input directory:     {inputs.input_dir}")
    print(f"Reference directory: {inputs.reference_dir}")
    print()
    print(f"{'key':<18} {'req':<4} {'source':<10} {'date':<11} file")
    for row in inputs.summary_rows():
        req = "yes" if row["required"] else "opt"
        print(f"{row['key']:<18} {req:<4} {str(row['source'] or '-'):<10} {str(row['date'] or '-'):<11} {row['file'] or '(not found)'}")
        for ign in row["ignored"]:
            print(f"{'':<18} {'':<4} {'':<10} {'':<11}   ignored older: {ign}")
    print()
    for key, info in report.inputs.items():
        if info.get("encoding"):
            print(f"  {key}: encoding {info['encoding']}")
    print()
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


def cmd_run(args: argparse.Namespace) -> int:
    try:
        from .pipeline.run import run_from_cli  # implemented in PR 8
    except ImportError:
        raise SystemExit("'hubs run' is not available yet: the orchestrator lands in PR 8. Use 'hubs validate' for now.")
    return run_from_cli(args)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {"validate": cmd_validate, "show-config": cmd_show_config, "run": cmd_run}
    return handlers[args.command](args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
