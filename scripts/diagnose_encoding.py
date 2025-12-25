#!/usr/bin/env python3
"""
Diagnostic script to identify encoding issues in shapefiles.

Run this script to diagnose encoding problems with your metro and districts shapefiles.

Usage:
    python scripts/diagnose_encoding.py
"""

import sys
import os
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.encoding_fix import diagnose_encoding_issue


def main():
    """Run encoding diagnosis on configured shapefiles."""

    print("\n" + "="*80)
    print("SHAPEFILE ENCODING DIAGNOSTIC TOOL")
    print("="*80 + "\n")

    print("This script will help you identify encoding issues in your shapefiles.")
    print("It will try multiple encodings and show you exactly what text is being read.\n")

    # Get shapefile paths from user
    print("Enter the path to your METRO shapefile:")
    metro_path = input("> ").strip()

    print("\nEnter the path to your DISTRICTS shapefile:")
    districts_path = input("> ").strip()

    # Diagnose metro shapefile
    if os.path.exists(metro_path):
        print("\n" + "="*80)
        print("DIAGNOSING METRO SHAPEFILE")
        print("="*80)

        expected_columns = ['METRO_NAME', 'ZONE_NAME', 'MetroName', 'ZoneName', 'NAME', 'SHEM']
        diagnose_encoding_issue(metro_path, expected_columns)

    else:
        print(f"\n✗ Metro shapefile not found: {metro_path}")

    # Diagnose districts shapefile
    if os.path.exists(districts_path):
        print("\n" + "="*80)
        print("DIAGNOSING DISTRICTS SHAPEFILE")
        print("="*80)

        expected_columns = ['MACHOZ', 'SHEM_MACHOZ', 'SHEM_NAFA', 'District', 'NAME', 'SHEM']
        diagnose_encoding_issue(districts_path, expected_columns)

    else:
        print(f"\n✗ Districts shapefile not found: {districts_path}")

    print("\n" + "="*80)
    print("DIAGNOSIS COMPLETE")
    print("="*80)
    print("\nReview the output above to identify:")
    print("1. Which encoding shows proper Hebrew characters (not gibberish)")
    print("2. Any columns that contain invalid/garbled text")
    print("\nIf you found the correct encoding, you can specify it in the notebook")
    print("by setting FORCE_METRO_ENCODING and FORCE_DISTRICTS_ENCODING variables.\n")


if __name__ == "__main__":
    main()
