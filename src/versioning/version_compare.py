"""
Version Comparison Tools
========================
Compare different versions and generate diff reports.
"""

import pandas as pd
from typing import Dict, Any, Optional
from pathlib import Path

from .version_store import VersionStore
from ..utils.logging import get_logger

logger = get_logger(__name__)


def compare_data_versions(
    version1_id: str,
    version2_id: str,
    store: Optional[VersionStore] = None
) -> Dict[str, Any]:
    """
    Compare two data versions.

    Args:
        version1_id: First version ID
        version2_id: Second version ID
        store: Version store instance

    Returns:
        Comparison dictionary
    """
    store = store or VersionStore()

    # Load metadata
    v1_meta = store.get_data_version(version1_id)
    v2_meta = store.get_data_version(version2_id)

    if not v1_meta or not v2_meta:
        raise ValueError("One or both versions not found")

    # Basic metadata comparison
    comparison = {
        'version1': {
            'id': version1_id,
            'created_at': v1_meta['created_at'],
            'record_count': v1_meta.get('record_count')
        },
        'version2': {
            'id': version2_id,
            'created_at': v2_meta['created_at'],
            'record_count': v2_meta.get('record_count')
        },
        'record_count_change': None,
        'summary': ''
    }

    # Compare record counts
    if v1_meta.get('record_count') and v2_meta.get('record_count'):
        change = v2_meta['record_count'] - v1_meta['record_count']
        comparison['record_count_change'] = change
        comparison['summary'] = f"Record count changed by {change:+d}"

    # Try to load and compare data if CSV
    try:
        from .data_version import DataVersion

        dv1 = DataVersion(v1_meta, store)
        dv2 = DataVersion(v2_meta, store)

        df1 = dv1.load_data()
        df2 = dv2.load_data()

        # Detailed comparison for specific data types
        data_type = v1_meta['data_type']

        if data_type == 'transit_lines' and 'line_id' in df1.columns and 'line_id' in df2.columns:
            comparison['detailed'] = compare_transit_lines(df1, df2)
        elif data_type == 'transit_stations' and 'node_id' in df1.columns and 'node_id' in df2.columns:
            comparison['detailed'] = compare_transit_stations(df1, df2)
        elif data_type == 'demand_2050' and 'node_id' in df1.columns and 'node_id' in df2.columns:
            comparison['detailed'] = compare_demand_data(df1, df2)

    except Exception as e:
        logger.warning(f"Could not perform detailed comparison: {e}")
        comparison['detailed'] = None

    return comparison


def compare_transit_lines(df1: pd.DataFrame, df2: pd.DataFrame) -> Dict[str, Any]:
    """Compare two transit lines datasets."""
    lines1 = set(df1['line_id'])
    lines2 = set(df2['line_id'])

    added = lines2 - lines1
    removed = lines1 - lines2
    common = lines1 & lines2

    # Check for modifications in common lines
    modified = []
    if len(common) > 0:
        # Compare key fields for common lines
        for line_id in common:
            row1 = df1[df1['line_id'] == line_id].iloc[0]
            row2 = df2[df2['line_id'] == line_id].iloc[0]

            changes = {}
            for col in ['mode', 'status', 'operational_year']:
                if col in df1.columns and col in df2.columns:
                    if row1[col] != row2[col]:
                        changes[col] = {'from': row1[col], 'to': row2[col]}

            if changes:
                modified.append({'line_id': line_id, 'changes': changes})

    return {
        'added': list(added),
        'removed': list(removed),
        'modified': modified,
        'added_count': len(added),
        'removed_count': len(removed),
        'modified_count': len(modified)
    }


def compare_transit_stations(df1: pd.DataFrame, df2: pd.DataFrame) -> Dict[str, Any]:
    """Compare two transit stations datasets."""
    nodes1 = set(df1['node_id'])
    nodes2 = set(df2['node_id'])

    added = nodes2 - nodes1
    removed = nodes1 - nodes2
    common = nodes1 & nodes2

    # Check for coordinate changes
    coord_changes = []
    if 'x_coord' in df1.columns and 'x_coord' in df2.columns:
        for node_id in common:
            row1 = df1[df1['node_id'] == node_id].iloc[0]
            row2 = df2[df2['node_id'] == node_id].iloc[0]

            if abs(row1['x_coord'] - row2['x_coord']) > 1 or abs(row1['y_coord'] - row2['y_coord']) > 1:
                coord_changes.append({
                    'node_id': node_id,
                    'old_coords': (row1['x_coord'], row1['y_coord']),
                    'new_coords': (row2['x_coord'], row2['y_coord'])
                })

    return {
        'added': list(added),
        'removed': list(removed),
        'coord_changes': coord_changes,
        'added_count': len(added),
        'removed_count': len(removed),
        'coord_changes_count': len(coord_changes)
    }


def compare_demand_data(df1: pd.DataFrame, df2: pd.DataFrame) -> Dict[str, Any]:
    """Compare two demand datasets."""
    nodes1 = set(df1['node_id'])
    nodes2 = set(df2['node_id'])

    added = nodes2 - nodes1
    removed = nodes1 - nodes2
    common = nodes1 & nodes2

    # Check for significant demand changes (>10%)
    demand_changes = []
    if 'total_demand' in df1.columns and 'total_demand' in df2.columns:
        for node_id in common:
            row1 = df1[df1['node_id'] == node_id].iloc[0]
            row2 = df2[df2['node_id'] == node_id].iloc[0]

            old_demand = row1['total_demand']
            new_demand = row2['total_demand']

            if old_demand > 0:
                pct_change = (new_demand - old_demand) / old_demand * 100
                if abs(pct_change) > 10:  # More than 10% change
                    demand_changes.append({
                        'node_id': node_id,
                        'old_demand': old_demand,
                        'new_demand': new_demand,
                        'pct_change': pct_change
                    })

    return {
        'added': list(added),
        'removed': list(removed),
        'demand_changes': demand_changes,
        'added_count': len(added),
        'removed_count': len(removed),
        'significant_changes_count': len(demand_changes)
    }


def compare_run_versions(
    run1_id: str,
    run2_id: str,
    store: Optional[VersionStore] = None
) -> Dict[str, Any]:
    """
    Compare two model run versions.

    Args:
        run1_id: First run ID
        run2_id: Second run ID
        store: Version store instance

    Returns:
        Comparison dictionary
    """
    store = store or VersionStore()

    # Load metadata
    run1 = store.get_run_version(run1_id)
    run2 = store.get_run_version(run2_id)

    if not run1 or not run2:
        raise ValueError("One or both runs not found")

    comparison = {
        'run1': {
            'id': run1_id,
            'created_at': run1['created_at'],
            'model_version': run1.get('model_version', {}).get('code_version'),
            'status': run1.get('status')
        },
        'run2': {
            'id': run2_id,
            'created_at': run2['created_at'],
            'model_version': run2.get('model_version', {}).get('code_version'),
            'status': run2.get('status')
        },
        'config_differences': compare_configurations(
            run1.get('configuration', {}),
            run2.get('configuration', {})
        ),
        'data_version_differences': compare_data_inputs(
            run1.get('input_data_versions', {}),
            run2.get('input_data_versions', {})
        ),
        'results_differences': compare_results_summary(
            run1.get('results_summary', {}),
            run2.get('results_summary', {})
        )
    }

    return comparison


def compare_configurations(config1: Dict[str, Any], config2: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two configuration dictionaries."""
    differences = {}

    all_keys = set(config1.keys()) | set(config2.keys())

    for key in all_keys:
        val1 = config1.get(key)
        val2 = config2.get(key)

        if val1 != val2:
            differences[key] = {
                'run1': val1,
                'run2': val2
            }

    return differences


def compare_data_inputs(inputs1: Dict[str, str], inputs2: Dict[str, str]) -> Dict[str, Any]:
    """Compare input data versions used in two runs."""
    differences = {}

    all_types = set(inputs1.keys()) | set(inputs2.keys())

    for data_type in all_types:
        ver1 = inputs1.get(data_type)
        ver2 = inputs2.get(data_type)

        if ver1 != ver2:
            differences[data_type] = {
                'run1': ver1,
                'run2': ver2
            }

    return differences


def compare_results_summary(results1: Dict[str, Any], results2: Dict[str, Any]) -> Dict[str, Any]:
    """Compare results summaries from two runs."""
    comparison = {}

    # Compare total hubs
    if 'total_hubs' in results1 and 'total_hubs' in results2:
        comparison['total_hubs_change'] = results2['total_hubs'] - results1['total_hubs']

    # Compare hubs by tier
    if 'hubs_by_tier' in results1 and 'hubs_by_tier' in results2:
        tier_changes = {}
        for tier in set(results1['hubs_by_tier'].keys()) | set(results2['hubs_by_tier'].keys()):
            count1 = results1['hubs_by_tier'].get(tier, 0)
            count2 = results2['hubs_by_tier'].get(tier, 0)
            if count1 != count2:
                tier_changes[tier] = {
                    'run1': count1,
                    'run2': count2,
                    'change': count2 - count1
                }
        comparison['tier_changes'] = tier_changes

    # Compare hubs by area
    if 'hubs_by_area' in results1 and 'hubs_by_area' in results2:
        area_changes = {}
        for area in set(results1['hubs_by_area'].keys()) | set(results2['hubs_by_area'].keys()):
            count1 = results1['hubs_by_area'].get(area, 0)
            count2 = results2['hubs_by_area'].get(area, 0)
            if count1 != count2:
                area_changes[area] = {
                    'run1': count1,
                    'run2': count2,
                    'change': count2 - count1
                }
        comparison['area_changes'] = area_changes

    return comparison
