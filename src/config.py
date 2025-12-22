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
# OPTIONAL: RAIL-ONLY HUB FILTERING
# ============================================================================
# When enabled, a hub is only eligible if it has at least one non-rail
# mass-transit mode (Metro, LRT, BRT). Hubs with only rail modes
# (Suburban Rail, Interurban Rail, HighSpeed Rail, Rail) are excluded.

# Set to True to require at least one non-rail transit mode
REQUIRE_NON_RAIL_MODE = True

# Rail-only modes (rail infrastructure without urban transit integration)
# 22/12/2025 - Updated to exclude HighSpeed Rail.
RAIL_ONLY_MODES = {
    'Rail',              # רכבת - Generic rail
    'Suburban Rail',     # רכבת פרברית
    'Interurban Rail'   # רכבת בין-עירונית
}

# Non-rail mass-transit modes (urban transit modes that qualify hubs)
NON_RAIL_TRANSIT_MODES = {
    'Metro',  # מטרו
    'LRT',    # רק"ל (Light Rail Transit)
    'BRT',    # מטרונית (Bus Rapid Transit)
    'HighSpeed Rail'    #  רכבת מהירה
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

# Monte Carlo Distribution Reporting parameters
MC_DIST_TOP_N_HUBS = 30  # Number of hubs for portfolio-level plots
MC_DIST_HISTOGRAM_BINS = 50  # Number of bins for per-hub histograms
MC_DIST_EXPORT_RAW_SCORES = True  # Whether to export raw scores in long format
MC_DIST_PRECISION = 6  # Decimal precision for exported statistics
MC_DIST_MAX_HUB_HISTOGRAMS = None  # None = all hubs, or set a number to limit

# AHP (Analytic Hierarchy Process) parameters
AHP_ENABLED = False  # Set to True to enable AHP scoring alongside Monte Carlo
AHP_CONSISTENCY_RATIO_THRESHOLD = 0.10  # Maximum acceptable CR (Saaty recommends 0.10)
AHP_AGGREGATION_METHOD = 'geometric_mean'  # How to combine expert weights: 'geometric_mean', 'arithmetic_mean', 'median'
AHP_EXPERT_CSV_PATH = DATA_DIR / "ahp_expert_comparisons.csv"  # Path to expert pairwise comparisons

# Saaty Scale for AHP pairwise comparisons
AHP_SAATY_SCALE = {
    1: 'Equal importance',
    2: 'Weak or slight',
    3: 'Moderate importance',
    4: 'Moderate plus',
    5: 'Strong importance',
    6: 'Strong plus',
    7: 'Very strong importance',
    8: 'Very, very strong',
    9: 'Extreme importance',
}

# ============================================================================
# SCORING CRITERIA CONFIGURATION
# ============================================================================

# 1. PASSENGER ACTIVITY SCORE
# Uses log10 transformation to avoid extreme skew
ACTIVITY_SCORE_USE_LOG = True  # Apply log10 transformation
ACTIVITY_SCORE_LOG_BASE = 10

# 2. SERVICE & HIERARCHY OF MODES SCORE
# Modal weights (based on notebook implementation)
# 22/12/2025 Updated in a new order - Metro and Suburban leveled to 6.0, all mode under were upped by 1.0
MODE_WEIGHTS = {
    'Funicular': 2.0,
    'Cable Line': 3.0,
    'BRT': 4.0,
    'LRT': 5.0,
    'Metro': 6.0,
    'Suburban Rail': 6.0,
    'Interurban Rail': 7.0,
    'HighSpeed Rail': 8.0,
    'Rail': 7.0,  # Generic rail (treat as Interurban)
    'Express Bus': 3.0,
    'Bus': 1.0,  # Regular bus (lowest weight)
}

# Diminishing returns for multiple lines of same mode
# Returns factor = 1 / sqrt(line_count)
MODE_LINE_DIMINISHING_RETURNS = True

# Diversity bonus for multiple modes
# Bonus = (num_modes - 1) * 0.1 (i.e., 10% per additional mode)
MODE_DIVERSITY_BONUS_PCT = 0.10  # 10% bonus per additional mode

# 3. LOCATION SCORE (GEOGRAPHIC & METROPOLITAN)
# Regional weights (for national equity) - based on notebook 'area' field
# Tel Aviv = 0 (lower priority), Others = 1 (higher priority for periphery)
REGION_WEIGHTS = {
    'תל אביב': 0,  # Tel Aviv
    'Tel Aviv': 0,
    'Center': 0,
    'צפון': 1,  # North
    'North': 1,
    'חיפה': 1,  # Haifa
    'Haifa': 1,
    'דרום': 1,  # South
    'South': 1,
    'באר שבע': 1,  # Beer Sheva
    'Jerusalem': 1,
    'ירושלים': 1,
}

# Metropolitan position weights - based on notebook 'location' field
# גלעין (Core) = 3, טבעת (Ring) = 2, Periphery = 1
METRO_POSITION_WEIGHTS = {
    'גלעין': 3,  # Core
    'Core': 3,
    'טבעת': 2,  # Ring (First Ring)
    'טבעת פנימית': 2,  # Inner Ring
    'טבעת חיצונית': 2,  # Outer Ring
    'טבעת תיכונה': 2,  # Middle Ring
    'First Ring': 2,
    'Inner Ring': 2,
    'Outer Ring': 2,
    'Middle Ring': 2,
    'צפון': 1,  # North (periphery)
    'חיפה': 1,  # Haifa (periphery)
    'דרום': 1,  # South (periphery)
    'Outer': 1,
}

# 4. POPULATION & JOBS SCORE
# Catchment area rings (in meters) - based on notebook columns
# pop_0_500, emp_0_500, pop_500_1000, emp_500_1000, pop_1000_1500, emp_1000_1500
CATCHMENT_RINGS = [
    (0, 500),  # Ring 1: 0-500m
    (500, 1000),  # Ring 2: 500-1000m
    (1000, 1500),  # Ring 3: 1000-1500m
]

# Distance decay beta parameter (used in notebook scoring function)
# Formula: decay = midpoint^beta
DISTANCE_DECAY_BETA = 1.5

# Ring midpoints (meters) - calculated from rings
RING_MIDPOINTS = [250, 750, 1250]  # Midpoint of each ring

# Ring weights for distance decay (inverse decay: closer rings weighted higher)
# Calculated as: weight_i = (1 / midpoint_i^beta) normalized to sum to 1
# With beta=1.5, midpoints=[250, 750, 1250]:
#   Ring 0 (0-500m):    1/250^1.5  = 0.000253 → normalized: 0.78
#   Ring 1 (500-1000m): 1/750^1.5  = 0.000049 → normalized: 0.15
#   Ring 2 (1000-1500m):1/1250^1.5 = 0.000023 → normalized: 0.07
_raw_weights = [1.0 / (mid ** DISTANCE_DECAY_BETA) for mid in RING_MIDPOINTS]
_weight_sum = sum(_raw_weights)
_normalized_weights = [w / _weight_sum for w in _raw_weights]
RING_WEIGHTS = {i: weight for i, weight in enumerate(_normalized_weights)}

# Population vs Employment mix by tier
POP_JOB_MIX = {
    TIER_NATIONAL: {'jobs': 0.8, 'population': 0.2},  # National hubs serve employment
    TIER_METRO: {'jobs': 0.8, 'population': 0.2},  # Metro hubs serve employment
    TIER_LOCAL: {'jobs': 0.2, 'population': 0.8},  # Local hubs serve residential
}

# 5. BUS TERMINAL PROXIMITY SCORE
TERMINAL_PROXIMITY_DISTANCE_M = 200  # Maximum distance to terminal

# Terminal classification weights - based on notebook 'term_type' field
TERMINAL_WEIGHTS = {
    'חניון לילה': 1.0,  # Night parking
    'מסוף קטן': 2.0,  # Small terminal
    'מסוף בינוני': 2.0,  # Medium terminal
    'מסוף גדול': 3.0,  # Large terminal
    'מתקן משולב': 3.0,  # Integrated facility
    # English equivalents
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
