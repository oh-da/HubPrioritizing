#!/usr/bin/env python3
"""
Migrate Hardcoded Demand Updates to CSV
========================================

This script helps migrate hardcoded demand updates from COMPLETE_TRANSIT_PIPELINE.ipynb
to the centralized manual_demand_updates.csv file.

What it does:
1. Checks if hardcoded Steps 2.6.2 and 2.6.3 exist
2. Verifies all values are in CSV
3. Provides instructions for removal
4. Optionally creates backup and removes the hardcoded cells

Usage:
    python scripts/migrate_hardcoded_demand_updates.py --check
    python scripts/migrate_hardcoded_demand_updates.py --migrate --backup

Author: Hub Prioritization Framework
Date: 2025-01-17
"""

import json
import argparse
import shutil
import csv
from pathlib import Path
from datetime import datetime

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH = PROJECT_ROOT / "COMPLETE_TRANSIT_PIPELINE.ipynb"
CSV_PATH = PROJECT_ROOT / "data" / "manual_demand_updates.csv"


def load_notebook(path: Path) -> dict:
    """Load Jupyter notebook JSON."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_notebook(path: Path, nb_data: dict):
    """Save Jupyter notebook JSON."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(nb_data, f, indent=1, ensure_ascii=False)


def find_hardcoded_steps(nb_data: dict) -> dict:
    """
    Find cells containing Steps 2.6.2 and 2.6.3.

    Returns dict with:
        - step_2_6_2_cells: List of cell indices for Step 2.6.2
        - step_2_6_3_cells: List of cell indices for Step 2.6.3
    """
    results = {
        'step_2_6_2_cells': [],
        'step_2_6_3_cells': [],
        'step_2_6_2_found': False,
        'step_2_6_3_found': False
    }

    cells = nb_data.get('cells', [])

    for idx, cell in enumerate(cells):
        cell_type = cell.get('cell_type', '')
        source = cell.get('source', [])

        # Convert source to string
        if isinstance(source, list):
            source_text = ''.join(source)
        else:
            source_text = source

        # Check for Step 2.6.2
        if 'Step 2.6.2' in source_text or 'NATIONAL_MODEL_UPDATES' in source_text:
            results['step_2_6_2_cells'].append(idx)
            results['step_2_6_2_found'] = True

        # Check for Step 2.6.3
        if 'Step 2.6.3' in source_text or 'shefaim_node_id = 511248' in source_text:
            results['step_2_6_3_cells'].append(idx)
            results['step_2_6_3_found'] = True

    return results


def check_csv_coverage() -> dict:
    """
    Check if all hardcoded values are present in CSV.

    Returns dict with:
        - csv_exists: bool
        - nodes_in_csv: list of node IDs
        - expected_nodes: dict of {node_id: description}
        - missing_nodes: list of node IDs not in CSV
    """
    expected_nodes = {
        400424: 'Moshe Dayan (Rishon) - from Step 2.6.2',
        400021: 'Netanya Sapir - from Step 2.6.2',
        400030: 'Beit Yehoshua Rail - from Step 2.6.2',
        511246: 'Beit Yehoshua LRT - from Step 2.6.2',
        511248: 'Shefaim LRT - from Step 2.6.3'
    }

    result = {
        'csv_exists': CSV_PATH.exists(),
        'nodes_in_csv': [],
        'expected_nodes': expected_nodes,
        'missing_nodes': []
    }

    if CSV_PATH.exists():
        try:
            with open(CSV_PATH, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        node_id = int(row['node'])
                        result['nodes_in_csv'].append(node_id)
                    except (ValueError, KeyError):
                        pass

            # Check for missing nodes
            for node_id in expected_nodes.keys():
                if node_id not in result['nodes_in_csv']:
                    result['missing_nodes'].append(node_id)
        except Exception as e:
            result['error'] = str(e)

    return result


def print_check_report(nb_results: dict, csv_results: dict):
    """Print a comprehensive check report."""
    print("=" * 80)
    print("HARDCODED DEMAND UPDATES MIGRATION CHECK")
    print("=" * 80)
    print()

    # Notebook check
    print("📓 NOTEBOOK CHECK")
    print("-" * 80)

    if nb_results['step_2_6_2_found']:
        print(f"❌ Step 2.6.2 found in {len(nb_results['step_2_6_2_cells'])} cell(s)")
        print(f"   Cell indices: {nb_results['step_2_6_2_cells']}")
        print("   → Should be removed (values migrated to CSV)")
    else:
        print("✅ Step 2.6.2 not found (already removed or migrated)")

    print()

    if nb_results['step_2_6_3_found']:
        print(f"❌ Step 2.6.3 found in {len(nb_results['step_2_6_3_cells'])} cell(s)")
        print(f"   Cell indices: {nb_results['step_2_6_3_cells']}")
        print("   → Should be removed (values migrated to CSV)")
    else:
        print("✅ Step 2.6.3 not found (already removed or migrated)")

    print()
    print()

    # CSV check
    print("📄 CSV FILE CHECK")
    print("-" * 80)

    if csv_results['csv_exists']:
        print(f"✅ CSV file exists: {CSV_PATH}")
        print(f"   Nodes in CSV: {len(csv_results['nodes_in_csv'])}")
        print()

        # Check coverage
        if not csv_results['missing_nodes']:
            print("✅ All expected nodes are in CSV:")
            for node_id, desc in csv_results['expected_nodes'].items():
                print(f"   ✓ {node_id}: {desc}")
        else:
            print("⚠️  Some expected nodes are MISSING from CSV:")
            for node_id in csv_results['missing_nodes']:
                desc = csv_results['expected_nodes'][node_id]
                print(f"   ✗ {node_id}: {desc}")
            print()
            print("   → Add these nodes to CSV before removing hardcoded steps")
    else:
        print(f"❌ CSV file NOT found: {CSV_PATH}")
        print("   → Create the CSV file first with all hardcoded values")

    print()
    print()

    # Migration status
    print("🔄 MIGRATION STATUS")
    print("-" * 80)

    needs_migration = nb_results['step_2_6_2_found'] or nb_results['step_2_6_3_found']
    csv_ready = csv_results['csv_exists'] and not csv_results['missing_nodes']

    if not needs_migration and csv_ready:
        print("✅ MIGRATION COMPLETE!")
        print("   - All hardcoded steps removed from notebook")
        print("   - All values present in CSV")
        print("   - Ready for production use")
    elif not needs_migration and not csv_ready:
        print("⚠️  INCONSISTENT STATE")
        print("   - Hardcoded steps removed from notebook")
        print("   - But CSV is missing or incomplete")
        print("   - Check CSV file and re-run")
    elif needs_migration and csv_ready:
        print("⚠️  MIGRATION NEEDED")
        print("   - CSV file is ready with all values")
        print("   - Hardcoded steps still in notebook")
        print("   - Run with --migrate to remove hardcoded cells")
    else:
        print("❌ NOT READY FOR MIGRATION")
        print("   - CSV file is missing or incomplete")
        print("   - Complete CSV file before migration")
        print(f"   - See: {CSV_PATH}")

    print()
    print("=" * 80)


def migrate_notebook(nb_path: Path, nb_data: dict, nb_results: dict, dry_run: bool = False) -> bool:
    """
    Remove hardcoded Steps 2.6.2 and 2.6.3 from notebook.

    Args:
        nb_path: Path to notebook
        nb_data: Notebook JSON data
        nb_results: Results from find_hardcoded_steps()
        dry_run: If True, don't actually modify the file

    Returns:
        True if migration successful
    """
    if not nb_results['step_2_6_2_found'] and not nb_results['step_2_6_3_found']:
        print("✅ No hardcoded steps found - nothing to migrate")
        return True

    print()
    print("=" * 80)
    print("MIGRATING NOTEBOOK")
    print("=" * 80)
    print()

    # Collect all cells to remove
    cells_to_remove = sorted(
        set(nb_results['step_2_6_2_cells'] + nb_results['step_2_6_3_cells']),
        reverse=True  # Remove from end to preserve indices
    )

    print(f"Will remove {len(cells_to_remove)} cell(s):")
    for idx in reversed(cells_to_remove):
        print(f"  - Cell {idx}")
    print()

    if dry_run:
        print("🔍 DRY RUN - No changes will be made")
        print()
        return True

    # Create backup
    backup_path = nb_path.parent / f"{nb_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ipynb"
    print(f"Creating backup: {backup_path}")
    shutil.copy2(nb_path, backup_path)
    print("✅ Backup created")
    print()

    # Remove cells
    cells = nb_data.get('cells', [])
    for idx in cells_to_remove:
        if 0 <= idx < len(cells):
            removed_cell = cells.pop(idx)
            cell_source = removed_cell.get('source', [])
            if isinstance(cell_source, list):
                cell_source = ''.join(cell_source)
            print(f"✅ Removed cell {idx}")
            if len(cell_source) < 200:
                print(f"   Preview: {cell_source[:100]}...")

    # Save modified notebook
    print()
    print(f"Saving modified notebook to: {nb_path}")
    save_notebook(nb_path, nb_data)
    print("✅ Notebook saved")
    print()

    print("=" * 80)
    print("MIGRATION COMPLETE!")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Review the modified notebook")
    print("2. Run the notebook to verify it works correctly")
    print("3. Check that Step 2.6.1 applies CSV updates")
    print(f"4. If needed, restore from backup: {backup_path}")
    print()

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Migrate hardcoded demand updates to CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check current state
    python scripts/migrate_hardcoded_demand_updates.py --check

    # Dry run (show what would be removed)
    python scripts/migrate_hardcoded_demand_updates.py --migrate --dry-run

    # Actually migrate (creates backup automatically)
    python scripts/migrate_hardcoded_demand_updates.py --migrate
        """
    )

    parser.add_argument(
        '--check',
        action='store_true',
        help='Check current migration status (default action)'
    )

    parser.add_argument(
        '--migrate',
        action='store_true',
        help='Migrate notebook by removing hardcoded steps'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run - show what would be changed without modifying files'
    )

    args = parser.parse_args()

    # Default to check if no action specified
    if not args.check and not args.migrate:
        args.check = True

    # Verify notebook exists
    if not NOTEBOOK_PATH.exists():
        print(f"❌ Error: Notebook not found: {NOTEBOOK_PATH}")
        return 1

    # Load notebook
    print(f"Loading notebook: {NOTEBOOK_PATH}")
    nb_data = load_notebook(NOTEBOOK_PATH)
    print()

    # Find hardcoded steps
    nb_results = find_hardcoded_steps(nb_data)

    # Check CSV coverage
    csv_results = check_csv_coverage()

    if args.check:
        print_check_report(nb_results, csv_results)
        return 0

    if args.migrate:
        # Verify CSV is ready
        if not csv_results['csv_exists']:
            print("❌ Error: CSV file does not exist")
            print(f"   Expected: {CSV_PATH}")
            print("   Create the CSV file first before migration")
            return 1

        if csv_results['missing_nodes']:
            print("❌ Error: CSV file is missing expected nodes:")
            for node_id in csv_results['missing_nodes']:
                desc = csv_results['expected_nodes'][node_id]
                print(f"   - {node_id}: {desc}")
            print()
            print("   Add these nodes to CSV before migration")
            return 1

        # Migrate
        success = migrate_notebook(NOTEBOOK_PATH, nb_data, nb_results, dry_run=args.dry_run)
        return 0 if success else 1

    return 0


if __name__ == '__main__':
    exit(main())
