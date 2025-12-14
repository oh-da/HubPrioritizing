#!/usr/bin/env python3
"""
Fix Existing Scoring Calculations
==================================
This script reads an existing hub scoring file and recalculates:
- Num_Modes (count of mode-specific line columns > 0)
- score (weighted mode service score with diversity bonus)
- RegionLocation (Region_category × Location_category)
- And their normalized versions

Use this to fix files created before the scoring calculation bugs were fixed.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# MODE WEIGHTS (from CLAUDE.md)
MODE_WEIGHTS = {
    'Funicular': 1.0,
    'Cable Line': 2.0,
    'BRT': 3.0,
    'LRT': 4.0,
    'Metro': 5.0,
    'Suburban Rail': 6.0,
    'Interurban Rail': 7.0,
    'HighSpeed Rail': 8.0,
    'Rail': 7.0,
    'Express Bus': 3.0,
    'Bus': 2.0,
}

# MODE LINE COLUMNS to check
MODE_LINE_COLS = [
    'BRT Lines', 'Cable Line Lines', 'Funicular Lines',
    'HighSpeed Rail Lines', 'Interurban Rail Lines', 'LRT Lines',
    'Metro Lines', 'Suburban Rail Lines'
]


def count_positive_mode_lines(row):
    """Count how many mode-specific line columns have values > 0."""
    count = 0
    for col in MODE_LINE_COLS:
        if col in row.index and pd.notna(row[col]) and row[col] > 0:
            count += 1
    return count


def calculate_mode_score(row):
    """Calculate mode service score with mode weights and diversity bonus."""
    score = 0.0
    alpha = 0.1  # Diversity bonus factor (10% per additional mode)

    # Calculate score for each mode
    for mode, weight in MODE_WEIGHTS.items():
        column_name = f'{mode} Lines'
        if column_name in row.index and pd.notna(row[column_name]) and row[column_name] > 0:
            # Multiply line count by mode weight
            score += row[column_name] * weight

    # Apply diversity bonus based on number of modes
    n_modes = row.get('Num_Modes', 1)
    if pd.notna(n_modes) and n_modes > 0:
        score = score * (1 + alpha * (n_modes - 1))

    return score


def parse_string_list(value):
    """
    Parse a string representation of a list to extract the actual value.
    Handles: "['value']", ['value'], or 'value'
    Returns the first value if it's a list, or the value itself.
    """
    if pd.isna(value):
        return None

    # Convert to string
    value_str = str(value).strip()

    # Remove brackets and quotes if present
    # Handle cases like "['צפון']" or ['צפון']
    if value_str.startswith('[') and value_str.endswith(']'):
        # Remove outer brackets
        value_str = value_str[1:-1].strip()

    # Remove quotes
    value_str = value_str.replace("'", "").replace('"', '').strip()

    # If multiple values separated by comma, take the first
    if ',' in value_str:
        value_str = value_str.split(',')[0].strip()

    return value_str if value_str else None


def get_region_category(area):
    """
    Map area to region category.
    0 = Tel Aviv/Center (lower priority for national equity)
    1 = Periphery (higher priority for national equity)
    """
    # Parse string list format if needed
    area_clean = parse_string_list(area)

    if not area_clean:
        return 1  # Default to periphery

    area_str = str(area_clean).strip()
    # Check for Tel Aviv / Center
    if any(keyword in area_str for keyword in ['תל אביב', 'Tel Aviv', 'תל-אביב', 'מרכז', 'Center']):
        return 0
    return 1


def get_location_category(location):
    """
    Map location to metropolitan position category.
    3 = Core (גלעין)
    2 = Ring (טבעת)
    1 = Periphery / Other
    """
    # Parse string list format if needed
    location_clean = parse_string_list(location)

    if not location_clean:
        return 1  # Default to periphery

    location_str = str(location_clean).strip()
    if 'גלעין' in location_str or 'Core' in location_str:
        return 3
    elif 'טבעת' in location_str or 'Ring' in location_str:
        return 2
    else:
        return 1


def normalize_col_by_type(df, col, hub_type_col='HubType'):
    """Normalize a column to 1-10 scale, separately per hub type."""
    normalized_col = col + '_Norm'

    for hub_type in df[hub_type_col].unique():
        if pd.isna(hub_type):
            continue

        mask = df[hub_type_col] == hub_type
        values = df.loc[mask, col]

        min_val = values.min()
        max_val = values.max()

        if max_val > min_val:
            df.loc[mask, normalized_col] = 1 + (values - min_val) * 9 / (max_val - min_val)
        else:
            # All values are the same - use midpoint
            df.loc[mask, normalized_col] = 5.5

    return df


def fix_scoring_calculations(input_file, output_file=None):
    """
    Fix scoring calculations in an existing hub data file.

    Args:
        input_file: Path to input CSV or Excel file
        output_file: Path to output file (if None, overwrites input)
    """
    input_path = Path(input_file)

    if not input_path.exists():
        print(f"❌ Error: File not found: {input_file}")
        return False

    print("="*80)
    print("FIXING SCORING CALCULATIONS")
    print("="*80)
    print(f"\nInput file: {input_file}")

    # Read file
    print("\n1. Reading file...")
    try:
        if input_path.suffix in ['.xlsx', '.xls']:
            df = pd.read_excel(input_file)
        else:
            df = pd.read_csv(input_file, encoding='utf-8-sig')
        print(f"   ✓ Loaded {len(df)} rows, {len(df.columns)} columns")
    except Exception as e:
        print(f"   ❌ Error reading file: {e}")
        return False

    # Check for required columns
    print("\n2. Checking for required columns...")
    has_mode_cols = any(col in df.columns for col in MODE_LINE_COLS)
    has_area = 'area' in df.columns
    has_location = 'location' in df.columns
    has_hub_type = 'HubType' in df.columns

    if not has_mode_cols:
        print(f"   ⚠ Warning: No mode-specific line columns found!")
        print(f"   Expected columns like: {MODE_LINE_COLS[:3]}")
        print(f"   Available columns: {list(df.columns)}")
        print(f"\n   Cannot calculate Num_Modes and score without these columns.")
        return False

    print(f"   ✓ Mode line columns: Found")
    print(f"   {'✓' if has_area else '⚠'} area column: {'Found' if has_area else 'Not found (will use default)'}")
    print(f"   {'✓' if has_location else '⚠'} location column: {'Found' if has_location else 'Not found (will use default)'}")
    print(f"   {'✓' if has_hub_type else '⚠'} HubType column: {'Found' if has_hub_type else 'Not found (normalization will use all data)'}")

    # Calculate Num_Modes
    print("\n3. Calculating Num_Modes...")
    df['Num_Modes'] = df.apply(count_positive_mode_lines, axis=1)
    print(f"   ✓ Calculated Num_Modes")
    print(f"      Range: {df['Num_Modes'].min()} - {df['Num_Modes'].max()}")
    print(f"      Mean: {df['Num_Modes'].mean():.2f}")
    print(f"      Distribution: {df['Num_Modes'].value_counts().sort_index().to_dict()}")

    # Calculate score
    print("\n4. Calculating mode service score...")
    df['score'] = df.apply(calculate_mode_score, axis=1)
    print(f"   ✓ Calculated score")
    print(f"      Range: {df['score'].min():.2f} - {df['score'].max():.2f}")
    print(f"      Mean: {df['score'].mean():.2f}")

    # Calculate Region_category
    print("\n5. Calculating Region_category...")
    if has_area:
        df['Region_category'] = df['area'].apply(get_region_category)
    else:
        df['Region_category'] = 1  # Default to periphery
    print(f"   ✓ Calculated Region_category")
    print(f"      Distribution: {df['Region_category'].value_counts().sort_index().to_dict()}")

    # Calculate Location_category
    print("\n6. Calculating Location_category...")
    if has_location:
        df['Location_category'] = df['location'].apply(get_location_category)
    else:
        df['Location_category'] = 1  # Default to periphery
    print(f"   ✓ Calculated Location_category")
    print(f"      Distribution: {df['Location_category'].value_counts().sort_index().to_dict()}")

    # Calculate RegionLocation
    print("\n7. Calculating RegionLocation...")
    df['RegionLocation'] = df['Region_category'] * df['Location_category']
    print(f"   ✓ Calculated RegionLocation")
    print(f"      Range: {df['RegionLocation'].min()} - {df['RegionLocation'].max()}")
    print(f"      Mean: {df['RegionLocation'].mean():.2f}")
    print(f"      Distribution: {df['RegionLocation'].value_counts().sort_index().to_dict()}")

    # Normalize scores
    print("\n8. Normalizing scores...")
    if has_hub_type:
        print(f"   Normalizing by HubType...")
        for col in ['RegionLocation', 'score']:
            df = normalize_col_by_type(df, col, hub_type_col='HubType')
            print(f"   ✓ Normalized {col} -> {col}_Norm")
            print(f"      Range: {df[col + '_Norm'].min():.2f} - {df[col + '_Norm'].max():.2f}")
    else:
        print(f"   ⚠ No HubType column - normalizing across all hubs...")
        for col in ['RegionLocation', 'score']:
            min_val, max_val = df[col].min(), df[col].max()
            if max_val > min_val:
                df[col + '_Norm'] = 1 + (df[col] - min_val) * 9 / (max_val - min_val)
            else:
                df[col + '_Norm'] = 5.5
            print(f"   ✓ Normalized {col} -> {col}_Norm")

    # Save output
    if output_file is None:
        output_file = input_file.replace('.csv', '_FIXED.csv').replace('.xlsx', '_FIXED.xlsx')
        if output_file == input_file:
            output_file = str(input_path.with_stem(input_path.stem + '_FIXED'))

    output_path = Path(output_file)

    print(f"\n9. Saving output...")
    print(f"   Output file: {output_file}")

    try:
        if output_path.suffix in ['.xlsx', '.xls']:
            df.to_excel(output_file, index=False, engine='openpyxl')
        else:
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"   ✓ Saved successfully")
    except Exception as e:
        print(f"   ❌ Error saving file: {e}")
        return False

    # Summary
    print("\n" + "="*80)
    print("✅ SCORING CALCULATIONS FIXED!")
    print("="*80)
    print(f"\nFixed columns:")
    print(f"  • Num_Modes: {df['Num_Modes'].min()}-{df['Num_Modes'].max()} (was all 0)")
    print(f"  • score: {df['score'].min():.1f}-{df['score'].max():.1f} (was all 0)")
    print(f"  • RegionLocation: {df['RegionLocation'].min()}-{df['RegionLocation'].max()} (was all 1)")
    print(f"  • RegionLocation_Norm: {df['RegionLocation_Norm'].min():.1f}-{df['RegionLocation_Norm'].max():.1f} (was all 5.5)")
    print(f"  • score_Norm: {df['score_Norm'].min():.1f}-{df['score_Norm'].max():.1f} (was all 5.5)")

    print(f"\nOutput file: {output_file}")
    print("="*80)

    return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Fix scoring calculations in hub data files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fix_existing_scores.py score_hubs_final.xlsx
  python fix_existing_scores.py input.csv -o output.csv
  python fix_existing_scores.py data/results/hubs.xlsx
        """
    )
    parser.add_argument('input_file', help='Input CSV or Excel file')
    parser.add_argument('-o', '--output', help='Output file (default: input_FIXED.ext)')

    args = parser.parse_args()

    success = fix_scoring_calculations(args.input_file, args.output)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
