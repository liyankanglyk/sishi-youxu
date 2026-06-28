"""Generic repository base.

Skeleton: a thin async-friendly CRUD surface. Subclasses inject their model type
and rely on the soft-delete filter being applied automatically.
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base import SoftDeleteMixin

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Skeleton repository with soft-delete awareness."""

    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------- helpers ----------

    def _apply_soft_delete_filter(self, stmt: Any) -> Any:
        """Inject `WHERE deleted_at IS NULL` when the model supports it."""
        if issubclass(self.model, SoftDeleteMixin):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return stmt

    # ---------- queries ----------

    async def get(self, uuid: str) -> T | None:
        stmt = select(self.model).where(self.model.uuid == uuid)
        stmt = self._apply_soft_delete_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[T]:
        stmt = select(self.model).limit(limit).offset(offset)
        stmt = self._apply_soft_delete_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **fields: Any) -> T:
        instance = self.model(**fields)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def soft_delete(self, uuid: str) -> bool:
        """Mark the row deleted (only if it has SoftDeleteMixin)."""
        if not issubclass(self.model, SoftDeleteMixin):
            return False
        instance = await self.get(uuid)
        if instance is None:
            return False
        from datetime import datetime

        instance.deleted_at = datetime.utcnow()
        await self.session.flush()
        return True

    async def hard_delete(self, uuid: str) -> bool:
        stmt = delete(self.model).where(self.model.uuid == uuid)
        result = await self.session.execute(stmt)
        return (result.rowcount or 0) > 0