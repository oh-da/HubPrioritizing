"""
Hub eligibility filtering.

Determines which locations qualify as integrated transport hubs.

Demonstrates:
- Single Responsibility: Each filter checks one eligibility criterion
- Composite Pattern: CompositeFilter combines multiple filters
"""

import logging
from typing import Tuple, List

from ..interfaces import IEligibilityFilter, HubData, IConfiguration
from ..config import get_config

logger = logging.getLogger(__name__)


class PassengerEligibilityFilter(IEligibilityFilter):
    """
    Filters based on minimum passenger threshold.

    Single Responsibility: Only checks passenger count eligibility.
    """

    def __init__(self, config: IConfiguration | None = None):
        """
        Initialize with configuration.

        Dependency Injection: Configuration provided externally.
        """
        self.config = config or get_config()
        self.min_passengers = self.config.get_int(
            'thresholds.eligibility_min_passengers',
            default=1000
        )

    def is_eligible(self, hub_data: HubData) -> Tuple[bool, str]:
        """Check if hub meets minimum passenger threshold"""
        passengers = hub_data.passengers_2050

        if passengers < self.min_passengers:
            return False, f"Insufficient passengers: {passengers} < {self.min_passengers}"

        return True, f"Meets passenger threshold: {passengers} >= {self.min_passengers}"


class ModeEligibilityFilter(IEligibilityFilter):
    """
    Filters based on minimum number of mass-transit modes.

    Single Responsibility: Only checks modal diversity eligibility.
    """

    def __init__(self, config: IConfiguration | None = None):
        """
        Initialize with configuration.

        Dependency Injection: Configuration provided externally.
        """
        self.config = config or get_config()
        self.min_modes = self.config.get_int(
            'thresholds.eligibility_min_modes',
            default=2
        )

    def is_eligible(self, hub_data: HubData) -> Tuple[bool, str]:
        """Check if hub has minimum number of mass-transit modes"""
        mode_count = len(hub_data.modes)

        if mode_count < self.min_modes:
            return False, f"Insufficient modes: {mode_count} < {self.min_modes}"

        return True, f"Meets mode requirement: {mode_count} >= {self.min_modes}"


class LocationEligibilityFilter(IEligibilityFilter):
    """
    Filters based on geographic/location criteria.

    Single Responsibility: Only checks location-based eligibility.
    """

    def is_eligible(self, hub_data: HubData) -> Tuple[bool, str]:
        """Check if hub location is valid"""
        if not hub_data.location:
            return False, "No location data provided"

        # Check coordinates are in valid range
        lat, lon = hub_data.location.lat, hub_data.location.lon

        # Israel bounding box (approximate)
        if not (29.0 <= lat <= 33.5):
            return False, f"Latitude {lat} outside Israel bounds"

        if not (34.0 <= lon <= 36.0):
            return False, f"Longitude {lon} outside Israel bounds"

        return True, "Location is valid"


class CompositeEligibilityFilter(IEligibilityFilter):
    """
    Combines multiple eligibility filters.

    Demonstrates Composite Pattern:
    - Treats single and composite filters uniformly
    - All filters must pass for eligibility
    """

    def __init__(self, filters: List[IEligibilityFilter] | None = None):
        """
        Initialize with list of filters.

        Dependency Injection: Filters provided externally.
        """
        self.filters = filters or []

    def add_filter(self, filter_instance: IEligibilityFilter) -> None:
        """Add a filter to the composite"""
        self.filters.append(filter_instance)

    def is_eligible(self, hub_data: HubData) -> Tuple[bool, str]:
        """
        Check eligibility against all filters.

        Returns eligible only if ALL filters pass.
        """
        if not self.filters:
            return True, "No filters configured (default: eligible)"

        failed_reasons = []

        for filter_instance in self.filters:
            is_eligible, reason = filter_instance.is_eligible(hub_data)

            if not is_eligible:
                failed_reasons.append(reason)

        if failed_reasons:
            combined_reason = "; ".join(failed_reasons)
            return False, f"Failed eligibility: {combined_reason}"

        return True, "Passed all eligibility filters"


def create_default_eligibility_filter(config: IConfiguration | None = None) -> IEligibilityFilter:
    """
    Factory function to create default eligibility filter.

    Returns composite filter with standard eligibility criteria.
    """
    composite = CompositeEligibilityFilter([
        PassengerEligibilityFilter(config),
        ModeEligibilityFilter(config),
        LocationEligibilityFilter()
    ])

    return composite
