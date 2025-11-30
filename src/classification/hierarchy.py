"""
Hub Hierarchy Classification
=============================
Functions to classify hubs into hierarchy tiers (ארצי, מטרופוליני, עירוני).
"""

import geopandas as gpd
import pandas as pd

from ..config import (
    TIER_NATIONAL,
    TIER_METRO,
    TIER_LOCAL,
    NATIONAL_HUB_MIN_PASSENGERS,
    METRO_HUB_MIN_PASSENGERS,
    get_tier_from_ridership,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


def classify_hub_tier(
    total_demand: float,
    tier_national: str = TIER_NATIONAL,
    tier_metro: str = TIER_METRO,
    tier_local: str = TIER_LOCAL,
) -> str:
    """
    Classify a single hub into hierarchy tier based on ridership.

    Tier classification:
    - National (ארצי): >= 50,000 passengers/day
    - Metropolitan (מטרופוליני): 5,000-50,000 passengers/day
    - Local (עירוני): < 5,000 passengers/day

    Args:
        total_demand: Total daily passengers
        tier_national: National tier label
        tier_metro: Metropolitan tier label
        tier_local: Local tier label

    Returns:
        Tier name (Hebrew)
    """
    return get_tier_from_ridership(total_demand)


def assign_hub_tiers(
    gdf: gpd.GeoDataFrame,
    demand_column: str = 'TotalDemand',
    tier_column: str = 'tier',
) -> gpd.GeoDataFrame:
    """
    Assign hierarchy tiers to all hubs.

    Args:
        gdf: GeoDataFrame with hub groups
        demand_column: Column name for total demand
        tier_column: Column name for tier assignment

    Returns:
        GeoDataFrame with added tier column
    """
    logger.info("Assigning hub hierarchy tiers...")

    gdf_copy = gdf.copy()

    if demand_column not in gdf_copy.columns:
        logger.warning(f"Demand column '{demand_column}' not found, using default tier")
        gdf_copy[tier_column] = TIER_LOCAL
        return gdf_copy

    # Classify each hub
    gdf_copy[tier_column] = gdf_copy[demand_column].apply(classify_hub_tier)

    # Log tier distribution
    tier_counts = gdf_copy[tier_column].value_counts()

    logger.info("Hub tier distribution:")
    for tier, count in tier_counts.items():
        logger.info(f"  {tier}: {count} hubs")

    # Calculate total demand by tier
    if demand_column in gdf_copy.columns:
        tier_demand = gdf_copy.groupby(tier_column)[demand_column].sum()
        logger.info("Total demand by tier:")
        for tier, demand in tier_demand.items():
            logger.info(f"  {tier}: {demand:,.0f} passengers/day")

    return gdf_copy


def get_tier_statistics(
    gdf: gpd.GeoDataFrame,
    tier_column: str = 'tier',
    demand_column: str = 'TotalDemand',
) -> pd.DataFrame:
    """
    Generate detailed statistics for each tier.

    Args:
        gdf: GeoDataFrame with tier assignments
        tier_column: Column name for tier
        demand_column: Column name for demand

    Returns:
        DataFrame with tier statistics
    """
    if tier_column not in gdf.columns:
        logger.warning(f"Tier column '{tier_column}' not found")
        return pd.DataFrame()

    stats_list = []

    for tier in [TIER_NATIONAL, TIER_METRO, TIER_LOCAL]:
        tier_hubs = gdf[gdf[tier_column] == tier]
        n_hubs = len(tier_hubs)

        if n_hubs == 0:
            continue

        stats = {
            'Tier': tier,
            'Count': n_hubs,
            'Percentage': n_hubs / len(gdf) * 100
        }

        if demand_column in gdf.columns:
            stats['Total Demand'] = tier_hubs[demand_column].sum()
            stats['Avg Demand'] = tier_hubs[demand_column].mean()
            stats['Min Demand'] = tier_hubs[demand_column].min()
            stats['Max Demand'] = tier_hubs[demand_column].max()

        if 'num_modes' in gdf.columns:
            stats['Avg Modes'] = tier_hubs['num_modes'].mean()

        if 'Line_Nunique' in gdf.columns:
            stats['Avg Lines'] = tier_hubs['Line_Nunique'].mean()

        stats_list.append(stats)

    stats_df = pd.DataFrame(stats_list)

    return stats_df


def filter_by_tier(
    gdf: gpd.GeoDataFrame,
    tier: str,
    tier_column: str = 'tier',
) -> gpd.GeoDataFrame:
    """
    Filter hubs by tier.

    Args:
        gdf: GeoDataFrame with tier assignments
        tier: Tier to filter (ארצי, מטרופוליני, or עירוני)
        tier_column: Column name for tier

    Returns:
        Filtered GeoDataFrame
    """
    if tier_column not in gdf.columns:
        logger.warning(f"Tier column '{tier_column}' not found")
        return gdf

    filtered = gdf[gdf[tier_column] == tier].copy()

    logger.info(f"Filtered to {len(filtered)} {tier} hubs")

    return filtered


def add_tier_metadata(
    gdf: gpd.GeoDataFrame,
    tier_column: str = 'tier',
) -> gpd.GeoDataFrame:
    """
    Add tier metadata columns (English name, numeric code, etc.).

    Args:
        gdf: GeoDataFrame with tier assignments
        tier_column: Column name for tier

    Returns:
        GeoDataFrame with added metadata columns
    """
    logger.debug("Adding tier metadata...")

    gdf_copy = gdf.copy()

    # Tier name mappings
    tier_english = {
        TIER_NATIONAL: 'National',
        TIER_METRO: 'Metropolitan',
        TIER_LOCAL: 'Local'
    }

    tier_numeric = {
        TIER_NATIONAL: 3,
        TIER_METRO: 2,
        TIER_LOCAL: 1
    }

    if tier_column in gdf_copy.columns:
        gdf_copy['tier_english'] = gdf_copy[tier_column].map(tier_english)
        gdf_copy['tier_numeric'] = gdf_copy[tier_column].map(tier_numeric)

    logger.debug("✓ Tier metadata added")

    return gdf_copy
