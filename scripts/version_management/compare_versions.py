#!/usr/bin/env python3
"""
Compare Versions CLI Tool
==========================
Compare two versions and generate a comparison report.

Usage:
    python compare_versions.py --type data --version1 DATA1 --version2 DATA2
    python compare_versions.py --type runs --version1 RUN1 --version2 RUN2 --output report.html
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.versioning import VersionStore, compare_data_versions, compare_run_versions


def print_data_comparison(comparison):
    """Print data version comparison in human-readable format."""
    print("\n" + "=" * 80)
    print("DATA VERSION COMPARISON")
    print("=" * 80)

    print(f"\nVersion 1: {comparison['version1']['id']}")
    print(f"  Created: {comparison['version1']['created_at']}")
    print(f"  Records: {comparison['version1']['record_count']}")

    print(f"\nVersion 2: {comparison['version2']['id']}")
    print(f"  Created: {comparison['version2']['created_at']}")
    print(f"  Records: {comparison['version2']['record_count']}")

    if comparison['record_count_change'] is not None:
        print(f"\nRecord count change: {comparison['record_count_change']:+d}")

    if comparison.get('detailed'):
        print("\n" + "-" * 80)
        print("DETAILED CHANGES")
        print("-" * 80)

        detailed = comparison['detailed']

        if 'added_count' in detailed:
            print(f"\nAdded: {detailed['added_count']}")
            if detailed.get('added') and len(detailed['added']) <= 10:
                for item in detailed['added']:
                    print(f"  + {item}")
            elif detailed.get('added'):
                print(f"  (Showing first 10 of {len(detailed['added'])})")
                for item in list(detailed['added'])[:10]:
                    print(f"  + {item}")

        if 'removed_count' in detailed:
            print(f"\nRemoved: {detailed['removed_count']}")
            if detailed.get('removed') and len(detailed['removed']) <= 10:
                for item in detailed['removed']:
                    print(f"  - {item}")
            elif detailed.get('removed'):
                print(f"  (Showing first 10 of {len(detailed['removed'])})")
                for item in list(detailed['removed'])[:10]:
                    print(f"  - {item}")

        if 'modified_count' in detailed:
            print(f"\nModified: {detailed['modified_count']}")
            if detailed.get('modified') and len(detailed['modified']) <= 10:
                for mod in detailed['modified']:
                    print(f"  ~ {mod}")

        if 'significant_changes_count' in detailed:
            print(f"\nSignificant demand changes (>10%): {detailed['significant_changes_count']}")

    print("\n" + "=" * 80)


def print_run_comparison(comparison):
    """Print run version comparison in human-readable format."""
    print("\n" + "=" * 80)
    print("MODEL RUN COMPARISON")
    print("=" * 80)

    print(f"\nRun 1: {comparison['run1']['id']}")
    print(f"  Created: {comparison['run1']['created_at']}")
    print(f"  Model version: {comparison['run1']['model_version']}")
    print(f"  Status: {comparison['run1']['status']}")

    print(f"\nRun 2: {comparison['run2']['id']}")
    print(f"  Created: {comparison['run2']['created_at']}")
    print(f"  Model version: {comparison['run2']['model_version']}")
    print(f"  Status: {comparison['run2']['status']}")

    # Configuration differences
    if comparison['config_differences']:
        print("\n" + "-" * 80)
        print("CONFIGURATION DIFFERENCES")
        print("-" * 80)
        for key, diff in comparison['config_differences'].items():
            print(f"\n{key}:")
            print(f"  Run 1: {diff['run1']}")
            print(f"  Run 2: {diff['run2']}")

    # Data version differences
    if comparison['data_version_differences']:
        print("\n" + "-" * 80)
        print("DATA VERSION DIFFERENCES")
        print("-" * 80)
        for data_type, diff in comparison['data_version_differences'].items():
            print(f"\n{data_type}:")
            print(f"  Run 1: {diff['run1']}")
            print(f"  Run 2: {diff['run2']}")

    # Results differences
    if comparison['results_differences']:
        print("\n" + "-" * 80)
        print("RESULTS DIFFERENCES")
        print("-" * 80)

        results = comparison['results_differences']

        if 'total_hubs_change' in results:
            print(f"\nTotal hubs change: {results['total_hubs_change']:+d}")

        if 'tier_changes' in results and results['tier_changes']:
            print("\nHubs by tier:")
            for tier, change in results['tier_changes'].items():
                print(f"  {tier}: {change['run1']} → {change['run2']} ({change['change']:+d})")

        if 'area_changes' in results and results['area_changes']:
            print("\nHubs by area:")
            for area, change in results['area_changes'].items():
                print(f"  {area}: {change['run1']} → {change['run2']} ({change['change']:+d})")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Compare two versions (data or runs)'
    )

    parser.add_argument(
        '--type',
        choices=['data', 'runs'],
        required=True,
        help='Type of versions to compare'
    )

    parser.add_argument(
        '--version1',
        required=True,
        help='First version ID'
    )

    parser.add_argument(
        '--version2',
        required=True,
        help='Second version ID'
    )

    parser.add_argument(
        '--output',
        help='Output file path (for HTML/JSON report)'
    )

    parser.add_argument(
        '--format',
        choices=['text', 'json', 'html'],
        default='text',
        help='Output format'
    )

    args = parser.parse_args()

    # Initialize version store
    store = VersionStore()

    # Perform comparison
    try:
        if args.type == 'data':
            comparison = compare_data_versions(args.version1, args.version2, store)

            if args.format == 'json':
                output = json.dumps(comparison, indent=2, ensure_ascii=False)
                if args.output:
                    Path(args.output).write_text(output, encoding='utf-8')
                else:
                    print(output)
            else:
                print_data_comparison(comparison)

        elif args.type == 'runs':
            comparison = compare_run_versions(args.version1, args.version2, store)

            if args.format == 'json':
                output = json.dumps(comparison, indent=2, ensure_ascii=False)
                if args.output:
                    Path(args.output).write_text(output, encoding='utf-8')
                else:
                    print(output)
            else:
                print_run_comparison(comparison)

        if args.output and args.format == 'text':
            print(f"\nNote: Text output not saved to file. Use --format json for file output.")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
