"""
Data Validation Functions
==========================
Functions for validating data quality, completeness, and consistency.
"""

import pandas as pd
import geopandas as gpd
from typing import List, Optional

from ..config import (
    MIN_EXPECTED_HUBS,
    MAX_EXPECTED_HUBS,
    SCORE_MIN,
    SCORE_MAX,
    SCORE_VALIDATION_TOLERANCE,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_required_columns(
    df: pd.DataFrame,
    required_columns: List[str],
    data_name: str = "dataset"
) -> None:
    """
    Validate that required columns exist in DataFrame.

    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        data_name: Descriptive name for error messages

    Raises:
        ValidationError: If required columns are missing
    """
    missing_cols = [col for col in required_columns if col not in df.columns]

    if missing_cols:
        error_msg = f"{data_name} missing required columns: {missing_cols}"
        logger.error(error_msg)
        logger.info(f"Available columns: {list(df.columns)}")
        raise ValidationError(error_msg)

    logger.debug(f"✓ All required columns present in {data_name}")


def validate_geometry(gdf: gpd.GeoDataFrame, data_name: str = "GeoDataFrame") -> None:
    """
    Validate geometry column in GeoDataFrame.

    Args:
        gdf: GeoDataFrame to validate
        data_name: Descriptive name for error messages

    Raises:
        ValidationError: If geometry is missing or invalid
    """
    if 'geometry' not in gdf.columns:
        raise ValidationError(f"{data_name} has no geometry column")

    # Check for null geometries
    null_count = gdf.geometry.isna().sum()
    if null_count > 0:
        logger.warning(f"{data_name} has {null_count} null geometries")

    # Check for invalid geometries
    invalid_count = (~gdf.geometry.is_valid).sum()
    if invalid_count > 0:
        logger.warning(f"{data_name} has {invalid_count} invalid geometries")

    logger.debug(f"✓ Geometry validation passed for {data_name}")


def validate_crs(gdf: gpd.GeoDataFrame, expected_crs: str, data_name: str = "GeoDataFrame") -> None:
    """
    Validate that GeoDataFrame has expected CRS.

    Args:
        gdf: GeoDataFrame to validate
        expected_crs: Expected CRS string
        data_name: Descriptive name for error messages

    Raises:
        ValidationError: If CRS doesn't match
    """
    if gdf.crs is None:
        logger.warning(f"{data_name} has no CRS defined")
    elif str(gdf.crs) != expected_crs:
        logger.warning(f"{data_name} CRS ({gdf.crs}) differs from expected ({expected_crs})")

    logger.debug(f"✓ CRS check passed for {data_name}")


def validate_numeric_range(
    df: pd.DataFrame,
    column: str,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    allow_null: bool = False,
    data_name: str = "dataset"
) -> None:
    """
    Validate that numeric column values are within expected range.

    Args:
        df: DataFrame to validate
        column: Column name
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        allow_null: Whether null values are allowed
        data_name: Descriptive name for error messages

    Raises:
        ValidationError: If values are out of range
    """
    if column not in df.columns:
        raise ValidationError(f"{data_name} missing column: {column}")

    # Check for nulls
    null_count = df[column].isna().sum()
    if null_count > 0 and not allow_null:
        raise ValidationError(f"{data_name}.{column} has {null_count} null values")

    # Get non-null values
    values = df[column].dropna()

    if len(values) == 0:
        logger.warning(f"{data_name}.{column} has no non-null values")
        return

    # Check range
    actual_min = values.min()
    actual_max = values.max()

    if min_value is not None and actual_min < min_value:
        raise ValidationError(
            f"{data_name}.{column} has values below minimum: "
            f"{actual_min} < {min_value}"
        )

    if max_value is not None and actual_max > max_value:
        raise ValidationError(
            f"{data_name}.{column} has values above maximum: "
            f"{actual_max} > {max_value}"
        )

    logger.debug(f"✓ Range validation passed for {data_name}.{column}")


def validate_score_column(
    df: pd.DataFrame,
    column: str,
    strict: bool = True,
    data_name: str = "dataset"
) -> None:
    """
    Validate that score column is within [SCORE_MIN, SCORE_MAX] range.

    Args:
        df: DataFrame to validate
        column: Score column name
        strict: If True, raise error on out-of-range; if False, warn only
        data_name: Descriptive name for error messages

    Raises:
        ValidationError: If strict and scores are out of range
    """
    if column not in df.columns:
        logger.warning(f"{data_name} missing score column: {column}")
        return

    values = df[column].dropna()

    if len(values) == 0:
        logger.warning(f"{data_name}.{column} has no values")
        return

    # Check range with tolerance
    min_allowed = SCORE_MIN - SCORE_VALIDATION_TOLERANCE
    max_allowed = SCORE_MAX + SCORE_VALIDATION_TOLERANCE

    out_of_range = (values < min_allowed) | (values > max_allowed)
    n_out_of_range = out_of_range.sum()

    if n_out_of_range > 0:
        msg = (
            f"{data_name}.{column} has {n_out_of_range} values "
            f"outside valid range [{SCORE_MIN}, {SCORE_MAX}]"
        )
        if strict:
            logger.error(msg)
            raise ValidationError(msg)
        else:
            logger.warning(msg)

    logger.debug(f"✓ Score validation passed for {data_name}.{column}")


def validate_hub_count(
    hubs: gpd.GeoDataFrame,
    min_count: int = MIN_EXPECTED_HUBS,
    max_count: int = MAX_EXPECTED_HUBS,
) -> None:
    """
    Validate that hub count is within expected range.

    Args:
        hubs: Hub GeoDataFrame
        min_count: Minimum expected hubs
        max_count: Maximum expected hubs

    Raises:
        ValidationError: If count is out of range
    """
    n_hubs = len(hubs)

    if n_hubs < min_count:
        msg = f"Hub count ({n_hubs}) is below minimum expected ({min_count})"
        logger.warning(msg)
        # Don't raise error, just warn
    elif n_hubs > max_count:
        msg = f"Hub count ({n_hubs}) exceeds maximum expected ({max_count})"
        logger.warning(msg)
        # Don't raise error, just warn
    else:
        logger.info(f"✓ Hub count ({n_hubs}) is within expected range")


def validate_no_duplicates(
    df: pd.DataFrame,
    columns: List[str],
    data_name: str = "dataset"
) -> None:
    """
    Validate that there are no duplicate rows based on specified columns.

    Args:
        df: DataFrame to validate
        columns: Columns to check for duplicates
        data_name: Descriptive name for error messages

    Raises:
        ValidationError: If duplicates are found
    """
    duplicates = df.duplicated(subset=columns, keep=False)
    n_duplicates = duplicates.sum()

    if n_duplicates > 0:
        logger.warning(
            f"{data_name} has {n_duplicates} duplicate rows based on columns: {columns}"
        )
        # Log first few duplicates for inspection
        logger.debug(f"First duplicates:\n{df[duplicates].head()}")

    logger.debug(f"✓ Duplicate check passed for {data_name}")


def validate_completeness(
    df: pd.DataFrame,
    critical_columns: List[str],
    data_name: str = "dataset",
    max_null_pct: float = 0.1
) -> None:
    """
    Validate data completeness for critical columns.

    Args:
        df: DataFrame to validate
        critical_columns: Columns that should be mostly complete
        data_name: Descriptive name for error messages
        max_null_pct: Maximum allowed percentage of null values

    Raises:
        ValidationError: If null percentage exceeds threshold
    """
    for col in critical_columns:
        if col not in df.columns:
            continue

        null_count = df[col].isna().sum()
        null_pct = null_count / len(df)

        if null_pct > max_null_pct:
            msg = (
                f"{data_name}.{col} has {null_pct*100:.1f}% null values "
                f"(threshold: {max_null_pct*100:.1f}%)"
            )
            logger.warning(msg)

    logger.debug(f"✓ Completeness validation passed for {data_name}")


def validate_hubs_dataset(hubs: gpd.GeoDataFrame) -> None:
    """
    Comprehensive validation for hubs dataset.

    Args:
        hubs: Hub GeoDataFrame to validate

    Raises:
        ValidationError: If validation fails
    """
    logger.info("Validating hubs dataset...")

    # Required columns
    validate_required_columns(
        hubs,
        required_columns=['group', 'geometry'],
        data_name="hubs"
    )

    # Geometry validation
    validate_geometry(hubs, data_name="hubs")

    # Hub count
    validate_hub_count(hubs)

    # Optional: Check for demand data
    if 'TotalDemand' in hubs.columns:
        validate_numeric_range(
            hubs,
            'TotalDemand',
            min_value=0,
            allow_null=True,
            data_name="hubs"
        )

    logger.info("✓ Hubs dataset validation passed")


def validate_scored_hubs(hubs: gpd.GeoDataFrame) -> None:
    """
    Comprehensive validation for scored hubs dataset.

    Args:
        hubs: Scored hub GeoDataFrame

    Raises:
        ValidationError: If validation fails
    """
    logger.info("Validating scored hubs dataset...")

    # Basic validation
    validate_hubs_dataset(hubs)

    # Check for tier classification
    if 'tier' in hubs.columns:
        validate_required_columns(
            hubs,
            required_columns=['tier'],
            data_name="scored hubs"
        )

    # Validate score columns (if they exist)
    score_columns = [
        'activity_score',
        'service_score',
        'location_score',
        'pop_jobs_score',
        'terminal_score',
        'final_score'
    ]

    for col in score_columns:
        if col in hubs.columns:
            validate_score_column(hubs, col, strict=False, data_name="scored hubs")

    logger.info("✓ Scored hubs dataset validation passed")
