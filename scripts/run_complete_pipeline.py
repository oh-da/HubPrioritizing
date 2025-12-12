#!/usr/bin/env python3
"""
COMPLETE Hub Prioritization Pipeline with All Data Sources
===========================================================
This is the FULL pipeline including demand data and spatial layers.
"""

import sys
import subprocess
import os
from pathlib import Path

# ============================================================================
# SETUP - Change to project directory if needed
# ============================================================================

# Get the project root directory
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Change to project root if not already there
if Path.cwd() != PROJECT_ROOT:
    print(f"Changing working directory to: {PROJECT_ROOT}")
    os.chdir(PROJECT_ROOT)

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
        requirements_file = PROJECT_ROOT / "requirements.txt"

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

# Add project root to Python path
sys.path.insert(0, str(PROJECT_ROOT))

# Verify src directory exists
src_dir = PROJECT_ROOT / "src"
if not src_dir.exists():
    print(f"\n❌ Error: 'src' directory not found!")
    print(f"Current working directory: {Path.cwd()}")
    print(f"Script location: {Path(__file__).resolve()}")
    print(f"Expected project root: {PROJECT_ROOT}")
    print(f"Expected src directory: {src_dir}")
    print("\nDirectory contents:")
    if PROJECT_ROOT.exists():
        print(f"  {list(PROJECT_ROOT.iterdir())[:10]}")
    print("\nPlease ensure the project structure is intact.")
    sys.exit(1)

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

# Import existing data processors
try:
    from hub_demand_processor import DemandDataProcessor
    DEMAND_PROCESSOR_AVAILABLE = True
except ImportError:
    DEMAND_PROCESSOR_AVAILABLE = False
    logger = setup_logger(__name__)
    logger.warning("hub_demand_processor.py not found - will use placeholder demand values")

try:
    from influence_area_processor import InfluenceAreaProcessor
    INFLUENCE_PROCESSOR_AVAILABLE = True
except ImportError:
    INFLUENCE_PROCESSOR_AVAILABLE = False
    if 'logger' not in locals():
        logger = setup_logger(__name__)
    logger.warning("influence_area_processor.py not found - will use placeholder demographic values")

if 'logger' not in locals():
    logger = setup_logger(__name__)


# ============================================================================
# CONFIGURE YOUR INPUT FILE PATHS HERE
# ============================================================================

# Transit network (REQUIRED)
INPUT_TRANSIT_NODES = RAW_DATA_DIR / "All_nodes+lines.csv"
INPUT_LINES_MODES = RAW_DATA_DIR / "Lines_and_Planned_Mode.csv"

# Demand forecasts (REQUIRED for activity scoring)
INPUT_DEMAND_CSV = RAW_DATA_DIR / "Demand_2050_all.csv"

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
        if not SKIP_DEMAND_DATA and INPUT_DEMAND_CSV.exists():
            logger.info("\n1.3: Loading demand data...")
            self.demand_data = loaders.load_demand_data(INPUT_DEMAND_CSV)
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
        """Step 4: Add demand forecasts to hubs.

        Reads demand data from Excel file with multiple worksheets (one per region)
        or from a combined CSV file. Handles various column naming conventions
        used by different regional transport models.
        """
        logger.info("\n" + "="*80)
        logger.info("STEP 4: ADD DEMAND DATA")
        logger.info("="*80)

        if SKIP_DEMAND_DATA:
            logger.warning("⚠ Skipping demand data - disabled")
            self.hubs_with_demand = self.grouped_hubs.copy()
            self.hubs_with_demand['TotalDemand'] = 5000  # Placeholder
            self.hubs_with_demand['TotalTransfers'] = 0
            logger.info("✓ Step 4 complete (skipped)")
            return

        # Sheet name mapping: technical names to region names
        SHEET_NAME_MAPPING = {
            '5040_Daily': 'Haifa',
            'Daily_5087': 'Tel Aviv',
            'Daily_BS': 'Beer Sheva',
            'Daily_Hadera': 'Hadera',
            'Daily_Jerusalem': 'Jerusalem',
            'HaifaNewMetronit': 'Haifa Metronit',
            'Daily_5093': 'Ashdod-Ashkelon',
            'National': 'Rail',
            # Also accept already-mapped names
            'Haifa': 'Haifa',
            'TelAviv': 'Tel Aviv',
            'Tel Aviv': 'Tel Aviv',
            'BeerSheva': 'Beer Sheva',
            'Beer Sheva': 'Beer Sheva',
            'Hadera': 'Hadera',
            'Jerusalem': 'Jerusalem',
            'Ashdod': 'Ashdod-Ashkelon',
            'Ashdod-Ashkelon': 'Ashdod-Ashkelon',
            'Ashkelon': 'Ashdod-Ashkelon',
            'HaifaMetronit': 'Haifa Metronit',
            'Haifa Metronit': 'Haifa Metronit',
        }

        # Per-sheet column configurations
        # Each entry: (node_col_options, boardings_col_options, alightings_col_options, has_transfers)
        SHEET_COLUMN_CONFIG = {
            'Beer Sheva': {
                'node_cols': ['NODE_ID', 'Node', 'node'],
                'boardings_cols': ['Boardings', 'Boardings_Daily', 'TotalBoardings'],
                'alightings_cols': ['Alightings', 'Alightings_Daily', 'TotalAlight'],
                'transfer_cols': [],
            },
            'Hadera': {
                'node_cols': ['NodeID', 'Node', 'node'],
                'boardings_cols': ['On', 'Boardings', 'Boardings_Daily'],
                'alightings_cols': ['Off', 'Alightings', 'Alightings_Daily'],
                'transfer_cols': [],
            },
            'Tel Aviv': {
                'node_cols': ['Node', 'node'],
                'boardings_cols': ['TotalBoardings', 'Boardings', 'Boardings_Daily'],
                'alightings_cols': ['TotalAlight', 'Alightings', 'Alightings_Daily'],
                'transfer_cols': ['TransferBoardings', 'TransferAlight'],
            },
            'Ashdod-Ashkelon': {
                'node_cols': ['Node', 'node'],
                'boardings_cols': ['InitialBoardings', 'Boardings', 'TotalBoardings'],
                'alightings_cols': ['FinalAlight', 'Alightings', 'TotalAlight'],
                'transfer_cols': [],
            },
            'Haifa': {
                'node_cols': ['Node', 'node'],
                'boardings_cols': ['TotalBoardings', 'Boardings', 'Boardings_Daily'],
                'alightings_cols': ['TotalAlight', 'Alightings', 'Alightings_Daily'],
                'transfer_cols': ['TransferBoardings', 'TransferAlight'],
            },
            'Haifa Metronit': {
                'node_cols': ['ModelNode', 'Node', 'node'],
                'boardings_cols': ['Boardings_Daily', 'Boardings', 'TotalBoardings'],
                'alightings_cols': ['Alightings_Daily', 'Alightings', 'TotalAlight'],
                'transfer_cols': [],
            },
            'Jerusalem': {
                'node_cols': ['ID', 'Node', 'node'],
                'boardings_cols': ['DailyBoard_2050', 'Boardings', 'Boardings_Daily'],
                'alightings_cols': ['DailyAlight_2050', 'Alightings', 'Alightings_Daily'],
                'transfer_cols': [],
            },
            'Rail': {
                'node_cols': ['Node', 'node', 'NODE_ID'],
                'boardings_cols': ['Boardings', 'TotalBoardings', 'Boardings_Daily'],
                'alightings_cols': ['Alightings', 'TotalAlight', 'Alightings_Daily'],
                'transfer_cols': [],
            },
        }

        # Default column config for unknown sheets
        DEFAULT_COLUMN_CONFIG = {
            'node_cols': ['Node', 'node', 'NODE_ID', 'NodeID', 'ID', 'ModelNode', 'N'],
            'boardings_cols': ['Boardings', 'TotalBoardings', 'Boardings_Daily', 'InitialBoardings', 'On', 'DailyBoard_2050'],
            'alightings_cols': ['Alightings', 'TotalAlight', 'Alightings_Daily', 'FinalAlight', 'Off', 'DailyAlight_2050'],
            'transfer_cols': ['Transfers', 'TotalTransfers', 'TransferBoardings', 'TransferAlight'],
        }

        def find_column(df_columns, possible_names):
            """Find matching column from list of possible names."""
            for name in possible_names:
                if name in df_columns:
                    return name
                # Case-insensitive fallback
                for col in df_columns:
                    if col.lower() == name.lower():
                        return col
            return None

        def process_sheet(df, sheet_name, region_name):
            """Process a single sheet and return dict of node_id -> (demand, transfers)."""
            # Get column config for this region
            config = SHEET_COLUMN_CONFIG.get(region_name, DEFAULT_COLUMN_CONFIG)

            # Find columns
            node_col = find_column(df.columns, config['node_cols'])
            boardings_col = find_column(df.columns, config['boardings_cols'])
            alightings_col = find_column(df.columns, config['alightings_cols'])
            transfer_cols = [find_column(df.columns, [tc]) for tc in config.get('transfer_cols', [])]
            transfer_cols = [tc for tc in transfer_cols if tc]  # Remove None values

            if node_col is None:
                logger.warning(f"    No node column found in sheet '{sheet_name}' (region: {region_name})")
                logger.warning(f"    Available columns: {list(df.columns)}")
                logger.warning(f"    Tried: {config['node_cols']}")
                return {}

            logger.info(f"    Using columns: node='{node_col}', boardings='{boardings_col}', alightings='{alightings_col}'")
            if transfer_cols:
                logger.info(f"    Transfer columns: {transfer_cols}")

            result = {}
            rows_processed = 0

            for _, row in df.iterrows():
                try:
                    # Get node ID
                    node_val = row[node_col]
                    if pd.isna(node_val):
                        continue
                    node_id = int(float(node_val))

                    # Calculate boardings
                    boardings = 0
                    if boardings_col and pd.notna(row.get(boardings_col)):
                        boardings = float(row[boardings_col])

                    # Calculate alightings
                    alightings = 0
                    if alightings_col and pd.notna(row.get(alightings_col)):
                        alightings = float(row[alightings_col])

                    demand = boardings + alightings

                    # Calculate transfers (sum of transfer columns)
                    transfers = 0
                    for tc in transfer_cols:
                        if pd.notna(row.get(tc)):
                            transfers += float(row[tc])

                    # Store result
                    if node_id not in result:
                        result[node_id] = {'demand': demand, 'transfers': transfers}
                    else:
                        result[node_id]['demand'] += demand
                        result[node_id]['transfers'] += transfers

                    rows_processed += 1

                except (ValueError, TypeError) as e:
                    continue

            logger.info(f"    Processed {rows_processed} rows, {len(result)} unique nodes")
            return result

        # Try to find demand file (Excel or CSV)
        demand_excel = RAW_DATA_DIR / "Demand_2050_all.xlsx"
        demand_xls = RAW_DATA_DIR / "Demand_2050_all.xls"
        # Also check for the original filename pattern
        demand_excel_alt = RAW_DATA_DIR / "Nodes_w_results_21082025.xlsx"
        demand_csv = INPUT_DEMAND_CSV

        node_demand = {}

        try:
            # Try Excel file first (with multiple sheets)
            excel_file = None
            for ef in [demand_excel, demand_xls, demand_excel_alt]:
                if ef.exists():
                    excel_file = ef
                    break

            if excel_file:
                logger.info(f"Loading demand from Excel: {excel_file}")

                # Get all sheet names
                xl = pd.ExcelFile(excel_file)
                raw_sheet_names = xl.sheet_names
                logger.info(f"Found sheets: {raw_sheet_names}")

                # Process each sheet
                for sheet in raw_sheet_names:
                    # Map sheet name to region name
                    region_name = SHEET_NAME_MAPPING.get(sheet)
                    if region_name is None:
                        # Try case-insensitive match
                        for key, value in SHEET_NAME_MAPPING.items():
                            if key.lower() == sheet.lower():
                                region_name = value
                                break

                    if region_name is None:
                        logger.warning(f"  Sheet '{sheet}': Unknown region, using default config")
                        region_name = sheet  # Use sheet name as region name

                    try:
                        df = pd.read_excel(excel_file, sheet_name=sheet)
                        logger.info(f"  Sheet '{sheet}' → Region '{region_name}': {len(df)} rows")
                        logger.info(f"    Columns: {list(df.columns)}")

                        sheet_demand = process_sheet(df, sheet, region_name)

                        # Merge into main demand dict
                        for node_id, data in sheet_demand.items():
                            if node_id not in node_demand:
                                node_demand[node_id] = {'demand': data['demand'], 'transfers': data['transfers']}
                            else:
                                node_demand[node_id]['demand'] += data['demand']
                                node_demand[node_id]['transfers'] += data['transfers']

                    except Exception as e:
                        logger.warning(f"    Error loading sheet '{sheet}': {e}")

            # If no Excel or no data found, try CSV
            elif demand_csv.exists():
                logger.info(f"Loading demand from CSV: {demand_csv}")
                df_demand = pd.read_csv(demand_csv, encoding='utf-8-sig')
                logger.info(f"Loaded {len(df_demand)} rows")
                logger.info(f"Columns: {list(df_demand.columns)}")

                # Use default config for CSV
                sheet_demand = process_sheet(df_demand, 'CSV', 'default')
                node_demand = sheet_demand

            else:
                logger.warning("⚠ No demand file found!")
                logger.info(f"  Looked for: {demand_excel}, {demand_xls}, {demand_excel_alt}, {demand_csv}")
                self.hubs_with_demand = self.grouped_hubs.copy()
                self.hubs_with_demand['TotalDemand'] = 5000  # Placeholder
                self.hubs_with_demand['TotalTransfers'] = 0
                logger.info("✓ Step 4 complete (no file)")
                return

            logger.info(f"\n✓ Total demand loaded for {len(node_demand)} unique nodes")

            # Debug: Show sample of node IDs from demand data
            sample_demand_nodes = list(node_demand.keys())[:10]
            logger.info(f"  Sample demand node IDs: {sample_demand_nodes}")

            # Match demand to grouped hubs
            hubs_with_demand = self.grouped_hubs.copy()

            # Initialize demand columns
            hubs_with_demand['TotalDemand'] = 0.0
            hubs_with_demand['TotalTransfers'] = 0.0

            # Debug: Show sample of node IDs from hubs
            import ast
            sample_hub_nodes = []
            for idx, row in hubs_with_demand.head(5).iterrows():
                nodes = row.get('node', [])
                if isinstance(nodes, str):
                    try:
                        nodes = ast.literal_eval(nodes)
                    except:
                        nodes = [nodes]
                sample_hub_nodes.extend(nodes[:3] if isinstance(nodes, list) else [nodes])
            logger.info(f"  Sample hub node IDs: {sample_hub_nodes[:10]}")

            # For each hub group, sum demand from all its nodes
            matched_hubs = 0
            total_nodes_checked = 0
            total_nodes_matched = 0

            for idx, row in hubs_with_demand.iterrows():
                # Get list of nodes in this hub group
                nodes_in_group = row.get('node', [])

                # Handle string representation of list from CSV (e.g., "[123, 456]")
                if isinstance(nodes_in_group, str):
                    try:
                        nodes_in_group = ast.literal_eval(nodes_in_group)
                    except (ValueError, SyntaxError):
                        nodes_in_group = [nodes_in_group]

                # Handle if it's a single value or list
                if not isinstance(nodes_in_group, list):
                    nodes_in_group = [nodes_in_group]

                # Sum demand from all nodes in the group
                total_demand = 0
                total_transfers = 0
                nodes_matched = 0

                for node in nodes_in_group:
                    total_nodes_checked += 1
                    try:
                        node = int(node)
                    except (ValueError, TypeError):
                        continue

                    if node in node_demand:
                        total_demand += node_demand[node]['demand']
                        total_transfers += node_demand[node]['transfers']
                        nodes_matched += 1
                        total_nodes_matched += 1

                # Assign to hub
                hubs_with_demand.at[idx, 'TotalDemand'] = total_demand
                hubs_with_demand.at[idx, 'TotalTransfers'] = total_transfers

                if nodes_matched > 0:
                    matched_hubs += 1

            # Summary statistics
            logger.info("\n  DEMAND MATCHING SUMMARY:")
            logger.info(f"  ─────────────────────────")
            logger.info(f"  Hub groups processed: {len(hubs_with_demand)}")
            logger.info(f"  Hub groups with demand: {matched_hubs} ({matched_hubs/len(hubs_with_demand)*100:.1f}%)")
            logger.info(f"  Hub groups without demand: {len(hubs_with_demand) - matched_hubs}")
            logger.info(f"  Nodes checked: {total_nodes_checked}")
            logger.info(f"  Nodes matched: {total_nodes_matched} ({total_nodes_matched/max(total_nodes_checked,1)*100:.1f}%)")
            logger.info(f"  Total demand: {hubs_with_demand['TotalDemand'].sum():,.0f}")
            logger.info(f"  Total transfers: {hubs_with_demand['TotalTransfers'].sum():,.0f}")
            logger.info(f"  Demand range: {hubs_with_demand['TotalDemand'].min():,.0f} - {hubs_with_demand['TotalDemand'].max():,.0f}")

            # Flag hubs with no demand for debugging
            hubs_with_demand['has_demand_data'] = hubs_with_demand['TotalDemand'] > 0

            if total_nodes_matched == 0:
                logger.warning("\n  ⚠ WARNING: No nodes were matched to demand data!")
                logger.warning("     Possible causes:")
                logger.warning("     1. Node IDs in demand file don't match node IDs in hub groups")
                logger.warning("     2. Demand file uses different node numbering system")
                logger.warning("     3. Node column format mismatch (string vs integer)")
                logger.warning("     Check sample node IDs above to compare formats")

            self.hubs_with_demand = hubs_with_demand
            logger.info("\n✓ Step 4 complete")

        except Exception as e:
            logger.error(f"Error loading demand data: {e}", exc_info=True)
            logger.warning("Using placeholder values")
            self.hubs_with_demand = self.grouped_hubs.copy()
            self.hubs_with_demand['TotalDemand'] = 5000
            self.hubs_with_demand['TotalTransfers'] = 0
            logger.info("✓ Step 4 complete (error - used placeholders)")

    def step_5_add_spatial_tags(self):
        """Step 5: Tag hubs with spatial attributes."""
        logger.info("\n" + "="*80)
        logger.info("STEP 5: ADD SPATIAL TAGS (for location scoring)")
        logger.info("="*80)

        hubs_tagged = self.hubs_with_demand.copy()

        # Convert to projected CRS for spatial operations
        hubs_proj = hubs_tagged.to_crs('EPSG:2039')

        # Tag with district (for region determination)
        if self.districts is not None and not SKIP_SPATIAL_LAYERS:
            logger.info("Spatial join with districts...")
            try:
                # Find district column
                district_col = None
                for col in ['MACHOZ', 'SHEM_NAFA', 'District', 'district', 'NAME']:
                    if col in self.districts.columns:
                        district_col = col
                        break

                if district_col:
                    districts_proj = self.districts.to_crs('EPSG:2039')
                    joined = gpd.sjoin(hubs_proj, districts_proj[[district_col, 'geometry']],
                                     how='left', predicate='within')

                    # Handle duplicates
                    if joined.index.duplicated().any():
                        joined = joined[~joined.index.duplicated(keep='first')]

                    hubs_tagged['district'] = joined[district_col]

                    # Map district to region
                    def map_to_region(district):
                        if pd.isna(district):
                            return 'Center'
                        dist_lower = str(district).lower()
                        if 'חיפה' in dist_lower or 'haifa' in dist_lower:
                            return 'Haifa'
                        elif 'צפון' in dist_lower or 'north' in dist_lower:
                            return 'North'
                        elif 'דרום' in dist_lower or 'south' in dist_lower or 'באר שבע' in dist_lower:
                            return 'South'
                        elif 'ירושלים' in dist_lower or 'jerusalem' in dist_lower:
                            return 'Jerusalem'
                        else:
                            return 'Center'

                    hubs_tagged['region'] = hubs_tagged['district'].apply(map_to_region)
                    logger.info(f"✓ Tagged with districts")
                else:
                    logger.warning("No district column found")
                    hubs_tagged['region'] = 'Center'
                    hubs_tagged['district'] = 'Unknown'
            except Exception as e:
                logger.warning(f"District tagging failed: {e}")
                hubs_tagged['region'] = 'Center'
                hubs_tagged['district'] = 'Unknown'
        else:
            logger.warning("No districts layer - using default region")
            hubs_tagged['region'] = 'Center'
            hubs_tagged['district'] = 'Unknown'

        # Tag with metro position (simplified - using distance from city centers)
        # TODO: Implement proper metro position determination
        hubs_tagged['metro_position'] = 'Core'  # Default for now

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

        if not INFLUENCE_PROCESSOR_AVAILABLE:
            logger.warning("⚠ InfluenceAreaProcessor not available - using placeholder")
            for zone in ['zone1', 'zone2', 'zone3']:
                self.hubs_with_demand[f'pop_{zone}'] = 1000
                self.hubs_with_demand[f'emp_{zone}'] = 500
            self.hubs_with_demographics = self.hubs_with_demand
            logger.info("✓ Step 6 complete (placeholder)")
            return

        # Use the actual influence area processor
        logger.info("Using InfluenceAreaProcessor...")
        processor = InfluenceAreaProcessor()

        # Save hubs temporarily
        temp_csv = PROCESSED_DATA_DIR / f"temp_hubs_{self.timestamp}.csv"
        export_df = self.hubs_with_demand.copy()
        export_df['geometry'] = export_df['geometry'].apply(lambda x: x.wkt if x else None)
        export_df.to_csv(temp_csv, index=False, encoding='utf-8-sig')

        # Process influence areas
        try:
            result_gdf = processor.process_full_pipeline(
                hubs_csv=str(temp_csv),
                taz_shp=str(INPUT_TAZ_ZONES),
                terminals_shp=str(INPUT_BUS_TERMINALS) if INPUT_BUS_TERMINALS.exists() else None,
                output_csv=None  # Don't save intermediate file
            )
            self.hubs_with_demographics = result_gdf
            logger.info("✓ Demographics added successfully")
        except Exception as e:
            logger.error(f"Demographics processing failed: {e}")
            logger.warning("Using placeholder values")
            for zone in ['zone1', 'zone2', 'zone3']:
                self.hubs_with_demand[f'pop_{zone}'] = 1000
                self.hubs_with_demand[f'emp_{zone}'] = 500
            self.hubs_with_demographics = self.hubs_with_demand

        # Clean up temp file
        if temp_csv.exists():
            temp_csv.unlink()

        logger.info("✓ Step 6 complete")

    def step_7_add_terminal_proximity(self):
        """Step 7: Identify proximity to bus terminals."""
        logger.info("\n" + "="*80)
        logger.info("STEP 7: IDENTIFY TERMINAL PROXIMITY")
        logger.info("="*80)

        # Check if already added by influence area processor
        if 'near_bus_terminal' in self.hubs_with_demographics.columns:
            logger.info("✓ Terminal proximity already added by InfluenceAreaProcessor")
            return

        if self.bus_terminals is None:
            logger.warning("⚠ No bus terminals data")
            self.hubs_with_demographics['near_bus_terminal'] = False
            logger.info("✓ Step 7 complete (skipped)")
            return

        # Implement buffer check
        logger.info("Checking terminal proximity (200m buffer)...")
        try:
            hubs_proj = self.hubs_with_demographics.to_crs('EPSG:2039')
            terminals_proj = self.bus_terminals.to_crs('EPSG:2039')

            # Create 200m buffer around hub centroids
            centroids = hubs_proj.geometry.centroid
            buffers = centroids.buffer(200)

            # Check intersections
            near_terminal = []
            for buffer in buffers:
                intersects = terminals_proj.intersects(buffer).any()
                near_terminal.append(intersects)

            self.hubs_with_demographics['near_bus_terminal'] = near_terminal

            n_near = sum(near_terminal)
            logger.info(f"✓ Found {n_near} hubs near terminals ({n_near/len(near_terminal)*100:.1f}%)")
        except Exception as e:
            logger.warning(f"Terminal proximity check failed: {e}")
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
