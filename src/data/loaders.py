"""
Data loaders implementing IDataLoader interface.

Single Responsibility: Each loader handles one type of data source.
Open/Closed: Extend by adding new loader classes, not modifying existing ones.
"""

from abc import ABC
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging

from ..interfaces import IDataLoader, TransitMode

logger = logging.getLogger(__name__)


class BaseDataLoader(IDataLoader, ABC):
    """
    Base class for all data loaders.

    Provides common functionality while enforcing IDataLoader interface.
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def _check_file_exists(self) -> bool:
        """Verify file exists before loading"""
        if not self.file_path.exists():
            logger.error(f"File not found: {self.file_path}")
            return False
        return True


class CSVDataLoader(BaseDataLoader):
    """
    Loads data from CSV files.

    Single Responsibility: Only handles CSV file loading.
    """

    def load(self) -> Any:
        """Load data from CSV file"""
        if not self._check_file_exists():
            return None

        try:
            # Note: In production, use pandas or polars
            # This is a placeholder implementation
            logger.info(f"Loading CSV from {self.file_path}")

            # Mock implementation - replace with actual CSV loading
            return {"type": "csv", "path": str(self.file_path)}

        except Exception as e:
            logger.error(f"Error loading CSV {self.file_path}: {e}")
            raise

    def validate_schema(self, data: Any) -> bool:
        """Validate CSV data structure"""
        # Placeholder - implement actual schema validation
        return data is not None


class GeoJSONDataLoader(BaseDataLoader):
    """
    Loads spatial data from GeoJSON files.

    Single Responsibility: Only handles GeoJSON file loading.
    """

    def load(self) -> Any:
        """Load data from GeoJSON file"""
        if not self._check_file_exists():
            return None

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            logger.info(f"Loaded GeoJSON from {self.file_path}")
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {self.file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading GeoJSON {self.file_path}: {e}")
            raise

    def validate_schema(self, data: Any) -> bool:
        """Validate GeoJSON structure"""
        if not isinstance(data, dict):
            return False

        # Basic GeoJSON validation
        required_keys = ['type']
        if not all(key in data for key in required_keys):
            return False

        return data.get('type') in ['FeatureCollection', 'Feature', 'GeometryCollection']


class TransitLineLoader(BaseDataLoader):
    """
    Specialized loader for transit line data.

    Single Responsibility: Load and parse transit line information.
    """

    def load(self) -> List[Dict[str, Any]]:
        """Load transit line data"""
        if not self._check_file_exists():
            return []

        try:
            # Placeholder - implement actual loading logic
            logger.info(f"Loading transit lines from {self.file_path}")

            # Mock data structure
            return [
                {
                    "line_id": "rail_001",
                    "name": "Tel Aviv - Jerusalem",
                    "mode": TransitMode.RAIL,
                    "stations": [],
                    "frequency_2050": 15  # minutes
                }
            ]

        except Exception as e:
            logger.error(f"Error loading transit lines: {e}")
            raise

    def validate_schema(self, data: Any) -> bool:
        """Validate transit line data structure"""
        if not isinstance(data, list):
            return False

        required_fields = ['line_id', 'name', 'mode', 'stations']
        for line in data:
            if not all(field in line for field in required_fields):
                return False

        return True


class StationDataLoader(BaseDataLoader):
    """
    Specialized loader for station/stop data.

    Single Responsibility: Load station locations and forecasts.
    """

    def load(self) -> List[Dict[str, Any]]:
        """Load station data"""
        if not self._check_file_exists():
            return []

        try:
            logger.info(f"Loading stations from {self.file_path}")

            # Mock data structure
            return [
                {
                    "station_id": "sta_001",
                    "name": "Tel Aviv Savidor",
                    "lat": 32.0853,
                    "lon": 34.7818,
                    "passengers_2050": 120000,
                    "modes": [TransitMode.RAIL, TransitMode.BUS]
                }
            ]

        except Exception as e:
            logger.error(f"Error loading stations: {e}")
            raise

    def validate_schema(self, data: Any) -> bool:
        """Validate station data structure"""
        if not isinstance(data, list):
            return False

        required_fields = ['station_id', 'name', 'lat', 'lon', 'passengers_2050']
        for station in data:
            if not all(field in station for field in required_fields):
                return False

        return True


class DemographicDataLoader(BaseDataLoader):
    """
    Specialized loader for demographic and land use data.

    Single Responsibility: Load population and employment forecasts.
    """

    def load(self) -> Dict[str, Any]:
        """Load demographic data"""
        if not self._check_file_exists():
            return {}

        try:
            logger.info(f"Loading demographic data from {self.file_path}")

            # Mock data structure
            return {
                "population_2050": {},
                "jobs_2050": {},
                "metadata": {
                    "source": "National Planning Authority",
                    "year": 2050
                }
            }

        except Exception as e:
            logger.error(f"Error loading demographic data: {e}")
            raise

    def validate_schema(self, data: Any) -> bool:
        """Validate demographic data structure"""
        if not isinstance(data, dict):
            return False

        required_keys = ['population_2050', 'jobs_2050']
        return all(key in data for key in required_keys)


class DataLoaderFactory:
    """
    Factory for creating appropriate data loaders.

    Single Responsibility: Create loader instances.
    Open/Closed: Register new loader types without modifying factory core.
    """

    _loaders: Dict[str, type] = {
        '.csv': CSVDataLoader,
        '.geojson': GeoJSONDataLoader,
        '.json': GeoJSONDataLoader,
    }

    @classmethod
    def register_loader(cls, extension: str, loader_class: type) -> None:
        """Register a new loader type"""
        cls._loaders[extension] = loader_class

    @classmethod
    def create_loader(cls, file_path: Path) -> Optional[IDataLoader]:
        """Create appropriate loader for file type"""
        extension = file_path.suffix.lower()

        loader_class = cls._loaders.get(extension)
        if loader_class is None:
            logger.warning(f"No loader registered for {extension}")
            return None

        return loader_class(file_path)
