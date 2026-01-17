"""
Data Version Management
=======================
Create and manage versions of input data files.
"""

import pandas as pd
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .version_store import VersionStore
from ..config import DATA_DIR
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DataVersion:
    """
    Represents a versioned snapshot of input data.
    """

    def __init__(self, metadata: Dict[str, Any], store: Optional[VersionStore] = None):
        """
        Initialize data version.

        Args:
            metadata: Version metadata dictionary
            store: Version store instance (creates new if None)
        """
        self.metadata = metadata
        self.store = store or VersionStore()
        self.version_id = metadata['data_version_id']
        self.data_type = metadata['data_type']

    @classmethod
    def load(cls, version_id: str, store: Optional[VersionStore] = None):
        """
        Load existing data version.

        Args:
            version_id: Version identifier
            store: Version store instance

        Returns:
            DataVersion instance
        """
        store = store or VersionStore()
        metadata = store.get_data_version(version_id)
        if not metadata:
            raise ValueError(f"Data version not found: {version_id}")
        return cls(metadata, store)

    def get_file_path(self) -> Path:
        """Get path to versioned data file."""
        version_dir = self.store.base_dir / self.data_type / self.version_id
        # Find the data file (should be only CSV/Excel file in directory)
        for ext in ['.csv', '.xlsx', '.geojson', '.shp']:
            candidate = version_dir / f"{self.data_type}{ext}"
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Data file not found for {self.version_id}")

    def load_data(self) -> pd.DataFrame:
        """
        Load the versioned data as DataFrame.

        Returns:
            DataFrame with data
        """
        filepath = self.get_file_path()

        if filepath.suffix == '.csv':
            return pd.read_csv(filepath, encoding='utf-8')
        elif filepath.suffix == '.xlsx':
            return pd.read_excel(filepath)
        else:
            raise ValueError(f"Unsupported file type: {filepath.suffix}")

    def compare_with(self, other_version_id: str) -> Dict[str, Any]:
        """
        Compare this version with another.

        Args:
            other_version_id: Other version to compare with

        Returns:
            Comparison summary dictionary
        """
        from .version_compare import compare_data_versions
        return compare_data_versions(self.version_id, other_version_id, self.store)


def create_data_version(
    data_type: str,
    source_file: Path,
    created_by: Optional[str] = None,
    notes: Optional[str] = None,
    tags: Optional[List[str]] = None,
    validation_report: Optional[Dict[str, Any]] = None,
    store: Optional[VersionStore] = None
) -> DataVersion:
    """
    Create a new data version from a source file.

    Args:
        data_type: Type of data (e.g., 'transit_lines', 'demand_2050')
        source_file: Path to source data file
        created_by: User who created this version
        notes: Optional notes about this version
        tags: Optional tags for categorization
        validation_report: Optional validation results
        store: Version store instance

    Returns:
        DataVersion instance

    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If data_type is invalid
    """
    store = store or VersionStore()
    source_file = Path(source_file)

    if not source_file.exists():
        raise FileNotFoundError(f"Source file not found: {source_file}")

    # Valid data types
    valid_types = [
        'transit_lines',
        'transit_stations',
        'demand_2050',
        'metro_areas',
        'taz_zones',
        'bus_terminals',
        'manual_overrides'
    ]

    if data_type not in valid_types:
        raise ValueError(f"Invalid data_type. Must be one of: {valid_types}")

    # Generate version ID
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    version_id = f"data_{data_type}_{timestamp}"

    # Create version directory
    version_dir = store.base_dir / data_type / version_id
    version_dir.mkdir(parents=True, exist_ok=True)

    # Copy source file to version directory
    dest_file = version_dir / source_file.name
    shutil.copy2(source_file, dest_file)

    # Compute file hash
    file_hash = store.compute_file_hash(dest_file)

    # Load data to get record count
    try:
        if source_file.suffix == '.csv':
            df = pd.read_csv(source_file, encoding='utf-8')
        elif source_file.suffix == '.xlsx':
            df = pd.read_excel(source_file)
        else:
            df = None

        record_count = len(df) if df is not None else None
    except Exception as e:
        logger.warning(f"Could not load data to count records: {e}")
        record_count = None

    # Get previous version for comparison
    previous_version = store.get_latest_data_version(data_type)
    changes_from_previous = None

    if previous_version:
        try:
            # Simple comparison of record counts
            prev_count = previous_version.get('record_count', 0)
            if record_count:
                changes_from_previous = {
                    'previous_version': previous_version['data_version_id'],
                    'record_count_change': record_count - prev_count,
                    'summary': f"Record count changed from {prev_count} to {record_count}"
                }
        except Exception as e:
            logger.warning(f"Could not compare with previous version: {e}")

    # Create metadata
    metadata = {
        'data_version_id': version_id,
        'created_at': datetime.now().isoformat(),
        'data_type': data_type,
        'source_file': source_file.name,
        'source_file_hash': file_hash,
        'record_count': record_count,
        'changes_from_previous': changes_from_previous,
        'validation': validation_report or {'status': 'not_validated'},
        'created_by': created_by or 'system',
        'notes': notes or '',
        'tags': tags or []
    }

    # Save metadata
    store.save_data_version(metadata)

    # Save validation report if provided
    if validation_report:
        report_path = version_dir / 'validation_report.json'
        import json
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(validation_report, f, indent=2, ensure_ascii=False)

    logger.info(f"Created data version: {version_id}")
    logger.info(f"  Data type: {data_type}")
    logger.info(f"  Records: {record_count}")
    logger.info(f"  File: {dest_file}")

    return DataVersion(metadata, store)


def get_current_data_versions(store: Optional[VersionStore] = None) -> Dict[str, str]:
    """
    Get current (latest) versions of all data types.

    Args:
        store: Version store instance

    Returns:
        Dictionary mapping data_type to version_id
    """
    store = store or VersionStore()

    data_types = [
        'transit_lines',
        'transit_stations',
        'demand_2050',
        'metro_areas',
        'taz_zones',
        'bus_terminals',
        'manual_overrides'
    ]

    current_versions = {}

    for data_type in data_types:
        latest = store.get_latest_data_version(data_type)
        if latest:
            current_versions[data_type] = latest['data_version_id']

    return current_versions


def update_current_data_link(
    data_type: str,
    version_id: str,
    store: Optional[VersionStore] = None
):
    """
    Update symlink in data/current/ to point to specified version.

    Args:
        data_type: Type of data
        version_id: Version to link to
        store: Version store instance
    """
    store = store or VersionStore()

    # Get version metadata
    metadata = store.get_data_version(version_id)
    if not metadata:
        raise ValueError(f"Version not found: {version_id}")

    # Find source file
    version_dir = store.base_dir / data_type / version_id
    source_file = None
    for ext in ['.csv', '.xlsx', '.geojson', '.shp']:
        candidate = version_dir / f"{data_type}{ext}"
        if candidate.exists():
            source_file = candidate
            break

    if not source_file:
        raise FileNotFoundError(f"Data file not found in {version_dir}")

    # Create current directory
    current_dir = DATA_DIR / 'current'
    current_dir.mkdir(parents=True, exist_ok=True)

    # Create symlink
    link_path = current_dir / source_file.name

    # Remove existing link/file
    if link_path.exists() or link_path.is_symlink():
        link_path.unlink()

    # Create new symlink
    link_path.symlink_to(source_file)

    logger.info(f"Updated current link for {data_type} -> {version_id}")
