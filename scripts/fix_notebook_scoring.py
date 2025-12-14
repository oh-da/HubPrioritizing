#!/usr/bin/env python3
"""
Fix Scoring Calculations in COMPLETE_TRANSIT_PIPELINE.ipynb
============================================================
This script fixes the three scoring calculation bugs in the notebook.
"""

import json
import sys
from pathlib import Path

def fix_notebook():
    """Fix the notebook scoring calculations."""

    notebook_path = Path('/home/user/HubPrioritizing/COMPLETE_TRANSIT_PIPELINE.ipynb')

    if not notebook_path.exists():
        print(f"❌ Notebook not found: {notebook_path}")
        return False

    print("="*80)
    print("FIXING COMPLETE_TRANSIT_PIPELINE.IPYNB")
    print("="*80)

    # Read notebook
    print("\n1. Reading notebook...")
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    print(f"   ✓ Loaded notebook with {len(nb['cells'])} cells")

    cells_modified = []

    # FIX 1: Num_Modes calculation in Part 2 (cell 42)
    print("\n2. Fixing Num_Modes calculation (Part 2)...")
    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            if "grouped['Num_Modes'] = grouped['Mode_Planned'].apply(" in source:
                print(f"   Found at cell {i}")

                # Replace the calculation
                new_source = source.replace(
                    """    # Calculate number of modes
    if 'Mode_Planned' in grouped.columns:
        grouped['Num_Modes'] = grouped['Mode_Planned'].apply(
            lambda x: len(x) if isinstance(x, list) else 1
        )""",
                    """    # Calculate number of modes - FIXED: count mode-specific line columns > 0
    # MODE LINE COLUMNS to check
    MODE_LINE_COLS = [
        'BRT Lines', 'Cable Line Lines', 'Funicular Lines',
        'HighSpeed Rail Lines', 'Interurban Rail Lines', 'LRT Lines',
        'Metro Lines', 'Suburban Rail Lines'
    ]

    def count_positive_mode_lines(row):
        \"\"\"Count how many mode-specific line columns have values > 0.\"\"\"
        count = 0
        for col in MODE_LINE_COLS:
            if col in row.index and pd.notna(row[col]) and row[col] > 0:
                count += 1
        return count

    grouped['Num_Modes'] = grouped.apply(count_positive_mode_lines, axis=1)"""
                )

                # Also add 'location' to aggregation columns
                new_source = new_source.replace(
                    "for col in ['address', 'area', 'district', 'metro_area']:",
                    "for col in ['address', 'area', 'district', 'metro_area', 'location']:"
                )

                cell['source'] = new_source.split('\n')
                if not new_source.endswith('\n'):
                    cell['source'][-1] += '\n'
                else:
                    cell['source'].append('')

                cells_modified.append(('Num_Modes', i))
                print(f"   ✓ Fixed Num_Modes calculation at cell {i}")
                break

    # FIX 2 & 3: Find Step 4.3 and add score and RegionLocation calculations
    print("\n3. Finding Step 4.3 (Mode score calculation)...")
    step_4_3_found = False

    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source'])
            if 'Step 4.3' in source and 'Mode' in source:
                print(f"   Found Step 4.3 header at cell {i}")
                step_4_3_found = True

                # The code cell should be next
                if i + 1 < len(nb['cells']) and nb['cells'][i + 1]['cell_type'] == 'code':
                    code_cell = nb['cells'][i + 1]
                    source = ''.join(code_cell['source'])

                    # Check if it already has the fixes
                    if 'calculate_mode_score' in source and 'get_region_category' in source:
                        print(f"   ⚠ Cell {i+1} already has fixes, skipping")
                    else:
                        print(f"   Adding fixes to cell {i+1}")

                        # Create new cell content with all scoring calculations
                        new_cell_source = """# Step 4.3: Calculate Mode Score, RegionLocation, and Bus Terminal Score

# MODE WEIGHTS for scoring (from CLAUDE.md)
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
    \"\"\"Count how many mode-specific line columns have values > 0.\"\"\"
    count = 0
    for col in MODE_LINE_COLS:
        if col in row.index and pd.notna(row[col]) and row[col] > 0:
            count += 1
    return count

def calculate_mode_score(row):
    \"\"\"Calculate mode service score with mode weights and diversity bonus.\"\"\"
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

def get_region_category(area):
    \"\"\"
    Map area to region category.
    0 = Tel Aviv/Center (lower priority for national equity)
    1 = Periphery (higher priority for national equity)
    \"\"\"
    if pd.isna(area):
        return 1  # Default to periphery
    area_str = str(area).strip()
    # Check for Tel Aviv / Center
    if any(keyword in area_str for keyword in ['תל אביב', 'Tel Aviv', 'תל-אביב', 'מרכז', 'Center']):
        return 0
    return 1

def get_location_category(location):
    \"\"\"
    Map location to metropolitan position category.
    3 = Core (גלעין)
    2 = Ring (טבעת)
    1 = Periphery / Other
    \"\"\"
    if pd.isna(location):
        return 1  # Default to periphery
    location_str = str(location).strip()
    if 'גלעין' in location_str or 'Core' in location_str:
        return 3
    elif 'טבעת' in location_str or 'Ring' in location_str:
        return 2
    else:
        return 1

def bus_terminal_score(term_type):
    \"\"\"Convert terminal type to score.\"\"\"
    if pd.isna(term_type):
        return 0
    term_type = str(term_type).strip()

    if 'חניון לילה' in term_type:
        return 1
    elif 'מסוף קטן' in term_type or 'מסוף בינוני' in term_type:
        return 2
    elif 'מסוף גדול' in term_type or 'מתקן משולב' in term_type:
        return 3
    return 0

# Recalculate Num_Modes if not already correct
if 'Num_Modes' not in df_scoring.columns or df_scoring['Num_Modes'].max() == 0:
    print("Recalculating Num_Modes...")
    df_scoring['Num_Modes'] = df_scoring.apply(count_positive_mode_lines, axis=1)
    print(f"  Num_Modes range: {df_scoring['Num_Modes'].min()} - {df_scoring['Num_Modes'].max()}")

# Calculate mode service score
print("Calculating mode service score...")
df_scoring['score'] = df_scoring.apply(calculate_mode_score, axis=1)
print(f"  score range: {df_scoring['score'].min():.2f} - {df_scoring['score'].max():.2f}")

# Calculate Region and Location categories
print("Calculating Region and Location categories...")
if 'area' in df_scoring.columns:
    df_scoring['Region_category'] = df_scoring['area'].apply(get_region_category)
else:
    df_scoring['Region_category'] = 1
    print("  ⚠ No 'area' column, using default Region_category=1")

if 'location' in df_scoring.columns:
    df_scoring['Location_category'] = df_scoring['location'].apply(get_location_category)
else:
    df_scoring['Location_category'] = 1
    print("  ⚠ No 'location' column, using default Location_category=1")

# Calculate RegionLocation
df_scoring['RegionLocation'] = df_scoring['Region_category'] * df_scoring['Location_category']
print(f"  RegionLocation range: {df_scoring['RegionLocation'].min()} - {df_scoring['RegionLocation'].max()}")
print(f"  RegionLocation distribution: {df_scoring['RegionLocation'].value_counts().sort_index().to_dict()}")

# Calculate bus terminal score
if 'term_type' in df_scoring.columns:
    df_scoring['bus_terminal'] = df_scoring['term_type'].apply(bus_terminal_score)
else:
    df_scoring['bus_terminal'] = 0
    print("  ⚠ No 'term_type' column, setting bus_terminal=0")

print("\\n✓ Step 4.3 complete - All scoring columns calculated!")
print(f"  Columns added/updated: Num_Modes, score, Region_category, Location_category, RegionLocation, bus_terminal")
"""

                        code_cell['source'] = new_cell_source.split('\n')
                        if not new_cell_source.endswith('\n'):
                            code_cell['source'][-1] += '\n'
                        else:
                            code_cell['source'].append('')

                        cells_modified.append(('Step 4.3', i+1))
                        print(f"   ✓ Added score and RegionLocation calculations at cell {i+1}")
                break

    if not step_4_3_found:
        print("   ⚠ Warning: Step 4.3 not found. You may need to add it manually.")

    # Save modified notebook
    print(f"\n4. Saving modified notebook...")
    backup_path = notebook_path.with_suffix('.ipynb.backup')

    # Create backup
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print(f"   ✓ Backup saved: {backup_path}")

    # Save modified version
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print(f"   ✓ Modified notebook saved")

    # Summary
    print("\n" + "="*80)
    print("✅ NOTEBOOK FIXES APPLIED!")
    print("="*80)
    print(f"\nModified {len(cells_modified)} cells:")
    for fix_name, cell_num in cells_modified:
        print(f"  • {fix_name}: Cell {cell_num}")

    print(f"\nBackup saved to: {backup_path}")
    print(f"Original notebook: {notebook_path}")

    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Open the notebook in Jupyter")
    print("2. Run the modified cells to verify they work")
    print("3. Run the full scoring pipeline (Part 4)")
    print("4. Check that Num_Modes, score, and RegionLocation have varied values")
    print("="*80)

    return True

if __name__ == "__main__":
    success = fix_notebook()
    sys.exit(0 if success else 1)
