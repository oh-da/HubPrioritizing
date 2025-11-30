"""
Data layer for Hub Prioritization Framework.

Following Single Responsibility Principle:
- Each class has one clear responsibility
- Separation of concerns: loading, validation, transformation, storage
"""

from .loaders import (
    CSVDataLoader,
    GeoJSONDataLoader,
    TransitLineLoader,
    StationDataLoader,
    DemographicDataLoader
)

from .validators import (
    SchemaValidator,
    DataQualityValidator,
    GeometryValidator
)

from .repository import HubDataRepository

__all__ = [
    'CSVDataLoader',
    'GeoJSONDataLoader',
    'TransitLineLoader',
    'StationDataLoader',
    'DemographicDataLoader',
    'SchemaValidator',
    'DataQualityValidator',
    'GeometryValidator',
    'HubDataRepository',
]
