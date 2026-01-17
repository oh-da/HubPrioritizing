#!/usr/bin/env python3
"""
List Versions CLI Tool
======================
List all versions of data, runs, or model code with optional filtering.

Usage:
    python list_versions.py --type data
    python list_versions.py --type runs --limit 10
    python list_versions.py --type runs --tag production
    python list_versions.py --type data --data-type transit_lines
"""

import argparse
import json
import sys
from pathlib import Path
from tabulate import tabulate

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.versioning import VersionStore


def format_data_versions(versions, verbose=False):
    """Format data versions for display."""
    if not versions:
        return "No data versions found."

    rows = []
    for v in versions:
        row = [
            v['data_version_id'],
            v['data_type'],
            v['created_at'][:16],  # Truncate timestamp
            v.get('record_count', 'N/A'),
            v.get('created_by', 'N/A')
        ]
        if verbose:
            row.extend([
                v.get('notes', '')[:50],  # Truncate notes
                ', '.join(v.get('tags', []))
            ])
        rows.append(row)

    headers = ['Version ID', 'Data Type', 'Created At', 'Records', 'Created By']
    if verbose:
        headers.extend(['Notes', 'Tags'])

    return tabulate(rows, headers=headers, tablefmt='grid')


def format_run_versions(versions, verbose=False):
    """Format run versions for display."""
    if not versions:
        return "No run versions found."

    rows = []
    for v in versions:
        row = [
            v['run_version_id'],
            v.get('run_number', 'N/A'),
            v.get('model_version', {}).get('code_version', 'N/A'),
            v['created_at'][:16],
            v.get('status', 'N/A'),
            v.get('created_by', 'N/A')
        ]
        if verbose:
            row.extend([
                f"{v.get('execution_time_seconds', 0):.1f}s",
                v.get('run_purpose', '')[:30],
                ', '.join(v.get('tags', []))
            ])
        rows.append(row)

    headers = ['Run ID', '#', 'Model Ver', 'Created At', 'Status', 'Created By']
    if verbose:
        headers.extend(['Time', 'Purpose', 'Tags'])

    return tabulate(rows, headers=headers, tablefmt='grid')


def main():
    parser = argparse.ArgumentParser(
        description='List versions of data, runs, or model code'
    )

    parser.add_argument(
        '--type',
        choices=['data', 'runs', 'model'],
        required=True,
        help='Type of versions to list'
    )

    parser.add_argument(
        '--data-type',
        help='Filter data versions by type (e.g., transit_lines)'
    )

    parser.add_argument(
        '--status',
        help='Filter run versions by status (created, running, completed, failed)'
    )

    parser.add_argument(
        '--tag',
        action='append',
        help='Filter by tag (can specify multiple times)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of results'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed information'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    args = parser.parse_args()

    # Initialize version store
    store = VersionStore()

    # Get versions
    if args.type == 'data':
        versions = store.list_data_versions(
            data_type=args.data_type,
            limit=args.limit,
            tags=args.tag
        )

        if args.json:
            print(json.dumps(versions, indent=2, ensure_ascii=False))
        else:
            print(format_data_versions(versions, args.verbose))
            print(f"\nTotal: {len(versions)} version(s)")

    elif args.type == 'runs':
        versions = store.list_run_versions(
            status=args.status,
            limit=args.limit,
            tags=args.tag
        )

        if args.json:
            print(json.dumps(versions, indent=2, ensure_ascii=False))
        else:
            print(format_run_versions(versions, args.verbose))
            print(f"\nTotal: {len(versions)} run(s)")

    elif args.type == 'model':
        # Model versions - would need to implement list functionality
        print("Model version listing not yet implemented")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
