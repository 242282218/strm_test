"""
STRM domain entity.

Represents a STRM file in the domain layer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib
import os


@dataclass(frozen=True)
class StrmKey:
    """
    Value object for STRM unique key.

    Uses SHA1 hash of the raw URL.
    """

    value: str

    @classmethod
    def from_url(cls, raw_url: str) -> "StrmKey":
        """Create key from raw URL."""
        return cls(value=hashlib.sha1(raw_url.encode()).hexdigest())

    def __str__(self) -> str:
        return self.value


@dataclass
class StrmEntity:
    """
    STRM domain entity.

    Represents a STRM file with its metadata and behaviors.
    """

    name: str
    local_dir: str
    remote_dir: str
    raw_url: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    _key: Optional[StrmKey] = field(default=None, repr=False)

    @property
    def key(self) -> StrmKey:
        """Get the unique key for this STRM."""
        if self._key is None:
            self._key = StrmKey.from_url(self.raw_url)
        return self._key

    @property
    def full_path(self) -> str:
        """Get the full file path."""
        return os.path.join(self.local_dir, self.name)

    def generate_file(self, overwrite: bool = False) -> bool:
        """
        Generate the STRM file on disk.

        Args:
            overwrite: Whether to overwrite existing file

        Returns:
            True if file was created, False if skipped
        """
        try:
            os.makedirs(self.local_dir, exist_ok=True)

            if not overwrite and os.path.exists(self.full_path):
                return False

            with open(self.full_path, "w", encoding="utf-8") as f:
                f.write(self.raw_url)

            return True
        except Exception as e:
            raise RuntimeError(f"Failed to generate STRM file {self.full_path}: {e}")

    def delete_file(self) -> bool:
        """
        Delete the STRM file from disk.

        Returns:
            True if file was deleted, False if not found
        """
        try:
            if os.path.exists(self.full_path):
                os.remove(self.full_path)
                return True
            return False
        except Exception as e:
            raise RuntimeError(f"Failed to delete STRM file {self.full_path}: {e}")

    def file_exists(self) -> bool:
        """Check if the STRM file exists on disk."""
        return os.path.exists(self.full_path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StrmEntity):
            return False
        return self.key == other.key

    def __hash__(self) -> int:
        return hash(self.key)
