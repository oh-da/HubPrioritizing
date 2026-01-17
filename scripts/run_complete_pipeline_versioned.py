#!/usr/bin/env python3
"""
COMPLETE Hub Prioritization Pipeline with Versioning
====================================================
This is the FULL pipeline including demand data, spatial layers, and AUTOMATIC VERSIONING.

All pipeline runs are automatically versioned, tracked, and saved for reproducibility.
"""

import sys
import subprocess
import os
import argparse
from pathlib import Path
from datetime import datetime
import time

# Get the project root directory
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Change to project root if not already there
if Path.cwd() != PROJECT_ROOT:
    print(f"Changing working directory to: {PROJECT_ROOT}")
    os.chdir(PROJECT_ROOT)

# Add project root to Python path
sys.path.insert(0, str(PROJECT_ROOT))

# Import versioning FIRST
from src.versioning import (
    create_run_version,
    finalize_run_version,
    get_current_model_version,
    get_current_data_versions,
)
from src.config import *
from src.utils.logging import setup_logger

# Setup logger
logger = setup_logger(__name__)

# Import the original pipeline class
# We'll just patch the run method to add versioning
import importlib
import scripts.run_complete_pipeline as original_pipeline

# Make CompleteHubPipeline available
CompleteHubPipeline = original_pipeline.CompleteHubPipeline


class VersionedHubPipeline(CompleteHubPipeline):
    """
    Extended pipeline with automatic versioning.

    Wraps the original pipeline to add:
    - Automatic run version creation
    - Input data version tracking
    - Configuration snapshotting
    - Results archiving
    - Execution time tracking
    """

    def __init__(self, run_purpose=None, created_by=None, tags=None):
        """
        Initialize versioned pipeline.

        Args:
            run_purpose: Description of this run's purpose
            created_by: User executing this run
            tags: List of tags for categorization
        """
        super().__init__()
        self.run_purpose = run_purpose
        self.created_by = created_by or os.environ.get('USER', 'system')
        self.tags = tags or []
        self.run_version = None
        self.start_time = None

    def create_run_version(self):
        """Create and initialize run version."""
        logger.info("\n" + "="*80)
        logger.info("INITIALIZING RUN VERSION")
        logger.info("="*80)

        # Get current model version
        model_version = get_current_model_version()
        logger.info(f"Model version: {model_version}")

        # Get current data versions
        try:
            data_versions = get_current_data_versions()
            logger.info(f"Input data versions:")
            for data_type, version_id in data_versions.items():
                logger.info(f"  {data_type}: {version_id}")
        except Exception as e:
            logger.warning(f"Could not get data versions: {e}")
            data_versions = {}

        # Capture all configuration
        configuration = {
            # H3 and spatial
            'h3_resolution': H3_RESOLUTION,
            'hub_merge_threshold_m': HUB_MERGE_THRESHOLD_M,
            'hub_merge_tolerance_m': HUB_MERGE_TOLERANCE_M,

            # Eligibility
            'eligibility_min_passengers': ELIGIBILITY_MIN_PASSENGERS,
            'eligibility_min_modes': ELIGIBILITY_MIN_MODES,
            'require_non_rail_mode': REQUIRE_NON_RAIL_MODE,

            # Hierarchy
            'national_hub_min_passengers': NATIONAL_HUB_MIN_PASSENGERS,
            'metro_hub_min_passengers': METRO_HUB_MIN_PASSENGERS,
            'local_hub_max_passengers': LOCAL_HUB_MAX_PASSENGERS,

            # Scoring
            'monte_carlo_iterations': MONTE_CARLO_ITERATIONS,
            'monte_carlo_random_seed': MONTE_CARLO_RANDOM_SEED,
            'max_criterion_weight': MAX_CRITERION_WEIGHT,
            'score_range': SCORE_RANGE,
            'ahp_enabled': AHP_ENABLED,

            # Mode weights
            'mode_weights': MODE_WEIGHTS,
            'mode_diversity_bonus_pct': MODE_DIVERSITY_BONUS_PCT,

            # Demographics
            'catchment_rings': CATCHMENT_RINGS,
            'distance_decay_beta': DISTANCE_DECAY_BETA,
            'pop_job_mix': POP_JOB_MIX,

            # Terminal
            'terminal_proximity_distance_m': TERMINAL_PROXIMITY_DISTANCE_M,
        }

        # Create run version
        self.run_version = create_run_version(
            model_version=model_version,
            configuration=configuration,
            input_data_versions=data_versions,
            run_purpose=self.run_purpose or 'Standard pipeline execution',
            created_by=self.created_by,
            notes=f'Automatic versioning of pipeline run at {datetime.now().isoformat()}',
            tags=self.tags
        )

        logger.info(f"\n✓ Created run version: {self.run_version.run_id}")
        logger.info(f"  Results will be saved to: {self.run_version.get_results_dir()}")

        # Update status to running
        self.run_version.update_status('running')

    def finalize_run_version(self, status='completed'):
        """
        Finalize run version with results.

        Args:
            status: Final status ('completed' or 'failed')
        """
        if not self.run_version:
            logger.warning("No run version to finalize")
            return

        logger.info("\n" + "="*80)
        logger.info("FINALIZING RUN VERSION")
        logger.info("="*80)

        # Calculate execution time
        execution_time = time.time() - self.start_time if self.start_time else None

        # Gather results summary
        results_summary = {}

        if hasattr(self, 'transit_nodes') and self.transit_nodes is not None:
            results_summary['total_nodes'] = len(self.transit_nodes)

        if hasattr(self, 'h3_hexagons') and self.h3_hexagons is not None:
            results_summary['total_hexes'] = len(self.h3_hexagons)

        if hasattr(self, 'grouped_hubs') and self.grouped_hubs is not None:
            results_summary['total_hub_groups'] = len(self.grouped_hubs)

        if hasattr(self, 'eligible_hubs') and self.eligible_hubs is not None:
            results_summary['eligible_hubs'] = len(self.eligible_hubs)

        if hasattr(self, 'scored_hubs') and self.scored_hubs is not None:
            results_summary['total_hubs'] = len(self.scored_hubs)

            # Count by tier
            if 'tier' in self.scored_hubs.columns:
                tier_counts = self.scored_hubs['tier'].value_counts().to_dict()
                results_summary['hubs_by_tier'] = tier_counts

            # Count by area/region
            if 'region' in self.scored_hubs.columns:
                area_counts = self.scored_hubs['region'].value_counts().to_dict()
                results_summary['hubs_by_area'] = area_counts
            elif 'area' in self.scored_hubs.columns:
                area_counts = self.scored_hubs['area'].value_counts().to_dict()
                results_summary['hubs_by_area'] = area_counts

        # Get output files
        results_dir = self.run_version.get_results_dir()
        output_files = list(results_dir.glob('*')) if results_dir.exists() else []

        # Finalize
        finalize_run_version(
            run_version=self.run_version,
            results_summary=results_summary,
            output_files=output_files,
            status=status
        )

        logger.info(f"✓ Finalized run version: {self.run_version.run_id}")
        logger.info(f"  Status: {status}")
        if execution_time:
            logger.info(f"  Execution time: {execution_time:.1f}s ({execution_time/60:.1f}m)")
        logger.info(f"  Total hubs: {results_summary.get('total_hubs', 'N/A')}")

    def step_12_export_results(self):
        """Step 12: Export final results to versioned directory."""
        logger.info("\n" + "="*80)
        logger.info("STEP 12: EXPORT RESULTS (VERSIONED)")
        logger.info("="*80)

        # Get versioned results directory
        if self.run_version:
            results_dir = self.run_version.get_results_dir()
        else:
            results_dir = RESULTS_DIR / f"run_{self.timestamp}"
            results_dir.mkdir(parents=True, exist_ok=True)

        # CSV
        csv_path = results_dir / "scored_hubs.csv"
        export_df = self.scored_hubs.copy()
        export_df['geometry'] = export_df['geometry'].apply(lambda x: x.wkt if x else None)
        export_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"✓ CSV: {csv_path}")

        # GeoJSON
        geojson_path = results_dir / "scored_hubs.geojson"
        self.scored_hubs.to_file(geojson_path, driver='GeoJSON')
        logger.info(f"✓ GeoJSON: {geojson_path}")

        # Map
        try:
            from src.visualization import maps
            map_path = results_dir / "hub_map.html"
            maps.create_hub_map(self.scored_hubs, color_by='final_score', output_file=str(map_path))
            logger.info(f"✓ Map: {map_path}")
        except Exception as e:
            logger.warning(f"Could not create map: {e}")

        # Also save to legacy location for backward compatibility
        legacy_csv = RESULTS_DIR / f"hub_prioritization_results_{self.timestamp}.csv"
        export_df.to_csv(legacy_csv, index=False, encoding='utf-8-sig')
        logger.info(f"✓ Legacy CSV: {legacy_csv}")

        logger.info("✓ Step 12 complete")

    def run(self):
        """Run complete pipeline with versioning."""
        self.start_time = time.time()

        try:
            # Create run version
            self.create_run_version()

            # Run all pipeline steps (from parent class)
            self.step_1_load_all_data()
            self.step_2_create_h3_hexagons()
            self.step_3_group_hexagons()
            self.step_4_add_demand_data()
            self.step_5_add_spatial_tags()
            self.step_6_add_demographics()
            self.step_7_add_terminal_proximity()
            self.step_8_filter_eligibility()
            self.step_9_classify_hierarchy()
            self.step_10_calculate_scores()
            self.step_11_run_mc_distribution()
            self.step_12_export_results()  # Our versioned export

            # Finalize run version
            self.finalize_run_version(status='completed')

            logger.info("\n" + "="*80)
            logger.info("✅ VERSIONED PIPELINE COMPLETE!")
            logger.info("="*80)
            logger.info(f"\nRun Version: {self.run_version.run_id if self.run_version else 'N/A'}")
            logger.info(f"Results Directory: {self.run_version.get_results_dir() if self.run_version else RESULTS_DIR}")
            logger.info(f"Total Hubs: {len(self.scored_hubs)}")
            logger.info(f"\nTo view this run:")
            if self.run_version:
                logger.info(f"  python scripts/version_management/list_versions.py --type runs --limit 1")
                logger.info(f"\nTo compare with previous run:")
                logger.info(f"  python scripts/version_management/compare_versions.py --type runs \\")
                logger.info(f"    --version1 <previous_run> --version2 {self.run_version.run_id}")

            return self.scored_hubs

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)

            # Mark run as failed
            if self.run_version:
                self.finalize_run_version(status='failed')

            raise


def main():
    """Main entry point with argument parsing."""

    parser = argparse.ArgumentParser(
        description='Run complete hub prioritization pipeline with automatic versioning'
    )

    parser.add_argument(
        '--purpose',
        type=str,
        help='Purpose/description of this run (e.g., "Production run for Q1 2025")'
    )

    parser.add_argument(
        '--user',
        type=str,
        help='User executing this run (default: system username)'
    )

    parser.add_argument(
        '--tags',
        type=str,
        help='Comma-separated tags (e.g., "production,2025_Q1,validated")'
    )

    parser.add_argument(
        '--no-version',
        action='store_true',
        help='Run without versioning (use original pipeline)'
    )

    args = parser.parse_args()

    # Parse tags
    tags = args.tags.split(',') if args.tags else []

    # Check required files
    INPUT_TRANSIT_NODES = RAW_DATA_DIR / "All_nodes+lines.csv"
    INPUT_LINES_MODES = RAW_DATA_DIR / "Lines_and_Planned_Mode.csv"

    if not INPUT_TRANSIT_NODES.exists():
        logger.error(f"❌ Transit nodes not found: {INPUT_TRANSIT_NODES}")
        logger.info("Please update INPUT_TRANSIT_NODES path or place file in data/raw/")
        sys.exit(1)

    if not INPUT_LINES_MODES.exists():
        logger.error(f"❌ Lines/modes not found: {INPUT_LINES_MODES}")
        logger.info("Please update INPUT_LINES_MODES path or place file in data/raw/")
        sys.exit(1)

    # Run pipeline (versioned or original)
    if args.no_version:
        logger.info("Running WITHOUT versioning (original pipeline)")
        pipeline = CompleteHubPipeline()
    else:
        logger.info("Running WITH automatic versioning")
        pipeline = VersionedHubPipeline(
            run_purpose=args.purpose,
            created_by=args.user,
            tags=tags
        )

    results = pipeline.run()

    logger.info("\n🎉 Done! Check results in data/results/")


if __name__ == "__main__":
    main()
