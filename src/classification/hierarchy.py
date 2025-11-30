"""
Hub hierarchy classification.

Assigns hubs to tiers: ארצי (National), מטרופוליני (Metropolitan), עירוני (Local).

Demonstrates:
- Strategy Pattern: Different classification strategies
- Single Responsibility: Each classifier uses one classification logic
"""

import logging
from typing import Dict, Any

from ..interfaces import IHubClassifier, HubData, HubTier, IConfiguration
from ..config import get_config

logger = logging.getLogger(__name__)


class PassengerBasedClassifier(IHubClassifier):
    """
    Classifies hubs based solely on passenger thresholds.

    Single Responsibility: Classification by passenger volume only.

    Thresholds:
    - National: >= 50,000 passengers/day
    - Metropolitan: 5,000 - 50,000 passengers/day
    - Local: < 5,000 passengers/day
    """

    def __init__(self, config: IConfiguration | None = None):
        """
        Initialize with configuration.

        Dependency Injection: Configuration provided externally.
        """
        self.config = config or get_config()

        self.national_threshold = self.config.get_int(
            'thresholds.national_hub_min_passengers',
            default=50000
        )

        self.metro_threshold = self.config.get_int(
            'thresholds.metro_hub_min_passengers',
            default=5000
        )

    def classify(self, hub_data: HubData) -> HubTier:
        """Classify hub based on passenger count"""
        passengers = hub_data.passengers_2050

        if passengers >= self.national_threshold:
            tier = HubTier.NATIONAL
        elif passengers >= self.metro_threshold:
            tier = HubTier.METROPOLITAN
        else:
            tier = HubTier.LOCAL

        logger.debug(
            f"Classified hub {hub_data.hub_id} as {tier.value} "
            f"({passengers} passengers)"
        )

        return tier


class RuleBasedClassifier(IHubClassifier):
    """
    Classifies hubs using multi-criteria rules.

    Considers:
    - Passenger volume
    - Number of modes
    - Geographic context
    - Network role

    Demonstrates Open/Closed: Extend rules without modifying base logic.
    """

    def __init__(self, config: IConfiguration | None = None):
        """
        Initialize with configuration.

        Dependency Injection: Configuration provided externally.
        """
        self.config = config or get_config()
        self.passenger_classifier = PassengerBasedClassifier(config)

    def classify(self, hub_data: HubData) -> HubTier:
        """
        Classify hub using rule-based logic.

        Algorithm:
        1. Start with passenger-based classification
        2. Apply adjustment rules based on other factors
        3. Return final classification
        """
        # Base classification from passengers
        base_tier = self.passenger_classifier.classify(hub_data)

        # Apply adjustment rules
        adjusted_tier = self._apply_adjustment_rules(hub_data, base_tier)

        logger.debug(
            f"Classified hub {hub_data.hub_id}: "
            f"base={base_tier.value}, adjusted={adjusted_tier.value}"
        )

        return adjusted_tier

    def _apply_adjustment_rules(self,
                                hub_data: HubData,
                                base_tier: HubTier) -> HubTier:
        """
        Apply rules to potentially adjust tier classification.

        Rules:
        - High modal diversity can upgrade LOCAL -> METROPOLITAN
        - Strategic location can influence tier
        - Network role (from metadata) can override

        Returns:
            Potentially adjusted tier
        """
        tier = base_tier

        # Rule 1: Modal diversity upgrade
        if tier == HubTier.LOCAL and len(hub_data.modes) >= 3:
            # Many modes despite lower ridership -> upgrade to METRO
            logger.debug(
                f"Upgrading {hub_data.hub_id} from LOCAL to METRO "
                f"due to modal diversity ({len(hub_data.modes)} modes)"
            )
            tier = HubTier.METROPOLITAN

        # Rule 2: Strategic location (from metadata)
        network_role = hub_data.metadata.get('network_role')
        if network_role == 'national_gateway':
            # Strategic importance overrides passenger count
            if tier != HubTier.NATIONAL:
                logger.debug(
                    f"Upgrading {hub_data.hub_id} to NATIONAL "
                    f"due to strategic role: {network_role}"
                )
                tier = HubTier.NATIONAL

        # Rule 3: Passenger threshold near boundaries
        passengers = hub_data.passengers_2050

        # If just below national threshold but has many modes, upgrade
        if (tier == HubTier.METROPOLITAN and
            passengers >= 45000 and  # Within 10% of threshold
            len(hub_data.modes) >= 3):

            logger.debug(
                f"Upgrading {hub_data.hub_id} to NATIONAL "
                f"(near threshold: {passengers}, high modal diversity)"
            )
            tier = HubTier.NATIONAL

        return tier


class RegionalClassifier(IHubClassifier):
    """
    Classifies hubs with regional context.

    Applies different thresholds based on regional context
    (e.g., lower thresholds in peripheral regions).

    Demonstrates Open/Closed: New classification strategy without modifying existing.
    """

    def __init__(self,
                 config: IConfiguration | None = None,
                 regional_adjustments: Dict[str, float] | None = None):
        """
        Initialize with regional adjustment factors.

        Args:
            config: Configuration instance
            regional_adjustments: Dict mapping region to threshold multiplier
                                Example: {'south': 0.7} means 70% of base threshold
        """
        self.config = config or get_config()
        self.passenger_classifier = PassengerBasedClassifier(config)

        # Default regional adjustments (favor periphery)
        self.regional_adjustments = regional_adjustments or {
            'center': 1.0,
            'tel_aviv': 1.0,
            'haifa': 0.9,
            'north': 0.8,
            'south': 0.8,
            'jerusalem': 0.9
        }

    def classify(self, hub_data: HubData) -> HubTier:
        """
        Classify with regional context.

        Applies adjustment factor to effective passenger count before classification.
        """
        if not hub_data.location:
            return self.passenger_classifier.classify(hub_data)

        region = hub_data.location.region.lower()
        adjustment = self.regional_adjustments.get(region, 1.0)

        # Adjust passenger count (effectively lowering threshold in periphery)
        adjusted_passengers = hub_data.passengers_2050 / adjustment

        # Create temporary hub data with adjusted passengers
        adjusted_hub = HubData(
            hub_id=hub_data.hub_id,
            name=hub_data.name,
            location=hub_data.location,
            tier=hub_data.tier,
            passengers_2050=int(adjusted_passengers),
            modes=hub_data.modes,
            metadata=hub_data.metadata
        )

        return self.passenger_classifier.classify(adjusted_hub)
