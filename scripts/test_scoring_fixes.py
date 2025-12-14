#!/usr/bin/env python3
"""
Test Script for Scoring Calculation Fixes
==========================================
Validates that Num_Modes, score, and RegionLocation are calculated correctly.
"""

import pandas as pd
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_scoring_calculations():
    """Test the scoring calculations with sample data."""

    print("="*80)
    print("TESTING SCORING CALCULATION FIXES")
    print("="*80)

    # Create sample data that mimics the structure
    test_data = pd.DataFrame({
        'hub_id': [1, 2, 3, 4],
        'area': ['תל אביב', 'צפון', 'חיפה', 'מרכז'],
        'location': ['גלעין', 'טבעת', 'צפון', 'Core'],
        'BRT Lines': [2, 0, 1, 0],
        'LRT Lines': [0, 3, 0, 0],
        'Metro Lines': [1, 0, 0, 2],
        'HighSpeed Rail Lines': [0, 2, 0, 0],
        'Interurban Rail Lines': [0, 0, 1, 0],
        'Suburban Rail Lines': [0, 0, 0, 0],
        'Cable Line Lines': [0, 0, 0, 0],
        'Funicular Lines': [0, 0, 0, 0],
    })

    print("\nTest Data:")
    print(test_data[['hub_id', 'area', 'location', 'BRT Lines', 'LRT Lines', 'Metro Lines', 'HighSpeed Rail Lines']])

    # MODE WEIGHTS (from hub_demand_processor.py)
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
        alpha = 0.1  # Diversity bonus factor

        for mode, weight in MODE_WEIGHTS.items():
            column_name = f'{mode} Lines'
            if column_name in row.index and pd.notna(row[column_name]) and row[column_name] > 0:
                score += row[column_name] * weight

        n_modes = row.get('Num_Modes', 1)
        if pd.notna(n_modes) and n_modes > 0:
            score = score * (1 + alpha * (n_modes - 1))

        return score

    def get_region_category(area):
        """Map area to region category."""
        if pd.isna(area):
            return 1
        area_str = str(area).strip()
        if any(keyword in area_str for keyword in ['תל אביב', 'Tel Aviv', 'תל-אביב', 'מרכז', 'Center']):
            return 0
        return 1

    def get_location_category(location):
        """Map location to metropolitan position category."""
        if pd.isna(location):
            return 1
        location_str = str(location).strip()
        if 'גלעין' in location_str or 'Core' in location_str:
            return 3
        elif 'טבעת' in location_str or 'Ring' in location_str:
            return 2
        else:
            return 1

    # Apply calculations
    test_data['Num_Modes'] = test_data.apply(count_positive_mode_lines, axis=1)
    test_data['score'] = test_data.apply(calculate_mode_score, axis=1)
    test_data['Region_category'] = test_data['area'].apply(get_region_category)
    test_data['Location_category'] = test_data['location'].apply(get_location_category)
    test_data['RegionLocation'] = test_data['Region_category'] * test_data['Location_category']

    print("\n" + "="*80)
    print("RESULTS:")
    print("="*80)

    print("\nCalculated Values:")
    print(test_data[['hub_id', 'Num_Modes', 'score', 'Region_category', 'Location_category', 'RegionLocation']])

    # Expected values
    expected = {
        1: {'Num_Modes': 2, 'score': 11.0, 'Region_category': 0, 'Location_category': 3, 'RegionLocation': 0},
        2: {'Num_Modes': 2, 'score': 28.6, 'Region_category': 1, 'Location_category': 2, 'RegionLocation': 2},
        3: {'Num_Modes': 2, 'score': 10.45, 'Region_category': 1, 'Location_category': 1, 'RegionLocation': 1},
        4: {'Num_Modes': 1, 'score': 10.0, 'Region_category': 0, 'Location_category': 3, 'RegionLocation': 0},
    }

    print("\n" + "="*80)
    print("VALIDATION:")
    print("="*80)

    all_passed = True
    for hub_id in expected.keys():
        row = test_data[test_data['hub_id'] == hub_id].iloc[0]
        print(f"\nHub {hub_id}:")

        # Num_Modes
        if row['Num_Modes'] == expected[hub_id]['Num_Modes']:
            print(f"  ✓ Num_Modes: {row['Num_Modes']} (correct)")
        else:
            print(f"  ✗ Num_Modes: {row['Num_Modes']} (expected {expected[hub_id]['Num_Modes']})")
            all_passed = False

        # score (allow small floating point differences)
        if abs(row['score'] - expected[hub_id]['score']) < 0.1:
            print(f"  ✓ score: {row['score']:.2f} (correct)")
        else:
            print(f"  ✗ score: {row['score']:.2f} (expected {expected[hub_id]['score']:.2f})")
            all_passed = False

        # RegionLocation
        if row['RegionLocation'] == expected[hub_id]['RegionLocation']:
            print(f"  ✓ RegionLocation: {row['RegionLocation']} (correct)")
        else:
            print(f"  ✗ RegionLocation: {row['RegionLocation']} (expected {expected[hub_id]['RegionLocation']})")
            all_passed = False

    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
    print("="*80)

    return all_passed

if __name__ == "__main__":
    success = test_scoring_calculations()
    sys.exit(0 if success else 1)
