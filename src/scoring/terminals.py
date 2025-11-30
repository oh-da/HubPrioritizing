"""
Bus terminal proximity scorer.

Scores based on integration with bus network infrastructure.
"""

import logging
from typing import Dict, Any

from ..interfaces import HubData, INormalizer
from .base import BaseScorer

logger = logging.getLogger(__name__)


class BusTerminalScorer(BaseScorer):
    """
    Scores hubs based on bus terminal proximity and integration.

    Measures integration with bus network for first/last mile connectivity.
    """

    # Terminal type weights
    TERMINAL_WEIGHTS = {
        'national': 1.0,
        'regional': 0.8,
        'metropolitan': 0.6,
        'local': 0.4
    }

    def __init__(self, normalizer: INormalizer, proximity_threshold_m: float = 200):
        """
        Initialize with proximity threshold.

        Dependency Injection: Threshold provided externally.
        """
        super().__init__(normalizer)
        self.proximity_threshold_m = proximity_threshold_m

    def extract_raw_value(self, hub_data: HubData) -> float:
        """
        Calculate terminal integration score.

        In production: Query terminals within threshold distance.
        For now: Use placeholder data from metadata.
        """
        # Extract terminal data from metadata
        terminals_nearby = hub_data.metadata.get('bus_terminals_nearby', [])

        if not terminals_nearby:
            return 0.0

        # Calculate weighted score from terminals
        score = 0.0
        for terminal in terminals_nearby:
            terminal_type = terminal.get('type', 'local').lower()
            distance_m = terminal.get('distance_m', float('inf'))

            # Apply distance decay
            if distance_m <= self.proximity_threshold_m:
                terminal_weight = self.TERMINAL_WEIGHTS.get(terminal_type, 0.4)
                proximity_factor = 1.0 - (distance_m / self.proximity_threshold_m)
                score += terminal_weight * proximity_factor

        return score

    def get_criterion_name(self) -> str:
        return "bus_terminal_proximity"

    def get_metadata(self, hub_data: HubData) -> Dict[str, Any]:
        """Add terminal-specific metadata"""
        metadata = super().get_metadata(hub_data)

        terminals = hub_data.metadata.get('bus_terminals_nearby', [])
        metadata.update({
            'terminal_count': len(terminals),
            'proximity_threshold_m': self.proximity_threshold_m,
            'terminals': terminals
        })

        return metadata
