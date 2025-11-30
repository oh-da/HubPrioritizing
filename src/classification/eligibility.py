"""
Hub Eligibility Filtering
==========================
Functions to determine which hub groups meet eligibility criteria.
"""

import geopandas as gpd
import pandas as pd
from typing import Set

from ..config import (
    ELIGIBILITY_MIN_PASSENGERS,
    ELIGIBILITY_MIN_MODES,
    MASS_TRANSIT_MODES,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


def count_mass_transit_modes(modes: list) -> int:
    """
    Count number of mass-transit modes in a list.

    Args:
        modes: List of mode names

    Returns:
        Number of mass-transit modes
    """
    if not isinstance(modes, list):
        modes = [modes]

    mass_transit_count = sum(1 for mode in modes if mode in MASS_TRANSIT_MODES)
    return mass_transit_count


def is_eligible_hub(
    total_demand: float,
    modes: list,
    min_passengers: float = ELIGIBILITY_MIN_PASSENGERS,
    min_modes: int = ELIGIBILITY_MIN_MODES,
) -> bool:
    """
    Check if a hub meets eligibility criteria.

    Eligibility requirements:
    1. Total daily demand >= min_passengers
    2. At least min_modes mass-transit modes

    Args:
        total_demand: Total daily passengers
        modes: List of transport modes
        min_passengers: Minimum passenger threshold
        min_modes: Minimum number of mass-transit modes

    Returns:
        True if hub is eligible
    """
    # Check passenger threshold
    if pd.isna(total_demand) or total_demand < min_passengers:
        return False

    # Check mode requirement
    n_mass_transit = count_mass_transit_modes(modes)
    if n_mass_transit < min_modes:
        return False

    return True


def filter_eligible_hubs(
    gdf: gpd.GeoDataFrame,
    demand_column: str = 'TotalDemand',
    modes_column: str = 'modes',
    min_passengers: float = ELIGIBILITY_MIN_PASSENGERS,
    min_modes: int = ELIGIBILITY_MIN_MODES,
) -> gpd.GeoDataFrame:
    """
    Filter hub groups to keep only those meeting eligibility criteria.

    Args:
        gdf: GeoDataFrame with hub groups
        demand_column: Column name for total demand
        modes_column: Column name for modes list
        min_passengers: Minimum passenger threshold
        min_modes: Minimum number of mass-transit modes

    Returns:
        Filtered GeoDataFrame with only eligible hubs
    """
    logger.info("Filtering hubs by eligibility criteria...")
    logger.info(f"  Min passengers: {min_passengers:,.0f}/day")
    logger.info(f"  Min mass-transit modes: {min_modes}")

    initial_count = len(gdf)

    # Check required columns
    if demand_column not in gdf.columns:
        logger.warning(f"Demand column '{demand_column}' not found, cannot filter by demand")
        demand_filter = pd.Series([True] * len(gdf), index=gdf.index)
    else:
        demand_filter = gdf[demand_column] >= min_passengers

    if modes_column not in gdf.columns:
        logger.warning(f"Modes column '{modes_column}' not found, cannot filter by modes")
        modes_filter = pd.Series([True] * len(gdf), index=gdf.index)
    else:
        gdf['_num_mass_transit_modes'] = gdf[modes_column].apply(count_mass_transit_modes)
        modes_filter = gdf['_num_mass_transit_modes'] >= min_modes
        gdf = gdf.drop(columns=['_num_mass_transit_modes'])

    # Combined filter
    eligible_filter = demand_filter & modes_filter

    filtered = gdf[eligible_filter].copy()

    # Log filtering results
    removed_count = initial_count - len(filtered)
    removed_pct = (removed_count / initial_count * 100) if initial_count > 0 else 0

    logger.info(f"✓ Filtered out {removed_count} ineligible hubs ({removed_pct:.1f}%)")
    logger.info(f"✓ Remaining eligible hubs: {len(filtered)}")

    # Break down filtering reasons
    demand_failed = (~demand_filter).sum()
    modes_failed = (~modes_filter).sum()

    logger.info("Filtering breakdown:")
    logger.info(f"  Failed passenger threshold: {demand_failed}")
    logger.info(f"  Failed mode requirement: {modes_failed}")
    logger.info(f"  Failed both: {(~demand_filter & ~modes_filter).sum()}")

    return filtered


def add_eligibility_flags(
    gdf: gpd.GeoDataFrame,
    demand_column: str = 'TotalDemand',
    modes_column: str = 'modes',
) -> gpd.GeoDataFrame:
    """
    Add eligibility flag columns without filtering.

    Adds columns:
    - eligible: Boolean indicating if hub meets all criteria
    - eligible_demand: Boolean for demand criterion
    - eligible_modes: Boolean for mode criterion
    - num_mass_transit_modes: Count of mass-transit modes

    Args:
        gdf: GeoDataFrame with hub groups
        demand_column: Column name for total demand
        modes_column: Column name for modes list

    Returns:
        GeoDataFrame with added eligibility columns
    """
    logger.info("Adding eligibility flag columns...")

    gdf_copy = gdf.copy()

    # Count mass-transit modes
    if modes_column in gdf_copy.columns:
        gdf_copy['num_mass_transit_modes'] = gdf_copy[modes_column].apply(count_mass_transit_modes)
        gdf_copy['eligible_modes'] = gdf_copy['num_mass_transit_modes'] >= ELIGIBILITY_MIN_MODES
    else:
        gdf_copy['num_mass_transit_modes'] = 0
        gdf_copy['eligible_modes'] = False

    # Check demand threshold
    if demand_column in gdf_copy.columns:
        gdf_copy['eligible_demand'] = gdf_copy[demand_column] >= ELIGIBILITY_MIN_PASSENGERS
    else:
        gdf_copy['eligible_demand'] = False

    # Overall eligibility
    gdf_copy['eligible'] = gdf_copy['eligible_demand'] & gdf_copy['eligible_modes']

    n_eligible = gdf_copy['eligible'].sum()
    logger.info(f"✓ {n_eligible} hubs are eligible ({n_eligible/len(gdf_copy)*100:.1f}%)")

    return gdf_copy


def get_eligibility_summary(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Generate summary statistics for hub eligibility.

    Args:
        gdf: GeoDataFrame with eligibility flags

    Returns:
        DataFrame with summary statistics
    """
    if 'eligible' not in gdf.columns:
        logger.warning("No eligibility flags found, run add_eligibility_flags first")
        return pd.DataFrame()

    summary = pd.DataFrame({
        'Criterion': [
            'Total Hubs',
            'Eligible (All Criteria)',
            'Eligible (Demand)',
            'Eligible (Modes)',
            'Ineligible'
        ],
        'Count': [
            len(gdf),
            gdf['eligible'].sum() if 'eligible' in gdf.columns else 0,
            gdf['eligible_demand'].sum() if 'eligible_demand' in gdf.columns else 0,
            gdf['eligible_modes'].sum() if 'eligible_modes' in gdf.columns else 0,
            (~gdf['eligible']).sum() if 'eligible' in gdf.columns else len(gdf)
        ]
    })

    summary['Percentage'] = (summary['Count'] / len(gdf) * 100).round(1)

    return summary
