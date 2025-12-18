#!/usr/bin/env python3
"""
Fix Hebrew Text Truncation in COMPLETE_TRANSIT_PIPELINE.ipynb

This script adds a fix_truncated_hebrew() function that repairs truncated Hebrew text
in the area and location columns.

Issue: Hebrew text is being truncated, losing the final letter:
- 'גלעין' becomes 'גלעי'
- 'טבעת פנימית' becomes 'טבעת פנימי'
"""

import json
import re

# Define the fix function to be inserted
FIX_FUNCTION = '''    def fix_truncated_hebrew(text):
        """
        Fix truncated Hebrew text by restoring the missing final letter.

        Common truncations:
        - 'גלעי' -> 'גלעין' (Core)
        - 'טבעת פנימי' -> 'טבעת פנימית' (Inner Ring)
        - 'טבעת חיצוני' -> 'טבעת חיצונית' (Outer Ring)
        - 'טבעת תיכונ' -> 'טבעת תיכונה' (Middle Ring)
        - Any word ending with 'י' that should end with 'ית' (feminine adjective)

        Args:
            text: Hebrew text string that may be truncated

        Returns:
            Fixed Hebrew text with proper final letters
        """
        if not isinstance(text, str) or not text:
            return text

        # Known truncation patterns and their fixes
        # Format: (truncated_pattern, correct_replacement)
        fixes = [
            # Exact matches (most specific)
            (r'^גלעי$', 'גלעין'),  # Core (exact word)
            (r'^טבעת פנימי$', 'טבעת פנימית'),  # Inner Ring
            (r'^טבעת חיצוני$', 'טבעת חיצונית'),  # Outer Ring
            (r'^טבעת תיכונ$', 'טבעת תיכונה'),  # Middle Ring
            (r'^טבע$', 'טבעת'),  # Ring (if severely truncated)

            # Word-level fixes (match within larger strings)
            (r'\\bגלעי\\b', 'גלעין'),  # Core (as word)
            (r'\\bטבעת פנימי\\b', 'טבעת פנימית'),  # Inner Ring (as phrase)
            (r'\\bטבעת חיצוני\\b', 'טבעת חיצונית'),  # Outer Ring (as phrase)
            (r'\\bטבעת תיכונ\\b', 'טבעת תיכונה'),  # Middle Ring (as phrase)

            # General pattern: Hebrew word ending with 'י' should end with 'ית' (feminine)
            # Only apply if the word is likely an adjective (e.g., after 'טבעת')
            (r'(טבעת\\s+\\S*?)י(?=\\s|$)', r'\\1ית'),  # Any adjective after טבעת ending in י
        ]

        fixed_text = text.strip()

        # Apply each fix pattern
        for pattern, replacement in fixes:
            fixed_text = re.sub(pattern, replacement, fixed_text)

        # If text changed, log it
        if fixed_text != text.strip():
            # This will be visible during notebook execution
            pass  # Logging will be done by caller

        return fixed_text

    def fix_truncated_hebrew_in_gdf(gdf, columns):
        """
        Apply Hebrew text fixes to specified columns in a GeoDataFrame.

        Args:
            gdf: GeoDataFrame to fix
            columns: List of column names to fix

        Returns:
            Number of values fixed
        """
        fixes_count = 0

        for col in columns:
            if col not in gdf.columns:
                continue

            # Apply fix to non-null string values
            original_values = gdf[col].copy()
            gdf[col] = gdf[col].apply(
                lambda x: fix_truncated_hebrew(x) if pd.notna(x) and isinstance(x, str) else x
            )

            # Count how many were fixed
            changed = (original_values != gdf[col]) & original_values.notna()
            if changed.any():
                fixes_count += changed.sum()
                print(f"    ✓ Fixed {changed.sum()} truncated values in column '{col}'")
                # Show examples of fixes
                for idx in gdf[changed].index[:3]:  # Show first 3 examples
                    old_val = original_values.loc[idx]
                    new_val = gdf.loc[idx, col]
                    print(f"      '{old_val}' -> '{new_val}'")

        return fixes_count

'''

# Define code to apply the fix after tagging
APPLY_FIX_CODE = '''
    # ============================================================================
    # FIX: Repair truncated Hebrew text in area and location columns
    # ============================================================================
    print("\\n  Fixing any truncated Hebrew text...")

    # Fix area column (string values)
    if 'area' in gdf_demand.columns:
        original_areas = gdf_demand['area'].copy()
        gdf_demand['area'] = gdf_demand['area'].apply(
            lambda x: fix_truncated_hebrew(x) if pd.notna(x) else x
        )
        area_fixed = ((original_areas != gdf_demand['area']) & original_areas.notna()).sum()
        if area_fixed > 0:
            print(f"    ✓ Fixed {area_fixed} truncated values in 'area' column")
            # Show examples
            for idx in gdf_demand[(original_areas != gdf_demand['area']) & original_areas.notna()].index[:3]:
                print(f"      '{original_areas.loc[idx]}' -> '{gdf_demand.loc[idx, 'area']}'")

    # Fix location column (list values - fix each element)
    if 'location' in gdf_demand.columns:
        location_fixed = 0
        for idx in gdf_demand.index:
            loc_val = gdf_demand.loc[idx, 'location']
            if isinstance(loc_val, list):
                fixed_loc = [fix_truncated_hebrew(item) if isinstance(item, str) else item
                            for item in loc_val]
                if fixed_loc != loc_val:
                    location_fixed += 1
                    if location_fixed <= 3:  # Show first 3 examples
                        print(f"      '{loc_val}' -> '{fixed_loc}'")
                gdf_demand.at[idx, 'location'] = fixed_loc

        if location_fixed > 0:
            print(f"    ✓ Fixed {location_fixed} truncated values in 'location' column")

    print("  ✓ Hebrew text fix complete")
'''


def main():
    print("Loading COMPLETE_TRANSIT_PIPELINE.ipynb...")

    with open('COMPLETE_TRANSIT_PIPELINE.ipynb', 'r', encoding='utf-8') as f:
        nb = json.load(f)

    print(f"Notebook has {len(nb['cells'])} cells")

    # Find Cell 30 (the one with helper functions and tagging logic)
    target_cell_idx = None
    for i, cell in enumerate(nb['cells']):
        if cell.get('cell_type') == 'code':
            source = ''.join(cell.get('source', []))
            if 'def check_hebrew_truncation' in source and 'Step 2.3' in source:
                target_cell_idx = i
                print(f"Found target cell at index {i}")
                break

    if target_cell_idx is None:
        print("ERROR: Could not find Cell 30 with helper functions")
        return False

    # Get the cell source
    cell = nb['cells'][target_cell_idx]
    source_lines = cell['source']
    source_text = ''.join(source_lines)

    # Check if fix function already exists
    if 'def fix_truncated_hebrew(' in source_text:
        print("Fix function already exists - updating it...")
        # Remove old version
        lines = source_text.split('\n')
        new_lines = []
        skip = False
        for line in lines:
            if 'def fix_truncated_hebrew(' in line:
                skip = True
            elif skip and line and not line[0].isspace():
                # End of function
                skip = False

            if not skip:
                new_lines.append(line)

        source_text = '\n'.join(new_lines)

    # Find where to insert the fix function (before check_hebrew_truncation)
    lines = source_text.split('\n')
    insert_idx = None
    for i, line in enumerate(lines):
        if 'def check_hebrew_truncation(' in line:
            insert_idx = i
            print(f"Will insert fix function before line {i}")
            break

    if insert_idx is None:
        print("ERROR: Could not find insertion point")
        return False

    # Insert the fix function
    fix_lines = FIX_FUNCTION.split('\n')
    lines = lines[:insert_idx] + fix_lines + lines[insert_idx:]

    # Now find where to apply the fix (after the summary section, before "Step 2.3 complete")
    apply_idx = None
    for i, line in enumerate(lines):
        if '✓ Step 2.3 complete!' in line:
            apply_idx = i
            print(f"Will insert fix application before line {i}")
            break

    if apply_idx is None:
        print("WARNING: Could not find '✓ Step 2.3 complete!' - searching for alternative insertion point")
        # Look for the summary section
        for i, line in enumerate(lines):
            if 'Sample data verification:' in line:
                # Insert after the diagnostic section (look for next print statement group)
                for j in range(i, len(lines)):
                    if 'DIAGNOSTIC - After Step 2.3:' in lines[j]:
                        apply_idx = j
                        print(f"Will insert fix application before line {j}")
                        break
                break

    if apply_idx is None:
        print("ERROR: Could not find where to apply the fix")
        return False

    # Check if fix is already applied
    has_fix_applied = any('Fixing any truncated Hebrew text' in line for line in lines)

    if not has_fix_applied:
        # Insert the fix application code
        apply_lines = APPLY_FIX_CODE.split('\n')
        lines = lines[:apply_idx] + apply_lines + lines[apply_idx:]
        print("Inserted fix application code")
    else:
        print("Fix application code already exists")

    # Reconstruct the cell source
    new_source = '\n'.join(lines)

    # Convert back to list of lines (Jupyter format)
    # Each line should end with \n except the last one
    new_source_lines = []
    split_lines = new_source.split('\n')
    for i, line in enumerate(split_lines):
        if i < len(split_lines) - 1:
            new_source_lines.append(line + '\n')
        else:
            new_source_lines.append(line)

    # Update the cell
    nb['cells'][target_cell_idx]['source'] = new_source_lines

    # Save the notebook
    print("Saving modified notebook...")
    with open('COMPLETE_TRANSIT_PIPELINE.ipynb', 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

    print("✓ Successfully updated COMPLETE_TRANSIT_PIPELINE.ipynb")
    print("\nChanges made:")
    print("  1. Added fix_truncated_hebrew() function")
    print("  2. Added fix_truncated_hebrew_in_gdf() function")
    print("  3. Applied fix to area and location columns after tagging")
    print("\nThe fix will:")
    print("  - Repair 'גלעי' -> 'גלעין'")
    print("  - Repair 'טבעת פנימי' -> 'טבעת פנימית'")
    print("  - Repair other similar truncations")

    return True


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
