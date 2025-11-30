#!/usr/bin/env python3
"""
Hub Prioritization Framework - Main Pipeline
=============================================
Complete pipeline from transit nodes to final prioritized hub rankings.

Usage:
    python scripts/run_pipeline.py --config config.yaml

Or run with default paths (edit this file to configure):
    python scripts/run_pipeline.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import geopandas as gpd
import pandas as pd
from datetime import datetime

# Import all pipeline modules
from src.config import (
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    RESULTS_DIR,
    print_config_summary,
)
from src.utils.logging import setup_logger
from src.data import loaders, validators
from src.spatial import h3_operations, merging
from src.classification import eligibility, hierarchy
from src.scoring import monte_carlo
from src.visualization import maps

# Setup logging
logger = setup_logger(__name__)


class HubPrioritizationPipeline:
    """
    Main pipeline orchestrator for hub prioritization framework.
    """

    def __init__(self):
        """Initialize pipeline."""
        self.logger = logger
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Pipeline data holders
        self.transit_nodes = None
        self.lines_modes = None
        self.h3_hexagons = None
        self.grouped_hubs = None
        self.eligible_hubs = None
        self.classified_hubs = None
        self.scored_hubs = None

        self.logger.info("="*80)
        self.logger.info("HUB PRIORITIZATION FRAMEWORK - MAIN PIPELINE")
        self.logger.info("="*80)
        print_config_summary()

    def step_1_load_transit_data(
        self,
        nodes_csv: str,
        lines_modes_csv: str,
    ):
        """
        Step 1: Load transit nodes and line/mode data.

        Args:
            nodes_csv: Path to transit nodes CSV
            lines_modes_csv: Path to lines and modes CSV
        """
        self.logger.info("\n" + "="*80)
        self.logger.info("STEP 1: LOAD TRANSIT DATA")
        self.logger.info("="*80)

        # Load transit nodes
        self.transit_nodes = loaders.load_transit_nodes(nodes_csv)

        # Load lines and modes
        self.lines_modes = loaders.load_lines_and_modes(lines_modes_csv)

        self.logger.info(f"✓ Step 1 complete")

    def step_2_create_h3_hexagons(self):
        """
        Step 2: Assign H3 indices and create hexagon geometries.
        """
        self.logger.info("\n" + "="*80)
        self.logger.info("STEP 2: CREATE H3 HEXAGONS")
        self.logger.info("="*80)

        # Merge transit nodes with mode information
        self.logger.info("Merging transit nodes with mode data...")
        nodes_with_modes = self.transit_nodes.merge(
            self.lines_modes,
            left_on='LINE_ID',
            right_on='Line_ModelName',
            how='left'
        )

        # Assign H3 and aggregate
        self.h3_hexagons = h3_operations.aggregate_by_h3(
            nodes_with_modes,
            mode_column='Mode_Planned',
            line_column='LINE_ID',
            node_column='node'
        )

        # Save intermediate result
        output_path = PROCESSED_DATA_DIR / f"h3_hexagons_{self.timestamp}.csv"
        self.h3_hexagons['geometry'] = self.h3_hexagons['geometry'].apply(lambda x: x.wkt)
        self.h3_hexagons.to_csv(output_path, index=False, encoding='utf-8-sig')
        self.logger.info(f"✓ Saved H3 hexagons to {output_path}")

        self.logger.info(f"✓ Step 2 complete")

    def step_3_group_hexagons(self):
        """
        Step 3: Group nearby hexagons into hub areas.
        """
        self.logger.info("\n" + "="*80)
        self.logger.info("STEP 3: GROUP HEXAGONS INTO HUB AREAS")
        self.logger.info("="*80)

        # Create proximity groups
        hexagons_grouped = merging.create_proximity_groups(self.h3_hexagons)

        # Aggregate groups
        self.grouped_hubs = merging.aggregate_groups(hexagons_grouped)

        # Save intermediate result
        output_path = PROCESSED_DATA_DIR / f"grouped_hubs_{self.timestamp}.csv"
        grouped_export = self.grouped_hubs.copy()
        grouped_export['geometry'] = grouped_export['geometry'].apply(lambda x: x.wkt)
        grouped_export.to_csv(output_path, index=False, encoding='utf-8-sig')
        self.logger.info(f"✓ Saved grouped hubs to {output_path}")

        self.logger.info(f"✓ Step 3 complete")

    def step_4_filter_eligibility(self):
        """
        Step 4: Filter hubs by eligibility criteria.
        """
        self.logger.info("\n" + "="*80)
        self.logger.info("STEP 4: FILTER BY ELIGIBILITY")
        self.logger.info("="*80)

        # Assume demand data has been added (this would normally be loaded)
        # For now, we'll proceed with whatever data exists

        # Add eligibility flags
        hubs_with_flags = eligibility.add_eligibility_flags(
            self.grouped_hubs,
            modes_column='modes'
        )

        # Get summary
        summary = eligibility.get_eligibility_summary(hubs_with_flags)
        self.logger.info(f"\nEligibility Summary:\n{summary}")

        # Filter to eligible only
        self.eligible_hubs = eligibility.filter_eligible_hubs(
            hubs_with_flags,
            modes_column='modes'
        )

        self.logger.info(f"✓ Step 4 complete")

    def step_5_classify_hierarchy(self):
        """
        Step 5: Classify hubs into hierarchy tiers.
        """
        self.logger.info("\n" + "="*80)
        self.logger.info("STEP 5: CLASSIFY HUB HIERARCHY")
        self.logger.info("="*80)

        # Assign tiers
        self.classified_hubs = hierarchy.assign_hub_tiers(self.eligible_hubs)

        # Get statistics
        stats = hierarchy.get_tier_statistics(self.classified_hubs)
        self.logger.info(f"\nTier Statistics:\n{stats}")

        # Add metadata
        self.classified_hubs = hierarchy.add_tier_metadata(self.classified_hubs)

        self.logger.info(f"✓ Step 5 complete")

    def step_6_calculate_scores(self):
        """
        Step 6: Calculate all scoring criteria.
        """
        self.logger.info("\n" + "="*80)
        self.logger.info("STEP 6: CALCULATE SCORES")
        self.logger.info("="*80)

        # Run complete scoring pipeline
        self.scored_hubs = monte_carlo.run_complete_scoring_pipeline(
            self.classified_hubs,
            tier_column='tier'
        )

        # Get score summary
        summary = monte_carlo.get_score_summary(self.scored_hubs)
        self.logger.info(f"\nScore Summary:\n{summary.head(20)}")

        self.logger.info(f"✓ Step 6 complete")

    def step_7_export_results(self):
        """
        Step 7: Export final results.
        """
        self.logger.info("\n" + "="*80)
        self.logger.info("STEP 7: EXPORT RESULTS")
        self.logger.info("="*80)

        # Export to CSV
        csv_path = RESULTS_DIR / f"hub_prioritization_results_{self.timestamp}.csv"
        export_df = self.scored_hubs.copy()
        export_df['geometry'] = export_df['geometry'].apply(lambda x: x.wkt if x else None)
        export_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        self.logger.info(f"✓ Saved results to {csv_path}")

        # Export to GeoJSON
        geojson_path = RESULTS_DIR / f"hub_prioritization_results_{self.timestamp}.geojson"
        self.scored_hubs.to_file(geojson_path, driver='GeoJSON')
        self.logger.info(f"✓ Saved GeoJSON to {geojson_path}")

        # Create map
        map_path = RESULTS_DIR / f"hub_map_{self.timestamp}.html"
        maps.create_hub_map(
            self.scored_hubs,
            color_by='final_score',
            output_file=str(map_path)
        )
        if map_path.exists():
            self.logger.info(f"✓ Saved map to {map_path}")

        self.logger.info(f"✓ Step 7 complete")

    def run_complete_pipeline(
        self,
        nodes_csv: str,
        lines_modes_csv: str,
    ):
        """
        Run the complete pipeline from start to finish.

        Args:
            nodes_csv: Path to transit nodes CSV
            lines_modes_csv: Path to lines and modes CSV
        """
        try:
            # Run all steps
            self.step_1_load_transit_data(nodes_csv, lines_modes_csv)
            self.step_2_create_h3_hexagons()
            self.step_3_group_hexagons()
            self.step_4_filter_eligibility()
            self.step_5_classify_hierarchy()
            self.step_6_calculate_scores()
            self.step_7_export_results()

            # Final summary
            self.logger.info("\n" + "="*80)
            self.logger.info("PIPELINE COMPLETE!")
            self.logger.info("="*80)
            self.logger.info(f"\nFinal Results:")
            self.logger.info(f"  Total hubs processed: {len(self.grouped_hubs)}")
            self.logger.info(f"  Eligible hubs: {len(self.eligible_hubs)}")
            self.logger.info(f"  Classified hubs: {len(self.classified_hubs)}")
            self.logger.info(f"  Scored hubs: {len(self.scored_hubs)}")
            self.logger.info(f"\nResults saved to: {RESULTS_DIR}")

            return self.scored_hubs

        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise


def main():
    """Main entry point."""
    # Configure input file paths here
    # TODO: Update these paths to match your data location
    NODES_CSV = RAW_DATA_DIR / "All_nodes+lines.csv"
    LINES_MODES_CSV = RAW_DATA_DIR / "Lines_and_Planned_Mode.csv"

    # Check if files exist
    if not NODES_CSV.exists():
        logger.error(f"Transit nodes file not found: {NODES_CSV}")
        logger.info("Please update the file path in scripts/run_pipeline.py")
        sys.exit(1)

    if not LINES_MODES_CSV.exists():
        logger.error(f"Lines/modes file not found: {LINES_MODES_CSV}")
        logger.info("Please update the file path in scripts/run_pipeline.py")
        sys.exit(1)

    # Initialize and run pipeline
    pipeline = HubPrioritizationPipeline()
    results = pipeline.run_complete_pipeline(
        nodes_csv=str(NODES_CSV),
        lines_modes_csv=str(LINES_MODES_CSV)
    )

    logger.info("\n✓ Pipeline execution complete!")
    logger.info(f"Top 10 hubs:\n{results.nlargest(10, 'final_score')[['group', 'tier', 'final_score', 'rank']]}")


if __name__ == "__main__":
    main()
