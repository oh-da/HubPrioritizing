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
    REQUIRE_NON_RAIL_MODE,
    RAIL_ONLY_MODES,
    NON_RAIL_TRANSIT_MODES,
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


def has_non_rail_transit_mode(modes: list) -> bool:
    """
    Check if the modes list contains at least one non-rail transit mode.

    Non-rail transit modes include Metro, LRT, and BRT - these are urban
    transit modes that indicate true multimodal integration beyond just
    rail-to-rail transfers.

    Args:
        modes: List of mode names

    Returns:
        True if at least one non-rail transit mode is present
    """
    if not isinstance(modes, list):
        modes = [modes] if pd.notna(modes) else []

    return any(mode in NON_RAIL_TRANSIT_MODES for mode in modes)


def is_rail_only_hub(modes: list) -> bool:
    """
    Check if the hub has only rail modes (no Metro, LRT, or BRT).

    A rail-only hub has combinations of Suburban Rail, Interurban Rail,
    HighSpeed Rail, or generic Rail, but lacks urban transit integration
    via Metro, LRT, or BRT.

    Args:
        modes: List of mode names

    Returns:
        True if hub has only rail modes (no non-rail transit)
    """
    if not isinstance(modes, list):
        modes = [modes] if pd.notna(modes) else []

    # Get mass-transit modes only
    mass_transit = [m for m in modes if m in MASS_TRANSIT_MODES]

    if not mass_transit:
        return False  # No mass-transit modes at all

    # Check if all mass-transit modes are rail-only
    return all(mode in RAIL_ONLY_MODES for mode in mass_transit)


def is_eligible_hub(
    total_demand: float,
    modes: list,
    min_passengers: float = ELIGIBILITY_MIN_PASSENGERS,
    min_modes: int = ELIGIBILITY_MIN_MODES,
    require_non_rail: bool = REQUIRE_NON_RAIL_MODE,
) -> bool:
    """
    Check if a hub meets eligibility criteria.

    Eligibility requirements:
    1. Total daily demand >= min_passengers
    2. At least min_modes mass-transit modes
    3. (Optional) At least one non-rail transit mode (Metro, LRT, BRT)

    Args:
        total_demand: Total daily passengers
        modes: List of transport modes
        min_passengers: Minimum passenger threshold
        min_modes: Minimum number of mass-transit modes
        require_non_rail: If True, hub must have at least one non-rail
                          transit mode (Metro, LRT, BRT). Rail-only hubs
                          (Suburban/Interurban/HighSpeed Rail combinations)
                          will be excluded. Default: REQUIRE_NON_RAIL_MODE from config.

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

    # Optional: Check for non-rail transit mode requirement
    if require_non_rail and is_rail_only_hub(modes):
        return False

    return True


def filter_eligible_hubs(
    gdf: gpd.GeoDataFrame,
    demand_column: str = 'TotalDemand',
    modes_column: str = 'modes',
    min_passengers: float = ELIGIBILITY_MIN_PASSENGERS,
    min_modes: int = ELIGIBILITY_MIN_MODES,
    require_non_rail: bool = REQUIRE_NON_RAIL_MODE,
) -> gpd.GeoDataFrame:
    """
    Filter hub groups to keep only those meeting eligibility criteria.

    Args:
        gdf: GeoDataFrame with hub groups
        demand_column: Column name for total demand
        modes_column: Column name for modes list
        min_passengers: Minimum passenger threshold
        min_modes: Minimum number of mass-transit modes
        require_non_rail: If True, exclude hubs that only have rail modes.
                          Hub must have at least one non-rail transit mode
                          (Metro, LRT, BRT). Default: REQUIRE_NON_RAIL_MODE from config.

    Returns:
        Filtered GeoDataFrame with only eligible hubs
    """
    logger.info("Filtering hubs by eligibility criteria...")
    logger.info(f"  Min passengers: {min_passengers:,.0f}/day")
    logger.info(f"  Min mass-transit modes: {min_modes}")
    logger.info(f"  Require non-rail mode: {require_non_rail}")

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
        non_rail_filter = pd.Series([True] * len(gdf), index=gdf.index)
    else:
        gdf['_num_mass_transit_modes'] = gdf[modes_column].apply(count_mass_transit_modes)
        modes_filter = gdf['_num_mass_transit_modes'] >= min_modes
        gdf = gdf.drop(columns=['_num_mass_transit_modes'])

        # Optional: Filter out rail-only hubs
        if require_non_rail:
            non_rail_filter = ~gdf[modes_column].apply(is_rail_only_hub)
        else:
            non_rail_filter = pd.Series([True] * len(gdf), index=gdf.index)

    # Combined filter
    eligible_filter = demand_filter & modes_filter & non_rail_filter

    filtered = gdf[eligible_filter].copy()

    # Log filtering results
    removed_count = initial_count - len(filtered)
    removed_pct = (removed_count / initial_count * 100) if initial_count > 0 else 0

    logger.info(f"✓ Filtered out {removed_count} ineligible hubs ({removed_pct:.1f}%)")
    logger.info(f"✓ Remaining eligible hubs: {len(filtered)}")

    # Break down filtering reasons
    demand_failed = (~demand_filter).sum()
    modes_failed = (~modes_filter).sum()
    rail_only_failed = (~non_rail_filter).sum() if require_non_rail else 0

    logger.info("Filtering breakdown:")
    logger.info(f"  Failed passenger threshold: {demand_failed}")
    logger.info(f"  Failed mode requirement: {modes_failed}")
    if require_non_rail:
        logger.info(f"  Failed non-rail requirement (rail-only): {rail_only_failed}")
    logger.info(f"  Failed multiple criteria: {(~eligible_filter & (demand_filter | modes_filter | non_rail_filter)).sum()}")

    return filtered


def add_eligibility_flags(
    gdf: gpd.GeoDataFrame,
    demand_column: str = 'TotalDemand',
    modes_column: str = 'modes',
    require_non_rail: bool = REQUIRE_NON_RAIL_MODE,
) -> gpd.GeoDataFrame:
    """
    Add eligibility flag columns without filtering.

    Adds columns:
    - eligible: Boolean indicating if hub meets all criteria
    - eligible_demand: Boolean for demand criterion
    - eligible_modes: Boolean for mode criterion
    - eligible_non_rail: Boolean for non-rail criterion (if require_non_rail is True)
    - is_rail_only: Boolean indicating if hub has only rail modes
    - num_mass_transit_modes: Count of mass-transit modes

    Args:
        gdf: GeoDataFrame with hub groups
        demand_column: Column name for total demand
        modes_column: Column name for modes list
        require_non_rail: If True, adds non-rail eligibility check

    Returns:
        GeoDataFrame with added eligibility columns
    """
    logger.info("Adding eligibility flag columns...")

    gdf_copy = gdf.copy()

    # Count mass-transit modes
    if modes_column in gdf_copy.columns:
        gdf_copy['num_mass_transit_modes'] = gdf_copy[modes_column].apply(count_mass_transit_modes)
        gdf_copy['eligible_modes'] = gdf_copy['num_mass_transit_modes'] >= ELIGIBILITY_MIN_MODES

        # Check for rail-only hubs
        gdf_copy['is_rail_only'] = gdf_copy[modes_column].apply(is_rail_only_hub)
        gdf_copy['has_non_rail_transit'] = gdf_copy[modes_column].apply(has_non_rail_transit_mode)
        gdf_copy['eligible_non_rail'] = ~gdf_copy['is_rail_only']
    else:
        gdf_copy['num_mass_transit_modes'] = 0
        gdf_copy['eligible_modes'] = False
        gdf_copy['is_rail_only'] = False
        gdf_copy['has_non_rail_transit'] = False
        gdf_copy['eligible_non_rail'] = True

    # Check demand threshold
    if demand_column in gdf_copy.columns:
        gdf_copy['eligible_demand'] = gdf_copy[demand_column] >= ELIGIBILITY_MIN_PASSENGERS
    else:
        gdf_copy['eligible_demand'] = False

    # Overall eligibility
    if require_non_rail:
        gdf_copy['eligible'] = (
            gdf_copy['eligible_demand'] &
            gdf_copy['eligible_modes'] &
            gdf_copy['eligible_non_rail']
        )
    else:
        gdf_copy['eligible'] = gdf_copy['eligible_demand'] & gdf_copy['eligible_modes']

    n_eligible = gdf_copy['eligible'].sum()
    n_rail_only = gdf_copy['is_rail_only'].sum()
    logger.info(f"✓ {n_eligible} hubs are eligible ({n_eligible/len(gdf_copy)*100:.1f}%)")
    logger.info(f"  Rail-only hubs: {n_rail_only}")
    if require_non_rail:
        logger.info(f"  (Rail-only hubs excluded from eligibility)")

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

    criteria = [
        'Total Hubs',
        'Eligible (All Criteria)',
        'Eligible (Demand)',
        'Eligible (Modes)',
    ]
    counts = [
        len(gdf),
        gdf['eligible'].sum() if 'eligible' in gdf.columns else 0,
        gdf['eligible_demand'].sum() if 'eligible_demand' in gdf.columns else 0,
        gdf['eligible_modes'].sum() if 'eligible_modes' in gdf.columns else 0,
    ]

    # Add non-rail statistics if available
    if 'eligible_non_rail' in gdf.columns:
        criteria.append('Eligible (Non-Rail)')
        counts.append(gdf['eligible_non_rail'].sum())

    if 'is_rail_only' in gdf.columns:
        criteria.append('Rail-Only Hubs')
        counts.append(gdf['is_rail_only'].sum())

    if 'has_non_rail_transit' in gdf.columns:
        criteria.append('Has Non-Rail Transit')
        counts.append(gdf['has_non_rail_transit'].sum())

    criteria.append('Ineligible')
    counts.append((~gdf['eligible']).sum() if 'eligible' in gdf.columns else len(gdf))

    summary = pd.DataFrame({
        'Criterion': criteria,
        'Count': counts
    })

    summary['Percentage'] = (summary['Count'] / len(gdf) * 100).round(1)

    return summary
