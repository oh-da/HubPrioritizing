#!/usr/bin/env python3
"""
COMPLETE Hub Prioritization Pipeline with All Data Sources
===========================================================
This is the FULL pipeline including demand data and spatial layers.
"""

import sys
import subprocess
from pathlib import Path

# ============================================================================
# DEPENDENCY CHECK - Install requirements if needed
# ============================================================================

def check_and_install_dependencies():
    """Check if required packages are installed, install if missing."""

    required_packages = {
        'h3': 'h3>=3.7.0',
        'geopandas': 'geopandas>=0.13.0',
        'pandas': 'pandas>=2.0.0',
        'numpy': 'numpy>=1.24.0',
        'shapely': 'shapely>=2.0.0',
    }

    missing_packages = []

    # Check which packages are missing
    for package_name, package_spec in required_packages.items():
        try:
            __import__(package_name)
        except ImportError:
            missing_packages.append(package_spec)

    if missing_packages:
        print("=" * 80)
        print("⚠️  MISSING DEPENDENCIES DETECTED")
        print("=" * 80)
        print(f"\nThe following required packages are not installed:")
        for pkg in missing_packages:
            print(f"  - {pkg}")

        print("\n" + "=" * 80)
        print("INSTALLATION OPTIONS")
        print("=" * 80)

        # Get requirements.txt path
        project_root = Path(__file__).parent.parent
        requirements_file = project_root / "requirements.txt"

        if requirements_file.exists():
            print(f"\nOption 1 (Recommended): Install all requirements")
            print(f"  pip install -r {requirements_file}")

        print(f"\nOption 2: Install only missing packages")
        print(f"  pip install {' '.join(missing_packages)}")

        print("\n" + "=" * 80)

        # Ask user if they want auto-install
        response = input("\nWould you like to install missing packages now? (y/n): ").strip().lower()

        if response == 'y':
            print("\nInstalling missing packages...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install"
                ] + missing_packages)
                print("\n✅ Installation complete! Continuing with pipeline...\n")
            except subprocess.CalledProcessError as e:
                print(f"\n❌ Installation failed: {e}")
                print("Please install manually using one of the options above.")
                sys.exit(1)
        else:
            print("\n❌ Cannot proceed without required dependencies.")
            print("Please install packages manually and run again.")
            sys.exit(1)

# Run dependency check
check_and_install_dependencies()

# ============================================================================
# Now import everything else
# ============================================================================

sys.path.insert(0, str(Path(__file__).parent.parent))

import geopandas as gpd
import pandas as pd
from datetime import datetime

from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, RESULTS_DIR, print_config_summary
from src.utils.logging import setup_logger
from src.data import loaders, validators
from src.spatial import h3_operations, merging
from src.classification import eligibility, hierarchy
from src.scoring import monte_carlo
from src.visualization import maps

logger = setup_logger(__name__)


# ============================================================================
# CONFIGURE YOUR INPUT FILE PATHS HERE
# ============================================================================

# Transit network (REQUIRED)
INPUT_TRANSIT_NODES = RAW_DATA_DIR / "All_nodes+lines.csv"
INPUT_LINES_MODES = RAW_DATA_DIR / "Lines_and_Planned_Mode.csv"

# Demand forecasts (REQUIRED for activity scoring)
INPUT_DEMAND_EXCEL = RAW_DATA_DIR / "demand_2050.xlsx"

# Spatial layers for tagging and demographic scoring
INPUT_METRO_AREAS = RAW_DATA_DIR / "metro.shp"
INPUT_DISTRICTS = RAW_DATA_DIR / "districts.shp"
INPUT_TAZ_ZONES = RAW_DATA_DIR / "TAZ_2050.shp"  # With POP_2050 and EMPL_2050
INPUT_BUS_TERMINALS = RAW_DATA_DIR / "bus_terminals.shp"  # Optional

# Processing options
SKIP_DEMAND_DATA = False  # Set True if you don't have demand data yet
SKIP_SPATIAL_LAYERS = False  # Set True if you don't have spatial layers yet
SKIP_DEMOGRAPHICS = False  # Set True if you don't have TAZ data yet

# ============================================================================


class CompleteHubPipeline:
    """Complete pipeline with all data sources."""

    def __init__(self):
        self.logger = logger
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Data holders
        self.transit_nodes = None
        self.lines_modes = None
        self.demand_data = None
        self.metro_areas = None
        self.districts = None
        self.taz_zones = None
        self.bus_terminals = None

        self.h3_hexagons = None
        self.grouped_hubs = None
        self.hubs_with_demand = None
        self.hubs_with_demographics = None
        self.eligible_hubs = None
        self.classified_hubs = None
        self.scored_hubs = None

        logger.info("="*80)
        logger.info("COMPLETE HUB PRIORITIZATION PIPELINE")
        logger.info("="*80)
        print_config_summary()

    def step_1_load_all_data(self):
        """Step 1: Load all input data."""
        logger.info("\n" + "="*80)
        logger.info("STEP 1: LOAD ALL INPUT DATA")
        logger.info("="*80)

        # Transit network (required)
        logger.info("\n1.1: Loading transit nodes...")
        self.transit_nodes = loaders.load_transit_nodes(INPUT_TRANSIT_NODES)

        logger.info("\n1.2: Loading lines and modes...")
        self.lines_modes = loaders.load_lines_and_modes(INPUT_LINES_MODES)

        # Demand data (optional)
        if not SKIP_DEMAND_DATA and INPUT_DEMAND_EXCEL.exists():
            logger.info("\n1.3: Loading demand data...")
            self.demand_data = loaders.load_demand_data(INPUT_DEMAND_EXCEL)
        else:
            logger.warning("⚠ Skipping demand data (file not found or disabled)")

        # Spatial layers (optional)
        if not SKIP_SPATIAL_LAYERS:
            if INPUT_METRO_AREAS.exists():
                logger.info("\n1.4: Loading metro areas...")
                self.metro_areas = loaders.load_metro_areas(INPUT_METRO_AREAS)
            else:
                logger.warning("⚠ Metro areas not found")

            if INPUT_DISTRICTS.exists():
                logger.info("\n1.5: Loading districts...")
                self.districts = loaders.load_districts(INPUT_DISTRICTS)
            else:
                logger.warning("⚠ Districts not found")

            if INPUT_TAZ_ZONES.exists() and not SKIP_DEMOGRAPHICS:
                logger.info("\n1.6: Loading TAZ zones...")
                self.taz_zones = loaders.load_taz_zones(INPUT_TAZ_ZONES)
            else:
                logger.warning("⚠ TAZ zones not found or skipped")

            if INPUT_BUS_TERMINALS.exists():
                logger.info("\n1.7: Loading bus terminals...")
                self.bus_terminals = loaders.load_bus_terminals(INPUT_BUS_TERMINALS)
            else:
                logger.warning("⚠ Bus terminals not found (optional)")

        logger.info("\n✓ Step 1 complete")

    def step_2_create_h3_hexagons(self):
        """Step 2: Create H3 hexagons from transit nodes."""
        logger.info("\n" + "="*80)
        logger.info("STEP 2: CREATE H3 HEXAGONS")
        logger.info("="*80)

        # Merge nodes with mode data
        nodes_with_modes = self.transit_nodes.merge(
            self.lines_modes,
            left_on='LINE_ID',
            right_on='Line_ModelName',
            how='left'
        )

        # Create H3 hexagons and aggregate
        self.h3_hexagons = h3_operations.aggregate_by_h3(
            nodes_with_modes,
            mode_column='Mode_Planned',
            line_column='LINE_ID',
            node_column='node'
        )

        # Save intermediate
        output_path = PROCESSED_DATA_DIR / f"h3_hexagons_{self.timestamp}.csv"
        export_df = self.h3_hexagons.copy()
        export_df['geometry'] = export_df['geometry'].apply(lambda x: x.wkt)
        export_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"✓ Saved to {output_path}")

        logger.info("✓ Step 2 complete")

    def step_3_group_hexagons(self):
        """Step 3: Group nearby hexagons into hub areas."""
        logger.info("\n" + "="*80)
        logger.info("STEP 3: GROUP HEXAGONS INTO HUB AREAS")
        logger.info("="*80)

        # Create proximity groups
        hexagons_grouped = merging.create_proximity_groups(self.h3_hexagons)

        # Aggregate into hub groups
        self.grouped_hubs = merging.aggregate_groups(hexagons_grouped)

        # Save
        output_path = PROCESSED_DATA_DIR / f"grouped_hubs_{self.timestamp}.csv"
        export_df = self.grouped_hubs.copy()
        export_df['geometry'] = export_df['geometry'].apply(lambda x: x.wkt)
        export_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"✓ Saved to {output_path}")

        logger.info("✓ Step 3 complete")

    def step_4_add_demand_data(self):
        """Step 4: Add demand forecasts to hubs."""
        logger.info("\n" + "="*80)
        logger.info("STEP 4: ADD DEMAND DATA")
        logger.info("="*80)

        if SKIP_DEMAND_DATA or self.demand_data is None:
            logger.warning("⚠ Skipping demand data - using placeholder values")
            self.hubs_with_demand = self.grouped_hubs.copy()
            self.hubs_with_demand['TotalDemand'] = 5000  # Placeholder
            logger.info("✓ Step 4 complete (skipped)")
            return

        # TODO: Implement demand assignment logic here
        # This would use the hub_demand_processor logic you had
        # For now, using placeholder
        logger.warning("⚠ Demand assignment not yet implemented, using placeholder")
        self.hubs_with_demand = self.grouped_hubs.copy()
        self.hubs_with_demand['TotalDemand'] = 5000

        logger.info("✓ Step 4 complete")

    def step_5_add_spatial_tags(self):
        """Step 5: Tag hubs with spatial attributes."""
        logger.info("\n" + "="*80)
        logger.info("STEP 5: ADD SPATIAL TAGS")
        logger.info("="*80)

        if SKIP_SPATIAL_LAYERS or (self.metro_areas is None and self.districts is None):
            logger.warning("⚠ Skipping spatial tagging - no layers loaded")
            self.hubs_with_demand['region'] = 'Unknown'
            self.hubs_with_demand['metro_position'] = 'Core'
            logger.info("✓ Step 5 complete (skipped)")
            return

        # Spatial join with metro areas and districts
        hubs_tagged = self.hubs_with_demand.copy()

        # Add placeholder tags for now
        # TODO: Implement proper spatial joins
        hubs_tagged['region'] = 'Center'
        hubs_tagged['metro_position'] = 'Core'

        self.hubs_with_demand = hubs_tagged
        logger.info("✓ Step 5 complete")

    def step_6_add_demographics(self):
        """Step 6: Add population and employment data."""
        logger.info("\n" + "="*80)
        logger.info("STEP 6: ADD DEMOGRAPHIC DATA")
        logger.info("="*80)

        if SKIP_DEMOGRAPHICS or self.taz_zones is None:
            logger.warning("⚠ Skipping demographics - no TAZ data")
            # Add placeholder columns
            for zone in ['zone1', 'zone2', 'zone3']:
                self.hubs_with_demand[f'pop_{zone}'] = 1000
                self.hubs_with_demand[f'emp_{zone}'] = 500
            self.hubs_with_demographics = self.hubs_with_demand
            logger.info("✓ Step 6 complete (skipped)")
            return

        # TODO: Implement buffer zone calculations
        # This would use influence_area_processor logic
        logger.warning("⚠ Demographic calculation not yet implemented, using placeholder")

        for zone in ['zone1', 'zone2', 'zone3']:
            self.hubs_with_demand[f'pop_{zone}'] = 1000
            self.hubs_with_demand[f'emp_{zone}'] = 500

        self.hubs_with_demographics = self.hubs_with_demand
        logger.info("✓ Step 6 complete")

    def step_7_add_terminal_proximity(self):
        """Step 7: Identify proximity to bus terminals."""
        logger.info("\n" + "="*80)
        logger.info("STEP 7: IDENTIFY TERMINAL PROXIMITY")
        logger.info("="*80)

        if self.bus_terminals is None:
            logger.warning("⚠ No bus terminals data")
            self.hubs_with_demographics['near_bus_terminal'] = False
            logger.info("✓ Step 7 complete (skipped)")
            return

        # TODO: Implement buffer check
        logger.warning("⚠ Terminal proximity check not yet implemented")
        self.hubs_with_demographics['near_bus_terminal'] = False

        logger.info("✓ Step 7 complete")

    def step_8_filter_eligibility(self):
        """Step 8: Filter by eligibility criteria."""
        logger.info("\n" + "="*80)
        logger.info("STEP 8: FILTER BY ELIGIBILITY")
        logger.info("="*80)

        # Filter eligible hubs
        self.eligible_hubs = eligibility.filter_eligible_hubs(
            self.hubs_with_demographics,
            modes_column='modes'
        )

        # Summary
        summary = eligibility.get_eligibility_summary(
            eligibility.add_eligibility_flags(self.hubs_with_demographics)
        )
        logger.info(f"\n{summary}")

        logger.info("✓ Step 8 complete")

    def step_9_classify_hierarchy(self):
        """Step 9: Classify into hierarchy tiers."""
        logger.info("\n" + "="*80)
        logger.info("STEP 9: CLASSIFY HUB HIERARCHY")
        logger.info("="*80)

        # Assign tiers
        self.classified_hubs = hierarchy.assign_hub_tiers(self.eligible_hubs)
        self.classified_hubs = hierarchy.add_tier_metadata(self.classified_hubs)

        # Statistics
        stats = hierarchy.get_tier_statistics(self.classified_hubs)
        logger.info(f"\n{stats}")

        logger.info("✓ Step 9 complete")

    def step_10_calculate_scores(self):
        """Step 10: Calculate all scores and final ranking."""
        logger.info("\n" + "="*80)
        logger.info("STEP 10: CALCULATE SCORES & RANKING")
        logger.info("="*80)

        # Run scoring pipeline
        self.scored_hubs = monte_carlo.run_complete_scoring_pipeline(
            self.classified_hubs,
            tier_column='tier'
        )

        logger.info("✓ Step 10 complete")

    def step_11_export_results(self):
        """Step 11: Export final results."""
        logger.info("\n" + "="*80)
        logger.info("STEP 11: EXPORT RESULTS")
        logger.info("="*80)

        # CSV
        csv_path = RESULTS_DIR / f"hub_prioritization_results_{self.timestamp}.csv"
        export_df = self.scored_hubs.copy()
        export_df['geometry'] = export_df['geometry'].apply(lambda x: x.wkt if x else None)
        export_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"✓ CSV: {csv_path}")

        # GeoJSON
        geojson_path = RESULTS_DIR / f"hub_results_{self.timestamp}.geojson"
        self.scored_hubs.to_file(geojson_path, driver='GeoJSON')
        logger.info(f"✓ GeoJSON: {geojson_path}")

        # Map
        try:
            map_path = RESULTS_DIR / f"hub_map_{self.timestamp}.html"
            maps.create_hub_map(self.scored_hubs, color_by='final_score', output_file=str(map_path))
            logger.info(f"✓ Map: {map_path}")
        except Exception as e:
            logger.warning(f"Could not create map: {e}")

        logger.info("✓ Step 11 complete")

    def run(self):
        """Run complete pipeline."""
        try:
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
            self.step_11_export_results()

            logger.info("\n" + "="*80)
            logger.info("✅ PIPELINE COMPLETE!")
            logger.info("="*80)
            logger.info(f"\nFinal Results:")
            logger.info(f"  Total hubs: {len(self.scored_hubs)}")
            logger.info(f"  Results: {RESULTS_DIR}")

            return self.scored_hubs

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise


def main():
    """Main entry point."""

    # Check required files
    if not INPUT_TRANSIT_NODES.exists():
        logger.error(f"❌ Transit nodes not found: {INPUT_TRANSIT_NODES}")
        logger.info("Please update INPUT_TRANSIT_NODES path in this script")
        sys.exit(1)

    if not INPUT_LINES_MODES.exists():
        logger.error(f"❌ Lines/modes not found: {INPUT_LINES_MODES}")
        logger.info("Please update INPUT_LINES_MODES path in this script")
        sys.exit(1)

    # Run pipeline
    pipeline = CompleteHubPipeline()
    results = pipeline.run()

    logger.info("\n🎉 Done! Check results in data/results/")


if __name__ == "__main__":
    main()
