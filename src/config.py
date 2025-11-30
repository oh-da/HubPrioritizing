"""
Configuration module for Hub Prioritization Framework.

Follows Single Responsibility Principle: only manages configuration.
Implements IConfiguration protocol for dependency inversion.
"""

from pathlib import Path
from typing import Any, Dict
from dataclasses import dataclass, field


@dataclass
class PathConfig:
    """Configuration for file paths"""
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def raw_data_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_data_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def results_dir(self) -> Path:
        return self.data_dir / "results"

    @property
    def src_dir(self) -> Path:
        return self.project_root / "src"

    @property
    def tests_dir(self) -> Path:
        return self.project_root / "tests"


@dataclass
class ThresholdConfig:
    """Configuration for hub eligibility and classification thresholds"""

    # Eligibility thresholds
    eligibility_min_passengers: int = 1000
    eligibility_min_modes: int = 2

    # Classification thresholds (passengers/day)
    national_hub_min_passengers: int = 50000
    metro_hub_min_passengers: int = 5000

    # Spatial thresholds
    h3_resolution: int = 9  # ~150m hexes
    hub_merge_threshold_m: float = 300.0


@dataclass
class ScoringConfig:
    """Configuration for scoring parameters"""

    # Monte Carlo simulation
    monte_carlo_iterations: int = 10000
    max_criterion_weight: float = 0.5  # 50%

    # Score normalization
    score_min: float = 1.0
    score_max: float = 10.0

    # Catchment area rings (meters)
    catchment_rings: list[float] = field(default_factory=lambda: [0, 400, 800, 1500])

    # Bus terminal proximity threshold (meters)
    terminal_proximity_threshold_m: float = 200.0


@dataclass
class ModeWeights:
    """Weights for different transit modes in service scoring"""
    rail: float = 1.0
    metro: float = 0.95
    light_rail: float = 0.85
    brt: float = 0.70
    local_bus: float = 0.50


@dataclass
class DemographicMixConfig:
    """Job/population mix ratios by hub type"""

    # National and Metropolitan hubs: employment-focused
    national_metro_job_weight: float = 0.8
    national_metro_pop_weight: float = 0.2

    # Local hubs: residential-focused
    local_job_weight: float = 0.2
    local_pop_weight: float = 0.8


class Configuration:
    """
    Main configuration class implementing IConfiguration protocol.

    Single Responsibility: Provides centralized configuration access.
    Dependency Inversion: Clients depend on IConfiguration protocol.
    """

    def __init__(self):
        self.paths = PathConfig()
        self.thresholds = ThresholdConfig()
        self.scoring = ScoringConfig()
        self.mode_weights = ModeWeights()
        self.demographic_mix = DemographicMixConfig()

        # Additional configuration dictionary for extensibility
        self._custom: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key"""
        parts = key.split('.')

        if len(parts) == 1:
            return self._custom.get(key, default)

        # Navigate nested attributes
        obj = self
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return default
        return obj

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value"""
        value = self.get(key, default)
        return int(value) if value is not None else default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value"""
        value = self.get(key, default)
        return float(value) if value is not None else default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value"""
        value = self.get(key, default)
        return bool(value) if value is not None else default

    def set(self, key: str, value: Any) -> None:
        """Set custom configuration value"""
        self._custom[key] = value


# Singleton instance for global access (optional, can also use DI)
_config_instance: Configuration | None = None


def get_config() -> Configuration:
    """Get global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Configuration()
    return _config_instance
