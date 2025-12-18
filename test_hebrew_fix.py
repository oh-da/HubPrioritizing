#!/usr/bin/env python3
"""
Test Hebrew truncation fix
"""

import sys
sys.path.insert(0, '/home/user/HubPrioritizing/src')

from scoring.location import fix_truncated_hebrew, get_metro_position_weight
from config import METRO_POSITION_WEIGHTS

def test_fix_truncated_hebrew():
    """Test the fix_truncated_hebrew function"""
    print("Testing fix_truncated_hebrew()...")

    test_cases = [
        ('גלעי', 'גלעין'),
        ('טבעת פנימי', 'טבעת פנימית'),
        ('טבעת חיצוני', 'טבעת חיצונית'),
        ('טבעת תיכונ', 'טבעת תיכונה'),
        ('טבעת', 'טבעת'),  # Should not change
        ('גלעין', 'גלעין'),  # Should not change
        (None, None),  # Should handle None
        ('', ''),  # Should handle empty string
    ]

    all_passed = True
    for input_text, expected in test_cases:
        result = fix_truncated_hebrew(input_text)
        passed = result == expected
        status = "✓" if passed else "✗"
        print(f"  {status} fix_truncated_hebrew('{input_text}') = '{result}' (expected: '{expected}')")
        if not passed:
            all_passed = False

    return all_passed


def test_get_metro_position_weight():
    """Test that truncated values get correct weights"""
    print("\nTesting get_metro_position_weight() with truncated values...")

    test_cases = [
        ('גלעי', 3),  # Truncated Core should map to 3
        ('גלעין', 3),  # Proper Core should map to 3
        ('טבעת פנימי', 2),  # Truncated Inner Ring should map to 2
        ('טבעת פנימית', 2),  # Proper Inner Ring should map to 2
        ('טבעת חיצוני', 2),  # Truncated Outer Ring should map to 2
        ('טבעת חיצונית', 2),  # Proper Outer Ring should map to 2
        ('טבעת', 2),  # Ring should map to 2
        ('Unknown', 1.5),  # Unknown should default to 1.5
    ]

    all_passed = True
    for input_text, expected in test_cases:
        result = get_metro_position_weight(input_text)
        passed = result == expected
        status = "✓" if passed else "✗"
        print(f"  {status} get_metro_position_weight('{input_text}') = {result} (expected: {expected})")
        if not passed:
            all_passed = False

    return all_passed


def test_config_coverage():
    """Test that config has all the necessary entries"""
    print("\nTesting config.py METRO_POSITION_WEIGHTS coverage...")

    required_entries = [
        'גלעין',
        'טבעת',
        'טבעת פנימית',
        'טבעת חיצונית',
        'טבעת תיכונה',
    ]

    all_passed = True
    for entry in required_entries:
        if entry in METRO_POSITION_WEIGHTS:
            print(f"  ✓ '{entry}' -> {METRO_POSITION_WEIGHTS[entry]}")
        else:
            print(f"  ✗ '{entry}' missing from METRO_POSITION_WEIGHTS")
            all_passed = False

    return all_passed


def main():
    print("=" * 60)
    print("Hebrew Truncation Fix Tests")
    print("=" * 60)

    test1_passed = test_fix_truncated_hebrew()
    test2_passed = test_get_metro_position_weight()
    test3_passed = test_config_coverage()

    print("\n" + "=" * 60)
    if test1_passed and test2_passed and test3_passed:
        print("✓ All tests PASSED")
        print("=" * 60)
        return 0
    else:
        print("✗ Some tests FAILED")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
