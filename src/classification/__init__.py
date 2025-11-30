"""
Hub classification system.

Demonstrates:
- Single Responsibility: Each classifier has one concern
- Open/Closed: Extend with new classification rules
- Strategy Pattern: Different classification strategies
"""

from .eligibility import PassengerEligibilityFilter, ModeEligibilityFilter, CompositeEligibilityFilter
from .hierarchy import PassengerBasedClassifier, RuleBasedClassifier

__all__ = [
    'PassengerEligibilityFilter',
    'ModeEligibilityFilter',
    'CompositeEligibilityFilter',
    'PassengerBasedClassifier',
    'RuleBasedClassifier',
]
