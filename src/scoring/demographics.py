"""
Population & Jobs Score (2050)
===============================
Score hubs based on catchment area population and employment.

Uses concentric rings with distance decay and different pop/job mixes by tier.
"""

import geopandas as gpd
import pandas as pd

from ..config import (
    CATCHMENT_RINGS,
    RING_WEIGHTS,
    POP_JOB_MIX,
    TIER_NATIONAL,
    TIER_METRO,
    TIER_LOCAL,
)
from .normalization import normalize_by_tier
from ..utils.logging import get_logger

logger = get_logger(__name__)


def calculate_weighted_pop_jobs(
    pop_values: list,
    job_values: list,
    tier: str,
    ring_weights: dict = RING_WEIGHTS,
    pop_job_mix: dict = POP_JOB_MIX,
) -> float:
    """
    Calculate weighted population and jobs score.

    Args:
        pop_values: List of population values for each ring
        job_values: List of employment values for each ring
        tier: Hub tier (determines pop/job mix)
        ring_weights: Distance decay weights for rings
        pop_job_mix: Population vs employment mix by tier

    Returns:
        Weighted score
    """
    if tier not in pop_job_mix:
        tier = TIER_METRO  # Default

    job_weight = pop_job_mix[tier]['jobs']
    pop_weight = pop_job_mix[tier]['population']

    total_score = 0.0

    for i, (pop, jobs) in enumerate(zip(pop_values, job_values)):
        ring_weight = ring_weights.get(i, 0.0)
        ring_score = (pop * pop_weight + jobs * job_weight) * ring_weight
        total_score += ring_score

    return total_score


def calculate_pop_jobs_score(
    gdf: gpd.GeoDataFrame,
    tier_column: str = 'tier',
    pop_zone_columns: list = ['pop_zone1', 'pop_zone2', 'pop_zone3'],
    emp_zone_columns: list = ['emp_zone1', 'emp_zone2', 'emp_zone3'],
) -> pd.Series:
    """
    Calculate population & jobs score for all hubs.

    Methodology:
    1. For each ring, calculate: (pop × pop_weight + jobs × job_weight) × distance_weight
    2. Sum across all rings
    3. Normalize to 1-10 scale per tier

    Args:
        gdf: GeoDataFrame with hubs
        tier_column: Column with tier classification
        pop_zone_columns: Columns with population by zone
        emp_zone_columns: Columns with employment by zone

    Returns:
        Series of pop/jobs scores (1-10)
    """
    logger.info("Calculating population & jobs scores...")

    # Check if demographic columns exist
    has_pop = all(col in gdf.columns for col in pop_zone_columns)
    has_emp = all(col in gdf.columns for col in emp_zone_columns)

    if not has_pop or not has_emp:
        logger.warning("Demographic zone columns not found, using defaults")
        return pd.Series([5.0] * len(gdf), index=gdf.index)

    # Calculate raw scores
    raw_scores = []

    for idx, row in gdf.iterrows():
        pop_values = [row.get(col, 0) for col in pop_zone_columns]
        job_values = [row.get(col, 0) for col in emp_zone_columns]

        tier = row.get(tier_column, TIER_METRO)

        score = calculate_weighted_pop_jobs(pop_values, job_values, tier)
        raw_scores.append(score)

    raw_scores_series = pd.Series(raw_scores, index=gdf.index)

    # Normalize by tier
    if tier_column in gdf.columns:
        normalized_scores = normalize_by_tier(
            gdf.assign(_raw_score=raw_scores_series),
            value_column='_raw_score',
            tier_column=tier_column
        )
    else:
        from .normalization import normalize_minmax
        normalized_scores = normalize_minmax(raw_scores_series)

    # Log statistics
    logger.info(f"✓ Pop/jobs scores calculated for {len(normalized_scores)} hubs")
    logger.info(f"  Mean: {normalized_scores.mean():.2f}, Median: {normalized_scores.median():.2f}")

    return normalized_scores
