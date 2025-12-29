"""
Bus Terminal Proximity Score
=============================
Score hubs based on proximity to bus terminals and terminal importance.

NORMALIZATION: GLOBAL (not per tier)
- All hubs normalized together across all tiers
- This ensures consistent terminal integration signals across the entire dataset
"""

import geopandas as gpd
import pandas as pd

from ..config import TERMINAL_PROXIMITY_DISTANCE_M, TERMINAL_WEIGHTS
from .normalization import normalize_minmax
from ..utils.logging import get_logger

logger = get_logger(__name__)


def get_terminal_weight(terminal_type: str) -> float:
    """
    Get weight for terminal type.

    Args:
        terminal_type: Terminal classification

    Returns:
        Terminal weight
    """
    if pd.isna(terminal_type):
        return 1.0

    terminal_clean = str(terminal_type).strip()

    for key, weight in TERMINAL_WEIGHTS.items():
        if key.lower() in terminal_clean.lower():
            return weight

    return 1.0


def calculate_terminal_score(
    gdf: gpd.GeoDataFrame,
    near_terminal_column: str = 'near_bus_terminal',
    terminal_type_column: str = 'terminal_type',
) -> pd.Series:
    """
    Calculate bus terminal proximity score.

    Methodology:
    1. Check if hub is within 200m of a bus terminal
    2. Weight by terminal type (National > Regional > Metropolitan > Local)
    3. Normalize to 1-10 scale

    Args:
        gdf: GeoDataFrame with hubs
        near_terminal_column: Boolean column for terminal proximity
        terminal_type_column: Column with terminal type/classification

    Returns:
        Series of terminal scores (1-10)
    """
    logger.info("Calculating bus terminal proximity scores...")

    # Check if proximity column exists
    if near_terminal_column not in gdf.columns:
        logger.warning(f"Terminal proximity column '{near_terminal_column}' not found")
        return pd.Series([1.0] * len(gdf), index=gdf.index)  # Minimum score

    raw_scores = []

    for idx, row in gdf.iterrows():
        near_terminal = row.get(near_terminal_column, False)

        if not near_terminal:
            raw_scores.append(0.0)
        else:
            # If near terminal, get terminal type weight
            if terminal_type_column in gdf.columns:
                terminal_type = row.get(terminal_type_column)
                weight = get_terminal_weight(terminal_type)
            else:
                weight = 1.5  # Default weight

            raw_scores.append(weight)

    raw_scores_series = pd.Series(raw_scores, index=gdf.index)

    # Normalize to 1-10 (hubs not near terminals get minimum score)
    if raw_scores_series.max() > 0:
        normalized_scores = normalize_minmax(raw_scores_series)
    else:
        normalized_scores = pd.Series([1.0] * len(gdf), index=gdf.index)

    # Log statistics
    n_near_terminal = (gdf[near_terminal_column] == True).sum() if near_terminal_column in gdf.columns else 0
    logger.info(f"✓ Terminal scores calculated for {len(normalized_scores)} hubs")
    logger.info(f"  Hubs near terminals: {n_near_terminal} ({n_near_terminal/len(gdf)*100:.1f}%)")
    logger.info(f"  Mean score: {normalized_scores.mean():.2f}")

    return normalized_scores
