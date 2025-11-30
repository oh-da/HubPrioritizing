"""
Constants and Enumerations for Hub Prioritization Framework
============================================================
"""

from enum import Enum


class HubTier(Enum):
    """Hub hierarchy tiers."""
    NATIONAL = "ארצי"  # National
    METROPOLITAN = "מטרופוליני"  # Metropolitan
    LOCAL = "עירוני"  # Local/Urban


class TransportMode(Enum):
    """Transport modes."""
    RAIL = "Rail"
    HIGH_SPEED_RAIL = "HighSpeed Rail"
    METRO = "Metro"
    LRT = "LRT"  # Light Rail Transit
    BRT = "BRT"  # Bus Rapid Transit
    EXPRESS_BUS = "Express Bus"
    BUS = "Bus"


class Region(Enum):
    """Israeli regions for scoring."""
    CENTER = "Center"
    TEL_AVIV = "Tel Aviv"
    HAIFA = "Haifa"
    NORTH = "North"
    SOUTH = "South"
    JERUSALEM = "Jerusalem"


class MetroPosition(Enum):
    """Metropolitan position for scoring."""
    CORE = "Core"
    FIRST_RING = "First Ring"
    OUTER = "Outer"


class TerminalType(Enum):
    """Bus terminal types."""
    NATIONAL = "National"
    REGIONAL = "Regional"
    METROPOLITAN = "Metropolitan"
    LOCAL = "Local"
    NEIGHBORHOOD = "Neighborhood"
