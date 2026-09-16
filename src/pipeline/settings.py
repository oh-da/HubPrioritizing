"""
Pipeline configuration.

Precedence (lowest to highest): built-in defaults < ``pipeline.yaml`` < ``--set key=value``.

All defaults reproduce the canonical notebook. Flags that deliberately preserve a
notebook quirk are documented in ``docs/DEVIATIONS.md`` (see the refactor plan, B5).
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from ..config import (
    H3_RESOLUTION,
    HUB_MERGE_THRESHOLD_M,
    HUB_MERGE_TOLERANCE_M,
    MONTE_CARLO_ITERATIONS,
    MONTE_CARLO_RANDOM_SEED,
    REQUIRE_NON_RAIL_MODE,
    TERMINAL_PROXIMITY_DISTANCE_M,
)


class ConfigError(ValueError):
    """Raised for unknown keys or values that cannot be coerced."""


@dataclass(frozen=True)
class LineDropRule:
    """Drop lines whose ``Line_ModelName`` matches ``pattern`` within ``area``.

    ``area`` matches the ``Area`` column of the lines file; ``None`` means any area.
    """

    pattern: str
    area: str | None = None


@dataclass(frozen=True)
class PipelineConfig:
    # --- Part 1: network and grouping -------------------------------------------------
    h3_resolution: int = H3_RESOLUTION
    merge_threshold_m: float = HUB_MERGE_THRESHOLD_M
    merge_tolerance_m: float = HUB_MERGE_TOLERANCE_M
    drop_line_rules: tuple[LineDropRule, ...] = (
        LineDropRule(pattern=r"^m", area="Haifa"),  # old Metronit lines
        LineDropRule(pattern=r"^LRT15[12]$", area="Netanya"),
    )
    # 'even' = notebook workaround (split Line_Nunique evenly across modes present);
    # 'exact' = count lines per mode from the node x line rows.
    per_mode_lines_method: str = "even"
    geocode: bool = False

    # --- Part 2: demand -------------------------------------------------------------------
    overlay_regions: tuple[str, ...] = ("Hadera", "Haifa Metronit")

    # --- Part 3: terminals and influence area -------------------------------------------
    terminal_buffer_m: float = TERMINAL_PROXIMITY_DISTANCE_M
    influence_rings: tuple[int, ...] = (500, 1000, 1500)

    # --- Part 4: scoring ----------------------------------------------------------------
    apply_eligibility_filter: bool = True
    require_non_rail_mode: bool = REQUIRE_NON_RAIL_MODE
    mode_diversity_alpha: float = 0.1
    distance_decay_beta: float = 1.5
    mc_iterations: int = MONTE_CARLO_ITERATIONS
    mc_seed: int = MONTE_CARLO_RANDOM_SEED
    mc_scope: str = "per_hubtype"  # or 'all_hubs'
    renormalize_globally: bool = False  # True reproduces the create_results_csv quirk

    # --- Output -------------------------------------------------------------------------
    output_basename: str = "hub_prioritization_results"
    output_sheet_name: str = "hubs_final_results"
    output_table_name: str = "טבלה1"
    extra_columns: tuple[str, ...] = ()
    keep_intermediates: bool = False

    # ------------------------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def validate(self) -> None:
        if self.per_mode_lines_method not in ("even", "exact"):
            raise ConfigError("per_mode_lines_method must be 'even' or 'exact'")
        if self.mc_scope not in ("per_hubtype", "all_hubs"):
            raise ConfigError("mc_scope must be 'per_hubtype' or 'all_hubs'")
        rings = list(self.influence_rings)
        if len(rings) < 1 or rings != sorted(rings) or rings[0] <= 0 or len(set(rings)) != len(rings):
            raise ConfigError("influence_rings must be strictly increasing positive radii")
        if self.mc_iterations < 1:
            raise ConfigError("mc_iterations must be >= 1")
        if self.h3_resolution not in range(0, 16):
            raise ConfigError("h3_resolution must be between 0 and 15")


# ----------------------------------------------------------------------------------------
# Loading and overrides
# ----------------------------------------------------------------------------------------

_FIELD_TYPES = {f.name: f.type for f in fields(PipelineConfig)}


def _coerce(name: str, value: Any) -> Any:
    """Coerce a YAML / CLI value to the dataclass field's type."""
    if name not in _FIELD_TYPES:
        raise ConfigError(f"unknown config key: {name}")
    default = getattr(PipelineConfig(), name)

    if name == "drop_line_rules":
        return tuple(_coerce_rule(v) for v in _as_list(value))
    if isinstance(default, tuple):
        items = _as_list(value)
        if name == "influence_rings":
            return tuple(int(x) for x in items)
        return tuple(str(x) for x in items)
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off"):
            return False
        raise ConfigError(f"{name}: expected a boolean, got {value!r}")
    try:
        if isinstance(default, int):
            return int(value)
        if isinstance(default, float):
            return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name}: expected a number, got {value!r}") from exc
    return str(value)


def _as_list(value: Any) -> list:
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("["):
            return list(json.loads(s))
        return [x.strip() for x in s.split(",") if x.strip()]
    return [value]


def _coerce_rule(value: Any) -> LineDropRule:
    if isinstance(value, LineDropRule):
        return value
    if isinstance(value, Mapping):
        return LineDropRule(pattern=str(value["pattern"]), area=value.get("area"))
    if isinstance(value, str):
        # "Haifa:^m" or "^m"
        if ":" in value:
            area, pattern = value.split(":", 1)
            return LineDropRule(pattern=pattern, area=area or None)
        return LineDropRule(pattern=value)
    raise ConfigError(f"cannot parse drop_line_rules entry: {value!r}")


def parse_set_overrides(items: Sequence[str]) -> dict[str, str]:
    """Parse ``--set key=value`` pairs into a dict (values are coerced later)."""
    out: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ConfigError(f"--set expects key=value, got {item!r}")
        key, value = item.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def load_config(
    yaml_path: Path | str | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> PipelineConfig:
    """Build a :class:`PipelineConfig` from defaults, an optional YAML file and overrides."""
    values: dict[str, Any] = {}

    if yaml_path is not None:
        yaml_path = Path(yaml_path)
        with yaml_path.open("r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        if not isinstance(loaded, Mapping):
            raise ConfigError(f"{yaml_path}: top level must be a mapping")
        for k, v in loaded.items():
            values[k] = _coerce(k, v)

    for k, v in (overrides or {}).items():
        values[k] = _coerce(k, v)

    cfg = PipelineConfig(**values)
    cfg.validate()
    return cfg


def default_yaml() -> str:
    """Return the defaults as YAML text (for ``hubs show-config --defaults``)."""
    d = PipelineConfig().to_dict()
    d["drop_line_rules"] = [dataclasses.asdict(r) for r in PipelineConfig().drop_line_rules]
    for k, v in d.items():
        if isinstance(v, tuple):
            d[k] = list(v)
    return yaml.safe_dump(d, allow_unicode=True, sort_keys=False)


# Keep a public name for the field list (used by the CLI help).
CONFIG_KEYS: tuple[str, ...] = tuple(_FIELD_TYPES)
__all__ = [
    "PipelineConfig",
    "LineDropRule",
    "ConfigError",
    "load_config",
    "parse_set_overrides",
    "default_yaml",
    "CONFIG_KEYS",
]
_ = field  # silence unused-import linters for dataclasses.field re-export
