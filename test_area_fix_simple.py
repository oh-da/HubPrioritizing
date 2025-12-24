#!/usr/bin/env python3
"""
Simple test script to verify that area column truncation fix works correctly.
Tests the fix logic without importing heavy dependencies.
"""

import re


def fix_truncated_hebrew(text: str) -> str:
    """
    Fix truncated Hebrew text by restoring missing final letters.
    (Copied from src/scoring/location.py for testing)
    """
    if not isinstance(text, str) or not text:
        return text

    # Known truncation fixes
    fixes = {
        # Location/position truncations
        'גלעי': 'גלעין',
        'טבעת פנימי': 'טבעת פנימית',
        'טבעת חיצוני': 'טבעת חיצונית',
        'טבעת תיכונ': 'טבעת תיכונה',
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

    # Check for pattern matches (word boundaries)
    for truncated, fixed in fixes.items():
        if re.search(r'\b' + re.escape(truncated) + r'\b', text_stripped):
            text_stripped = re.sub(r'\b' + re.escape(truncated) + r'\b', fixed, text_stripped)

    return text_stripped


def test_fix_truncated_hebrew():
    """Test the fix_truncated_hebrew function with known truncations."""

    test_cases = [
        # (input, expected_output, description)
        ('תל אבי', 'תל אביב', 'Tel Aviv truncation'),
        ('מרכ', 'מרכז', 'Center truncation'),
        ('צפו', 'צפון', 'North truncation'),
        ('דרו', 'דרום', 'South truncation'),
        ('חיפ', 'חיפה', 'Haifa truncation'),
        ('ירושלי', 'ירושלים', 'Jerusalem truncation'),
        ('באר שב', 'באר שבע', 'Beer Sheva truncation'),
        ('גלעי', 'גלעין', 'Core truncation'),
        ('טבעת פנימי', 'טבעת פנימית', 'Inner Ring truncation'),
        ('תל אביב', 'תל אביב', 'Already correct - no change'),
        ('מרכז', 'מרכז', 'Already correct - no change'),
    ]

    print("Testing fix_truncated_hebrew()...")
    print("=" * 70)

    all_passed = True
    for input_text, expected, description in test_cases:
        result = fix_truncated_hebrew(input_text)
        passed = result == expected
        all_passed = all_passed and passed

        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} | {description}")
        print(f"      Input:    '{input_text}'")
        print(f"      Expected: '{expected}'")
        print(f"      Got:      '{result}'")
        if not passed:
            print(f"      ERROR: Mismatch!")
        print()

    return all_passed


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("AREA COLUMN PARSING FIX - SIMPLE TEST")
    print("=" * 70 + "\n")

    # Run test
    all_passed = test_fix_truncated_hebrew()

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    if all_passed:
        print("\n✓✓✓ ALL TESTS PASSED ✓✓✓\n")
        print("The fix_truncated_hebrew() function correctly handles:")
        print("  • תל אבי → תל אביב (Tel Aviv)")
        print("  • מרכ → מרכז (Center)")
        print("  • All other region name truncations")
        print("\nThis should resolve the Region score issue where all scores")
        print("were 1 instead of 0 for Tel Aviv and Center regions.")
        exit(0)
    else:
        print("\n✗✗✗ SOME TESTS FAILED ✗✗✗\n")
        exit(1)
