#!/usr/bin/env python3
"""
Update the fix_truncated_hebrew() function in COMPLETE_TRANSIT_PIPELINE.ipynb
to include area/region name fixes.
"""

import json
import re

# The updated fix function
NEW_FIX_FUNCTION = '''    def fix_truncated_hebrew(text):
        """
        Fix truncated Hebrew text by restoring the missing final letter.

        Common truncations:
        - 'גלעי' -> 'גלעין' (Core)
        - 'טבעת פנימי' -> 'טבעת פנימית' (Inner Ring)
        - 'טבעת חיצוני' -> 'טבעת חיצונית' (Outer Ring)
        - 'טבעת תיכונ' -> 'טבעת תיכונה' (Middle Ring)
        - 'תל אבי' -> 'תל אביב' (Tel Aviv - area name)
        - 'מרכ' -> 'מרכז' (Center - area name)
        - Other area name truncations

        Args:
            text: Hebrew text string that may be truncated

        Returns:
            Fixed Hebrew text with proper final letters
        """
        if not isinstance(text, str) or not text:
            return text

        # Known truncation fixes (simple dict approach - more reliable than regex)
        fixes = {
            # Location/position truncations
            'גלעי': 'גלעין',
            'טבעת פנימי': 'טבעת פנימית',
            'טבעת חיצוני': 'טבעת חיצונית',
            'טבעת תיכונ': 'טבעת תיכונה',
            'טבע': 'טבעת',  # Ring (if severely truncated)
            # Area/region name truncations
            'תל אבי': 'תל אביב',  # Tel Aviv
            'מרכ': 'מרכז',  # Center
            'צפו': 'צפון',  # North (if truncated)
            'דרו': 'דרום',  # South (if truncated)
            'חיפ': 'חיפה',  # Haifa (if truncated)
            'ירושלי': 'ירושלים',  # Jerusalem (if truncated)
            'באר שב': 'באר שבע',  # Beer Sheva (if truncated)
        }

        text_stripped = text.strip()

        # Check for exact matches first
        if text_stripped in fixes:
            return fixes[text_stripped]

        # Check for pattern matches (word boundaries) using simple string operations
        for truncated, fixed in fixes.items():
            # Use word boundary matching with simple string methods
            if re.search(r'\\b' + re.escape(truncated) + r'\\b', text_stripped):
                text_stripped = re.sub(r'\\b' + re.escape(truncated) + r'\\b', fixed, text_stripped)

        return text_stripped
'''


def main():
    print("Loading COMPLETE_TRANSIT_PIPELINE.ipynb...")

    with open('COMPLETE_TRANSIT_PIPELINE.ipynb', 'r', encoding='utf-8') as f:
        nb = json.load(f)

    print(f"Notebook has {len(nb['cells'])} cells")

    # Find the cell with fix_truncated_hebrew function
    target_cell_idx = None
    for i, cell in enumerate(nb['cells']):
        if cell.get('cell_type') == 'code':
            source = ''.join(cell.get('source', []))
            if 'def fix_truncated_hebrew(text):' in source:
                target_cell_idx = i
                print(f"Found fix_truncated_hebrew function in cell {i}")
                break

    if target_cell_idx is None:
        print("ERROR: Could not find cell with fix_truncated_hebrew function")
        return False

    # Get the cell
    cell = nb['cells'][target_cell_idx]
    source_lines = cell['source']
    source_text = ''.join(source_lines)

    # Find the function definition and replace it
    lines = source_text.split('\n')
    new_lines = []
    in_function = False
    function_indent = None
    skip_until_next_def = False

    for i, line in enumerate(lines):
        if 'def fix_truncated_hebrew(text):' in line:
            # Found the start of the function - insert new version
            function_indent = len(line) - len(line.lstrip())
            new_lines.append(line)  # Keep the def line
            in_function = True
            skip_until_next_def = True
            continue

        if skip_until_next_def:
            # Check if we've reached the next function or end of indentation
            if line.strip() and not line.startswith(' ' * function_indent + ' '):
                # We've exited the function
                skip_until_next_def = False
                in_function = False
                # Insert the new function body before this line
                new_function_lines = NEW_FIX_FUNCTION.strip().split('\n')[1:]  # Skip 'def' line
                for func_line in new_function_lines:
                    new_lines.append(func_line + '\n')
                new_lines.append(line)
            elif 'def ' in line and line.strip().startswith('def ') and 'def fix_truncated_hebrew' not in line:
                # Reached next function definition
                skip_until_next_def = False
                in_function = False
                # Insert the new function body before this line
                new_function_lines = NEW_FIX_FUNCTION.strip().split('\n')[1:]  # Skip 'def' line
                for func_line in new_function_lines:
                    new_lines.append(func_line + '\n')
                new_lines.append(line)
            # Skip old function body lines
            continue
        else:
            new_lines.append(line)

    # Reconstruct the cell source
    new_source = '\n'.join(new_lines)

    # Convert back to Jupyter format (list of lines with \n)
    new_source_lines = []
    split_lines = new_source.split('\n')
    for i, line in enumerate(split_lines):
        if i < len(split_lines) - 1:
            new_source_lines.append(line + '\n')
        else:
            if line:  # Don't add empty last line
                new_source_lines.append(line)

    # Update the cell
    nb['cells'][target_cell_idx]['source'] = new_source_lines

    # Save the notebook
    print("Saving modified notebook...")
    with open('COMPLETE_TRANSIT_PIPELINE.ipynb', 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

    print("\n✓ Successfully updated COMPLETE_TRANSIT_PIPELINE.ipynb")
    print("\nChanges made:")
    print("  • Updated fix_truncated_hebrew() to include area name fixes")
    print("  • Added fixes for: תל אבי→תל אביב, מרכ→מרכז, and other regions")
    print("\nThe notebook will now correctly fix area column truncations when run.")

    return True


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
