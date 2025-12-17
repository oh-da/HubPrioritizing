#!/usr/bin/env python3
"""
Quick diagnostic script to check area and location columns in CSV outputs.
Run this to see what's actually in the CSV files.
"""

import pandas as pd
import os
import glob

print("=" * 80)
print("CSV COLUMN DIAGNOSTIC TOOL")
print("=" * 80)

# Find all CSV files in common output locations
search_paths = [
    "data/processed/*.csv",
    "data/results/*.csv",
    "output/*.csv",
    "*.csv"
]

csv_files = []
for pattern in search_paths:
    csv_files.extend(glob.glob(pattern))

# Remove duplicates
csv_files = list(set(csv_files))

if not csv_files:
    print("\n⚠ No CSV files found in common locations.")
    print("Please specify the path to your grouped hubs CSV file.")
    exit(1)

print(f"\nFound {len(csv_files)} CSV files:")
for i, f in enumerate(csv_files, 1):
    print(f"  {i}. {f}")

# Check each file
for csv_file in csv_files:
    print("\n" + "=" * 80)
    print(f"FILE: {csv_file}")
    print("=" * 80)

    try:
        # Try different encodings
        for encoding in ['utf-8-sig', 'utf-8', 'windows-1255', 'cp1255']:
            try:
                df = pd.read_csv(csv_file, encoding=encoding, nrows=5)
                print(f"✓ Read successfully with encoding: {encoding}")
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        else:
            print(f"✗ Could not read file with any encoding")
            continue

        print(f"\nShape: {df.shape[0]} rows × {df.shape[1]} columns")
        print(f"\nColumns ({len(df.columns)}):")
        for col in df.columns:
            print(f"  - {col}")

        # Check for area column
        print("\n--- AREA COLUMN ---")
        if 'area' in df.columns:
            print(f"✓ 'area' column EXISTS")
            print(f"  Dtype: {df['area'].dtype}")
            print(f"  Non-null: {df['area'].notna().sum()}/{len(df)}")
            print(f"  Sample values:")
            for i, val in enumerate(df['area'].head(5)):
                print(f"    Row {i}: {repr(val)} (type: {type(val).__name__})")
        else:
            print("✗ 'area' column MISSING")

        # Check for location column
        print("\n--- LOCATION COLUMN ---")
        if 'location' in df.columns:
            print(f"✓ 'location' column EXISTS")
            print(f"  Dtype: {df['location'].dtype}")
            print(f"  Non-null: {df['location'].notna().sum()}/{len(df)}")
            print(f"  Sample values:")
            for i, val in enumerate(df['location'].head(5)):
                print(f"    Row {i}: {repr(val)} (type: {type(val).__name__})")
        else:
            print("✗ 'location' column MISSING")

        # Check for related columns
        print("\n--- RELATED COLUMNS ---")
        related = [c for c in df.columns if any(x in c.lower() for x in ['region', 'metro', 'district', 'zone'])]
        if related:
            print(f"Found {len(related)} related columns:")
            for col in related:
                print(f"  - {col}")
        else:
            print("No related geographic columns found")

    except Exception as e:
        print(f"✗ Error reading file: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
