"""
Core interfaces and protocols for the Hub Prioritization Framework.

This module defines the contracts that ensure SOLID principles throughout the codebase:
- Single Responsibility: Each interface has one clear purpose
- Open/Closed: Extend via implementing interfaces, not modifying existing code
- Liskov Substitution: All implementations must honor the interface contract
- Interface Segregation: Small, focused interfaces
- Dependency Inversion: Depend on these abstractions, not concrete implementations
"""

from abc import ABC, abstractmethod
from typing import Protocol, Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# Domain Models (Value Objects)
# ============================================================================

class HubTier(Enum):
    """Hub hierarchy classification"""
    NATIONAL = "ארצי"  # National
    METROPOLITAN = "מטרופוליני"  # Metropolitan
    LOCAL = "עירוני"  # Local/Urban


class TransitMode(Enum):
    """Types of mass transit modes"""
    RAIL = "רכבת"  # Railway/Train
    METRO = "מטרו"  # Metro
    LIGHT_RAIL = "רק״ל"  # Light Rail
    BRT = "BRT"  # Bus Rapid Transit
    LOCAL_BUS = "אוטובוס מקומי"  # Local Bus


@dataclass(frozen=True)
class HubLocation:
    """Immutable location data for a hub"""
    lat: float
    lon: float
    h3_index: str
    region: str
    metropolitan_ring: str  # 'core', 'first_ring', 'outer'


@dataclass
class HubData:
    """Complete hub data container"""
    hub_id: str
    name: str
    location: HubLocation
    tier: Optional[HubTier]
    passengers_2050: int
    modes: List[TransitMode]
    metadata: Dict[str, Any]


@dataclass
class ScoringResult:
    """Result of scoring a hub on one criterion"""
    hub_id: str
    criterion_name: str
    raw_value: float
    normalized_score: float  # 1-10
    metadata: Dict[str, Any]


# ============================================================================
# Data Access Interfaces (Repository Pattern)
# ============================================================================

class IDataLoader(ABC):
    """
    Interface for loading data from various sources.

    Single Responsibility: Only concerned with loading raw data.
    Open/Closed: Extend by creating new implementations, not modifying this interface.
    """

    @abstractmethod
    def load(self) -> Any:
        """Load data from the source"""
        pass

    @abstractmethod
    def validate_schema(self, data: Any) -> bool:
        """Validate that loaded data matches expected schema"""
        pass


class IDataRepository(ABC):
    """
    Repository pattern for hub data access.

    Dependency Inversion: High-level modules depend on this abstraction.
    """

    @abstractmethod
    def get_hub(self, hub_id: str) -> Optional[HubData]:
        """Retrieve a single hub by ID"""
        pass

    @abstractmethod
    def get_all_hubs(self) -> List[HubData]:
        """Retrieve all hubs"""
        pass

    @abstractmethod
    def get_hubs_by_tier(self, tier: HubTier) -> List[HubData]:
        """Retrieve hubs filtered by tier"""
        pass

    @abstractmethod
    def save_hub(self, hub: HubData) -> None:
        """Persist hub data"""
        pass


# ============================================================================
# Validation Interfaces
# ============================================================================

class IValidator(ABC):
    """
    Interface for data validation.

    Single Responsibility: Only validates data quality.
    Interface Segregation: Minimal, focused interface.
    """

    @abstractmethod
    def validate(self, data: Any) -> tuple[bool, List[str]]:
        """
        Validate data and return (is_valid, error_messages)

        Returns:
            Tuple of (is_valid: bool, errors: List[str])
        """
        pass


# ============================================================================
# Spatial Operations Interfaces
# ============================================================================

class IH3Aggregator(ABC):
    """
    Interface for H3 hexagon operations.

    Single Responsibility: Only handles H3 spatial operations.
    """

    @abstractmethod
    def aggregate_to_hexes(self, points: List[tuple], resolution: int) -> Dict[str, Any]:
        """Aggregate point data to H3 hexagons"""
        pass

    @abstractmethod
    def merge_adjacent_hexes(self, hexes: List[str], threshold_m: float) -> List[List[str]]:
        """Merge adjacent hexes into hub areas"""
        pass


class ISpatialAnalyzer(ABC):
    """
    Interface for general spatial analysis operations.

    Single Responsibility: Geometric calculations and spatial queries.
    """

    @abstractmethod
    def calculate_distance(self, point1: tuple, point2: tuple) -> float:
        """Calculate distance between two points in meters"""
        pass

    @abstractmethod
    def create_buffer(self, point: tuple, radius_m: float) -> Any:
        """Create a buffer polygon around a point"""
        pass

    @abstractmethod
    def count_within_rings(self, center: tuple, rings: List[float], features: List[Any]) -> Dict[float, int]:
        """Count features within concentric rings"""
        pass


# ============================================================================
# Classification Interfaces
# ============================================================================

class IEligibilityFilter(ABC):
    """
    Interface for hub eligibility filtering.

    Single Responsibility: Determine if a location qualifies as a hub.
    """

    @abstractmethod
    def is_eligible(self, hub_data: HubData) -> tuple[bool, str]:
        """
        Check if hub meets eligibility criteria.

        Returns:
            Tuple of (is_eligible: bool, reason: str)
        """
        pass


class IHubClassifier(ABC):
    """
    Interface for assigning hub tier classification.

    Single Responsibility: Classify hubs into hierarchy tiers.
    """

    @abstractmethod
    def classify(self, hub_data: HubData) -> HubTier:
        """Assign tier classification to hub"""
        pass


# ============================================================================
# Scoring Interfaces (Strategy Pattern)
# ============================================================================

class IScorer(ABC):
    """
    Base interface for all scoring criteria.

    Open/Closed: Extend by creating new scorer implementations.
    Liskov Substitution: All scorers can be used interchangeably.
    """

    @abstractmethod
    def calculate_score(self, hub_data: HubData) -> ScoringResult:
        """
        Calculate score for a hub.

        Returns:
            ScoringResult with raw value and normalized score (1-10)
        """
        pass

    @abstractmethod
    def get_criterion_name(self) -> str:
        """Return the name of this scoring criterion"""
        pass


class INormalizer(ABC):
    """
    Interface for score normalization.

    Single Responsibility: Only handles normalization logic.
    """

    @abstractmethod
    def normalize(self, values: List[float], min_score: float = 1.0, max_score: float = 10.0) -> List[float]:
        """Normalize values to specified range"""
        pass


class IAggregator(ABC):
    """
    Interface for aggregating multiple scores.

    Single Responsibility: Combine multiple criterion scores into final score.
    """

    @abstractmethod
    def aggregate(self, scores: List[ScoringResult], weights: Optional[Dict[str, float]] = None) -> float:
        """
        Aggregate multiple criterion scores.

        Args:
            scores: List of scoring results
            weights: Optional dict mapping criterion names to weights

        Returns:
            Final aggregated score
        """
        pass


# ============================================================================
# Monte Carlo Simulation Interface
# ============================================================================

class IMonteCarloSimulator(ABC):
    """
    Interface for Monte Carlo weight simulation.

    Single Responsibility: Run Monte Carlo simulations for robust scoring.
    """

    @abstractmethod
    def simulate(self,
                 hubs: List[HubData],
                 scorers: List[IScorer],
                 iterations: int,
                 max_weight: float) -> Dict[str, float]:
        """
        Run Monte Carlo simulation to get robust final scores.

        Args:
            hubs: List of hubs to score
            scorers: List of scorer implementations
            iterations: Number of simulation iterations
            max_weight: Maximum weight for any single criterion (0-1)

        Returns:
            Dict mapping hub_id to final aggregated score
        """
        pass


# ============================================================================
# Service Interfaces (Application Layer)
# ============================================================================

class IHubIdentificationService(ABC):
    """
    Service for identifying potential hubs.

    Dependency Inversion: Depends on abstractions (IDataLoader, IH3Aggregator, etc.)
    """

    @abstractmethod
    def identify_potential_hubs(self) -> List[HubData]:
        """Execute hub identification workflow"""
        pass


class IHubScoringService(ABC):
    """
    Service for scoring and prioritizing hubs.

    Dependency Inversion: Depends on IScorer, IAggregator abstractions.
    """

    @abstractmethod
    def score_hubs(self, hubs: List[HubData]) -> Dict[str, Dict[str, float]]:
        """
        Score all hubs on all criteria.

        Returns:
            Dict mapping hub_id to dict of criterion scores
        """
        pass

    @abstractmethod
    def prioritize_hubs(self, hubs: List[HubData]) -> List[tuple[HubData, float]]:
        """
        Score and rank hubs by priority.

        Returns:
            List of (hub, final_score) tuples, sorted by score descending
        """
        pass


# ============================================================================
# Export/Visualization Interfaces
# ============================================================================

class IExporter(ABC):
    """
    Interface for exporting results.

    Single Responsibility: Only handles data export.
    Interface Segregation: Minimal export interface.
    """

    @abstractmethod
    def export(self, data: Any, output_path: str) -> None:
        """Export data to specified path"""
        pass


class IVisualizer(ABC):
    """
    Interface for visualization generation.

    Single Responsibility: Only creates visualizations.
    """

    @abstractmethod
    def visualize(self, data: Any) -> Any:
        """Create visualization from data"""
        pass


# ============================================================================
# Configuration Interface
# ============================================================================

class IConfiguration(Protocol):
    """
    Protocol for configuration access.

    Dependency Inversion: Components depend on this protocol, not concrete config.
    """

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        ...

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value"""
        ...

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value"""
        ...

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value"""
        ...
