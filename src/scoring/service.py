"""
Service and modal hierarchy scorer.

Demonstrates:
- Single Responsibility: Only scores service level and modal diversity
- Dependency Injection: Receives mode weights via constructor
"""

import logging
from typing import Dict, Any, List
import math

from ..interfaces import HubData, INormalizer, TransitMode
from .base import BaseScorer

logger = logging.getLogger(__name__)


class ServiceModeScorer(BaseScorer):
    """
    Scores hubs based on:
    1. Line count per mode (with diminishing returns)
    2. Modal weights (higher capacity = higher weight)
    3. Diversity bonus (multiple modes = network effects)
    """

    def __init__(self, normalizer: INormalizer, mode_weights: Dict[TransitMode, float]):
        """
        Initialize with mode weights.

        Dependency Injection: Mode weights provided externally.
        """
        super().__init__(normalizer)
        self.mode_weights = mode_weights

    def extract_raw_value(self, hub_data: HubData) -> float:
        """
        Calculate service score from modes and lines.

        Components:
        1. Weighted line counts (diminishing returns)
        2. Modal diversity bonus
        """
        if not hub_data.modes:
            return 0.0

        # Calculate base score from modes
        base_score = 0.0
        for mode in hub_data.modes:
            mode_weight = self.mode_weights.get(mode, 0.5)

            # For now, assume 1 line per mode
            # In production, extract actual line counts from metadata
            line_count = 1
            diminished_count = self._apply_diminishing_returns(line_count)

            base_score += mode_weight * diminished_count

        # Apply diversity bonus
        diversity_bonus = self._calculate_diversity_bonus(len(hub_data.modes))
        final_score = base_score * diversity_bonus

        return final_score

    def _apply_diminishing_returns(self, line_count: int) -> float:
        """
        Apply diminishing returns to line count.

        2nd/3rd lines matter more than 9th line.
        Uses logarithmic scaling.
        """
        if line_count <= 0:
            return 0.0

        # log(1+x) gives diminishing returns
        # 1 line = 0.69, 2 lines = 1.10, 5 lines = 1.79, 10 lines = 2.40
        return math.log(1 + line_count)

    def _calculate_diversity_bonus(self, mode_count: int) -> float:
        """
        Calculate bonus for modal diversity.

        2nd mode: +10%
        3rd mode: +20%
        4th mode: +30%
        And so on...
        """
        if mode_count <= 1:
            return 1.0

        # (mode_count - 1) * 10% bonus
        bonus_percent = (mode_count - 1) * 0.10
        return 1.0 + bonus_percent

    def get_criterion_name(self) -> str:
        return "service_mode_hierarchy"

    def get_metadata(self, hub_data: HubData) -> Dict[str, Any]:
        """Add service-specific metadata"""
        metadata = super().get_metadata(hub_data)
        metadata.update({
            'mode_count': len(hub_data.modes),
            'modes': [mode.value for mode in hub_data.modes],
            'diversity_bonus': self._calculate_diversity_bonus(len(hub_data.modes))
        })
        return metadata
