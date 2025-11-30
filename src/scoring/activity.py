"""
Activity (passenger volume) scorer.

Demonstrates:
- Open/Closed: New scorer type without modifying framework
- Single Responsibility: Only scores passenger activity
- Liskov Substitution: Can replace any IScorer
"""

import math
import logging
from typing import Dict, Any

from ..interfaces import HubData, INormalizer
from .base import BaseScorer

logger = logging.getLogger(__name__)


class ActivityScorer(BaseScorer):
    """
    Scores hubs based on 2050 passenger forecast.

    Uses log₁₀ transformation to prevent extreme skew from mega-stations.
    """

    def __init__(self, normalizer: INormalizer):
        super().__init__(normalizer)

    def extract_raw_value(self, hub_data: HubData) -> float:
        """Extract 2050 passenger forecast"""
        return float(hub_data.passengers_2050)

    def transform_value(self, value: float) -> float:
        """
        Apply log₁₀ transformation.

        A station with 100,000 passengers should not score 10× higher than 10,000.
        Logarithmic scale reflects diminishing marginal impact.
        """
        if value <= 0:
            return 0.0

        # log10(1000) ≈ 3, log10(10000) ≈ 4, log10(100000) ≈ 5
        return math.log10(value)

    def get_criterion_name(self) -> str:
        return "passenger_activity"

    def get_metadata(self, hub_data: HubData) -> Dict[str, Any]:
        """Add activity-specific metadata"""
        metadata = super().get_metadata(hub_data)
        metadata.update({
            'passengers_2050': hub_data.passengers_2050,
            'log_transform_applied': True
        })
        return metadata
