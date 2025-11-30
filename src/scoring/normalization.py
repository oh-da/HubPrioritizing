"""
Score normalization implementations.

Demonstrates:
- Single Responsibility: Each normalizer has one normalization strategy
- Open/Closed: Add new normalizers without modifying existing code
"""

import math
import logging
from typing import List

from ..interfaces import INormalizer

logger = logging.getLogger(__name__)


class MinMaxNormalizer(INormalizer):
    """
    Min-max normalization to specified range.

    Single Responsibility: Only handles min-max scaling.
    """

    def normalize(self,
                  values: List[float],
                  min_score: float = 1.0,
                  max_score: float = 10.0) -> List[float]:
        """
        Normalize values to [min_score, max_score] range using min-max scaling.

        Formula: normalized = min_score + (value - min_val) / (max_val - min_val) * (max_score - min_score)
        """
        if not values:
            return []

        # Handle single value or all same values
        min_val = min(values)
        max_val = max(values)

        if min_val == max_val:
            # All values are the same, return middle of range
            mid_score = (min_score + max_score) / 2
            return [mid_score] * len(values)

        # Normalize to range
        normalized = []
        value_range = max_val - min_val
        score_range = max_score - min_score

        for value in values:
            norm = min_score + ((value - min_val) / value_range) * score_range
            normalized.append(norm)

        return normalized


class LogNormalizer(INormalizer):
    """
    Logarithmic normalization for skewed distributions.

    Useful for data with extreme outliers (like passenger counts).
    """

    def __init__(self, base: float = 10.0):
        """
        Initialize with logarithm base.

        Args:
            base: Logarithm base (default: 10)
        """
        self.base = base

    def normalize(self,
                  values: List[float],
                  min_score: float = 1.0,
                  max_score: float = 10.0) -> List[float]:
        """
        Normalize using logarithmic transformation followed by min-max scaling.

        Formula:
        1. log_value = log_base(value + 1)  # +1 to handle zero
        2. normalized = min-max scale of log_values
        """
        if not values:
            return []

        # Apply log transformation
        log_values = []
        for value in values:
            if value < 0:
                logger.warning(f"Negative value {value} in log normalization, using 0")
                value = 0

            log_val = math.log(value + 1, self.base)
            log_values.append(log_val)

        # Min-max normalize the log-transformed values
        min_max = MinMaxNormalizer()
        return min_max.normalize(log_values, min_score, max_score)


class PerCategoryNormalizer(INormalizer):
    """
    Normalizes separately within categories (e.g., hub tiers).

    Ensures fair comparison within each tier.
    """

    def __init__(self, base_normalizer: INormalizer):
        """
        Initialize with base normalization strategy.

        Dependency Injection: Composition over inheritance.
        """
        self.base_normalizer = base_normalizer

    def normalize(self,
                  values: List[float],
                  min_score: float = 1.0,
                  max_score: float = 10.0) -> List[float]:
        """
        Normalize within categories.

        Note: This simplified version normalizes all values together.
        In production, you'd pass category labels and normalize per category.
        """
        return self.base_normalizer.normalize(values, min_score, max_score)

    def normalize_by_category(self,
                             values: List[float],
                             categories: List[str],
                             min_score: float = 1.0,
                             max_score: float = 10.0) -> List[float]:
        """
        Normalize separately for each category.

        Args:
            values: Values to normalize
            categories: Category label for each value
            min_score: Minimum normalized score
            max_score: Maximum normalized score

        Returns:
            Normalized values, maintaining original order
        """
        if len(values) != len(categories):
            raise ValueError("values and categories must have same length")

        # Group by category
        category_groups = {}
        for i, (value, category) in enumerate(zip(values, categories)):
            if category not in category_groups:
                category_groups[category] = []
            category_groups[category].append((i, value))

        # Normalize each group
        normalized = [0.0] * len(values)
        for category, group_items in category_groups.items():
            indices = [i for i, _ in group_items]
            group_values = [v for _, v in group_items]

            # Normalize this group
            group_normalized = self.base_normalizer.normalize(
                group_values, min_score, max_score
            )

            # Place back in original positions
            for idx, norm_val in zip(indices, group_normalized):
                normalized[idx] = norm_val

        return normalized
