"""
Scoring system for Hub Prioritization Framework.

Demonstrates SOLID principles:
- Single Responsibility: Each scorer handles one criterion
- Open/Closed: Add new scorers without modifying framework
- Liskov Substitution: All scorers interchangeable
- Interface Segregation: Focused IScorer interface
- Dependency Inversion: Framework depends on IScorer abstraction
"""

from .base import BaseScorer
from .activity import ActivityScorer
from .service import ServiceModeScorer
from .location import LocationScorer
from .demographics import DemographicsScorer
from .terminals import BusTerminalScorer
from .normalization import MinMaxNormalizer, LogNormalizer
from .aggregation import WeightedAggregator, MonteCarloAggregator

__all__ = [
    'BaseScorer',
    'ActivityScorer',
    'ServiceModeScorer',
    'LocationScorer',
    'DemographicsScorer',
    'BusTerminalScorer',
    'MinMaxNormalizer',
    'LogNormalizer',
    'WeightedAggregator',
    'MonteCarloAggregator',
]
