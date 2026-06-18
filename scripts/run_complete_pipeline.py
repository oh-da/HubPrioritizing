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

# Run the interactive dependency check only when this script is executed
# directly. When the module is imported (e.g. by the GUI), we must not block on
# input(); missing imports will surface naturally as ImportError instead.
if __name__ == "__main__":
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

import json
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List

import geopandas as gpd
import pandas as pd
from datetime import datetime

from src.config import (
    RAW_DATA_DIR, PROCESSED_DATA_DIR, RESULTS_DIR,
    print_config_summary,
    MC_DIST_EXPORT_RAW_SCORES,
    MC_DIST_TOP_N_HUBS,
    MONTE_CARLO_ITERATIONS,
    MONTE_CARLO_RANDOM_SEED,
    REQUIRE_NON_RAIL_MODE,
    RAIL_ONLY_MODES,
    NON_RAIL_TRANSIT_MODES,
)
from src.utils.logging import setup_logger
from src.data import loaders, validators
from src.spatial import h3_operations, merging
from src.classification import eligibility, hierarchy
from src.scoring import monte_carlo
from src.visualization import maps

# Import existing data processors
try:
    from src.data.hub_demand_processor import DemandDataProcessor
    DEMAND_PROCESSOR_AVAILABLE = True
except ImportError:
    DEMAND_PROCESSOR_AVAILABLE = False
    logger = setup_logger(__name__)
    logger.warning("src.data.hub_demand_processor not found - will use placeholder demand values")

try:
    from src.data.influence_area_processor import InfluenceAreaProcessor
    INFLUENCE_PROCESSOR_AVAILABLE = True
except ImportError:
    INFLUENCE_PROCESSOR_AVAILABLE = False
    if 'logger' not in locals():
        logger = setup_logger(__name__)
    logger.warning("src.data.influence_area_processor not found - will use placeholder demographic values")

if 'logger' not in locals():
    logger = setup_logger(__name__)


# ============================================================================
# DEFAULT INPUT FILE PATHS (used by the CLI / as fallbacks)
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


# ============================================================================
# RUN CONFIGURATION
# ============================================================================
# A RunConfig fully describes one execution of the pipeline: which input files
# to use, where to write outputs, which optional steps to run, and run metadata
# (who ran it and why). The GUI builds a RunConfig from user selections; the
# CLI builds a default one from the paths above.

# Field name -> list of filename match hints (lowercase substrings / patterns)
# used by resolve_inputs_from_directory() to auto-detect files in a folder.
INPUT_FILE_HINTS = {
    'transit_nodes': {'ext': ['.csv'], 'contains': ['nodes']},
    'lines_modes': {'ext': ['.csv'], 'contains': ['lines', 'mode']},
    'demand': {'ext': ['.xlsx', '.xls', '.csv'], 'contains': ['demand', 'nodes_w_results']},
    'metro_areas': {'ext': ['.shp'], 'contains': ['metro']},
    'districts': {'ext': ['.shp'], 'contains': ['district', 'machoz']},
    'taz_zones': {'ext': ['.shp'], 'contains': ['taz']},
    'bus_terminals': {'ext': ['.shp'], 'contains': ['terminal', 'bus_term']},
}

# Which inputs are mandatory for a run to proceed
REQUIRED_INPUTS = ['transit_nodes', 'lines_modes']


@dataclass
class RunConfig:
    """Full configuration for a single pipeline run."""

    # --- Input files (None = not provided) ---
    transit_nodes: Optional[Path] = None
    lines_modes: Optional[Path] = None
    demand: Optional[Path] = None
    metro_areas: Optional[Path] = None
    districts: Optional[Path] = None
    taz_zones: Optional[Path] = None
    bus_terminals: Optional[Path] = None

    # --- Output ---
    output_dir: Optional[Path] = None

    # --- Optional-step toggles ---
    skip_demand_data: bool = False
    skip_spatial_layers: bool = False
    skip_demographics: bool = False
    run_mc_distribution: bool = False

    # --- Run metadata (for the run log) ---
    run_by: str = ""
    remarks: str = ""
    run_id: str = field(default_factory=lambda: datetime.now().strftime('%Y%m%d_%H%M%S'))

    def __post_init__(self):
        # Normalise provided paths to Path objects
        for f in ['transit_nodes', 'lines_modes', 'demand', 'metro_areas',
                  'districts', 'taz_zones', 'bus_terminals', 'output_dir']:
            val = getattr(self, f)
            if val is not None and not isinstance(val, Path):
                setattr(self, f, Path(val))

        # Default output dir: data/results/run_<run_id>/
        if self.output_dir is None:
            self.output_dir = RESULTS_DIR / f"run_{self.run_id}"

    @property
    def results_dir(self) -> Path:
        """Directory for final outputs (CSV / GeoJSON / map / logs)."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir

    @property
    def processed_dir(self) -> Path:
        """Directory for intermediate artefacts."""
        d = self.output_dir / "processed"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def validate(self) -> List[str]:
        """Return a list of human-readable problems (empty = OK)."""
        problems = []
        for key in REQUIRED_INPUTS:
            val = getattr(self, key)
            if val is None:
                problems.append(f"Missing required input: {key}")
            elif not Path(val).exists():
                problems.append(f"Required input not found on disk: {val}")
        return problems


def default_run_config(**overrides) -> RunConfig:
    """Build a RunConfig from the default RAW_DATA_DIR paths (CLI behaviour)."""
    cfg = RunConfig(
        transit_nodes=INPUT_TRANSIT_NODES,
        lines_modes=INPUT_LINES_MODES,
        demand=INPUT_DEMAND_CSV if INPUT_DEMAND_CSV.exists() else None,
        metro_areas=INPUT_METRO_AREAS if INPUT_METRO_AREAS.exists() else None,
        districts=INPUT_DISTRICTS if INPUT_DISTRICTS.exists() else None,
        taz_zones=INPUT_TAZ_ZONES if INPUT_TAZ_ZONES.exists() else None,
        bus_terminals=INPUT_BUS_TERMINALS if INPUT_BUS_TERMINALS.exists() else None,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    cfg.__post_init__()
    return cfg


def resolve_inputs_from_directory(directory) -> Dict[str, Optional[str]]:
    """Scan a directory and auto-match expected input files by name/extension.

    Args:
        directory: Folder to scan (str or Path).

    Returns:
        Dict mapping each input field name to a matched file path (or None).
    """
    directory = Path(directory)
    found: Dict[str, Optional[str]] = {k: None for k in INPUT_FILE_HINTS}

    if not directory.is_dir():
        return found

    files = [p for p in directory.rglob('*') if p.is_file()]
    used: set = set()  # paths already claimed by an earlier field

    def score(path: Path, hints) -> int:
        """Number of hint words found in the filename stem (0 = no name match)."""
        stem = path.stem.lower()
        return sum(1 for c in hints['contains'] if c in stem)

    # Fields are processed in INPUT_FILE_HINTS order, which is arranged so that
    # the more specific names (e.g. 'nodes') claim their file before a more
    # generic hint (e.g. 'lines', which also appears in 'All_nodes+lines.csv').
    for field_name, hints in INPUT_FILE_HINTS.items():
        best = None
        best_score = 0
        for ext in hints['ext']:
            candidates = [p for p in files
                          if p.suffix.lower() == ext and p not in used]
            # Prefer the candidate matching the most hint words
            for p in candidates:
                s = score(p, hints)
                if s > best_score:
                    best, best_score = p, s
            if best is not None:
                break
            # If nothing name-matched but exactly one file of a single allowed
            # extension exists, accept it (unambiguous type, e.g. a lone .shp).
            if len(hints['ext']) == 1 and len(candidates) == 1:
                best = candidates[0]
                break
        if best is not None:
            used.add(best)
            found[field_name] = str(best)

    return found

# ============================================================================


class CompleteHubPipeline:
    """Complete pipeline with all data sources."""

    def __init__(self, config: Optional[RunConfig] = None):
        self.config = config if config is not None else default_run_config()
        self.logger = logger
        self.timestamp = self.config.run_id
        self.started_at = datetime.now()
        self.output_files: List[str] = []
        self.status = "running"
        self.error_message = None

        # Attach a per-run log file inside the output directory
        self._run_log_path = self.config.results_dir / f"run_{self.timestamp}.log"
        self._run_log_handler = logging.FileHandler(self._run_log_path, encoding='utf-8')
        self._run_log_handler.setLevel(logging.DEBUG)
        self._run_log_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(self._run_log_handler)

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
        self.mc_dist_results = None

        logger.info("="*80)
        logger.info("COMPLETE HUB PRIORITIZATION PIPELINE")
        logger.info("="*80)
        print_config_summary()

    def step_1_load_all_data(self):
        """Step 1: Load all input data."""
        logger.info("\n" + "="*80)
        logger.info("STEP 1: LOAD ALL INPUT DATA")
        logger.info("="*80)

        cfg = self.config

        # Transit network (required)
        logger.info("\n1.1: Loading transit nodes...")
        self.transit_nodes = loaders.load_transit_nodes(cfg.transit_nodes)

        logger.info("\n1.2: Loading lines and modes...")
        self.lines_modes = loaders.load_lines_and_modes(cfg.lines_modes)

        # Demand data (optional)
        if not cfg.skip_demand_data and cfg.demand and Path(cfg.demand).exists():
            logger.info("\n1.3: Loading demand data...")
            self.demand_data = loaders.load_demand_data(cfg.demand)
        else:
            logger.warning("⚠ Skipping demand data (file not found or disabled)")

        # Spatial layers (optional)
        if not cfg.skip_spatial_layers:
            if cfg.metro_areas and Path(cfg.metro_areas).exists():
                logger.info("\n1.4: Loading metro areas...")
                self.metro_areas = loaders.load_metro_areas(cfg.metro_areas)
            else:
                logger.warning("⚠ Metro areas not found")

            if cfg.districts and Path(cfg.districts).exists():
                logger.info("\n1.5: Loading districts...")
                self.districts = loaders.load_districts(cfg.districts)
            else:
                logger.warning("⚠ Districts not found")

            if cfg.taz_zones and Path(cfg.taz_zones).exists() and not cfg.skip_demographics:
                logger.info("\n1.6: Loading TAZ zones...")
                self.taz_zones = loaders.load_taz_zones(cfg.taz_zones)
            else:
                logger.warning("⚠ TAZ zones not found or skipped")

            if cfg.bus_terminals and Path(cfg.bus_terminals).exists():
                logger.info("\n1.7: Loading bus terminals...")
                self.bus_terminals = loaders.load_bus_terminals(cfg.bus_terminals)
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
        output_path = self.config.processed_dir / f"h3_hexagons_{self.timestamp}.csv"
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
        output_path = self.config.processed_dir / f"grouped_hubs_{self.timestamp}.csv"
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

        if self.config.skip_demand_data:
            logger.warning("⚠ Skipping demand data - disabled")
            self.hubs_with_demand = self.grouped_hubs.copy()
            self.hubs_with_demand['TotalDemand'] = 5000  # Placeholder
            self.hubs_with_demand['TotalTransfers'] = 0
            logger.info("✓ Step 4 complete (skipped)")
            return

        # First, assign 'area' column from metro/districts if available (needed for area-based demand matching)
        # Based on HubsCode_to_1_file.ipynb: uses metro shapefile first (METRO_NAME), then districts (MACHOZ)
        if 'area' not in self.grouped_hubs.columns or self.grouped_hubs['area'].isna().all() or (self.grouped_hubs['area'] == 'Unknown').all():
            logger.info("Assigning area from spatial layers for demand matching...")

            # Debug: Check what spatial layers are available
            logger.info(f"  Metro areas layer: {'LOADED' if self.metro_areas is not None else 'NOT LOADED'}")
            logger.info(f"  Districts layer: {'LOADED' if self.districts is not None else 'NOT LOADED'}")

            if self.metro_areas is not None:
                logger.info(f"  Metro columns: {list(self.metro_areas.columns)}")
            if self.districts is not None:
                logger.info(f"  Districts columns: {list(self.districts.columns)}")

            # Initialize area column
            self.grouped_hubs['area'] = None

            # Try metro shapefile first (has METRO_NAME column)
            if self.metro_areas is not None:
                try:
                    logger.info("  Trying metro layer...")
                    hubs_wgs = self.grouped_hubs.to_crs('EPSG:4326')
                    metro_wgs = self.metro_areas.to_crs('EPSG:4326')

                    logger.info(f"  Hub bounds: {hubs_wgs.total_bounds}")
                    logger.info(f"  Metro bounds: {metro_wgs.total_bounds}")

                    # Find metro name column
                    metro_col = None
                    for col in ['METRO_NAME', 'MetroName', 'metro_name', 'NAME', 'name']:
                        if col in metro_wgs.columns:
                            metro_col = col
                            break

                    if metro_col:
                        logger.info(f"  Using metro column: {metro_col}")
                        logger.info(f"  Metro values: {metro_wgs[metro_col].unique().tolist()}")

                        joined = gpd.sjoin(hubs_wgs, metro_wgs[[metro_col, 'geometry']],
                                         how='left', predicate='intersects')
                        if joined.index.duplicated().any():
                            joined = joined[~joined.index.duplicated(keep='first')]
                        self.grouped_hubs['area'] = joined[metro_col].values
                        n_tagged = self.grouped_hubs['area'].notna().sum()
                        logger.info(f"  ✓ Tagged {n_tagged}/{len(self.grouped_hubs)} hubs from metro layer")
                    else:
                        logger.warning(f"  No metro name column found!")
                except Exception as e:
                    logger.warning(f"  Metro tagging failed: {e}")
                    import traceback
                    logger.warning(f"  {traceback.format_exc()}")

            # Fall back to districts for untagged hubs (has MACHOZ column)
            if self.districts is not None:
                try:
                    nan_mask = self.grouped_hubs['area'].isna()
                    if nan_mask.any():
                        logger.info(f"  Trying districts layer for {nan_mask.sum()} untagged hubs...")
                        hubs_wgs = self.grouped_hubs[nan_mask].to_crs('EPSG:4326')
                        districts_wgs = self.districts.to_crs('EPSG:4326')

                        logger.info(f"  Hub bounds (untagged): {hubs_wgs.total_bounds}")
                        logger.info(f"  Districts bounds: {districts_wgs.total_bounds}")

                        # Find district name column
                        district_col = None
                        for col in ['MACHOZ', 'SHEM_MACHOZ', 'SHEM_NAFA', 'District', 'NAME']:
                            if col in districts_wgs.columns:
                                district_col = col
                                break

                        if district_col:
                            logger.info(f"  Using district column: {district_col}")
                            logger.info(f"  District values: {districts_wgs[district_col].unique().tolist()}")

                            joined = gpd.sjoin(hubs_wgs, districts_wgs[[district_col, 'geometry']],
                                             how='left', predicate='within')
                            if joined.index.duplicated().any():
                                joined = joined[~joined.index.duplicated(keep='first')]

                            logger.info(f"  Joined result - NaN count: {joined[district_col].isna().sum()}/{len(joined)}")

                            # Update only the NaN rows
                            for idx in joined.index:
                                if pd.notna(joined.loc[idx, district_col]):
                                    self.grouped_hubs.loc[idx, 'area'] = joined.loc[idx, district_col]

                            n_tagged_district = self.grouped_hubs['area'].notna().sum() - (~nan_mask).sum()
                            logger.info(f"  ✓ Tagged {n_tagged_district} additional hubs from districts layer")
                        else:
                            logger.warning(f"  No district column found in districts layer!")
                except Exception as e:
                    logger.warning(f"  District tagging failed: {e}")
                    import traceback
                    logger.warning(f"  {traceback.format_exc()}")

            # Fill remaining NaN with 'Unknown'
            self.grouped_hubs['area'] = self.grouped_hubs['area'].fillna('Unknown')
            logger.info(f"  Areas found: {self.grouped_hubs['area'].unique().tolist()}")

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

        # Determine demand file from the run configuration. Excel (multi-sheet)
        # is preferred; a single CSV is also supported. Fall back to the legacy
        # default locations only when no demand file was configured.
        configured_demand = Path(self.config.demand) if self.config.demand else None

        excel_file = None
        demand_csv = None
        if configured_demand and configured_demand.exists():
            if configured_demand.suffix.lower() in ('.xlsx', '.xls'):
                excel_file = configured_demand
            else:
                demand_csv = configured_demand
        else:
            # Legacy fallbacks (CLI without explicit config)
            for ef in [RAW_DATA_DIR / "Demand_2050_all.xlsx",
                       RAW_DATA_DIR / "Demand_2050_all.xls",
                       RAW_DATA_DIR / "Nodes_w_results_21082025.xlsx"]:
                if ef.exists():
                    excel_file = ef
                    break
            if excel_file is None and INPUT_DEMAND_CSV.exists():
                demand_csv = INPUT_DEMAND_CSV

        node_demand = {}

        try:
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
            elif demand_csv and demand_csv.exists():
                logger.info(f"Loading demand from CSV: {demand_csv}")
                df_demand = pd.read_csv(demand_csv, encoding='utf-8-sig')
                logger.info(f"Loaded {len(df_demand)} rows")
                logger.info(f"Columns: {list(df_demand.columns)}")

                # Use default config for CSV
                sheet_demand = process_sheet(df_demand, 'CSV', 'default')
                node_demand = sheet_demand

            else:
                logger.warning("⚠ No demand file found!")
                logger.info(f"  Configured demand file: {configured_demand}")
                self.hubs_with_demand = self.grouped_hubs.copy()
                self.hubs_with_demand['TotalDemand'] = 5000  # Placeholder
                self.hubs_with_demand['TotalTransfers'] = 0
                logger.info("✓ Step 4 complete (no file)")
                return

            logger.info(f"\n✓ Total demand loaded for {len(node_demand)} unique nodes")

            # Debug: Show sample of node IDs from demand data
            sample_demand_nodes = list(node_demand.keys())[:10]
            logger.info(f"  Sample demand node IDs: {sample_demand_nodes}")

            # Also store demand by region for area-based matching
            # region_demand = {region_name: {node_id: {demand, transfers}}}
            region_demand = {}
            for sheet in raw_sheet_names if excel_file else []:
                region_name = SHEET_NAME_MAPPING.get(sheet, sheet)
                if region_name not in region_demand:
                    region_demand[region_name] = {}
                try:
                    df = pd.read_excel(excel_file, sheet_name=sheet)
                    config = SHEET_COLUMN_CONFIG.get(region_name, DEFAULT_COLUMN_CONFIG)
                    node_col = find_column(df.columns, config['node_cols'])
                    boardings_col = find_column(df.columns, config['boardings_cols'])
                    alightings_col = find_column(df.columns, config['alightings_cols'])

                    if node_col:
                        for _, row in df.iterrows():
                            try:
                                node_val = row[node_col]
                                if pd.isna(node_val):
                                    continue
                                node_id = int(float(node_val))
                                boardings = float(row[boardings_col]) if boardings_col and pd.notna(row.get(boardings_col)) else 0
                                alightings = float(row[alightings_col]) if alightings_col and pd.notna(row.get(alightings_col)) else 0
                                demand = boardings + alightings

                                if node_id not in region_demand[region_name]:
                                    region_demand[region_name][node_id] = {'demand': demand, 'transfers': 0}
                                else:
                                    region_demand[region_name][node_id]['demand'] += demand
                            except (ValueError, TypeError):
                                continue
                except Exception:
                    pass

            # Area to region mapping (Hebrew area names to demand model regions)
            AREA_TO_REGION = {
                'חיפה': 'Haifa',
                'צפון': 'Haifa',
                'תל אביב': 'Tel Aviv',
                'תל-אביב': 'Tel Aviv',
                'מרכז': 'Tel Aviv',
                'באר שבע': 'Beer Sheva',
                'דרום': 'Beer Sheva',
                'ירושלים': 'Jerusalem',
                'אשדוד': 'Ashdod-Ashkelon',
                'אשקלון': 'Ashdod-Ashkelon',
                # English names
                'Haifa': 'Haifa',
                'North': 'Haifa',
                'Tel Aviv': 'Tel Aviv',
                'Center': 'Tel Aviv',
                'Beer Sheva': 'Beer Sheva',
                'South': 'Beer Sheva',
                'Jerusalem': 'Jerusalem',
            }

            # Match demand to grouped hubs
            hubs_with_demand = self.grouped_hubs.copy()

            # Initialize demand columns
            hubs_with_demand['TotalDemand'] = 0.0
            hubs_with_demand['TotalTransfers'] = 0.0

            # Check if 'area' column exists for area-based matching
            has_area_column = 'area' in hubs_with_demand.columns
            if has_area_column:
                logger.info("  Using area-based demand matching (area column found)")
                unique_areas = hubs_with_demand['area'].unique()
                logger.info(f"  Areas in data: {list(unique_areas)}")
            else:
                logger.info("  Using global demand matching (no area column)")

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

                # Get hub's area for area-based matching
                hub_area = row.get('area', None) if has_area_column else None
                hub_region = AREA_TO_REGION.get(hub_area) if hub_area else None

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

                    # Try area-based matching first
                    matched = False
                    if hub_region and hub_region in region_demand:
                        if node in region_demand[hub_region]:
                            total_demand += region_demand[hub_region][node]['demand']
                            total_transfers += region_demand[hub_region][node]['transfers']
                            nodes_matched += 1
                            total_nodes_matched += 1
                            matched = True

                    # Fall back to global matching if area-based didn't match
                    if not matched and node in node_demand:
                        total_demand += node_demand[node]['demand']
                        total_transfers += node_demand[node]['transfers']
                        nodes_matched += 1
                        total_nodes_matched += 1

                # Assign to hub
                hubs_with_demand.at[idx, 'TotalDemand'] = total_demand
                hubs_with_demand.at[idx, 'TotalTransfers'] = total_transfers

                if nodes_matched > 0:
                    matched_hubs += 1

            # Apply overlay models (Hadera, Haifa Metronit) - these ADD to existing demand
            overlay_regions = ['Hadera', 'Haifa Metronit']
            for overlay_region in overlay_regions:
                if overlay_region in region_demand:
                    overlay_matched = 0
                    for idx, row in hubs_with_demand.iterrows():
                        nodes_in_group = row.get('node', [])
                        if isinstance(nodes_in_group, str):
                            try:
                                nodes_in_group = ast.literal_eval(nodes_in_group)
                            except (ValueError, SyntaxError):
                                nodes_in_group = [nodes_in_group]
                        if not isinstance(nodes_in_group, list):
                            nodes_in_group = [nodes_in_group]

                        for node in nodes_in_group:
                            try:
                                node = int(node)
                            except (ValueError, TypeError):
                                continue
                            if node in region_demand[overlay_region]:
                                hubs_with_demand.at[idx, 'TotalDemand'] += region_demand[overlay_region][node]['demand']
                                hubs_with_demand.at[idx, 'TotalTransfers'] += region_demand[overlay_region][node]['transfers']
                                overlay_matched += 1
                    if overlay_matched > 0:
                        logger.info(f"  Applied {overlay_region} overlay: {overlay_matched} nodes updated")

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
                logger.warning("     4. Hub 'area' column doesn't map to any demand region")
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
        if self.districts is not None and not self.config.skip_spatial_layers:
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

        if self.config.skip_demographics or self.taz_zones is None:
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
        temp_csv = self.config.processed_dir / f"temp_hubs_{self.timestamp}.csv"
        export_df = self.hubs_with_demand.copy()
        export_df['geometry'] = export_df['geometry'].apply(lambda x: x.wkt if x else None)
        export_df.to_csv(temp_csv, index=False, encoding='utf-8-sig')

        # Process influence areas
        try:
            _terminals = self.config.bus_terminals
            result_gdf = processor.process_full_pipeline(
                hubs_csv=str(temp_csv),
                taz_shp=str(self.config.taz_zones),
                terminals_shp=str(_terminals) if _terminals and Path(_terminals).exists() else None,
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

        # Show non-rail filtering status
        if REQUIRE_NON_RAIL_MODE:
            logger.info(f"Non-rail mode filtering: ENABLED")
            logger.info(f"  Rail-only modes: {RAIL_ONLY_MODES}")
            logger.info(f"  Non-rail transit modes: {NON_RAIL_TRANSIT_MODES}")
            logger.info(f"  Hubs must have at least one non-rail transit mode (Metro/LRT/BRT)")
        else:
            logger.info(f"Non-rail mode filtering: DISABLED")
            logger.info(f"  All hubs with 2+ mass-transit modes are eligible")

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

        # Run scoring pipeline (includes Monte Carlo and optionally AHP)
        self.scored_hubs = monte_carlo.run_complete_scoring_pipeline(
            self.classified_hubs,
            tier_column='tier'
        )

        logger.info("✓ Step 10 complete")

    def step_11_run_mc_distribution(self):
        """Step 11: Run Monte Carlo distribution analysis (optional)."""
        logger.info("\n" + "="*80)
        logger.info("STEP 11: MONTE CARLO DISTRIBUTION ANALYSIS (OPTIONAL)")
        logger.info("="*80)

        # Check if user wants to run MC distribution (config flag or env var)
        run_mc_dist = self.config.run_mc_distribution or \
            os.environ.get('RUN_MC_DISTRIBUTION', 'false').lower() == 'true'

        if not run_mc_dist:
            logger.info("⊘ Skipping MC distribution analysis (not requested)")
            logger.info("  To enable: set run_mc_distribution=True in the RunConfig")
            logger.info("  or set environment variable RUN_MC_DISTRIBUTION=true")
            logger.info("✓ Step 11 complete (skipped)")
            return

        try:
            from src.scoring.mc_distribution import run_mc_distribution_analysis

            logger.info("Running Monte Carlo distribution analysis...")
            logger.info("This may take a few minutes...")

            # Extract score columns
            score_columns = [
                'activity_score',
                'service_score',
                'location_score',
                'pop_jobs_score',
                'terminal_score'
            ]

            # Check all columns exist
            missing_cols = [col for col in score_columns if col not in self.scored_hubs.columns]
            if missing_cols:
                logger.warning(f"Missing score columns: {missing_cols}")
                logger.warning("Skipping MC distribution analysis")
                logger.info("✓ Step 11 complete (missing data)")
                return

            # Extract score matrix
            score_matrix = self.scored_hubs[score_columns].copy()
            score_matrix.index = self.scored_hubs.index

            # Run distribution analysis
            mc_dist_dir = self.config.results_dir / f'mc_distribution_{self.timestamp}'
            mc_results = run_mc_distribution_analysis(
                score_matrix=score_matrix,
                output_dir=str(mc_dist_dir),
                n_iterations=MONTE_CARLO_ITERATIONS,
                random_seed=MONTE_CARLO_RANDOM_SEED,
                export_raw_scores=MC_DIST_EXPORT_RAW_SCORES,
                create_visualizations=True,
                top_n_for_plots=MC_DIST_TOP_N_HUBS,
            )

            logger.info(f"\n✓ MC Distribution Analysis complete!")
            logger.info(f"  Results saved to: {mc_dist_dir}")
            logger.info(f"  Files: mc_hub_stats.csv + visualizations (PNG)")

            # Store results
            self.mc_dist_results = mc_results

            logger.info("✓ Step 11 complete")

        except ImportError:
            logger.warning("mc_distribution module not found - skipping")
            logger.info("✓ Step 11 complete (module unavailable)")
        except Exception as e:
            logger.error(f"MC distribution analysis failed: {e}", exc_info=True)
            logger.warning("Continuing without MC distribution results")
            logger.info("✓ Step 11 complete (error - continued)")

    def step_12_export_results(self):
        """Step 12: Export final results."""
        logger.info("\n" + "="*80)
        logger.info("STEP 12: EXPORT RESULTS")
        logger.info("="*80)

        results_dir = self.config.results_dir

        # CSV
        csv_path = results_dir / f"hub_prioritization_results_{self.timestamp}.csv"
        export_df = self.scored_hubs.copy()
        export_df['geometry'] = export_df['geometry'].apply(lambda x: x.wkt if x else None)
        export_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        self.output_files.append(str(csv_path))
        logger.info(f"✓ CSV: {csv_path}")

        # GeoJSON
        geojson_path = results_dir / f"hub_results_{self.timestamp}.geojson"
        self.scored_hubs.to_file(geojson_path, driver='GeoJSON')
        self.output_files.append(str(geojson_path))
        logger.info(f"✓ GeoJSON: {geojson_path}")

        # Map
        try:
            map_path = results_dir / f"hub_map_{self.timestamp}.html"
            maps.create_hub_map(self.scored_hubs, color_by='final_score', output_file=str(map_path))
            self.output_files.append(str(map_path))
            logger.info(f"✓ Map: {map_path}")
        except Exception as e:
            logger.warning(f"Could not create map: {e}")

        logger.info("✓ Step 12 complete")

    # ------------------------------------------------------------------
    # Run logging / manifest
    # ------------------------------------------------------------------

    @staticmethod
    def _file_info(path) -> Dict:
        """Return name/size/mtime/sha256 metadata for an input file."""
        info = {'path': str(path), 'exists': False}
        try:
            p = Path(path)
            if p.exists():
                stat = p.stat()
                info.update({
                    'exists': True,
                    'name': p.name,
                    'size_bytes': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'),
                })
                # SHA-256 (skip very large files for speed)
                if stat.st_size <= 500 * 1024 * 1024:
                    h = hashlib.sha256()
                    with open(p, 'rb') as fh:
                        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
                            h.update(chunk)
                    info['sha256'] = h.hexdigest()
        except Exception as e:
            info['error'] = str(e)
        return info

    def write_run_manifest(self):
        """Write run_log.json + run_log.txt describing this run."""
        cfg = self.config
        finished_at = datetime.now()

        inputs = {}
        for key in ['transit_nodes', 'lines_modes', 'demand', 'metro_areas',
                    'districts', 'taz_zones', 'bus_terminals']:
            val = getattr(cfg, key)
            inputs[key] = self._file_info(val) if val else None

        summary = {}
        if self.scored_hubs is not None:
            summary['total_hubs'] = int(len(self.scored_hubs))
            if 'tier' in self.scored_hubs.columns:
                summary['hubs_by_tier'] = {
                    str(k): int(v)
                    for k, v in self.scored_hubs['tier'].value_counts().items()
                }

        manifest = {
            'run_id': cfg.run_id,
            'run_by': cfg.run_by or 'unknown',
            'remarks': cfg.remarks,
            'status': self.status,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat(timespec='seconds'),
            'finished_at': finished_at.isoformat(timespec='seconds'),
            'duration_seconds': round((finished_at - self.started_at).total_seconds(), 1),
            'output_dir': str(cfg.output_dir),
            'options': {
                'skip_demand_data': cfg.skip_demand_data,
                'skip_spatial_layers': cfg.skip_spatial_layers,
                'skip_demographics': cfg.skip_demographics,
                'run_mc_distribution': cfg.run_mc_distribution,
            },
            'inputs': inputs,
            'outputs': self.output_files,
            'log_file': str(self._run_log_path),
            'results_summary': summary,
        }

        # JSON manifest
        json_path = cfg.results_dir / "run_log.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        # Human-readable text log
        txt_path = cfg.results_dir / "run_log.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("HUB PRIORITIZATION - RUN LOG\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Run ID        : {manifest['run_id']}\n")
            f.write(f"Run by        : {manifest['run_by']}\n")
            f.write(f"Status        : {manifest['status']}\n")
            if self.error_message:
                f.write(f"Error         : {self.error_message}\n")
            f.write(f"Started       : {manifest['started_at']}\n")
            f.write(f"Finished      : {manifest['finished_at']}\n")
            f.write(f"Duration      : {manifest['duration_seconds']} s\n")
            f.write(f"Output dir    : {manifest['output_dir']}\n\n")
            f.write(f"Remarks:\n{cfg.remarks or '(none)'}\n\n")
            f.write("-" * 70 + "\n")
            f.write("INPUT FILES USED\n")
            f.write("-" * 70 + "\n")
            for key, info in inputs.items():
                if not info:
                    f.write(f"  {key:<16}: (not provided)\n")
                elif info.get('exists'):
                    f.write(f"  {key:<16}: {info['name']}  "
                            f"({info.get('size_bytes', '?')} bytes, "
                            f"modified {info.get('modified', '?')})\n")
                    f.write(f"  {'':<16}  path: {info['path']}\n")
                    if 'sha256' in info:
                        f.write(f"  {'':<16}  sha256: {info['sha256']}\n")
                else:
                    f.write(f"  {key:<16}: MISSING ({info['path']})\n")
            f.write("\n")
            f.write("-" * 70 + "\n")
            f.write("OPTIONS\n")
            f.write("-" * 70 + "\n")
            for k, v in manifest['options'].items():
                f.write(f"  {k:<22}: {v}\n")
            f.write("\n")
            f.write("-" * 70 + "\n")
            f.write("OUTPUT FILES PRODUCED\n")
            f.write("-" * 70 + "\n")
            for out in self.output_files:
                f.write(f"  {out}\n")
            f.write("\n")
            if summary:
                f.write("-" * 70 + "\n")
                f.write("RESULTS SUMMARY\n")
                f.write("-" * 70 + "\n")
                f.write(f"  Total hubs: {summary.get('total_hubs', '?')}\n")
                for tier, n in summary.get('hubs_by_tier', {}).items():
                    f.write(f"    {tier}: {n}\n")

        self.output_files.append(str(json_path))
        self.output_files.append(str(txt_path))
        logger.info(f"✓ Run log: {json_path}")
        logger.info(f"✓ Run log: {txt_path}")
        return manifest

    def _detach_log_handler(self):
        """Remove the per-run file handler from the shared logger."""
        try:
            logger.removeHandler(self._run_log_handler)
            self._run_log_handler.close()
        except Exception:
            pass

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
            self.step_11_run_mc_distribution()
            self.step_12_export_results()

            self.status = "success"

            logger.info("\n" + "="*80)
            logger.info("✅ PIPELINE COMPLETE!")
            logger.info("="*80)
            logger.info(f"\nFinal Results:")
            logger.info(f"  Total hubs: {len(self.scored_hubs)}")
            logger.info(f"  Results: {self.config.results_dir}")

            return self.scored_hubs

        except Exception as e:
            self.status = "error"
            self.error_message = str(e)
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
        finally:
            # Always write a manifest (even on failure) and detach the log file
            try:
                self.write_run_manifest()
            except Exception as e:
                logger.error(f"Could not write run manifest: {e}")
            self._detach_log_handler()


def run_pipeline(config: Optional[RunConfig] = None):
    """Run the full pipeline for a given configuration.

    This is the single entry point shared by the CLI and the GUI.

    Args:
        config: A RunConfig. If None, a default config is built from the
            RAW_DATA_DIR paths defined at the top of this module.

    Returns:
        The scored hubs GeoDataFrame.
    """
    cfg = config if config is not None else default_run_config()

    problems = cfg.validate()
    if problems:
        for p in problems:
            logger.error(f"❌ {p}")
        raise FileNotFoundError("; ".join(problems))

    pipeline = CompleteHubPipeline(cfg)
    return pipeline.run()


def main():
    """CLI entry point - runs with default RAW_DATA_DIR paths."""

    # Check required files
    if not INPUT_TRANSIT_NODES.exists():
        logger.error(f"❌ Transit nodes not found: {INPUT_TRANSIT_NODES}")
        logger.info("Please update INPUT_TRANSIT_NODES path in this script")
        sys.exit(1)

    if not INPUT_LINES_MODES.exists():
        logger.error(f"❌ Lines/modes not found: {INPUT_LINES_MODES}")
        logger.info("Please update INPUT_LINES_MODES path in this script")
        sys.exit(1)

    # Run pipeline with default configuration
    results = run_pipeline(default_run_config())

    logger.info("\n🎉 Done! Check results in data/results/")


if __name__ == "__main__":
    main()
