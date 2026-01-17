"""
Notebook Versioning Helper
===========================
Simplified versioning interface for Jupyter notebooks.

Makes it easy to version notebook runs without dealing with low-level APIs.

Usage in notebook:
    from src.versioning.notebook_helper import NotebookVersioning

    # At start of notebook
    nb = NotebookVersioning(
        purpose="Testing new metro lines scenario",
        tags=["scenario", "metro_2030"]
    )
    nb.start()

    # ... run your analysis ...

    # At end of notebook
    nb.finish(results_summary={
        'total_hubs': 86,
        'new_hubs': 3
    })
"""

import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .run_version import create_run_version, finalize_run_version
from .model_version import get_current_model_version
from .data_version import get_current_data_versions
from ..config import *
from ..utils.logging import get_logger

logger = get_logger(__name__)


class NotebookVersioning:
    """
    Simplified versioning for Jupyter notebooks.

    Handles creation and finalization of run versions automatically.
    """

    def __init__(
        self,
        purpose: str = "Notebook analysis",
        created_by: Optional[str] = None,
        tags: Optional[List[str]] = None,
        notebook_name: Optional[str] = None
    ):
        """
        Initialize notebook versioning.

        Args:
            purpose: Purpose of this notebook run
            created_by: User running the notebook
            tags: Tags for categorization
            notebook_name: Name of the notebook file
        """
        self.purpose = purpose
        self.created_by = created_by or "notebook_user"
        self.tags = tags or []
        self.notebook_name = notebook_name or "unknown_notebook"

        self.run_version = None
        self.start_time = None
        self.results_dir = None

        # Add notebook tag
        if 'notebook' not in self.tags:
            self.tags.append('notebook')

    def start(self):
        """
        Start versioned notebook run.

        Call this at the beginning of your notebook.
        """
        self.start_time = time.time()

        print("="*80)
        print("STARTING VERSIONED NOTEBOOK RUN")
        print("="*80)

        # Get model version
        model_version = get_current_model_version()
        print(f"Model version: {model_version}")

        # Get data versions
        try:
            data_versions = get_current_data_versions()
            print(f"Input data versions:")
            for data_type, version_id in data_versions.items():
                print(f"  {data_type}: {version_id}")
        except Exception as e:
            logger.warning(f"Could not get data versions: {e}")
            data_versions = {}

        # Capture configuration
        configuration = self._get_configuration()

        # Create run version
        self.run_version = create_run_version(
            model_version=model_version,
            configuration=configuration,
            input_data_versions=data_versions,
            run_purpose=f"[Notebook: {self.notebook_name}] {self.purpose}",
            created_by=self.created_by,
            notes=f"Notebook run started at {datetime.now().isoformat()}",
            tags=self.tags
        )

        self.results_dir = self.run_version.get_results_dir()

        print(f"\n✓ Created run version: {self.run_version.run_id}")
        print(f"  Results will be saved to: {self.results_dir}")

        # Update status
        self.run_version.update_status('running')

        print("\n" + "="*80)

        return self.run_version.run_id

    def save_intermediate(self, data: Any, filename: str, description: str = ""):
        """
        Save intermediate results to versioned directory.

        Args:
            data: Data to save (DataFrame, GeoDataFrame, dict, etc.)
            filename: Filename (will be saved in run results directory)
            description: Optional description
        """
        if not self.results_dir:
            logger.warning("No run version started - cannot save intermediate results")
            return None

        filepath = self.results_dir / filename

        # Save based on type
        import pandas as pd
        import geopandas as gpd

        if isinstance(data, gpd.GeoDataFrame):
            # Save as GeoJSON
            data.to_file(filepath.with_suffix('.geojson'), driver='GeoJSON')
            print(f"✓ Saved {description or filename}: {filepath.with_suffix('.geojson')}")

        elif isinstance(data, pd.DataFrame):
            # Save as CSV
            data.to_csv(filepath.with_suffix('.csv'), index=False, encoding='utf-8-sig')
            print(f"✓ Saved {description or filename}: {filepath.with_suffix('.csv')}")

        elif isinstance(data, dict):
            # Save as JSON
            import json
            with open(filepath.with_suffix('.json'), 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            print(f"✓ Saved {description or filename}: {filepath.with_suffix('.json')}")

        else:
            logger.warning(f"Unknown data type for {filename}: {type(data)}")
            return None

        return filepath

    def finish(
        self,
        results_summary: Optional[Dict[str, Any]] = None,
        status: str = 'completed'
    ):
        """
        Finish versioned notebook run.

        Call this at the end of your notebook.

        Args:
            results_summary: Summary of results (e.g., hub counts, scores)
            status: Final status ('completed' or 'failed')
        """
        if not self.run_version:
            logger.warning("No run version to finalize")
            return

        print("\n" + "="*80)
        print("FINALIZING NOTEBOOK RUN")
        print("="*80)

        # Calculate execution time
        execution_time = time.time() - self.start_time if self.start_time else None

        # Get output files
        output_files = list(self.results_dir.glob('*')) if self.results_dir.exists() else []

        # Finalize
        finalize_run_version(
            run_version=self.run_version,
            results_summary=results_summary or {},
            output_files=output_files,
            status=status
        )

        print(f"✓ Finalized run version: {self.run_version.run_id}")
        print(f"  Status: {status}")
        if execution_time:
            print(f"  Execution time: {execution_time:.1f}s ({execution_time/60:.1f}m)")
        if results_summary:
            print(f"  Results:")
            for key, value in results_summary.items():
                print(f"    {key}: {value}")

        print("\n" + "="*80)
        print("VERSIONING COMPLETE")
        print("="*80)
        print(f"\nRun ID: {self.run_version.run_id}")
        print(f"Results: {self.results_dir}")
        print(f"\nTo view this run:")
        print(f"  python scripts/version_management/list_versions.py --type runs --limit 1")
        print(f"\nTo compare with previous run:")
        print(f"  python scripts/version_management/compare_versions.py --type runs \\")
        print(f"    --version1 <previous_run> --version2 {self.run_version.run_id}")
        print("="*80)

    def _get_configuration(self) -> Dict[str, Any]:
        """Get current configuration snapshot."""
        return {
            'h3_resolution': H3_RESOLUTION,
            'hub_merge_threshold_m': HUB_MERGE_THRESHOLD_M,
            'eligibility_min_passengers': ELIGIBILITY_MIN_PASSENGERS,
            'eligibility_min_modes': ELIGIBILITY_MIN_MODES,
            'require_non_rail_mode': REQUIRE_NON_RAIL_MODE,
            'national_hub_min_passengers': NATIONAL_HUB_MIN_PASSENGERS,
            'metro_hub_min_passengers': METRO_HUB_MIN_PASSENGERS,
            'monte_carlo_iterations': MONTE_CARLO_ITERATIONS,
            'monte_carlo_random_seed': MONTE_CARLO_RANDOM_SEED,
            'max_criterion_weight': MAX_CRITERION_WEIGHT,
            'ahp_enabled': AHP_ENABLED,
            'mode_weights': MODE_WEIGHTS,
            'mode_diversity_bonus_pct': MODE_DIVERSITY_BONUS_PCT,
            'catchment_rings': CATCHMENT_RINGS,
            'distance_decay_beta': DISTANCE_DECAY_BETA,
            'terminal_proximity_distance_m': TERMINAL_PROXIMITY_DISTANCE_M,
        }


# Convenience function for quick notebook versioning
def quick_version(purpose: str = "Notebook analysis", tags: Optional[List[str]] = None):
    """
    Quick versioning decorator for notebook cells.

    Usage:
        nb = quick_version("Testing scenario")
        # ... do analysis ...
        nb.finish(results_summary={'hubs': 86})
    """
    nb = NotebookVersioning(purpose=purpose, tags=tags)
    nb.start()
    return nb
