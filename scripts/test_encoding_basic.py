#!/usr/bin/env python3
"""
Basic test script for encoding detection and Hebrew validation.

Run with: python scripts/test_encoding_basic.py
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.encoding_fix import is_valid_hebrew_text


def test_valid_hebrew():
    """Test valid Hebrew text."""
    print("\n=== Testing Valid Hebrew ===")

    test_cases = [
        ("תל אביב", True, "Pure Hebrew (Tel Aviv)"),
        ("חיפה", True, "Pure Hebrew (Haifa)"),
        ("ירושלים", True, "Pure Hebrew (Jerusalem)"),
        ("Tel Aviv - תל אביב", True, "Mixed Hebrew and English"),
    ]

    passed = 0
    failed = 0

    for text, expected, description in test_cases:
        result = is_valid_hebrew_text(text)
        status = "✓ PASS" if result == expected else "✗ FAIL"

        print(f"{status}: {description}")
        print(f"       Text: '{text}'")
        print(f"       Expected: {expected}, Got: {result}")

        if result == expected:
            passed += 1
        else:
            failed += 1

    print(f"\nValid Hebrew Tests: {passed} passed, {failed} failed")
    return failed == 0


def test_invalid_hebrew():
    """Test invalid/garbled Hebrew text."""
    print("\n=== Testing Invalid/Garbled Hebrew ===")

    test_cases = [
        ("'¬–¥–ª–™–__'", False, "Garbled text pattern 1"),
        ("₪˜™–__", False, "Garbled text pattern 2"),
        ("–ª–™–", False, "Garbled text pattern 3"),
        ("!@#$%^&*()", False, "Special characters only"),
        ("Tel Aviv", False, "Pure English (no Hebrew)"),
        ("Haifa", False, "Pure English (no Hebrew)"),
    ]

    passed = 0
    failed = 0

    for text, expected, description in test_cases:
        result = is_valid_hebrew_text(text)
        status = "✓ PASS" if result == expected else "✗ FAIL"

        print(f"{status}: {description}")
        print(f"       Text: '{text}'")
        print(f"       Expected: {expected}, Got: {result}")

        if result == expected:
            passed += 1
        else:
            failed += 1

    print(f"\nInvalid Hebrew Tests: {passed} passed, {failed} failed")
    return failed == 0


def test_edge_cases():
    """Test edge cases."""
    print("\n=== Testing Edge Cases ===")

    test_cases = [
        ("", True, "Empty string"),
        ("   ", True, "Whitespace only"),
        (None, True, "None value"),
    ]

    passed = 0
    failed = 0

    for text, expected, description in test_cases:
        result = is_valid_hebrew_text(text)
        status = "✓ PASS" if result == expected else "✗ FAIL"

        print(f"{status}: {description}")
        print(f"       Text: {text!r}")
        print(f"       Expected: {expected}, Got: {result}")

        if result == expected:
            passed += 1
        else:
            failed += 1

    print(f"\nEdge Case Tests: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all tests."""
    print("="*80)
    print("ENCODING FIX - BASIC TEST SUITE")
    print("="*80)

    all_passed = True

    # Run tests
    all_passed &= test_valid_hebrew()
    all_passed &= test_invalid_hebrew()
    all_passed &= test_edge_cases()

    # Summary
    print("\n" + "="*80)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("="*80 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
