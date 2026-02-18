"""
STRM repository implementation using SQLAlchemy.

Provides concrete implementation of IStrmRepository.
"""

from typing import List, Optional
from datetime import datetime

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.strm import StrmEntity, StrmKey
from app.domain.repositories.strm_repository import IStrmRepository
from app.models.strm import StrmRecord
from app.core.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyStrmRepository(IStrmRepository):
    """
    SQLAlchemy implementation of STRM repository.

    Uses async SQLAlchemy sessions for database operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self._session = session

    def _to_entity(self, record: StrmRecord) -> StrmEntity:
        """Convert ORM model to domain entity."""
        return StrmEntity(
            name=record.name,
            local_dir=record.local_dir,
            remote_dir=record.remote_dir,
            raw_url=record.raw_url,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _to_record(self, entity: StrmEntity) -> StrmRecord:
        """Convert domain entity to ORM model."""
        return StrmRecord(
            key=str(entity.key),
            name=entity.name,
            local_dir=entity.local_dir,
            remote_dir=entity.remote_dir,
            raw_url=entity.raw_url,
            created_at=entity.created_at or datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    async def get_by_key(self, key: StrmKey) -> Optional[StrmEntity]:
        stmt = select(StrmRecord).where(StrmRecord.key == str(key))
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return self._to_entity(record)

    async def get_by_remote_dir(self, remote_dir: str) -> List[StrmEntity]:
        stmt = select(StrmRecord).where(StrmRecord.remote_dir == remote_dir)
        result = await self._session.execute(stmt)
        records = result.scalars().all()

        return [self._to_entity(r) for r in records]

    async def get_all(self) -> List[StrmEntity]:
        stmt = select(StrmRecord)
        result = await self._session.execute(stmt)
        records = result.scalars().all()

        return [self._to_entity(r) for r in records]

    async def save(self, entity: StrmEntity) -> StrmEntity:
        existing = await self.get_by_key(entity.key)

        if existing:
            stmt = (
                StrmRecord.__table__.update()
                .where(StrmRecord.key == str(entity.key))
                .values(
                    name=entity.name,
                    local_dir=entity.local_dir,
                    remote_dir=entity.remote_dir,
                    raw_url=entity.raw_url,
                    updated_at=datetime.utcnow(),
                )
            )
            await self._session.execute(stmt)
        else:
            record = self._to_record(entity)
            self._session.add(record)

        await self._session.commit()
        return await self.get_by_key(entity.key)

    async def delete(self, key: StrmKey) -> bool:
        stmt = delete(StrmRecord).where(StrmRecord.key == str(key))
        result = await self._session.execute(stmt)
        await self._session.commit()

        return result.rowcount > 0

    async def exists(self, key: StrmKey) -> bool:
        stmt = select(func.count()).where(StrmRecord.key == str(key))
        result = await self._session.execute(stmt)
        count = result.scalar()

        return count > 0

    async def count(self) -> int:
        stmt = select(func.count()).select_from(StrmRecord)
        result = await self._session.execute(stmt)
        return result.scalar()
