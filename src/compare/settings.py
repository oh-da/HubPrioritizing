"""
Configuration of ``hubs compare-network``.

Precedence (lowest to highest): built-in defaults < YAML file < ``--set key=value``.
Mirrors :mod:`src.pipeline.settings` and reuses its ``ConfigError`` and ``--set`` parser.
"""

from __future__ import annotations

import dataclasses
import json
import math
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Mapping

import yaml

from ..pipeline.settings import ConfigError, parse_set_overrides


@dataclass(frozen=True)
class CompareConfig:
    """Tolerances and thresholds of the route and hub comparison.

    Distances are metres (ITM); ``match_min_score``, ``full_cov``, ``only_max_score`` and
    ``multi_cov`` are scores / coverages in [0, 1].
    """

    # --- Step 1: routes -------------------------------------------------------------------
    route_tol_m: float = 100.0  # a node counts as on an agency route within this distance
    rail_tol_m: float = 250.0  # same, for the rail types (the rail geometry is coarser)
    stop_tol_m: float = 150.0  # an agency stop counts as covered by a node within this distance
    rail_assign_tol_m: float = 250.0  # nearest rail feature for stations with line_id = 0
    match_min_score: float = 0.5  # lowest score of a candidate pair worth listing
    full_cov: float = 0.8  # both coverages at or above this = full match
    only_max_score: float = 0.2  # a route whose best score is below this is *_only
    multi_cov: float = 0.3  # both coverages at or above this = part of a split / merge
    # --- Offset between the two networks --------------------------------------------------
    apply_offset: bool = True
    offset_radius_m: float = 10000.0
    offset_passes: int = 2
    # --- Step 2: hubs ---------------------------------------------------------------------
    hub_match_tol_m: float = 400.0
    tod_join_tol_m: float = 200.0  # agency hub -> nearest scraped hub (--tod-gpkg)

    def to_dict(self) -> dict[str, Any]:
        """Return the configuration as a plain dict."""
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        """Return the configuration as indented JSON text."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def validate(self) -> None:
        """Check ranges and the relations between thresholds.

        Raises:
            ConfigError: If a tolerance is not positive, a score or coverage is outside
                [0, 1], ``only_max_score`` exceeds ``match_min_score`` or ``offset_passes``
                is negative.
        """
        for name in (
            "route_tol_m",
            "rail_tol_m",
            "stop_tol_m",
            "rail_assign_tol_m",
            "offset_radius_m",
            "hub_match_tol_m",
            "tod_join_tol_m",
        ):
            if not getattr(self, name) > 0:
                raise ConfigError(f"{name} must be > 0")
        for name in ("match_min_score", "full_cov", "only_max_score", "multi_cov"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ConfigError(f"{name} must be between 0 and 1")
        if self.only_max_score > self.match_min_score:
            raise ConfigError("only_max_score must be <= match_min_score")
        if self.offset_passes < 0:
            raise ConfigError("offset_passes must be >= 0")


_DEFAULTS = CompareConfig()
_FIELD_TYPES = {f.name: f.type for f in fields(CompareConfig)}


def _coerce(name: str, value: Any) -> Any:
    """Coerce a YAML / CLI value to the type of the field's default.

    Booleans are rejected for numeric fields, numbers must be finite and an integer field takes
    only whole numbers (``3`` or ``3.0``, not ``2.7``).
    """
    if name not in _FIELD_TYPES:
        raise ConfigError(f"unknown config key: {name}")
    default = getattr(_DEFAULTS, name)
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off"):
            return False
        raise ConfigError(f"{name}: expected a boolean, got {value!r}")
    if isinstance(value, bool):
        raise ConfigError(f"{name}: expected a number, got {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name}: expected a number, got {value!r}") from exc
    if not math.isfinite(number):
        raise ConfigError(f"{name}: expected a finite number, got {value!r}")
    if isinstance(default, int):
        if not number.is_integer():
            raise ConfigError(f"{name}: expected a whole number, got {value!r}")
        return int(number)
    return number


def load_compare_config(
    yaml_path: Path | str | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> CompareConfig:
    """Build a :class:`CompareConfig` from defaults, an optional YAML file and overrides.

    Args:
        yaml_path: Optional YAML file with a flat mapping of config keys.
        overrides: Optional ``key -> value`` pairs (e.g. from ``parse_set_overrides``);
            they win over the YAML file.

    Returns:
        The validated configuration.

    Raises:
        ConfigError: On an unknown key, a value that cannot be coerced or a failed check.
    """
    values: dict[str, Any] = {}
    if yaml_path is not None:
        yaml_path = Path(yaml_path)
        with yaml_path.open("r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        if not isinstance(loaded, Mapping):
            raise ConfigError(f"{yaml_path}: top level must be a mapping")
        for key, value in loaded.items():
            values[key] = _coerce(key, value)
    for key, value in (overrides or {}).items():
        values[key] = _coerce(key, value)
    cfg = CompareConfig(**values)
    cfg.validate()
    return cfg


COMPARE_KEYS: tuple[str, ...] = tuple(_FIELD_TYPES)
__all__ = [
    "CompareConfig",
    "ConfigError",
    "COMPARE_KEYS",
    "load_compare_config",
    "parse_set_overrides",
]
