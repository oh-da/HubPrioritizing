"""
Repository implementation for hub data persistence.

Follows Repository Pattern:
- Single Responsibility: Data access abstraction
- Dependency Inversion: Implements IDataRepository interface
"""

from typing import Dict, List, Optional
import logging

from ..interfaces import IDataRepository, HubData, HubTier

logger = logging.getLogger(__name__)


class HubDataRepository(IDataRepository):
    """
    In-memory implementation of hub data repository.

    Single Responsibility: Manage hub data storage and retrieval.
    Dependency Inversion: Implements IDataRepository interface.

    Note: In production, this could be backed by a database,
    but the interface remains the same (Open/Closed principle).
    """

    def __init__(self):
        self._hubs: Dict[str, HubData] = {}
        logger.info("Initialized HubDataRepository")

    def get_hub(self, hub_id: str) -> Optional[HubData]:
        """Retrieve a single hub by ID"""
        hub = self._hubs.get(hub_id)
        if hub is None:
            logger.warning(f"Hub not found: {hub_id}")
        return hub

    def get_all_hubs(self) -> List[HubData]:
        """Retrieve all hubs"""
        return list(self._hubs.values())

    def get_hubs_by_tier(self, tier: HubTier) -> List[HubData]:
        """Retrieve hubs filtered by tier"""
        return [
            hub for hub in self._hubs.values()
            if hub.tier == tier
        ]

    def save_hub(self, hub: HubData) -> None:
        """Persist hub data"""
        self._hubs[hub.hub_id] = hub
        logger.debug(f"Saved hub: {hub.hub_id}")

    def save_many(self, hubs: List[HubData]) -> None:
        """Persist multiple hubs"""
        for hub in hubs:
            self.save_hub(hub)
        logger.info(f"Saved {len(hubs)} hubs")

    def delete_hub(self, hub_id: str) -> bool:
        """Delete a hub by ID"""
        if hub_id in self._hubs:
            del self._hubs[hub_id]
            logger.info(f"Deleted hub: {hub_id}")
            return True
        logger.warning(f"Cannot delete hub {hub_id}: not found")
        return False

    def count(self) -> int:
        """Get total number of hubs"""
        return len(self._hubs)

    def clear(self) -> None:
        """Clear all hub data"""
        count = len(self._hubs)
        self._hubs.clear()
        logger.info(f"Cleared {count} hubs from repository")


class FileBasedHubRepository(IDataRepository):
    """
    File-based repository implementation.

    Demonstrates Open/Closed: New repository type without modifying interface.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._cache: Dict[str, HubData] = {}
        logger.info(f"Initialized FileBasedHubRepository: {file_path}")

    def get_hub(self, hub_id: str) -> Optional[HubData]:
        """Retrieve hub from file/cache"""
        # Placeholder - implement actual file loading
        return self._cache.get(hub_id)

    def get_all_hubs(self) -> List[HubData]:
        """Retrieve all hubs from file"""
        # Placeholder - implement actual file loading
        return list(self._cache.values())

    def get_hubs_by_tier(self, tier: HubTier) -> List[HubData]:
        """Retrieve hubs filtered by tier"""
        return [
            hub for hub in self._cache.values()
            if hub.tier == tier
        ]

    def save_hub(self, hub: HubData) -> None:
        """Save hub to file"""
        self._cache[hub.hub_id] = hub
        # Placeholder - implement actual file writing
        logger.debug(f"Saved hub to file: {hub.hub_id}")
