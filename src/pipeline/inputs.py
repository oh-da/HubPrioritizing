"""
Input directory contract: discovery, validation and encoding-aware readers.

Per-run model exports live in ``--input-dir``; stable layers live in
``--reference-dir`` (default ``data/reference``). A file in the input directory
with a reference file's name overrides the reference copy.

Discovery picks, for each input key, the newest matching file by the date embedded
in its name (``18062026``, ``18-06-2026``, ``2026-06-18`` ...), falling back to the
modification time. Validation collects *every* problem before raising so the user
fixes the directory once.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import geopandas as gpd
import pandas as pd

from ..config import REFERENCE_DATA_DIR
from ..utils.encoding_fix import is_valid_hebrew_text
from .report import RunReport


class InputError(ValueError):
    """Raised by :func:`require_valid_inputs` with the full list of problems."""

    def __init__(self, problems: Sequence[str]):
        self.problems = list(problems)
        super().__init__("Input validation failed:\n  - " + "\n  - ".join(self.problems))


# ----------------------------------------------------------------------------------------
# Specifications
# ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class InputSpec:
    key: str
    patterns: tuple[str, ...]  # glob patterns, tried in order
    kind: str  # 'csv' | 'xlsx' | 'shp' | 'parquet'
    required: bool
    description: str
    required_columns: tuple[str, ...] = ()
    any_of_columns: tuple[tuple[str, ...], ...] = ()  # each inner tuple: at least one present
    header: bool = True
    hebrew_columns: tuple[str, ...] = ()
    reference: bool = False  # lives in reference dir by default
    required_unless: str | None = None  # a required spec that another key can stand in for


INPUT_SPECS: tuple[InputSpec, ...] = (
    InputSpec(
        key="nodeslines",
        patterns=("All_nodeslines*.csv", "All_nodes+lines*.csv", "All_nodes_lines*.csv"),
        kind="csv",
        required=True,
        description="Node x line rows with ITM coordinates (built in GIS from Routes_and_Nodes)",
        required_columns=("node", "LINE_ID"),
        any_of_columns=(("X", "geometry"),),
    ),
    InputSpec(
        key="lines_mode",
        patterns=("Lines_and_Planned_Mode*.csv",),
        kind="csv",
        required=True,
        description="Line -> planned 2050 mode and metropolitan area",
        required_columns=("Line_ModelName", "Mode_Planned"),
        hebrew_columns=("Line_Name", "Line_Description"),
    ),
    InputSpec(
        key="demand",
        patterns=("Nodes_w_results*.xlsx", "Demand_2050*.xlsx"),
        kind="xlsx",
        required=True,
        description="2050 boardings/alightings per node, one sheet per regional model",
    ),
    InputSpec(
        key="line_names",
        patterns=("linesNames*.csv", "hebrew_line_names*.csv"),
        kind="csv",
        required=False,
        description="Line ID -> Hebrew display name '(mode)'; headerless file accepted",
        header=False,
    ),
    InputSpec(
        key="line_status",
        patterns=("line_status*.csv", "lines_exploded*.csv"),
        kind="csv",
        required=False,
        description="Line ID -> planning status code 0-7 (clean or legacy exploded format)",
        required_columns=("LineName",),
        any_of_columns=(("StatusID", "Status Id", "Status_Id"),),
    ),
    InputSpec(
        key="line_corrections",
        patterns=("BS_lines*.csv", "line_name_corrections*.csv"),
        kind="csv",
        required=False,
        description="Line name spelling corrections (LineName -> LineName_Correct)",
        required_columns=("LineName", "LineName_Correct"),
    ),
    InputSpec(
        key="routes",
        patterns=("Routes_and_Nodes*.xlsx",),
        kind="xlsx",
        required=False,
        description="Model routes (Line, Node, IsStop, Include, PlannedMode); stage 0 input",
    ),
    InputSpec(
        key="node_coords",
        patterns=("Nodes_coords*.csv", "Nodes_coords*.shp", "nodes_xy*.csv"),
        kind="csv",
        required=False,
        description="Model node coordinates (node, X, Y) in EPSG:2039; stage 0 input",
    ),
    # --- reference layers ------------------------------------------------------------------
    InputSpec(
        key="metro",
        patterns=("metro_2008.shp", "metro*.shp"),
        kind="shp",
        required=True,
        description="Metropolitan areas and rings (METRO_NAME, ZONE_NAME)",
        required_columns=("METRO_NAME", "ZONE_NAME"),
        hebrew_columns=("METRO_NAME", "ZONE_NAME"),
        reference=True,
        required_unless="h3_base",
    ),
    InputSpec(
        key="districts",
        patterns=("Districts.shp", "districts*.shp"),
        kind="shp",
        required=True,
        description="National districts (MACHOZ), fallback area tagging",
        required_columns=("MACHOZ",),
        hebrew_columns=("MACHOZ",),
        reference=True,
        required_unless="h3_base",
    ),
    InputSpec(
        key="bus_terminals",
        patterns=("BUS_TERMINAL_STRAT.shp", "bus_terminals*.shp"),
        kind="shp",
        required=True,
        description="Strategic bus terminals (term_type) for the terminal proximity score",
        required_columns=("term_type",),
        hebrew_columns=("term_type",),
        reference=True,
        required_unless="h3_base",
    ),
    InputSpec(
        key="taz",
        patterns=("TAZ_1270.shp", "TAZ*.shp"),
        kind="shp",
        required=True,
        description="Traffic analysis zones with POP_2050 / EMPL_2050",
        required_columns=("POP_2050", "EMPL_2050"),
        reference=True,
        required_unless="h3_base",
    ),
    InputSpec(
        key="h3_base",
        patterns=("h3_base.parquet", "h3_base*.parquet"),
        kind="parquet",
        required=False,
        description="Pre-allocated H3 base layer (hubs prepare-base): area, ring, terminal, pop/emp per cell",
        required_columns=("h3_index", "area", "location", "bus_terminal", "pop_2050", "emp_2050"),
        reference=True,
    ),
    InputSpec(
        key="hub_names",
        patterns=("hub_names.csv", "Hubs_Names*.csv", "HubsNames*.csv"),
        kind="csv",
        required=False,
        description="Hebrew hub display names keyed by h3_index",
        required_columns=("h3_index", "HubNameHE"),
        hebrew_columns=("HubNameHE",),
        reference=True,
    ),
    InputSpec(
        key="line_names_extra",
        patterns=("line_names_extra.csv",),
        kind="csv",
        required=False,
        description="Hebrew line names that fill gaps in the per-run line names file",
        required_columns=("LineName", "Line_n_Mode"),
        hebrew_columns=("Line_n_Mode",),
        reference=True,
    ),
    InputSpec(
        key="is_same_group",
        patterns=("is_same_group.csv", "IsSameGroup*.csv"),
        kind="csv",
        required=False,
        description="Manual hub merges: rows of comma-separated node IDs",
        required_columns=("Nodes in group",),
        reference=True,
    ),
    InputSpec(
        key="manual_demand",
        patterns=("manual_demand_updates.csv",),
        kind="csv",
        required=False,
        description="Node-level demand overrides (node, total_demand, total_transfers, optional model)",
        required_columns=("node", "total_demand", "total_transfers"),
        reference=True,
    ),
    InputSpec(
        key="node_positions",
        patterns=("node_position_overrides.csv",),
        kind="csv",
        required=False,
        description="Corrected coordinates (EPSG:2039) for nodes whose network rows disagree on position",
        required_columns=("node", "X", "Y"),
        reference=True,
    ),
)

SPEC_BY_KEY: dict[str, InputSpec] = {s.key: s for s in INPUT_SPECS}

SHAPEFILE_SIDECARS = (".shx", ".dbf")

_DATE_PATTERNS = (
    # 18062026 / 18-06-2026 / 18_06_2026  (day month year)
    re.compile(r"(?<!\d)(\d{2})[-_]?(\d{2})[-_]?(20\d{2})(?!\d)"),
    # 2026-06-18 / 20260618  (year month day)
    re.compile(r"(?<!\d)(20\d{2})[-_]?(\d{2})[-_]?(\d{2})(?!\d)"),
)


# ----------------------------------------------------------------------------------------
# Discovery
# ----------------------------------------------------------------------------------------


@dataclass
class ChosenFile:
    path: Path
    source: str  # 'input' | 'reference' | 'override'
    date: str | None
    ignored: tuple[Path, ...] = ()


@dataclass
class InputSet:
    input_dir: Path
    reference_dir: Path
    files: dict[str, ChosenFile] = field(default_factory=dict)

    def path(self, key: str) -> Path | None:
        chosen = self.files.get(key)
        return chosen.path if chosen else None

    def has(self, key: str) -> bool:
        return key in self.files

    def is_required(self, spec: InputSpec, spatial_source: str | None = None) -> bool:
        """Effective requirement of a spec for this input set.

        The four polygon layers can be replaced by the H3 base layer: with
        ``spatial_source=None`` (no configured source) they are required only when
        ``h3_base`` is absent; ``'shapefiles'`` always requires them; ``'h3_base'``
        requires the base layer instead.
        """
        required = spec.required
        if spec.required_unless is not None:
            if spatial_source == "shapefiles":
                required = True
            elif spatial_source == "h3_base" or self.has(spec.required_unless):
                required = False
        if spec.key == "h3_base" and spatial_source == "h3_base":
            required = True
        return required

    def missing_required(self, spatial_source: str | None = None) -> list[InputSpec]:
        """Required specs (see :meth:`is_required`) that are absent."""
        return [s for s in INPUT_SPECS if s.key not in self.files and self.is_required(s, spatial_source)]

    def summary_rows(self, spatial_source: str | None = None) -> list[dict[str, object]]:
        rows = []
        for spec in INPUT_SPECS:
            chosen = self.files.get(spec.key)
            rows.append(
                {
                    "key": spec.key,
                    "required": self.is_required(spec, spatial_source),
                    "file": str(chosen.path) if chosen else None,
                    "source": chosen.source if chosen else None,
                    "date": chosen.date if chosen else None,
                    "ignored": [str(p) for p in chosen.ignored] if chosen else [],
                }
            )
        return rows


def parse_date_from_name(name: str) -> str | None:
    """Return an ISO date (YYYY-MM-DD) embedded in a filename, or None."""
    m = _DATE_PATTERNS[0].search(name)
    if m:
        d, mo, y = m.groups()
        if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
            return f"{y}-{mo}-{d}"
    m = _DATE_PATTERNS[1].search(name)
    if m:
        y, mo, d = m.groups()
        if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
            return f"{y}-{mo}-{d}"
    return None


def pick_latest(paths: Iterable[Path]) -> tuple[Path | None, tuple[Path, ...]]:
    """Choose the newest file by name-embedded date, then mtime. Returns (chosen, ignored)."""
    paths = sorted(set(paths))
    if not paths:
        return None, ()

    def sort_key(p: Path):
        d = parse_date_from_name(p.name)
        return (d or "", p.stat().st_mtime, p.name)

    ordered = sorted(paths, key=sort_key, reverse=True)
    return ordered[0], tuple(ordered[1:])


def _glob_any(directory: Path, patterns: Sequence[str]) -> list[Path]:
    found: list[Path] = []
    for pat in patterns:
        found.extend(p for p in directory.glob(pat) if p.is_file())
    return found


def discover_inputs(
    input_dir: Path | str,
    reference_dir: Path | str | None = None,
    overrides: Mapping[str, Path | str] | None = None,
) -> InputSet:
    """Resolve every input key to a file (or nothing) without opening any file."""
    input_dir = Path(input_dir)
    reference_dir = Path(reference_dir) if reference_dir is not None else REFERENCE_DATA_DIR
    result = InputSet(input_dir=input_dir, reference_dir=reference_dir)

    overrides = {k: Path(v) for k, v in (overrides or {}).items()}
    for key in overrides:
        if key not in SPEC_BY_KEY:
            raise InputError([f"unknown input key in override: {key}"])

    for spec in INPUT_SPECS:
        if spec.key in overrides:
            p = overrides[spec.key]
            result.files[spec.key] = ChosenFile(p, "override", parse_date_from_name(p.name))
            continue

        # input dir always wins over the reference dir
        candidates = _glob_any(input_dir, spec.patterns) if input_dir.exists() else []
        source = "input"
        if not candidates and spec.reference and reference_dir.exists():
            candidates = _glob_any(reference_dir, spec.patterns)
            source = "reference"
        chosen, ignored = pick_latest(candidates)
        if chosen is not None:
            result.files[spec.key] = ChosenFile(chosen, source, parse_date_from_name(chosen.name), ignored)

    return result


# ----------------------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------------------


BASE_LAYER_SOURCE_KEYS = ("metro", "districts", "bus_terminals", "taz")


def base_layer_staleness(inputs: InputSet) -> list[str]:
    """Messages for source shapefiles that changed since ``h3_base`` was built (see
    :func:`base_layer.stale_sources`); empty when the layer is current or absent."""
    from .base_layer import manifest_path, stale_sources

    layer = inputs.path("h3_base")
    if layer is None:
        return []
    mp = manifest_path(layer)
    manifest = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else None
    return stale_sources(manifest, {k: inputs.path(k) for k in BASE_LAYER_SOURCE_KEYS})


def validate_inputs(
    inputs: InputSet,
    report: RunReport | None = None,
    spatial_source: str | None = None,
    on_stale_base_layer: str = "error",
) -> list[str]:
    """Return a list of problems (empty when the input set is usable).

    Checks: required keys present, shapefile sidecars present, required columns
    present (headers only are read), Excel workbook opens, and, unless the run uses
    ``spatial_source='shapefiles'``, that the H3 base layer is not older than the
    source shapefiles next to it (a problem, or only a report warning with
    ``on_stale_base_layer='warn'``). Never raises for a data problem; callers decide
    via :func:`require_valid_inputs`.
    """
    problems: list[str] = []
    if spatial_source != "shapefiles":
        for msg in base_layer_staleness(inputs):
            if on_stale_base_layer == "error":
                problems.append(msg)
            elif report is not None:
                report.warn("inputs", msg)
    if not inputs.input_dir.exists():
        problems.append(f"input directory does not exist: {inputs.input_dir}")

    for spec in inputs.missing_required(spatial_source):
        where = "reference dir" if spec.reference else "input dir"
        hint = " (run 'hubs prepare-base' or set spatial_source=shapefiles)" if spec.key == "h3_base" else ""
        problems.append(
            f"missing required {spec.kind} '{spec.key}' ({spec.description}); "
            f"expected one of {list(spec.patterns)} in the {where} "
            f"({inputs.reference_dir if spec.reference else inputs.input_dir}){hint}"
        )

    for key, chosen in inputs.files.items():
        spec = SPEC_BY_KEY[key]
        path = chosen.path
        if not path.exists():
            problems.append(f"'{key}': file not found: {path}")
            continue
        try:
            if spec.kind == "shp":
                for ext in SHAPEFILE_SIDECARS:
                    if not path.with_suffix(ext).exists():
                        problems.append(f"'{key}': shapefile sidecar missing: {path.with_suffix(ext).name}")
                cols = list(gpd.read_file(path, rows=1).columns)
            elif spec.kind == "xlsx":
                cols = []  # per-sheet validation happens in the demand stage
                pd.ExcelFile(path).sheet_names
            elif spec.kind == "parquet":
                import pyarrow.parquet as pq

                cols = list(pq.read_schema(path).names)
            else:
                df, enc = read_csv_auto(path, nrows=5, header=0 if spec.header else None)
                cols = [str(c) for c in df.columns]
                if report is not None:
                    report.record_input(key, path, encoding=enc, source=chosen.source, date=chosen.date)
        except Exception as exc:  # noqa: BLE001 - report every unreadable file
            problems.append(f"'{key}': cannot read {path.name}: {exc}")
            continue

        if spec.header and spec.kind != "xlsx":
            missing = [c for c in spec.required_columns if c not in cols]
            if missing:
                problems.append(f"'{key}': {path.name} is missing required columns {missing}; has {cols[:12]}")
            for group in spec.any_of_columns:
                if not any(c in cols for c in group):
                    problems.append(f"'{key}': {path.name} needs one of {list(group)}; has {cols[:12]}")

        if report is not None and spec.kind != "csv":
            report.record_input(key, path, source=chosen.source, date=chosen.date)

    return problems


def require_valid_inputs(inputs: InputSet, report: RunReport | None = None) -> None:
    problems = validate_inputs(inputs, report)
    if problems:
        raise InputError(problems)


# ----------------------------------------------------------------------------------------
# Readers
# ----------------------------------------------------------------------------------------

CSV_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "cp1255")


def read_csv_auto(
    path: Path | str,
    *,
    encodings: Sequence[str] = CSV_ENCODINGS,
    hebrew_columns: Sequence[str] = (),
    **read_csv_kwargs,
) -> tuple[pd.DataFrame, str]:
    """Read a CSV trying ``encodings`` in order; return (frame, encoding used).

    An encoding is accepted when decoding succeeds and, for the declared Hebrew
    columns, the first non-null values look like Hebrew (no mojibake).
    """
    path = Path(path)
    last_error: Exception | None = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc, **read_csv_kwargs)
        except (UnicodeDecodeError, UnicodeError) as exc:
            last_error = exc
            continue
        if _hebrew_columns_look_valid(df, hebrew_columns):
            return df, enc
        last_error = ValueError(f"{path.name}: Hebrew columns look garbled with {enc}")
    raise ValueError(f"could not decode {path} with any of {list(encodings)}: {last_error}")


def _hebrew_columns_look_valid(df: pd.DataFrame, columns: Sequence[str]) -> bool:
    for col in columns:
        if col not in df.columns:
            continue
        sample = df[col].dropna().astype(str).head(20)
        if sample.empty:
            continue
        ok = sum(1 for v in sample if is_valid_hebrew_text(v) or not any("֐" <= ch <= "׿" for ch in v))
        if ok < max(1, len(sample) // 2):
            return False
    return True


def read_shapefile(
    path: Path | str,
    *,
    hebrew_columns: Sequence[str] = (),
    encoding: str | None = None,
) -> tuple[gpd.GeoDataFrame, str]:
    """Read a shapefile with correct Hebrew, working around a GDAL decode quirk.

    GDAL/pyogrio drop the last character of CP1255 strings in some DBFs (the
    "truncated Hebrew" seen in ``metro_2008.shp``). Reading the attribute bytes as
    latin-1 and re-decoding them in Python yields the full strings. The code page is
    taken from ``encoding``, else the ``.cpg`` sidecar, else detected (cp1255 then utf-8).

    Returns (GeoDataFrame, code page used).
    """
    path = Path(path)
    raw = gpd.read_file(path, encoding="latin1")
    # pandas >= 3 gives text columns the 'str' dtype, older pandas 'object'
    text_cols = [
        c
        for c in raw.columns
        if c != raw.geometry.name
        and (pd.api.types.is_string_dtype(raw[c]) or pd.api.types.is_object_dtype(raw[c]))
    ]

    candidates = [encoding] if encoding else []
    cpg = path.with_suffix(".cpg")
    if cpg.exists():
        candidates.append(_normalise_codepage(cpg.read_text(encoding="ascii", errors="ignore").strip()))
    candidates += ["cp1255", "utf-8"]

    tried: list[str] = []
    for enc in candidates:
        if not enc or enc in tried:
            continue
        tried.append(enc)
        try:
            decoded = raw.copy()
            for c in text_cols:
                decoded[c] = raw[c].map(lambda v, e=enc: v.encode("latin1").decode(e) if isinstance(v, str) else v)
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
        check_cols = [c for c in hebrew_columns if c in decoded.columns] or text_cols
        if _hebrew_columns_look_valid(decoded, check_cols):
            return decoded, enc
    raise ValueError(f"could not decode attribute text of {path} with {tried}")


def _normalise_codepage(cpg: str) -> str:
    s = cpg.strip().upper().replace("-", "").replace("_", "")
    if s in ("CP1255", "WINDOWS1255", "1255", "HEBREW"):
        return "cp1255"
    if s in ("UTF8", "UTF8SIG"):
        return "utf-8"
    if s in ("ISO88598",):
        return "iso-8859-8"
    return cpg.strip().lower()


def read_excel_sheets(path: Path | str) -> dict[str, pd.DataFrame]:
    """Load every sheet of a workbook into a dict (sheet name -> frame)."""
    xl = pd.ExcelFile(path)
    return {name: xl.parse(name) for name in xl.sheet_names}
