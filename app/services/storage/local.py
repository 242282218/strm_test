import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from fastapi import HTTPException, status
from app.services.storage.base import StorageProvider
from app.schemas.file_manager import FileItem, FileType, StorageType
from app.core.logging import get_logger

logger = get_logger(__name__)

class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider."""

    def __init__(self):
        base_dir = os.getenv("SMART_MEDIA_LOCAL_ROOT")
        self._base_path: Optional[Path] = None
        if base_dir:
            self._base_path = Path(base_dir).expanduser().resolve()
            if not self._base_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Local storage base directory does not exist",
                )
            logger.info(f"Local storage restricted to: {self._base_path}")
        else:
            logger.warning("SMART_MEDIA_LOCAL_ROOT not set; local storage is unrestricted")

    @property
    def storage_type(self) -> StorageType:
        return StorageType.LOCAL

    def _map_to_file_item(self, full_path: Path) -> FileItem:
        """Map local file to FileItem."""
        stat = os.stat(full_path)
        is_dir = os.path.isdir(full_path)
        file_name = os.path.basename(full_path)

        return FileItem(
            id=str(full_path),
            name=file_name,
            path=str(full_path),
            parent_path=str(Path(full_path).parent),
            file_type=FileType.FOLDER if is_dir else FileType.FILE,
            storage_type=StorageType.LOCAL,
            extension=os.path.splitext(file_name)[1][1:] if not is_dir else None,
            size=stat.st_size if not is_dir else 0,
            updated_at=datetime.fromtimestamp(stat.st_mtime),
            is_readable=os.access(full_path, os.R_OK),
            is_writable=os.access(full_path, os.W_OK)
        )

    def _resolve_path(self, path: str) -> Path:
        if not path:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path is required")
        candidate = Path(path)
        if self._base_path and not candidate.is_absolute():
            candidate = self._base_path / candidate
        candidate = candidate.expanduser().resolve()
        if self._base_path:
            try:
                candidate.relative_to(self._base_path)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Path is outside allowed base directory",
                )
        return candidate

    def _is_within_base(self, path: Path) -> bool:
        if not self._base_path:
            return True
        try:
            path.relative_to(self._base_path)
            return True
        except ValueError:
            return False

    async def list(
        self,
        path: str,
        page: int = 1,
        size: int = 100
    ) -> Tuple[List[FileItem], int, Optional[str]]:
        """List local directory."""
        resolved = self._resolve_path(path)
        if not os.path.exists(resolved):
            raise FileNotFoundError(f"Path not found: {resolved}")

        items = []
        all_entries = os.listdir(resolved)
        total = len(all_entries)

        # Pagination
        start = (page - 1) * size
        end = start + size
        paged_entries = sorted(all_entries)[start:end]

        for entry in paged_entries:
            full_path = resolved / entry
            try:
                items.append(self._map_to_file_item(full_path))
            except Exception:
                continue

        # Parent directory
        parent_path = resolved.parent
        if not self._is_within_base(parent_path) or parent_path == resolved:
            parent_path = None

        return items, total, str(parent_path) if parent_path else None

    async def info(self, path: str) -> Optional[FileItem]:
        resolved = self._resolve_path(path)
        if not os.path.exists(resolved):
            return None
        return self._map_to_file_item(resolved)

    async def rename(self, path: str, new_name: str) -> FileItem:
        if os.path.basename(new_name) != new_name or (os.path.altsep and os.path.altsep in new_name) or os.path.sep in new_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid new name")
        resolved = self._resolve_path(path)
        parent = Path(resolved).parent
        new_path = parent / new_name
        os.rename(resolved, new_path)
        return self._map_to_file_item(new_path)

    async def move_batch(self, source_paths: List[str], target_dir: str) -> bool:
        """Batch move local files."""
        for path in source_paths:
            await self.move(path, target_dir)
        return True

    async def delete_batch(self, paths: List[str]) -> bool:
        """Batch delete local files."""
        for path in paths:
            await self.delete(path)
        return True

    async def move(self, source_path: str, target_dir: str) -> FileItem:
        resolved_source = self._resolve_path(source_path)
        resolved_target_dir = self._resolve_path(target_dir)
        file_name = os.path.basename(resolved_source)
        target_path = resolved_target_dir / file_name
        shutil.move(resolved_source, target_path)
        return self._map_to_file_item(target_path)

    async def delete(self, path: str) -> bool:
        resolved = self._resolve_path(path)
        if os.path.isdir(resolved):
            shutil.rmtree(resolved)
        else:
            os.remove(resolved)
        return True

    async def mkdir(self, parent_path: str, name: str) -> FileItem:
        if os.path.basename(name) != name or (os.path.altsep and os.path.altsep in name) or os.path.sep in name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid folder name")
        resolved_parent = self._resolve_path(parent_path)
        new_path = resolved_parent / name
        os.makedirs(new_path, exist_ok=True)
        return self._map_to_file_item(new_path)

    async def exists(self, path: str) -> bool:
        resolved = self._resolve_path(path)
        return os.path.exists(resolved)
