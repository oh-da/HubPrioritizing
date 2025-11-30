"""
Geographic/location scorer.

Balances national equity (periphery priority) with metropolitan efficiency.
"""

import logging
from typing import Dict, Any

from ..interfaces import HubData, INormalizer
from .base import BaseScorer

logger = logging.getLogger(__name__)


class LocationScorer(BaseScorer):
    """
    Scores hubs based on strategic location.

    Two-dimensional scoring:
    1. National region (periphery boost)
    2. Metropolitan position (core importance)
    """

    # Regional weights (inverted: periphery = higher weight)
    REGION_WEIGHTS = {
        'center': 0.0,
        'tel_aviv': 0.0,
        'haifa': 0.5,
        'north': 1.0,
        'south': 1.0,
        'jerusalem': 0.7
    }

    # Metropolitan ring scores
    RING_SCORES = {
        'core': 3,
        'first_ring': 2,
        'outer': 1
    }

    def __init__(self, normalizer: INormalizer):
        super().__init__(normalizer)

    def extract_raw_value(self, hub_data: HubData) -> float:
        """
        Calculate location score.

        Formula: region_weight × ring_score
        """
        if not hub_data.location:
            return 0.0

        region = hub_data.location.region.lower()
        ring = hub_data.location.metropolitan_ring.lower()

        region_weight = self.REGION_WEIGHTS.get(region, 0.5)
        ring_score = self.RING_SCORES.get(ring, 1)

        # Combine dimensions
        location_score = (1 + region_weight) * ring_score

        return location_score

    def get_criterion_name(self) -> str:
        return "geographic_location"

    def get_metadata(self, hub_data: HubData) -> Dict[str, Any]:
        """Add location-specific metadata"""
        metadata = super().get_metadata(hub_data)

        if hub_data.location:
            metadata.update({
                'region': hub_data.location.region,
                'metropolitan_ring': hub_data.location.metropolitan_ring,
                'region_weight': self.REGION_WEIGHTS.get(
                    hub_data.location.region.lower(), 0.5
                ),
                'ring_score': self.RING_SCORES.get(
                    hub_data.location.metropolitan_ring.lower(), 1
                )
            })

        return metadata
