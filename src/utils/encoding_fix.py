"""
Improved encoding detection and Hebrew text validation for shapefiles.

This module provides robust encoding detection specifically optimized for
Hebrew text in shapefiles, which commonly use Windows-1255 or ISO-8859-8 encoding.
"""

import geopandas as gpd
import pandas as pd
from typing import List, Tuple, Optional


def is_valid_hebrew_text(text: str, min_hebrew_ratio: float = 0.3, verbose: bool = False) -> bool:
    """
    Check if text contains valid Hebrew characters.

    Returns True if text looks like valid Hebrew, False if gibberish.

    Args:
        text: The text to validate
        min_hebrew_ratio: Minimum ratio of Hebrew characters (0-1)
        verbose: Print diagnostic information

    Returns:
        True if text appears to be valid Hebrew, False otherwise
    """
    if not isinstance(text, str) or len(text) == 0:
        return True  # Empty/None is ok

    # Hebrew Unicode range: 0x0590-0x05FF
    hebrew_chars = 0
    latin_chars = 0
    special_chars = 0

    for c in text:
        if '\u0590' <= c <= '\u05FF':
            hebrew_chars += 1
        elif c.isspace():
            continue  # Ignore spaces
        elif c.isalpha():
            latin_chars += 1
        else:
            special_chars += 1

    total_chars = hebrew_chars + latin_chars + special_chars

    if verbose:
        print(f"      Text: '{text}'")
        print(f"      Hebrew: {hebrew_chars}, Latin: {latin_chars}, Special: {special_chars}")

    # If no content, accept it
    if total_chars == 0:
        return True

    # Calculate Hebrew ratio
    hebrew_ratio = hebrew_chars / total_chars

    # Check for gibberish patterns
    # Gibberish often has many special characters and no Hebrew
    if special_chars > latin_chars and hebrew_chars == 0:
        if verbose:
            print(f"      ✗ Detected gibberish: {special_chars} special chars, {hebrew_chars} Hebrew")
        return False

    # Check if enough Hebrew characters
    if hebrew_ratio < min_hebrew_ratio:
        if verbose:
            print(f"      ✗ Hebrew ratio too low: {hebrew_ratio:.2%} < {min_hebrew_ratio:.2%}")
        return False

    if verbose:
        print(f"      ✓ Valid Hebrew: {hebrew_ratio:.2%}")

    return True


def validate_hebrew_in_gdf(gdf: gpd.GeoDataFrame,
                          columns_to_check: List[str],
                          verbose: bool = False) -> bool:
    """
    Check if a GeoDataFrame has valid Hebrew text in specified columns.

    Args:
        gdf: GeoDataFrame to validate
        columns_to_check: List of column names to check for Hebrew
        verbose: Print diagnostic information

    Returns:
        True if Hebrew looks valid in all columns, False if gibberish detected
    """
    for col in columns_to_check:
        if col not in gdf.columns:
            continue

        if verbose:
            print(f"    Checking column: {col}")

        # Check first few non-null values
        sample_values = gdf[col].dropna().head(5).tolist()

        for i, val in enumerate(sample_values):
            if not is_valid_hebrew_text(str(val), verbose=verbose):
                print(f"    ✗ Invalid Hebrew in column '{col}', row {i}: {val}")
                return False

    return True


def read_shapefile_with_encoding(filepath: str,
                                 name: str = "shapefile",
                                 hebrew_columns: Optional[List[str]] = None,
                                 force_encoding: Optional[str] = None,
                                 verbose: bool = True) -> Tuple[gpd.GeoDataFrame, str]:
    """
    Read shapefile with encoding strategies optimized for Hebrew data.

    Tries multiple encodings in order and validates that Hebrew text is readable.

    Args:
        filepath: Path to shapefile
        name: Name for error messages
        hebrew_columns: List of column names expected to contain Hebrew
        force_encoding: If specified, only try this encoding
        verbose: Print diagnostic information

    Returns:
        Tuple of (GeoDataFrame, encoding_used)

    Raises:
        ValueError: If shapefile cannot be loaded with any encoding
    """
    if force_encoding:
        encodings_to_try = [(force_encoding, force_encoding)]
    else:
        # Prioritize Hebrew encodings first
        encodings_to_try = [
            ('windows-1255', "Windows-1255 (Hebrew)"),
            ('cp1255', "CP1255 (Hebrew)"),
            ('ISO-8859-8', "ISO-8859-8 (Hebrew)"),
            ('utf-8', "UTF-8"),
            (None, "auto-detect"),
        ]

    errors = []

    for encoding, encoding_name in encodings_to_try:
        try:
            if verbose:
                print(f"    Trying encoding: {encoding_name}")

            if encoding is None:
                gdf = gpd.read_file(filepath)
            else:
                gdf = gpd.read_file(filepath, encoding=encoding)

            # Validate Hebrew text is readable
            if hebrew_columns:
                if verbose:
                    print(f"    Validating Hebrew in columns: {hebrew_columns}")

                if validate_hebrew_in_gdf(gdf, hebrew_columns, verbose=verbose):
                    print(f"    ✓ Successfully loaded with encoding: {encoding_name}")
                    return gdf, encoding_name
                else:
                    errors.append(f"      {encoding_name}: Hebrew text validation failed (gibberish detected)")
                    continue
            else:
                print(f"    ✓ Successfully loaded with encoding: {encoding_name}")
                return gdf, encoding_name

        except Exception as e:
            errors.append(f"      {encoding_name}: {str(e)[:100]}")
            continue

    # If all encodings failed, print errors and raise
    print(f"    ✗ Failed to load {name} with any encoding:")
    for error in errors:
        print(error)

    raise ValueError(f"Could not load {filepath} with any encoding")


def diagnose_encoding_issue(shapefile_path: str,
                           expected_hebrew_columns: List[str],
                           verbose: bool = True):
    """
    Diagnose encoding issues in a shapefile by trying all encodings
    and showing exactly what text is read.

    Args:
        shapefile_path: Path to shapefile to diagnose
        expected_hebrew_columns: Columns that should contain Hebrew
        verbose: Print detailed diagnostic information
    """
    print(f"\n{'='*80}")
    print(f"ENCODING DIAGNOSIS: {shapefile_path}")
    print(f"{'='*80}\n")

    encodings = [
        ('windows-1255', "Windows-1255"),
        ('cp1255', "CP1255"),
        ('ISO-8859-8', "ISO-8859-8"),
        ('utf-8', "UTF-8"),
        (None, "auto-detect"),
    ]

    for encoding, encoding_name in encodings:
        print(f"\n--- Trying: {encoding_name} ---")

        try:
            if encoding is None:
                gdf = gpd.read_file(shapefile_path)
            else:
                gdf = gpd.read_file(shapefile_path, encoding=encoding)

            print(f"✓ Loaded {len(gdf)} features")
            print(f"Columns: {list(gdf.columns)}")

            # Show sample values from Hebrew columns
            for col in expected_hebrew_columns:
                if col in gdf.columns:
                    print(f"\nColumn '{col}':")
                    samples = gdf[col].dropna().head(3).tolist()
                    for i, val in enumerate(samples):
                        print(f"  [{i}] {val!r}")
                        is_valid = is_valid_hebrew_text(str(val), verbose=True)
                        if not is_valid:
                            print(f"       ^ INVALID HEBREW!")

        except Exception as e:
            print(f"✗ Failed: {e}")

    print(f"\n{'='*80}\n")


def fix_encoding_in_dataframe(df: pd.DataFrame,
                              columns: List[str],
                              source_encoding: str = 'windows-1255',
                              target_encoding: str = 'utf-8') -> pd.DataFrame:
    """
    Attempt to fix encoding issues in specific columns of a DataFrame.

    This is useful when data has already been loaded with wrong encoding.

    Args:
        df: DataFrame with encoding issues
        columns: Columns to fix
        source_encoding: The encoding that was incorrectly applied
        target_encoding: The correct target encoding

    Returns:
        DataFrame with fixed encoding
    """
    df_fixed = df.copy()

    for col in columns:
        if col not in df.columns:
            continue

        def fix_text(text):
            if pd.isna(text) or not isinstance(text, str):
                return text

            try:
                # Try to re-encode
                # First encode with what we think it is (usually utf-8 or latin-1)
                # Then decode with the correct encoding
                fixed = text.encode('latin-1').decode(source_encoding)
                return fixed
            except (UnicodeDecodeError, UnicodeEncodeError):
                # If that fails, return original
                return text

        df_fixed[col] = df[col].apply(fix_text)

    return df_fixed
