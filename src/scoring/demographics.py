"""
Population and jobs (demographics) scorer.

Scores based on development potential and catchment area.
"""

import logging
from typing import Dict, Any, List

from ..interfaces import HubData, INormalizer, HubTier
from .base import BaseScorer

logger = logging.getLogger(__name__)


class DemographicsScorer(BaseScorer):
    """
    Scores hubs based on population and employment in catchment area.

    Uses concentric rings with distance decay.
    Different job/population mix by hub tier.
    """

    def __init__(self,
                 normalizer: INormalizer,
                 rings: List[float],
                 national_metro_job_weight: float = 0.8,
                 local_job_weight: float = 0.2):
        """
        Initialize with ring definitions and job/population weights.

        Dependency Injection: Ring sizes and weights provided externally.
        """
        super().__init__(normalizer)
        self.rings = rings
        self.national_metro_job_weight = national_metro_job_weight
        self.local_job_weight = local_job_weight

    def extract_raw_value(self, hub_data: HubData) -> float:
        """
        Calculate demographic score from catchment area.

        In production: Query actual population/job data within rings.
        For now: Use placeholder data from metadata.
        """
        # Determine job/population weights based on tier
        job_weight, pop_weight = self._get_weights_for_tier(hub_data.tier)

        # Extract demographic data from metadata
        # In production, this would query spatial database
        population_in_catchment = hub_data.metadata.get('population_catchment', 0)
        jobs_in_catchment = hub_data.metadata.get('jobs_catchment', 0)

        # Calculate weighted score
        score = (job_weight * jobs_in_catchment +
                pop_weight * population_in_catchment)

        return score

    def _get_weights_for_tier(self, tier: HubTier) -> tuple[float, float]:
        """
        Get job/population weights based on hub tier.

        National/Metropolitan: Employment-focused (80% jobs, 20% pop)
        Local: Residential-focused (20% jobs, 80% pop)
        """
        if tier in [HubTier.NATIONAL, HubTier.METROPOLITAN]:
            job_weight = self.national_metro_job_weight
            pop_weight = 1.0 - job_weight
        else:  # LOCAL
            job_weight = self.local_job_weight
            pop_weight = 1.0 - job_weight

        return job_weight, pop_weight

    def get_criterion_name(self) -> str:
        return "population_jobs"

    def get_metadata(self, hub_data: HubData) -> Dict[str, Any]:
        """Add demographics-specific metadata"""
        metadata = super().get_metadata(hub_data)

        job_weight, pop_weight = self._get_weights_for_tier(hub_data.tier)

        metadata.update({
            'job_weight': job_weight,
            'population_weight': pop_weight,
            'population_catchment': hub_data.metadata.get('population_catchment', 0),
            'jobs_catchment': hub_data.metadata.get('jobs_catchment', 0),
            'rings_m': self.rings
        })

        return metadata
