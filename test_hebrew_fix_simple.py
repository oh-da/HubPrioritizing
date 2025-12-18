#!/usr/bin/env python3
"""
Simple test for Hebrew truncation fix (no dependencies)
"""

import re

def fix_truncated_hebrew(text):
    """
    Fix truncated Hebrew text by restoring missing final letters.
    """
    if not isinstance(text, str) or not text:
        return text

    # Known truncation fixes
    fixes = {
        'גלעי': 'גלעין',
        'טבעת פנימי': 'טבעת פנימית',
        'טבעת חיצוני': 'טבעת חיצונית',
        'טבעת תיכונ': 'טבעת תיכונה',
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
        ('  גלעי  ', 'גלעין'),  # Should handle whitespace
        ('תל אביב גלעי', 'תל אביב גלעין'),  # Should work in phrases
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


def main():
    print("=" * 60)
    print("Hebrew Truncation Fix Tests")
    print("=" * 60)
    print()

    test_passed = test_fix_truncated_hebrew()

    print()
    print("=" * 60)
    if test_passed:
        print("✓ All tests PASSED")
        print("=" * 60)
        return 0
    else:
        print("✗ Some tests FAILED")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
