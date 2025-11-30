"""
Tests demonstrating SOLID principles.

This test file showcases how SOLID principles enable:
- Easy testing through dependency injection
- Extension without modification
- Interface substitution
- Focused, single-purpose components
"""

import pytest
from typing import List, Tuple

from src.interfaces import (
    IScorer, INormalizer, HubData, HubLocation, HubTier,
    TransitMode, ScoringResult, IEligibilityFilter, IHubClassifier
)
from src.scoring.base import BaseScorer
from src.scoring.normalization import MinMaxNormalizer, LogNormalizer
from src.scoring.activity import ActivityScorer
from src.classification.eligibility import (
    PassengerEligibilityFilter,
    ModeEligibilityFilter,
    CompositeEligibilityFilter
)
from src.classification.hierarchy import PassengerBasedClassifier


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_hub() -> HubData:
    """Create a sample hub for testing"""
    return HubData(
        hub_id="test_001",
        name="Test Hub",
        location=HubLocation(
            lat=32.0853,
            lon=34.7818,
            h3_index="h3_test",
            region="center",
            metropolitan_ring="core"
        ),
        tier=None,
        passengers_2050=25000,
        modes=[TransitMode.RAIL, TransitMode.BUS],
        metadata={}
    )


@pytest.fixture
def high_volume_hub() -> HubData:
    """Create a high-volume hub for testing"""
    return HubData(
        hub_id="test_national",
        name="National Hub",
        location=HubLocation(
            lat=32.0853,
            lon=34.7818,
            h3_index="h3_national",
            region="center",
            metropolitan_ring="core"
        ),
        tier=None,
        passengers_2050=120000,
        modes=[TransitMode.RAIL, TransitMode.METRO, TransitMode.BUS],
        metadata={}
    )


@pytest.fixture
def low_volume_hub() -> HubData:
    """Create a low-volume hub for testing"""
    return HubData(
        hub_id="test_local",
        name="Local Hub",
        location=HubLocation(
            lat=32.0,
            lon=34.8,
            h3_index="h3_local",
            region="north",
            metropolitan_ring="outer"
        ),
        tier=None,
        passengers_2050=800,  # Below eligibility threshold
        modes=[TransitMode.BUS],  # Only one mode
        metadata={}
    )


# ============================================================================
# Single Responsibility Principle Tests
# ============================================================================

class TestSingleResponsibility:
    """
    Demonstrate Single Responsibility Principle.

    Each class should have one reason to change.
    """

    def test_normalizer_only_normalizes(self):
        """
        MinMaxNormalizer has one responsibility: normalize values.
        It doesn't load data, score hubs, or classify - just normalizes.
        """
        normalizer = MinMaxNormalizer()
        values = [100, 500, 1000, 5000, 10000]

        normalized = normalizer.normalize(values, min_score=1.0, max_score=10.0)

        # Verify normalization worked
        assert len(normalized) == len(values)
        assert min(normalized) == 1.0  # Min value -> min score
        assert max(normalized) == 10.0  # Max value -> max score
        assert all(1.0 <= v <= 10.0 for v in normalized)  # All in range

    def test_eligibility_filter_only_filters(self, sample_hub, low_volume_hub):
        """
        PassengerEligibilityFilter has one responsibility: check passenger threshold.
        It doesn't classify tiers or score - just filters.
        """
        filter_instance = PassengerEligibilityFilter()

        # Hub with sufficient passengers
        is_eligible, reason = filter_instance.is_eligible(sample_hub)
        assert is_eligible is True

        # Hub with insufficient passengers
        is_eligible, reason = filter_instance.is_eligible(low_volume_hub)
        assert is_eligible is False
        assert "Insufficient passengers" in reason

    def test_classifier_only_classifies(self, sample_hub, high_volume_hub, low_volume_hub):
        """
        PassengerBasedClassifier has one responsibility: assign tier.
        It doesn't filter eligibility or score - just classifies.
        """
        classifier = PassengerBasedClassifier()

        # National tier
        assert classifier.classify(high_volume_hub) == HubTier.NATIONAL

        # Metropolitan tier
        assert classifier.classify(sample_hub) == HubTier.METROPOLITAN

        # Local tier
        assert classifier.classify(low_volume_hub) == HubTier.LOCAL


# ============================================================================
# Open/Closed Principle Tests
# ============================================================================

class CustomScorer(BaseScorer):
    """
    Custom scorer for testing Open/Closed principle.

    Extends BaseScorer without modifying existing code.
    """

    def extract_raw_value(self, hub_data: HubData) -> float:
        # Custom logic: score based on mode count
        return float(len(hub_data.modes))

    def get_criterion_name(self) -> str:
        return "custom_mode_count"


class TestOpenClosed:
    """
    Demonstrate Open/Closed Principle.

    System should be open for extension but closed for modification.
    """

    def test_add_new_scorer_without_modifying_framework(self, sample_hub):
        """
        We can add a new scorer by extending BaseScorer,
        without modifying the base framework.
        """
        normalizer = MinMaxNormalizer()
        custom_scorer = CustomScorer(normalizer)

        # New scorer works with existing infrastructure
        result = custom_scorer.calculate_score(sample_hub)

        assert isinstance(result, ScoringResult)
        assert result.criterion_name == "custom_mode_count"
        assert result.raw_value == 2.0  # sample_hub has 2 modes

    def test_add_new_normalizer_strategy(self):
        """
        We can add new normalization strategies without modifying existing scorers.
        """
        values = [100, 1000, 10000, 100000]

        # Use different normalizers interchangeably
        min_max = MinMaxNormalizer()
        log_norm = LogNormalizer(base=10)

        result1 = min_max.normalize(values)
        result2 = log_norm.normalize(values)

        # Both work, produce different but valid results
        assert len(result1) == len(values)
        assert len(result2) == len(values)
        assert result1 != result2  # Different strategies, different results

    def test_composite_eligibility_filter_extensibility(self, sample_hub):
        """
        Composite filter can be extended with new filters without modification.
        """
        # Start with basic filters
        composite = CompositeEligibilityFilter([
            PassengerEligibilityFilter(),
            ModeEligibilityFilter()
        ])

        # Can add new filters dynamically
        class CustomFilter(IEligibilityFilter):
            def is_eligible(self, hub_data: HubData) -> Tuple[bool, str]:
                # Custom rule: must be in center region
                if hub_data.location.region == "center":
                    return True, "In center region"
                return False, "Not in center region"

        composite.add_filter(CustomFilter())

        # Composite works with new filter
        is_eligible, reason = composite.is_eligible(sample_hub)
        assert is_eligible is True  # sample_hub is in center


# ============================================================================
# Liskov Substitution Principle Tests
# ============================================================================

class TestLiskovSubstitution:
    """
    Demonstrate Liskov Substitution Principle.

    Derived classes must be substitutable for their base classes.
    """

    def test_all_scorers_interchangeable(self, sample_hub):
        """
        All IScorer implementations can be used interchangeably.
        """
        normalizer = MinMaxNormalizer()

        scorers: List[IScorer] = [
            ActivityScorer(normalizer),
            CustomScorer(normalizer)
        ]

        # All scorers work through same interface
        for scorer in scorers:
            result = scorer.calculate_score(sample_hub)

            # All return valid ScoringResult
            assert isinstance(result, ScoringResult)
            assert result.hub_id == sample_hub.hub_id
            assert 1.0 <= result.normalized_score <= 10.0
            assert len(scorer.get_criterion_name()) > 0

    def test_all_normalizers_interchangeable(self):
        """
        All INormalizer implementations can be used interchangeably.
        """
        values = [100, 500, 1000, 5000]

        normalizers: List[INormalizer] = [
            MinMaxNormalizer(),
            LogNormalizer(base=10)
        ]

        # All normalizers work through same interface
        for normalizer in normalizers:
            result = normalizer.normalize(values, min_score=1.0, max_score=10.0)

            # All return valid normalized values
            assert len(result) == len(values)
            assert all(1.0 <= v <= 10.0 for v in result)


# ============================================================================
# Interface Segregation Principle Tests
# ============================================================================

class TestInterfaceSegregation:
    """
    Demonstrate Interface Segregation Principle.

    Clients shouldn't be forced to depend on interfaces they don't use.
    """

    def test_scorer_interface_minimal(self, sample_hub):
        """
        IScorer interface is minimal - only what scorers need.
        Scorers don't need to implement unrelated methods.
        """
        normalizer = MinMaxNormalizer()
        scorer = ActivityScorer(normalizer)

        # Scorer only needs to implement:
        # - calculate_score()
        # - get_criterion_name()
        # Nothing else required

        result = scorer.calculate_score(sample_hub)
        name = scorer.get_criterion_name()

        assert isinstance(result, ScoringResult)
        assert isinstance(name, str)

    def test_filter_interface_minimal(self, sample_hub):
        """
        IEligibilityFilter interface is minimal - just is_eligible().
        """
        filter_instance = PassengerEligibilityFilter()

        # Filter only needs to implement is_eligible()
        is_eligible, reason = filter_instance.is_eligible(sample_hub)

        assert isinstance(is_eligible, bool)
        assert isinstance(reason, str)

    def test_normalizer_interface_focused(self):
        """
        INormalizer interface is focused - just normalize().
        No data loading, scoring, or other unrelated methods.
        """
        normalizer = MinMaxNormalizer()

        # Normalizer only needs normalize()
        result = normalizer.normalize([1, 2, 3])

        assert isinstance(result, list)


# ============================================================================
# Dependency Inversion Principle Tests
# ============================================================================

class MockNormalizer(INormalizer):
    """Mock normalizer for testing dependency injection"""

    def normalize(self, values: List[float], min_score: float = 1.0, max_score: float = 10.0) -> List[float]:
        # Mock: return fixed value for testing
        return [5.0] * len(values)


class TestDependencyInversion:
    """
    Demonstrate Dependency Inversion Principle.

    High-level modules should depend on abstractions, not concretions.
    """

    def test_scorer_depends_on_normalizer_abstraction(self, sample_hub):
        """
        Scorer depends on INormalizer interface, not concrete implementation.
        We can inject different normalizers.
        """
        # Inject real normalizer
        real_normalizer = MinMaxNormalizer()
        scorer1 = ActivityScorer(real_normalizer)
        result1 = scorer1.calculate_score(sample_hub)

        # Inject mock normalizer
        mock_normalizer = MockNormalizer()
        scorer2 = ActivityScorer(mock_normalizer)
        result2 = scorer2.calculate_score(sample_hub)

        # Both work, demonstrating dependency on abstraction
        assert isinstance(result1, ScoringResult)
        assert isinstance(result2, ScoringResult)

    def test_classifier_depends_on_configuration_abstraction(self, sample_hub):
        """
        Classifier depends on IConfiguration interface, not concrete config.
        """
        # Can inject different configurations
        from src.config import Configuration

        custom_config = Configuration()
        custom_config.thresholds.national_hub_min_passengers = 30000

        classifier = PassengerBasedClassifier(config=custom_config)

        # Classifier uses injected configuration
        # sample_hub has 25,000 passengers
        # With default config (50,000 threshold): METROPOLITAN
        # With custom config (30,000 threshold): still METROPOLITAN

        tier = classifier.classify(sample_hub)
        assert tier == HubTier.METROPOLITAN

    def test_filters_can_be_composed(self, sample_hub):
        """
        Composite filter depends on IEligibilityFilter abstraction.
        Can compose any filters that implement the interface.
        """
        # Compose filters through dependency injection
        composite = CompositeEligibilityFilter([
            PassengerEligibilityFilter(),
            ModeEligibilityFilter()
        ])

        is_eligible, reason = composite.is_eligible(sample_hub)

        # Composition works through abstraction
        assert isinstance(is_eligible, bool)
