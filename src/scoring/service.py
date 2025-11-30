"""
Service & Hierarchy of Modes Scoring
=====================================
Score hubs based on service strength and modal diversity.

Considers:
1. Number of lines per mode (with diminishing returns)
2. Modal weights (Rail > Metro > LRT > BRT > Bus)
3. Diversity bonus for multiple modes
"""

import geopandas as gpd
import pandas as pd
import numpy as np

from ..config import (
    MODE_WEIGHTS,
    MODE_LINE_DIMINISHING_RETURNS,
    MODE_DIVERSITY_BONUS_PCT,
    get_mode_weight,
)
from .normalization import normalize_by_tier
from ..utils.logging import get_logger

logger = get_logger(__name__)


def calculate_line_score_with_diminishing_returns(n_lines: int) -> float:
    """
    Calculate line count score with diminishing returns.

    Formula: score = sqrt(n_lines)
    - 1 line: 1.00
    - 2 lines: 1.41
    - 4 lines: 2.00
    - 9 lines: 3.00

    Args:
        n_lines: Number of lines

    Returns:
        Score with diminishing returns
    """
    if n_lines <= 0:
        return 0.0
    return np.sqrt(n_lines)


def calculate_mode_service_score(
    modes: list,
    line_counts: dict = None,
    use_diminishing_returns: bool = MODE_LINE_DIMINISHING_RETURNS,
) -> float:
    """
    Calculate service score for a hub's modes.

    Args:
        modes: List of transport modes
        line_counts: Dictionary of mode -> line count (if None, assumes 1 per mode)
        use_diminishing_returns: Apply diminishing returns to line counts

    Returns:
        Service score (unnormalized)
    """
    if not isinstance(modes, list):
        modes = [modes]

    if line_counts is None:
        line_counts = {mode: 1 for mode in modes}

    total_score = 0.0

    for mode in modes:
        mode_weight = get_mode_weight(mode)
        n_lines = line_counts.get(mode, 1)

        if use_diminishing_returns:
            line_score = calculate_line_score_with_diminishing_returns(n_lines)
        else:
            line_score = n_lines

        mode_score = mode_weight * line_score
        total_score += mode_score

    # Apply diversity bonus
    n_modes = len(modes)
    if n_modes > 1:
        diversity_bonus = 1.0 + (n_modes - 1) * MODE_DIVERSITY_BONUS_PCT
        total_score *= diversity_bonus

    return total_score


def calculate_service_score(
    gdf: gpd.GeoDataFrame,
    modes_column: str = 'modes',
    tier_column: str = 'tier',
    line_count_column: str = 'Line_Nunique',
) -> pd.Series:
    """
    Calculate service & hierarchy of modes score for all hubs.

    Methodology:
    1. For each mode, calculate: mode_weight × line_count_with_diminishing_returns
    2. Sum across all modes
    3. Apply diversity bonus: (1 + (n_modes - 1) × 0.10)
    4. Normalize to 1-10 scale per tier

    Args:
        gdf: GeoDataFrame with hubs
        modes_column: Column with list of modes
        tier_column: Column with tier classification
        line_count_column: Column with total line count

    Returns:
        Series of service scores (1-10)
    """
    logger.info("Calculating service & hierarchy of modes scores...")

    if modes_column not in gdf.columns:
        logger.warning(f"Modes column '{modes_column}' not found")
        return pd.Series([5.0] * len(gdf), index=gdf.index)

    # Calculate raw service scores
    raw_scores = []

    for idx, row in gdf.iterrows():
        modes = row[modes_column]
        if not isinstance(modes, list):
            modes = [modes] if pd.notna(modes) else []

        # Simple approach: assume equal distribution of lines across modes
        # TODO: Could be enhanced with per-mode line counts if available
        line_counts = None
        if line_count_column in gdf.columns and pd.notna(row[line_count_column]):
            n_total_lines = row[line_count_column]
            n_modes = len(modes)
            if n_modes > 0:
                lines_per_mode = max(1, n_total_lines / n_modes)
                line_counts = {mode: lines_per_mode for mode in modes}

        score = calculate_mode_service_score(modes, line_counts=line_counts)
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
    logger.info(f"✓ Service scores calculated for {len(normalized_scores)} hubs")
    logger.info(f"  Mean: {normalized_scores.mean():.2f}, Median: {normalized_scores.median():.2f}")
    logger.info(f"  Min: {normalized_scores.min():.2f}, Max: {normalized_scores.max():.2f}")

    # Log mode diversity distribution
    if modes_column in gdf.columns:
        n_modes_dist = gdf[modes_column].apply(lambda x: len(x) if isinstance(x, list) else 0).value_counts().sort_index()
        logger.info("Mode diversity distribution:")
        for n_modes, count in n_modes_dist.items():
            logger.info(f"  {n_modes} modes: {count} hubs")

    return normalized_scores
