"""
Passenger Activity Scoring
===========================
Score hubs based on 2050 forecasted passenger demand.

Uses log10 transformation to prevent extreme skew from mega-stations.

NORMALIZATION: Per TIER only (not per metro area)
- All National (ארצי) hubs normalized together
- All Metropolitan (מטרופוליני) hubs normalized together (regardless of area)
- All Local (עירוני) hubs normalized together (regardless of area)
"""

import geopandas as gpd
import pandas as pd

from ..config import ACTIVITY_SCORE_USE_LOG
from .normalization import normalize_log10_by_tier, normalize_by_tier
from ..utils.logging import get_logger

logger = get_logger(__name__)


def calculate_activity_score(
    gdf: gpd.GeoDataFrame,
    demand_column: str = 'TotalDemand',
    tier_column: str = 'tier',
    use_log: bool = ACTIVITY_SCORE_USE_LOG,
) -> pd.Series:
    """
    Calculate passenger activity score.

    Methodology:
    1. Use 2050 passenger forecast (boardings + alightings)
    2. Apply log10 transformation (optional but recommended)
       - Prevents mega-stations from dominating (100k shouldn't score 10x higher than 10k)
       - log10(100,000) / log10(10,000) = 5/4 = 1.25x instead of 10x
    3. Normalize separately per tier (1-10 scale)

    Args:
        gdf: GeoDataFrame with hubs
        demand_column: Column with total daily demand
        tier_column: Column with tier classification
        use_log: Whether to apply log10 transformation

    Returns:
        Series of activity scores (1-10)
    """
    logger.info("Calculating passenger activity scores...")

    if demand_column not in gdf.columns:
        logger.warning(f"Demand column '{demand_column}' not found")
        return pd.Series([5.0] * len(gdf), index=gdf.index)

    if tier_column not in gdf.columns:
        logger.warning(f"Tier column '{tier_column}' not found, normalizing globally")
        if use_log:
            scores = normalize_log10_by_tier(
                gdf,
                value_column=demand_column,
                tier_column='_dummy_tier'
            )
        else:
            scores = normalize_by_tier(
                gdf,
                value_column=demand_column,
                tier_column='_dummy_tier'
            )
    else:
        # Normalize by tier with optional log transformation
        if use_log:
            scores = normalize_log10_by_tier(
                gdf,
                value_column=demand_column,
                tier_column=tier_column
            )
        else:
            scores = normalize_by_tier(
                gdf,
                value_column=demand_column,
                tier_column=tier_column
            )

    # Log statistics
    logger.info(f"✓ Activity scores calculated for {len(scores)} hubs")
    logger.info(f"  Mean: {scores.mean():.2f}, Median: {scores.median():.2f}")
    logger.info(f"  Min: {scores.min():.2f}, Max: {scores.max():.2f}")

    # Log statistics by tier
    if tier_column in gdf.columns:
        for tier in gdf[tier_column].unique():
            tier_scores = scores[gdf[tier_column] == tier]
            logger.info(f"  {tier}: mean={tier_scores.mean():.2f}, n={len(tier_scores)}")

    return scores
