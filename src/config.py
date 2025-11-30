"""
Configuration and Constants for Hub Prioritization Framework
==============================================================
Centralized configuration for all parameters, thresholds, file paths,
and constants used throughout the hub prioritization system.

All values are based on CLAUDE.md specifications.
"""

from pathlib import Path
from typing import Dict, Tuple

# ============================================================================
# PROJECT PATHS
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
RESULTS_DIR = DATA_DIR / "results"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
for directory in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, RESULTS_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# COORDINATE REFERENCE SYSTEMS
# ============================================================================

CRS_WGS84 = "EPSG:4326"  # WGS84 for H3 and general geographic operations
CRS_ISRAEL_TM = "EPSG:2039"  # Israel TM Grid for meter-based operations

# ============================================================================
# H3 SPATIAL PARAMETERS
# ============================================================================

H3_RESOLUTION = 10  # Resolution 10 = ~15m hexagons (actual: ~15.047m edge length)
HUB_MERGE_THRESHOLD_M = 120  # Maximum edge-to-edge distance for grouping hexagons
HUB_MERGE_TOLERANCE_M = 0.1  # 10cm tolerance for touching hexagons

# ============================================================================
# HUB ELIGIBILITY THRESHOLDS
# ============================================================================

# Minimum daily passengers for hub eligibility
ELIGIBILITY_MIN_PASSENGERS = 1000

# Minimum number of mass-transit modes required
ELIGIBILITY_MIN_MODES = 2  # Must have at least 2 mass-transit modes

# Mass-transit modes (modes that count towards eligibility)
MASS_TRANSIT_MODES = {
    'Rail',  # רכבת (Israeli Railways)
    'HighSpeed Rail',  # רכבת מהירה
    'Metro',  # מטרו
    'LRT',  # רק"ל (Light Rail Transit)
    'BRT',  # מטרונית (Bus Rapid Transit)
}

# Non-mass-transit modes (don't count for hub eligibility)
NON_MASS_TRANSIT_MODES = {
    'Bus',  # Regular bus service
    'Express Bus',  # קו אקספרס
    'Regional Bus',  # אוטובוס בין-עירוני
}

# ============================================================================
# HUB HIERARCHY THRESHOLDS
# ============================================================================

# National tier (ארצי)
NATIONAL_HUB_MIN_PASSENGERS = 50000  # Typically >100,000 in practice

# Metropolitan tier (מטרופוליני)
METRO_HUB_MIN_PASSENGERS = 5000
METRO_HUB_MAX_PASSENGERS = 50000

# Local tier (עירוני)
LOCAL_HUB_MAX_PASSENGERS = 5000

# Tier names (Hebrew and English)
TIER_NATIONAL = "ארצי"  # National
TIER_METRO = "מטרופוליני"  # Metropolitan
TIER_LOCAL = "עירוני"  # Local

# ============================================================================
# SCORING PARAMETERS
# ============================================================================

# Score range (all scores normalized to this range)
SCORE_MIN = 1
SCORE_MAX = 10
SCORE_RANGE = (SCORE_MIN, SCORE_MAX)

# Monte Carlo simulation parameters
MONTE_CARLO_ITERATIONS = 10000  # Number of simulation runs
MONTE_CARLO_RANDOM_SEED = 42  # For reproducibility
MAX_CRITERION_WEIGHT = 0.5  # Maximum weight for any single criterion (50%)
MIN_CRITERION_WEIGHT = 0.0  # Minimum weight

# ============================================================================
# SCORING CRITERIA CONFIGURATION
# ============================================================================

# 1. PASSENGER ACTIVITY SCORE
# Uses log10 transformation to avoid extreme skew
ACTIVITY_SCORE_USE_LOG = True  # Apply log10 transformation
ACTIVITY_SCORE_LOG_BASE = 10

# 2. SERVICE & HIERARCHY OF MODES SCORE
# Modal weights (higher capacity = higher weight)
MODE_WEIGHTS = {
    'Rail': 10.0,  # Highest capacity
    'HighSpeed Rail': 10.0,
    'Metro': 9.0,
    'LRT': 7.0,  # Light Rail
    'BRT': 5.0,  # Bus Rapid Transit
    'Express Bus': 3.0,
    'Bus': 2.0,  # Regular bus (lowest weight)
}

# Diminishing returns for multiple lines of same mode
# Returns factor = 1 / sqrt(line_count)
MODE_LINE_DIMINISHING_RETURNS = True

# Diversity bonus for multiple modes
# Bonus = (num_modes - 1) * 0.1 (i.e., 10% per additional mode)
MODE_DIVERSITY_BONUS_PCT = 0.10  # 10% bonus per additional mode

# 3. LOCATION SCORE (GEOGRAPHIC & METROPOLITAN)
# Regional weights (for national equity)
REGION_WEIGHTS = {
    'Center': 0,  # Tel Aviv region (inverted: 0 = prioritize less)
    'Tel Aviv': 0,
    'Haifa': 1,  # Periphery (inverted: 1 = prioritize more)
    'North': 1,
    'South': 1,
    'Jerusalem': 1,
}

# Metropolitan position weights
METRO_POSITION_WEIGHTS = {
    'Core': 3,  # City center
    'First Ring': 2,  # Inner suburbs
    'Outer': 1,  # Outer suburbs/periphery
}

# 4. POPULATION & JOBS SCORE
# Catchment area rings (in meters)
CATCHMENT_RINGS = [
    (0, 400),  # Ring 1: 0-400m
    (400, 800),  # Ring 2: 400-800m
    (800, 1500),  # Ring 3: 800-1500m
]

# Distance decay weights for rings
RING_WEIGHTS = {
    0: 1.0,  # 0-400m: full weight
    1: 0.7,  # 400-800m: 70% weight
    2: 0.4,  # 800-1500m: 40% weight
}

# Population vs Employment mix by tier
POP_JOB_MIX = {
    TIER_NATIONAL: {'jobs': 0.8, 'population': 0.2},  # National hubs serve employment
    TIER_METRO: {'jobs': 0.8, 'population': 0.2},  # Metro hubs serve employment
    TIER_LOCAL: {'jobs': 0.2, 'population': 0.8},  # Local hubs serve residential
}

# 5. BUS TERMINAL PROXIMITY SCORE
TERMINAL_PROXIMITY_DISTANCE_M = 200  # Maximum distance to terminal

# Terminal classification weights
TERMINAL_WEIGHTS = {
    'National': 3.0,
    'Regional': 2.5,
    'Metropolitan': 2.0,
    'Local': 1.5,
    'Neighborhood': 1.0,
}

# ============================================================================
# DATA FILE ENCODING
# ============================================================================

DEFAULT_ENCODING = 'windows-1255'  # For Hebrew text in CSV files
UTF8_ENCODING = 'utf-8-sig'  # For output files

# ============================================================================
# VISUALIZATION PARAMETERS
# ============================================================================

# Map tile provider
MAP_TILES = 'OpenStreetMap'
MAP_CENTER_ISRAEL = [31.5, 34.9]  # Lat, Lon for Israel center
MAP_ZOOM_DEFAULT = 8

# Color schemes by tier
TIER_COLORS = {
    TIER_NATIONAL: '#d62728',  # Red
    TIER_METRO: '#ff7f0e',  # Orange
    TIER_LOCAL: '#2ca02c',  # Green
}

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_TO_FILE = True
LOG_TO_CONSOLE = True

# ============================================================================
# EXPORT FORMATS
# ============================================================================

EXPORT_CSV = True
EXPORT_GEOJSON = True
EXPORT_EXCEL = True
EXPORT_SHAPEFILE = False  # Shapefile has field name length limitations

# ============================================================================
# VALIDATION THRESHOLDS
# ============================================================================

# Data quality checks
MIN_EXPECTED_HUBS = 50  # Expect at least this many hubs
MAX_EXPECTED_HUBS = 500  # Sanity check upper limit

# Score validation
SCORE_VALIDATION_STRICT = True  # Raise error if scores outside range
SCORE_VALIDATION_TOLERANCE = 0.01  # Allow 1% tolerance for floating point

# ============================================================================
# PERFORMANCE PARAMETERS
# ============================================================================

# Spatial index parameters
SPATIAL_INDEX_METHOD = 'rtree'  # Use R-tree spatial index

# Batch processing
BATCH_SIZE_SPATIAL_OPS = 100  # Process geometries in batches

# Progress reporting
PROGRESS_REPORT_INTERVAL = 100  # Report every N items

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_tier_from_ridership(ridership: float) -> str:
    """
    Classify hub tier based on daily ridership.

    Args:
        ridership: Daily passenger count

    Returns:
        Tier name (ארצי, מטרופוליני, or עירוני)
    """
    if ridership >= NATIONAL_HUB_MIN_PASSENGERS:
        return TIER_NATIONAL
    elif ridership >= METRO_HUB_MIN_PASSENGERS:
        return TIER_METRO
    else:
        return TIER_LOCAL


def is_mass_transit_mode(mode: str) -> bool:
    """
    Check if a mode qualifies as mass transit.

    Args:
        mode: Mode name

    Returns:
        True if mode is mass transit
    """
    return mode in MASS_TRANSIT_MODES


def get_mode_weight(mode: str) -> float:
    """
    Get weight for a transport mode.

    Args:
        mode: Mode name

    Returns:
        Mode weight (default 1.0 if not found)
    """
    return MODE_WEIGHTS.get(mode, 1.0)


# ============================================================================
# CONFIGURATION SUMMARY
# ============================================================================

def print_config_summary():
    """Print configuration summary for debugging."""
    print("=" * 80)
    print("HUB PRIORITIZATION FRAMEWORK - CONFIGURATION")
    print("=" * 80)
    print(f"\nProject Root: {PROJECT_ROOT}")
    print(f"Data Directory: {DATA_DIR}")
    print(f"\nH3 Resolution: {H3_RESOLUTION} (~15m hexagons)")
    print(f"Merge Threshold: {HUB_MERGE_THRESHOLD_M}m")
    print(f"\nEligibility:")
    print(f"  Min Passengers: {ELIGIBILITY_MIN_PASSENGERS}/day")
    print(f"  Min Modes: {ELIGIBILITY_MIN_MODES} mass-transit modes")
    print(f"\nHierarchy Thresholds:")
    print(f"  National (ארצי): ≥{NATIONAL_HUB_MIN_PASSENGERS:,}/day")
    print(f"  Metropolitan (מטרופוליני): {METRO_HUB_MIN_PASSENGERS:,}-{METRO_HUB_MAX_PASSENGERS:,}/day")
    print(f"  Local (עירוני): <{LOCAL_HUB_MAX_PASSENGERS:,}/day")
    print(f"\nScoring:")
    print(f"  Monte Carlo Iterations: {MONTE_CARLO_ITERATIONS:,}")
    print(f"  Max Criterion Weight: {MAX_CRITERION_WEIGHT * 100}%")
    print(f"  Score Range: {SCORE_MIN}-{SCORE_MAX}")
    print("=" * 80)


if __name__ == "__main__":
    print_config_summary()
