"""
Model Run Version Management
============================
Create and manage versions of complete pipeline runs.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import subprocess

from .version_store import VersionStore
from .data_version import get_current_data_versions
from ..config import DATA_DIR, RESULTS_DIR, PROJECT_ROOT
from ..utils.logging import get_logger

logger = get_logger(__name__)


class RunVersion:
    """
    Represents a versioned execution of the hub prioritization pipeline.
    """

    def __init__(self, metadata: Dict[str, Any], store: Optional[VersionStore] = None):
        """
        Initialize run version.

        Args:
            metadata: Run metadata dictionary
            store: Version store instance
        """
        self.metadata = metadata
        self.store = store or VersionStore()
        self.run_id = metadata['run_version_id']

    @classmethod
    def load(cls, run_id: str, store: Optional[VersionStore] = None):
        """
        Load existing run version.

        Args:
            run_id: Run identifier
            store: Version store instance

        Returns:
            RunVersion instance
        """
        store = store or VersionStore()
        metadata = store.get_run_version(run_id)
        if not metadata:
            raise ValueError(f"Run version not found: {run_id}")
        return cls(metadata, store)

    def get_results_dir(self) -> Path:
        """Get directory containing run results."""
        return RESULTS_DIR / self.run_id

    def get_output_files(self) -> List[Path]:
        """Get list of output files from this run."""
        results_dir = self.get_results_dir()
        if not results_dir.exists():
            return []

        return [
            f for f in results_dir.iterdir()
            if f.is_file() and f.suffix in ['.csv', '.geojson', '.html', '.xlsx']
        ]

    def update_status(
        self,
        status: str,
        execution_time: Optional[float] = None,
        results_summary: Optional[Dict[str, Any]] = None
    ):
        """
        Update run status.

        Args:
            status: New status ('running', 'completed', 'failed')
            execution_time: Total execution time in seconds
            results_summary: Summary of results
        """
        self.store.update_run_status(
            self.run_id,
            status,
            execution_time,
            results_summary
        )
        self.metadata = self.store.get_run_version(self.run_id)

    def compare_with(self, other_run_id: str) -> Dict[str, Any]:
        """
        Compare this run with another.

        Args:
            other_run_id: Other run to compare with

        Returns:
            Comparison summary dictionary
        """
        from .version_compare import compare_run_versions
        return compare_run_versions(self.run_id, other_run_id, self.store)


def create_run_version(
    model_version: str,
    configuration: Dict[str, Any],
    input_data_versions: Optional[Dict[str, str]] = None,
    run_purpose: Optional[str] = None,
    created_by: Optional[str] = None,
    notes: Optional[str] = None,
    tags: Optional[List[str]] = None,
    store: Optional[VersionStore] = None
) -> RunVersion:
    """
    Create a new model run version.

    Args:
        model_version: Model code version (e.g., '1.3.2')
        configuration: Configuration dictionary (from config.py)
        input_data_versions: Dict mapping data_type to version_id
        run_purpose: Purpose/description of this run
        created_by: User running the model
        notes: Additional notes
        tags: Tags for categorization
        store: Version store instance

    Returns:
        RunVersion instance
    """
    store = store or VersionStore()

    # Get current data versions if not provided
    if input_data_versions is None:
        input_data_versions = get_current_data_versions(store)

    # Get git info
    git_info = get_git_info()

    # Generate run ID
    today = datetime.now().strftime('%Y-%m-%d')
    run_number = store.get_next_run_number()

    # Count runs today to get sequence number
    existing_runs_today = [
        r for r in store.list_run_versions()
        if r.get('run_version_id', '').startswith(f"run_{today}")
    ]
    sequence = len(existing_runs_today) + 1

    run_id = f"run_{today}_{sequence:02d}"

    # Create results directory
    results_dir = RESULTS_DIR / run_id
    results_dir.mkdir(parents=True, exist_ok=True)

    # Create metadata
    metadata = {
        'run_version_id': run_id,
        'run_number': run_number,
        'created_at': datetime.now().isoformat(),
        'status': 'created',

        'model_version': {
            'code_version': model_version,
            'git_commit': git_info.get('commit'),
            'git_branch': git_info.get('branch')
        },

        'input_data_versions': input_data_versions,

        'configuration': configuration,

        'results_summary': None,  # Will be updated when run completes
        'output_files': [],  # Will be updated when run completes

        'created_by': created_by or 'system',
        'run_purpose': run_purpose or '',
        'notes': notes or '',
        'tags': tags or []
    }

    # Save metadata
    store.save_run_version(metadata)

    # Save configuration snapshot
    config_path = results_dir / 'config_snapshot.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(configuration, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Created run version: {run_id}")
    logger.info(f"  Model version: {model_version}")
    logger.info(f"  Run number: {run_number}")
    logger.info(f"  Results dir: {results_dir}")

    return RunVersion(metadata, store)


def finalize_run_version(
    run_version: RunVersion,
    results_summary: Dict[str, Any],
    output_files: List[Path],
    status: str = 'completed'
):
    """
    Finalize a run version after pipeline completion.

    Args:
        run_version: RunVersion instance
        results_summary: Summary of results
        output_files: List of output file paths
        status: Final status ('completed' or 'failed')
    """
    # Get execution time (difference between created and now)
    created_at = datetime.fromisoformat(run_version.metadata['created_at'])
    execution_time = (datetime.now() - created_at).total_seconds()

    # Update metadata
    run_version.metadata['status'] = status
    run_version.metadata['execution_time_seconds'] = execution_time
    run_version.metadata['results_summary'] = results_summary
    run_version.metadata['output_files'] = [str(f) for f in output_files]

    # Compare with previous run if exists
    previous_runs = run_version.store.list_run_versions(status='completed', limit=2)
    if len(previous_runs) >= 2:
        # Current run is first, previous completed is second
        prev_run_id = previous_runs[1]['run_version_id']

        # Simple comparison
        prev_summary = previous_runs[1].get('results_summary', {})
        comparison = {
            'previous_run': prev_run_id,
            'hub_count_change': (
                results_summary.get('total_hubs', 0) -
                prev_summary.get('total_hubs', 0)
            )
        }
        run_version.metadata['comparison_to_previous'] = comparison

    # Save updated metadata
    run_version.store.save_run_version(run_version.metadata)

    logger.info(f"Finalized run {run_version.run_id}: status={status}, time={execution_time:.1f}s")


def get_git_info() -> Dict[str, str]:
    """
    Get current git information.

    Returns:
        Dictionary with commit, branch, etc.
    """
    try:
        # Get current commit
        commit = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL
        ).decode().strip()

        # Get current branch
        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL
        ).decode().strip()

        # Check for uncommitted changes
        status = subprocess.check_output(
            ['git', 'status', '--porcelain'],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL
        ).decode().strip()

        has_uncommitted = len(status) > 0

        return {
            'commit': commit,
            'branch': branch,
            'has_uncommitted_changes': has_uncommitted
        }

    except Exception as e:
        logger.warning(f"Could not get git info: {e}")
        return {
            'commit': 'unknown',
            'branch': 'unknown',
            'has_uncommitted_changes': None
        }
