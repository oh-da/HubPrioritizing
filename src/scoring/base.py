"""
Base scorer implementation.

Provides common functionality for all scorers while maintaining
the IScorer interface contract.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

from ..interfaces import IScorer, HubData, ScoringResult, INormalizer

logger = logging.getLogger(__name__)


class BaseScorer(IScorer, ABC):
    """
    Abstract base class for all scorers.

    Template Method Pattern: Defines scoring workflow while allowing
    subclasses to customize specific steps.

    Single Responsibility: Manages the scoring workflow.
    Open/Closed: Extend by subclassing, don't modify this class.
    """

    def __init__(self, normalizer: INormalizer):
        """
        Initialize scorer with a normalizer.

        Dependency Inversion: Depends on INormalizer abstraction, not concrete class.
        """
        self.normalizer = normalizer

    def calculate_score(self, hub_data: HubData) -> ScoringResult:
        """
        Calculate score for a hub (Template Method).

        This method defines the algorithm structure:
        1. Extract raw value
        2. Validate value
        3. Transform value (if needed)
        4. Normalize to 1-10 range
        5. Create result object

        Subclasses customize by overriding extract_raw_value and transform_value.
        """
        try:
            # Step 1: Extract raw value
            raw_value = self.extract_raw_value(hub_data)

            # Step 2: Validate
            if not self.validate_value(raw_value):
                logger.warning(
                    f"Invalid value for {self.get_criterion_name()}: {raw_value}"
                )
                return self._create_invalid_result(hub_data.hub_id)

            # Step 3: Transform (optional, e.g., log transform)
            transformed_value = self.transform_value(raw_value)

            # Step 4: Normalize (this happens across all hubs of same tier,
            # so actual implementation may need batch normalization)
            normalized_score = self.normalize_value(transformed_value)

            # Step 5: Create result
            return ScoringResult(
                hub_id=hub_data.hub_id,
                criterion_name=self.get_criterion_name(),
                raw_value=raw_value,
                normalized_score=normalized_score,
                metadata=self.get_metadata(hub_data)
            )

        except Exception as e:
            logger.error(
                f"Error scoring hub {hub_data.hub_id} "
                f"on {self.get_criterion_name()}: {e}"
            )
            return self._create_invalid_result(hub_data.hub_id)

    @abstractmethod
    def extract_raw_value(self, hub_data: HubData) -> float:
        """
        Extract the raw value for this criterion from hub data.

        Subclasses must implement this.
        """
        pass

    @abstractmethod
    def get_criterion_name(self) -> str:
        """Return the name of this scoring criterion"""
        pass

    def validate_value(self, value: float) -> bool:
        """
        Validate the extracted value.

        Default: check for non-negative. Override if needed.
        """
        return value >= 0

    def transform_value(self, value: float) -> float:
        """
        Transform raw value before normalization.

        Default: no transformation. Override for log transforms, etc.
        """
        return value

    def normalize_value(self, value: float) -> float:
        """
        Normalize value to 1-10 range.

        Note: This is simplified. In practice, normalization happens
        across all hubs of the same tier.
        """
        # Placeholder - actual normalization needs all values
        return min(10.0, max(1.0, value))

    def get_metadata(self, hub_data: HubData) -> Dict[str, Any]:
        """
        Get additional metadata for the scoring result.

        Override to add criterion-specific metadata.
        """
        return {
            'hub_tier': hub_data.tier.value if hub_data.tier else None,
            'criterion': self.get_criterion_name()
        }

    def _create_invalid_result(self, hub_id: str) -> ScoringResult:
        """Create a result for invalid/failed scoring"""
        return ScoringResult(
            hub_id=hub_id,
            criterion_name=self.get_criterion_name(),
            raw_value=0.0,
            normalized_score=1.0,  # Minimum score
            metadata={'error': 'Invalid or missing data'}
        )
