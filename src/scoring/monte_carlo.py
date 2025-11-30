"""
Monte Carlo Weighted Scoring
==============================
Aggregates multiple scoring criteria using Monte Carlo simulation with random weights.

This approach prevents any single criterion from dominating the final score.
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from typing import List, Dict, Optional

from ..config import (
    MONTE_CARLO_ITERATIONS,
    MONTE_CARLO_RANDOM_SEED,
    MAX_CRITERION_WEIGHT,
    MIN_CRITERION_WEIGHT,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


def generate_random_weights(
    n_criteria: int,
    max_weight: float = MAX_CRITERION_WEIGHT,
    min_weight: float = MIN_CRITERION_WEIGHT,
    random_state: Optional[np.random.RandomState] = None,
) -> np.ndarray:
    """
    Generate random weights for criteria.

    Weights are uniformly distributed between min_weight and max_weight,
    then normalized to sum to 1.

    Args:
        n_criteria: Number of criteria
        max_weight: Maximum weight for any criterion
        min_weight: Minimum weight for any criterion
        random_state: Random state for reproducibility

    Returns:
        Array of normalized weights
    """
    if random_state is None:
        random_state = np.random.RandomState()

    # Generate random weights in range [min_weight, max_weight]
    weights = random_state.uniform(min_weight, max_weight, size=n_criteria)

    # Normalize to sum to 1
    weights = weights / weights.sum()

    return weights


def monte_carlo_scoring(
    score_matrix: pd.DataFrame,
    n_iterations: int = MONTE_CARLO_ITERATIONS,
    random_seed: int = MONTE_CARLO_RANDOM_SEED,
) -> pd.Series:
    """
    Calculate final scores using Monte Carlo simulation.

    Process:
    1. For each iteration:
       - Generate random weights (each criterion can be 0-50%)
       - Calculate weighted score for each hub
    2. Average scores across all iterations

    Args:
        score_matrix: DataFrame with hubs as rows, criteria as columns
        n_iterations: Number of Monte Carlo iterations
        random_seed: Random seed for reproducibility

    Returns:
        Series of final aggregated scores
    """
    logger.info(f"Running Monte Carlo simulation with {n_iterations:,} iterations...")

    n_hubs = len(score_matrix)
    n_criteria = len(score_matrix.columns)

    logger.info(f"  {n_hubs} hubs × {n_criteria} criteria")
    logger.info(f"  Criteria: {list(score_matrix.columns)}")

    # Initialize random state
    rng = np.random.RandomState(random_seed)

    # Store scores for each iteration
    iteration_scores = np.zeros((n_hubs, n_iterations))

    # Convert score matrix to numpy array for faster computation
    scores_array = score_matrix.values

    # Run Monte Carlo iterations
    for i in range(n_iterations):
        # Generate random weights
        weights = generate_random_weights(n_criteria, random_state=rng)

        # Calculate weighted scores for all hubs
        weighted_scores = scores_array @ weights  # Matrix multiplication

        # Store scores
        iteration_scores[:, i] = weighted_scores

        # Progress reporting
        if (i + 1) % 1000 == 0:
            logger.debug(f"  Completed {i + 1:,}/{n_iterations:,} iterations")

    # Calculate mean score across iterations
    final_scores = iteration_scores.mean(axis=1)

    # Create Series with original index
    final_scores_series = pd.Series(final_scores, index=score_matrix.index)

    # Log statistics
    logger.info(f"✓ Monte Carlo simulation complete")
    logger.info(f"  Final scores - Mean: {final_scores.mean():.2f}, Median: {np.median(final_scores):.2f}")
    logger.info(f"  Min: {final_scores.min():.2f}, Max: {final_scores.max():.2f}")
    logger.info(f"  Std Dev: {final_scores.std():.2f}")

    return final_scores_series


def calculate_all_scores(
    gdf: gpd.GeoDataFrame,
    tier_column: str = 'tier',
) -> gpd.GeoDataFrame:
    """
    Calculate all 5 scoring criteria for hubs.

    This is a convenience function that calls all scoring functions.

    Args:
        gdf: GeoDataFrame with hubs
        tier_column: Column with tier classification

    Returns:
        GeoDataFrame with all score columns added
    """
    logger.info("Calculating all scoring criteria...")

    from .activity import calculate_activity_score
    from .service import calculate_service_score
    from .location import calculate_location_score
    from .demographics import calculate_pop_jobs_score
    from .terminals import calculate_terminal_score

    gdf_scored = gdf.copy()

    # 1. Passenger Activity Score
    logger.info("\n1/5: Passenger Activity Score")
    gdf_scored['activity_score'] = calculate_activity_score(gdf_scored, tier_column=tier_column)

    # 2. Service & Hierarchy of Modes Score
    logger.info("\n2/5: Service & Hierarchy of Modes Score")
    gdf_scored['service_score'] = calculate_service_score(gdf_scored, tier_column=tier_column)

    # 3. Location Score
    logger.info("\n3/5: Location Score")
    gdf_scored['location_score'] = calculate_location_score(gdf_scored)

    # 4. Population & Jobs Score
    logger.info("\n4/5: Population & Jobs Score")
    gdf_scored['pop_jobs_score'] = calculate_pop_jobs_score(gdf_scored, tier_column=tier_column)

    # 5. Bus Terminal Proximity Score
    logger.info("\n5/5: Bus Terminal Proximity Score")
    gdf_scored['terminal_score'] = calculate_terminal_score(gdf_scored)

    logger.info("\n✓ All scoring criteria calculated")

    return gdf_scored


def calculate_final_scores(
    gdf: gpd.GeoDataFrame,
    score_columns: Optional[List[str]] = None,
    n_iterations: int = MONTE_CARLO_ITERATIONS,
    random_seed: int = MONTE_CARLO_RANDOM_SEED,
) -> gpd.GeoDataFrame:
    """
    Calculate final aggregated scores using Monte Carlo simulation.

    Args:
        gdf: GeoDataFrame with individual score columns
        score_columns: List of score column names (if None, uses defaults)
        n_iterations: Number of Monte Carlo iterations
        random_seed: Random seed

    Returns:
        GeoDataFrame with final_score column added
    """
    if score_columns is None:
        score_columns = [
            'activity_score',
            'service_score',
            'location_score',
            'pop_jobs_score',
            'terminal_score'
        ]

    # Check that all score columns exist
    missing_cols = [col for col in score_columns if col not in gdf.columns]
    if missing_cols:
        raise ValueError(f"Missing score columns: {missing_cols}")

    # Extract score matrix
    score_matrix = gdf[score_columns]

    # Run Monte Carlo simulation
    final_scores = monte_carlo_scoring(
        score_matrix,
        n_iterations=n_iterations,
        random_seed=random_seed
    )

    # Add to GeoDataFrame
    gdf_final = gdf.copy()
    gdf_final['final_score'] = final_scores

    # Add ranking
    gdf_final['rank'] = gdf_final['final_score'].rank(ascending=False, method='min')

    return gdf_final


def get_score_summary(gdf: gpd.GeoDataFrame, tier_column: str = 'tier') -> pd.DataFrame:
    """
    Generate summary statistics for all scores.

    Args:
        gdf: GeoDataFrame with scores
        tier_column: Column with tier classification

    Returns:
        DataFrame with summary statistics
    """
    score_columns = [col for col in gdf.columns if col.endswith('_score')]

    if not score_columns:
        logger.warning("No score columns found")
        return pd.DataFrame()

    summary_data = []

    # Overall statistics
    for col in score_columns:
        summary_data.append({
            'Score': col.replace('_score', '').title(),
            'Tier': 'All',
            'Mean': gdf[col].mean(),
            'Median': gdf[col].median(),
            'Std': gdf[col].std(),
            'Min': gdf[col].min(),
            'Max': gdf[col].max()
        })

    # Per-tier statistics
    if tier_column in gdf.columns:
        for tier in gdf[tier_column].unique():
            tier_data = gdf[gdf[tier_column] == tier]
            for col in score_columns:
                summary_data.append({
                    'Score': col.replace('_score', '').title(),
                    'Tier': tier,
                    'Mean': tier_data[col].mean(),
                    'Median': tier_data[col].median(),
                    'Std': tier_data[col].std(),
                    'Min': tier_data[col].min(),
                    'Max': tier_data[col].max()
                })

    summary_df = pd.DataFrame(summary_data)

    return summary_df


def run_complete_scoring_pipeline(
    gdf: gpd.GeoDataFrame,
    tier_column: str = 'tier',
) -> gpd.GeoDataFrame:
    """
    Run the complete scoring pipeline: calculate all criteria + Monte Carlo aggregation.

    Args:
        gdf: GeoDataFrame with hubs (must have tier column)
        tier_column: Column with tier classification

    Returns:
        GeoDataFrame with all scores and final ranking
    """
    logger.info("="*80)
    logger.info("SCORING PIPELINE")
    logger.info("="*80)

    # Calculate all individual scores
    gdf_scored = calculate_all_scores(gdf, tier_column=tier_column)

    # Calculate final aggregated scores
    logger.info("\nCalculating final aggregated scores...")
    gdf_final = calculate_final_scores(gdf_scored)

    # Log summary
    logger.info("\n" + "="*80)
    logger.info("SCORING COMPLETE")
    logger.info("="*80)
    logger.info(f"\n{len(gdf_final)} hubs scored and ranked")

    # Top 10 hubs
    top_10 = gdf_final.nlargest(10, 'final_score')
    logger.info("\nTop 10 Hubs by Final Score:")
    for i, (idx, row) in enumerate(top_10.iterrows(), 1):
        hub_id = row.get('group', idx)
        score = row['final_score']
        tier = row.get(tier_column, 'Unknown')
        logger.info(f"  {i}. Hub {hub_id} ({tier}): {score:.2f}")

    return gdf_final
