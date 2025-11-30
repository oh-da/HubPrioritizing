"""
Geometric operations and spatial analysis.

Demonstrates:
- Single Responsibility: Each class handles one geometric concern
- Composition: SpatialAnalyzer composes smaller components
"""

import math
import logging
from typing import List, Dict, Any, Tuple

from ..interfaces import ISpatialAnalyzer

logger = logging.getLogger(__name__)


class DistanceCalculator:
    """
    Calculates distances between geographic points.

    Single Responsibility: Only computes distances.
    """

    @staticmethod
    def haversine_distance(point1: Tuple[float, float],
                          point2: Tuple[float, float]) -> float:
        """
        Calculate great-circle distance between two points using Haversine formula.

        Args:
            point1: (lat, lon) tuple
            point2: (lat, lon) tuple

        Returns:
            Distance in meters
        """
        lat1, lon1 = point1
        lat2, lon2 = point2

        # Earth radius in meters
        R = 6371000

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        # Haversine formula
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c
        return distance

    @staticmethod
    def euclidean_distance_approximate(point1: Tuple[float, float],
                                       point2: Tuple[float, float]) -> float:
        """
        Approximate distance using Euclidean formula (faster, less accurate).

        Only suitable for short distances in Israel (< 100km).

        Returns:
            Distance in meters (approximate)
        """
        lat1, lon1 = point1
        lat2, lon2 = point2

        # Approximate conversion factors for Israel (latitude ~32°)
        meters_per_degree_lat = 111000  # ~111 km
        meters_per_degree_lon = 93000   # ~93 km at lat 32°

        dlat = (lat2 - lat1) * meters_per_degree_lat
        dlon = (lon2 - lon1) * meters_per_degree_lon

        return math.sqrt(dlat ** 2 + dlon ** 2)


class BufferCreator:
    """
    Creates buffer zones around points.

    Single Responsibility: Only handles buffer creation.
    """

    @staticmethod
    def create_circle_buffer(center: Tuple[float, float],
                            radius_m: float,
                            num_points: int = 32) -> List[Tuple[float, float]]:
        """
        Create circular buffer around a point.

        Args:
            center: (lat, lon) center point
            radius_m: Buffer radius in meters
            num_points: Number of points in circle approximation

        Returns:
            List of (lat, lon) points forming the buffer polygon

        Note: This is a simplified planar approximation.
        For production, use PostGIS or shapely with proper projections.
        """
        lat, lon = center

        # Approximate meters to degrees (for Israel)
        meters_per_degree_lat = 111000
        meters_per_degree_lon = 93000  # at lat ~32°

        radius_lat = radius_m / meters_per_degree_lat
        radius_lon = radius_m / meters_per_degree_lon

        # Create circle points
        points = []
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            point_lat = lat + radius_lat * math.sin(angle)
            point_lon = lon + radius_lon * math.cos(angle)
            points.append((point_lat, point_lon))

        return points


class SpatialAnalyzer(ISpatialAnalyzer):
    """
    Main spatial analysis component.

    Demonstrates:
    - Composition: Uses DistanceCalculator and BufferCreator
    - Dependency Injection: Components provided via constructor
    - Single Responsibility: Coordinates spatial operations
    """

    def __init__(self,
                 distance_calculator: DistanceCalculator | None = None,
                 buffer_creator: BufferCreator | None = None):
        """
        Initialize with component dependencies.

        Dependency Injection: Components can be swapped for testing or alternatives.
        """
        self.distance_calc = distance_calculator or DistanceCalculator()
        self.buffer_creator = buffer_creator or BufferCreator()

    def calculate_distance(self,
                          point1: Tuple[float, float],
                          point2: Tuple[float, float]) -> float:
        """Calculate distance between two points in meters"""
        return self.distance_calc.haversine_distance(point1, point2)

    def create_buffer(self,
                     point: Tuple[float, float],
                     radius_m: float) -> Any:
        """Create a buffer polygon around a point"""
        return self.buffer_creator.create_circle_buffer(point, radius_m)

    def count_within_rings(self,
                          center: Tuple[float, float],
                          rings: List[float],
                          features: List[Any]) -> Dict[float, int]:
        """
        Count features within concentric rings.

        Args:
            center: (lat, lon) center point
            rings: List of ring radii in meters (e.g., [400, 800, 1500])
            features: List of features with 'lat' and 'lon' attributes

        Returns:
            Dict mapping ring radius to count of features within that ring
        """
        counts = {radius: 0 for radius in rings}

        for feature in features:
            # Extract feature location
            if isinstance(feature, dict):
                feature_point = (feature.get('lat'), feature.get('lon'))
            else:
                feature_point = (getattr(feature, 'lat'), getattr(feature, 'lon'))

            # Calculate distance to center
            distance = self.calculate_distance(center, feature_point)

            # Assign to appropriate ring(s)
            for radius in rings:
                if distance <= radius:
                    counts[radius] += 1

        return counts

    def points_within_distance(self,
                               center: Tuple[float, float],
                               points: List[Tuple[float, float]],
                               max_distance_m: float) -> List[Tuple[Tuple[float, float], float]]:
        """
        Find all points within specified distance of center.

        Args:
            center: (lat, lon) center point
            points: List of (lat, lon) points to check
            max_distance_m: Maximum distance in meters

        Returns:
            List of (point, distance) tuples for points within distance
        """
        within_distance = []

        for point in points:
            distance = self.calculate_distance(center, point)
            if distance <= max_distance_m:
                within_distance.append((point, distance))

        return within_distance
