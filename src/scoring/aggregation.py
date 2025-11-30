"""
Score aggregation implementations.

Demonstrates:
- Strategy Pattern: Different aggregation strategies
- Dependency Inversion: Depends on IScorer abstraction
"""

import logging
import random
from typing import List, Dict, Optional

from ..interfaces import IAggregator, ScoringResult, IMonteCarloSimulator, HubData, IScorer

logger = logging.getLogger(__name__)


class WeightedAggregator(IAggregator):
    """
    Aggregates scores using weighted average.

    Single Responsibility: Only performs weighted aggregation.
    """

    def aggregate(self,
                  scores: List[ScoringResult],
                  weights: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate weighted average of scores.

        Args:
            scores: List of scoring results
            weights: Dict mapping criterion names to weights (0-1)
                    If None, uses equal weights

        Returns:
            Aggregated score
        """
        if not scores:
            return 1.0  # Minimum score

        # Default to equal weights
        if weights is None:
            weights = {score.criterion_name: 1.0 for score in scores}

        # Calculate weighted sum
        weighted_sum = 0.0
        total_weight = 0.0

        for score in scores:
            weight = weights.get(score.criterion_name, 0.0)
            weighted_sum += score.normalized_score * weight
            total_weight += weight

        # Avoid division by zero
        if total_weight == 0:
            return 1.0

        return weighted_sum / total_weight


class MonteCarloAggregator(IMonteCarloSimulator):
    """
    Monte Carlo simulation for robust score aggregation.

    Runs multiple iterations with random weight sets to avoid
    any single criterion dominating the final score.
    """

    def __init__(self,
                 aggregator: IAggregator,
                 random_seed: Optional[int] = None):
        """
        Initialize with aggregation strategy.

        Dependency Injection: Uses IAggregator for actual aggregation.
        """
        self.aggregator = aggregator
        if random_seed is not None:
            random.seed(random_seed)

    def simulate(self,
                 hubs: List[HubData],
                 scorers: List[IScorer],
                 iterations: int = 10000,
                 max_weight: float = 0.5) -> Dict[str, float]:
        """
        Run Monte Carlo simulation to get robust final scores.

        Process:
        1. For each iteration:
           - Generate random weights (0 to max_weight) for each criterion
           - Score all hubs with these weights
           - Record scores
        2. Average scores across all iterations

        Args:
            hubs: List of hubs to score
            scorers: List of scorer implementations
            iterations: Number of simulation iterations
            max_weight: Maximum weight for any single criterion (0-1)

        Returns:
            Dict mapping hub_id to final averaged score
        """
        logger.info(
            f"Running Monte Carlo simulation: {iterations} iterations, "
            f"{len(hubs)} hubs, {len(scorers)} criteria"
        )

        # Initialize score accumulators
        hub_score_sums = {hub.hub_id: 0.0 for hub in hubs}

        # Run iterations
        for iteration in range(iterations):
            if (iteration + 1) % 1000 == 0:
                logger.debug(f"Iteration {iteration + 1}/{iterations}")

            # Generate random weights for this iteration
            weights = self._generate_random_weights(scorers, max_weight)

            # Score all hubs with these weights
            for hub in hubs:
                scores = [scorer.calculate_score(hub) for scorer in scorers]
                aggregated_score = self.aggregator.aggregate(scores, weights)
                hub_score_sums[hub.hub_id] += aggregated_score

        # Calculate averages
        final_scores = {
            hub_id: score_sum / iterations
            for hub_id, score_sum in hub_score_sums.items()
        }

        logger.info("Monte Carlo simulation completed")
        return final_scores

    def _generate_random_weights(self,
                                 scorers: List[IScorer],
                                 max_weight: float) -> Dict[str, float]:
        """
        Generate random weights for criteria.

        Each weight is uniform random in [0, max_weight].
        Weights are NOT normalized to sum to 1 (this adds randomness).
        """
        weights = {}
        for scorer in scorers:
            criterion_name = scorer.get_criterion_name()
            weights[criterion_name] = random.uniform(0, max_weight)

        return weights


class RankAggregator(IAggregator):
    """
    Aggregates based on ranks rather than raw scores.

    Useful when score scales differ significantly between criteria.
    """

    def aggregate(self,
                  scores: List[ScoringResult],
                  weights: Optional[Dict[str, float]] = None) -> float:
        """
        Aggregate using rank-based method.

        Note: This simplified version just averages scores.
        In production with multiple hubs, it would:
        1. Rank hubs for each criterion
        2. Calculate weighted average of ranks
        3. Convert back to score
        """
        if not scores:
            return 1.0

        # Simplified: just average the normalized scores
        # In practice, this would operate across all hubs
        return sum(s.normalized_score for s in scores) / len(scores)
