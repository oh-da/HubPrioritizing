"""
Spatial operations for Hub Prioritization Framework.

Demonstrates:
- Dependency Injection: Components receive dependencies via constructor
- Single Responsibility: Each class has one spatial concern
"""

from .h3_operations import H3Aggregator
from .geometry import SpatialAnalyzer, DistanceCalculator, BufferCreator

__all__ = [
    'H3Aggregator',
    'SpatialAnalyzer',
    'DistanceCalculator',
    'BufferCreator',
]
