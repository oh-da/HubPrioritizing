"""
Data validators implementing IValidator interface.

Single Responsibility: Each validator has one validation concern.
Interface Segregation: Focused validator interfaces.
"""

from typing import Any, List, Tuple
import logging

from ..interfaces import IValidator, HubData

logger = logging.getLogger(__name__)


class SchemaValidator(IValidator):
    """
    Validates data against expected schema.

    Single Responsibility: Only validates data structure/schema.
    """

    def __init__(self, required_fields: List[str]):
        self.required_fields = required_fields

    def validate(self, data: Any) -> Tuple[bool, List[str]]:
        """Validate that data contains all required fields"""
        errors = []

        if not isinstance(data, dict):
            errors.append("Data must be a dictionary")
            return False, errors

        missing_fields = [
            field for field in self.required_fields
            if field not in data
        ]

        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
            return False, errors

        return True, []


class DataQualityValidator(IValidator):
    """
    Validates data quality (ranges, nulls, consistency).

    Single Responsibility: Only validates data quality.
    """

    def validate(self, data: Any) -> Tuple[bool, List[str]]:
        """Validate data quality"""
        errors = []

        if not isinstance(data, dict):
            errors.append("Data must be a dictionary")
            return False, errors

        # Validate passenger counts
        if 'passengers_2050' in data:
            passengers = data['passengers_2050']
            if not isinstance(passengers, (int, float)) or passengers < 0:
                errors.append(f"Invalid passenger count: {passengers}")

        # Validate coordinates
        if 'lat' in data and 'lon' in data:
            lat, lon = data['lat'], data['lon']
            if not (-90 <= lat <= 90):
                errors.append(f"Invalid latitude: {lat}")
            if not (-180 <= lon <= 180):
                errors.append(f"Invalid longitude: {lon}")

        # Check for null critical fields
        critical_fields = ['hub_id', 'name']
        for field in critical_fields:
            if field in data and (data[field] is None or data[field] == ''):
                errors.append(f"Critical field '{field}' is null or empty")

        is_valid = len(errors) == 0
        return is_valid, errors


class GeometryValidator(IValidator):
    """
    Validates geometric data.

    Single Responsibility: Only validates spatial/geometric data.
    """

    def validate(self, data: Any) -> Tuple[bool, List[str]]:
        """Validate geometry data"""
        errors = []

        if not isinstance(data, dict):
            errors.append("Geometry data must be a dictionary")
            return False, errors

        # Validate coordinate presence
        if 'lat' not in data or 'lon' not in data:
            errors.append("Missing lat/lon coordinates")
            return False, errors

        lat, lon = data['lat'], data['lon']

        # Validate coordinate ranges
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            errors.append("Coordinates must be numeric")
            return False, errors

        # Israel-specific bounds check (rough bounding box)
        israel_bounds = {
            'min_lat': 29.0,
            'max_lat': 33.5,
            'min_lon': 34.0,
            'max_lon': 36.0
        }

        if not (israel_bounds['min_lat'] <= lat <= israel_bounds['max_lat']):
            errors.append(
                f"Latitude {lat} outside Israel bounds "
                f"({israel_bounds['min_lat']}, {israel_bounds['max_lat']})"
            )

        if not (israel_bounds['min_lon'] <= lon <= israel_bounds['max_lon']):
            errors.append(
                f"Longitude {lon} outside Israel bounds "
                f"({israel_bounds['min_lon']}, {israel_bounds['max_lon']})"
            )

        is_valid = len(errors) == 0
        return is_valid, errors


class HubDataValidator:
    """
    Composite validator for complete hub data validation.

    Demonstrates Composite Pattern and Single Responsibility.
    """

    def __init__(self):
        self.validators: List[IValidator] = [
            SchemaValidator(['hub_id', 'name', 'location', 'passengers_2050']),
            DataQualityValidator(),
        ]

    def add_validator(self, validator: IValidator) -> None:
        """Add additional validator"""
        self.validators.append(validator)

    def validate(self, hub_data: HubData) -> Tuple[bool, List[str]]:
        """
        Run all validators on hub data.

        Returns:
            Tuple of (is_valid, all_errors)
        """
        all_errors = []

        # Convert HubData to dict for validation
        hub_dict = {
            'hub_id': hub_data.hub_id,
            'name': hub_data.name,
            'location': hub_data.location,
            'passengers_2050': hub_data.passengers_2050,
            'lat': hub_data.location.lat if hub_data.location else None,
            'lon': hub_data.location.lon if hub_data.location else None,
        }

        for validator in self.validators:
            is_valid, errors = validator.validate(hub_dict)
            if not is_valid:
                all_errors.extend(errors)

        is_valid = len(all_errors) == 0
        return is_valid, all_errors


class DataReconciliationValidator(IValidator):
    """
    Validates consistency across multiple data sources.

    Single Responsibility: Cross-dataset consistency validation.
    """

    def __init__(self, primary_data: List[Any], reference_data: List[Any]):
        self.primary_data = primary_data
        self.reference_data = reference_data

    def validate(self, data: Any) -> Tuple[bool, List[str]]:
        """Validate cross-dataset consistency"""
        errors = []

        # Example: Check that all station IDs in transit lines exist in station data
        # Placeholder implementation
        logger.info("Running cross-dataset reconciliation")

        return len(errors) == 0, errors
