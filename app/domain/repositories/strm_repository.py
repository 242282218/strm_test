"""
STRM repository interface.

Defines the contract for STRM data persistence.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.entities.strm import StrmEntity, StrmKey


class IStrmRepository(ABC):
    """
    Abstract repository interface for STRM entities.

    Defines the contract for persisting and retrieving STRM data.
    """

    @abstractmethod
    async def get_by_key(self, key: StrmKey) -> Optional[StrmEntity]:
        """
        Get a STRM entity by its key.

        Args:
            key: The unique STRM key

        Returns:
            The STRM entity or None if not found
        """
        pass

    @abstractmethod
    async def get_by_remote_dir(self, remote_dir: str) -> List[StrmEntity]:
        """
        Get all STRM entities for a remote directory.

        Args:
            remote_dir: The remote directory path

        Returns:
            List of STRM entities
        """
        pass

    @abstractmethod
    async def get_all(self) -> List[StrmEntity]:
        """
        Get all STRM entities.

        Returns:
            List of all STRM entities
        """
        pass

    @abstractmethod
    async def save(self, entity: StrmEntity) -> StrmEntity:
        """
        Save a STRM entity.

        Args:
            entity: The entity to save

        Returns:
            The saved entity
        """
        pass

    @abstractmethod
    async def delete(self, key: StrmKey) -> bool:
        """
        Delete a STRM entity.

        Args:
            key: The key of the entity to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, key: StrmKey) -> bool:
        """
        Check if a STRM entity exists.

        Args:
            key: The key to check

        Returns:
            True if exists, False otherwise
        """
        pass

    @abstractmethod
    async def count(self) -> int:
        """
        Get the total count of STRM entities.

        Returns:
            Total count
        """
        pass
