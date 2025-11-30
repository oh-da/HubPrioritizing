"""
Constants for Hub Prioritization Framework.

Single Responsibility: Define project-wide constants.
"""

from enum import Enum


class Region(Enum):
    """Israeli regions for geographic classification"""
    CENTER = "center"
    TEL_AVIV = "tel_aviv"
    HAIFA = "haifa"
    NORTH = "north"
    SOUTH = "south"
    JERUSALEM = "jerusalem"


class MetropolitanRing(Enum):
    """Metropolitan rings for spatial classification"""
    CORE = "core"
    FIRST_RING = "first_ring"
    OUTER = "outer"


# Coordinate reference systems
CRS_WGS84 = "EPSG:4326"  # Geographic coordinates
CRS_ITM = "EPSG:2039"    # Israel Transverse Mercator (for distances)

# Thresholds
DEFAULT_MIN_PASSENGERS = 1000
DEFAULT_MIN_MODES = 2
DEFAULT_NATIONAL_THRESHOLD = 50000
DEFAULT_METRO_THRESHOLD = 5000

# Spatial parameters
DEFAULT_H3_RESOLUTION = 9  # ~150m hexes
DEFAULT_HUB_MERGE_THRESHOLD_M = 300.0
DEFAULT_TERMINAL_PROXIMITY_M = 200.0

# Scoring parameters
DEFAULT_MONTE_CARLO_ITERATIONS = 10000
DEFAULT_MAX_CRITERION_WEIGHT = 0.5
DEFAULT_SCORE_MIN = 1.0
DEFAULT_SCORE_MAX = 10.0

# Catchment rings (meters)
DEFAULT_CATCHMENT_RINGS = [0, 400, 800, 1500]
