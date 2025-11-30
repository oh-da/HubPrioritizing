"""
Location Score (Geographic & Metropolitan)
===========================================
Score hubs based on strategic location importance.

Two-dimensional scoring:
1. National Region: Periphery prioritization (equity)
2. Metropolitan Position: Core prioritization (efficiency)
"""

import geopandas as gpd
import pandas as pd

from ..config import REGION_WEIGHTS, METRO_POSITION_WEIGHTS
from .normalization import normalize_minmax
from ..utils.logging import get_logger

logger = get_logger(__name__)


def get_region_weight(region: str) -> float:
    """
    Get regional weight for scoring.

    Center/Tel Aviv = 0 (lower priority for equity)
    Periphery = 1 (higher priority for equity)

    Args:
        region: Region name

    Returns:
        Region weight
    """
    if pd.isna(region):
        return 0.5  # Default

    region_clean = str(region).strip()

    for key, weight in REGION_WEIGHTS.items():
        if key.lower() in region_clean.lower():
            return weight

    return 0.5  # Default if not found


def get_metro_position_weight(position: str) -> float:
    """
    Get metropolitan position weight.

    Core = 3
    First Ring = 2
    Outer = 1

    Args:
        position: Metropolitan position

    Returns:
        Position weight
    """
    if pd.isna(position):
        return 1.5  # Default

    position_clean = str(position).strip()

    for key, weight in METRO_POSITION_WEIGHTS.items():
        if key.lower() in position_clean.lower():
            return weight

    return 1.5  # Default


def calculate_location_score(
    gdf: gpd.GeoDataFrame,
    region_column: str = 'region',
    metro_position_column: str = 'metro_position',
) -> pd.Series:
    """
    Calculate location score based on region and metropolitan position.

    Formula:
        location_score = region_weight × metro_position_weight
    Then normalized to 1-10 scale.

    Args:
        gdf: GeoDataFrame with hubs
        region_column: Column with region name
        metro_position_column: Column with metro position

    Returns:
        Series of location scores (1-10)
    """
    logger.info("Calculating location scores...")

    # Get region weights
    if region_column in gdf.columns:
        region_weights = gdf[region_column].apply(get_region_weight)
    else:
        logger.warning(f"Region column '{region_column}' not found, using default")
        region_weights = pd.Series([0.5] * len(gdf), index=gdf.index)

    # Get metro position weights
    if metro_position_column in gdf.columns:
        metro_weights = gdf[metro_position_column].apply(get_metro_position_weight)
    else:
        logger.warning(f"Metro position column '{metro_position_column}' not found, using default")
        metro_weights = pd.Series([1.5] * len(gdf), index=gdf.index)

    # Calculate combined score
    raw_scores = region_weights * metro_weights

    # Normalize to 1-10
    normalized_scores = normalize_minmax(raw_scores)

    # Log statistics
    logger.info(f"✓ Location scores calculated for {len(normalized_scores)} hubs")
    logger.info(f"  Mean: {normalized_scores.mean():.2f}, Median: {normalized_scores.median():.2f}")

    # Log distribution by region
    if region_column in gdf.columns:
        for region in gdf[region_column].unique():
            if pd.isna(region):
                continue
            region_scores = normalized_scores[gdf[region_column] == region]
            logger.info(f"  {region}: mean={region_scores.mean():.2f}, n={len(region_scores)}")

    return normalized_scores
