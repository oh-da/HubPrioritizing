"""
Score Normalization Functions
==============================
Functions for normalizing scores to 1-10 range.
"""

import pandas as pd
import numpy as np
from typing import Optional

from ..config import SCORE_MIN, SCORE_MAX
from ..utils.logging import get_logger

logger = get_logger(__name__)


def normalize_minmax(
    values: pd.Series,
    min_val: float = SCORE_MIN,
    max_val: float = SCORE_MAX,
    input_min: Optional[float] = None,
    input_max: Optional[float] = None,
) -> pd.Series:
    """
    Min-max normalization to specified range.

    Formula: normalized = (value - input_min) / (input_max - input_min) * (max_val - min_val) + min_val

    Args:
        values: Series to normalize
        min_val: Minimum value in output range
        max_val: Maximum value in output range
        input_min: Minimum value in input (if None, uses values.min())
        input_max: Maximum value in input (if None, uses values.max())

    Returns:
        Normalized series
    """
    if input_min is None:
        input_min = values.min()
    if input_max is None:
        input_max = values.max()

    # Handle case where all values are the same
    if input_max == input_min:
        logger.warning(f"All values are {input_min}, returning midpoint")
        return pd.Series([( min_val + max_val) / 2] * len(values), index=values.index)

    # Normalize
    normalized = (values - input_min) / (input_max - input_min) * (max_val - min_val) + min_val

    # Clip to range
    normalized = normalized.clip(min_val, max_val)

    return normalized


def normalize_by_tier(
    df: pd.DataFrame,
    value_column: str,
    tier_column: str,
    min_val: float = SCORE_MIN,
    max_val: float = SCORE_MAX,
) -> pd.Series:
    """
    Normalize values separately per tier.

    This ensures fair comparison within tiers (national hubs compared
    to national hubs, etc.).

    Args:
        df: DataFrame with values and tiers
        value_column: Column to normalize
        tier_column: Column containing tier labels
        min_val: Minimum value in output range
        max_val: Maximum value in output range

    Returns:
        Series of normalized values
    """
    logger.debug(f"Normalizing {value_column} by tier")

    normalized = pd.Series(index=df.index, dtype=float)

    for tier in df[tier_column].unique():
        tier_mask = df[tier_column] == tier
        tier_values = df.loc[tier_mask, value_column]

        tier_normalized = normalize_minmax(
            tier_values,
            min_val=min_val,
            max_val=max_val
        )

        normalized.loc[tier_mask] = tier_normalized

        logger.debug(f"  {tier}: normalized {tier_mask.sum()} values")

    return normalized


def normalize_log10(
    values: pd.Series,
    min_val: float = SCORE_MIN,
    max_val: float = SCORE_MAX,
) -> pd.Series:
    """
    Apply log10 transformation then normalize.

    Used for highly skewed distributions (e.g., passenger demand).

    Args:
        values: Series to normalize
        min_val: Minimum value in output range
        max_val: Maximum value in output range

    Returns:
        Normalized series
    """
    # Replace zeros/negatives with small positive value
    values_clean = values.copy()
    values_clean[values_clean <= 0] = 1

    # Apply log10
    log_values = np.log10(values_clean)

    # Normalize
    normalized = normalize_minmax(log_values, min_val=min_val, max_val=max_val)

    return normalized


def normalize_log10_by_tier(
    df: pd.DataFrame,
    value_column: str,
    tier_column: str,
    min_val: float = SCORE_MIN,
    max_val: float = SCORE_MAX,
) -> pd.Series:
    """
    Apply log10 transformation then normalize separately per tier.

    Args:
        df: DataFrame with values and tiers
        value_column: Column to normalize
        tier_column: Column containing tier labels
        min_val: Minimum value in output range
        max_val: Maximum value in output range

    Returns:
        Series of normalized values
    """
    logger.debug(f"Normalizing {value_column} with log10 by tier")

    normalized = pd.Series(index=df.index, dtype=float)

    for tier in df[tier_column].unique():
        tier_mask = df[tier_column] == tier
        tier_values = df.loc[tier_mask, value_column]

        tier_normalized = normalize_log10(
            tier_values,
            min_val=min_val,
            max_val=max_val
        )

        normalized.loc[tier_mask] = tier_normalized

        logger.debug(f"  {tier}: normalized {tier_mask.sum()} values")

    return normalized
