"""Tag domain service — Phase 2 implementation.

Covers:
- Tag CRUD with name uniqueness checks (per user + presets)
- HEX color validation
- Preset tag protection (cannot edit/delete presets)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from src.core.logger import get_logger
from src.models.task import Tag

logger = get_logger(__name__)

_HEX_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class TagService:
    """All tag-related business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _tag_to_out(tag: Tag) -> dict[str, Any]:
        return {
            "uuid": tag.uuid,
            "name": tag.name,
            "color": tag.color,
            "isPreset": tag.is_preset,
            "createdAt": tag.created_at.isoformat() if tag.created_at else None,
            "updatedAt": tag.updated_at.isoformat() if tag.updated_at else None,
        }

    async def list_tags(self, user_uuid: str) -> dict[str, Any]:
        """List all tags for a user (including presets)."""
        stmt = select(Tag).where(
            Tag.deleted_at.is_(None),
            (Tag.user_uuid == user_uuid) | (Tag.is_preset.is_(True)),
        ).order_by(Tag.is_preset.desc(), Tag.name.asc())

        rows = (await self.db.execute(stmt)).scalars().all()
        items = [self._tag_to_out(t) for t in rows]
        return {
            "items": items,
            "meta": {
                "total": len(items),
                "page": 1,
                "pageSize": max(len(items), 20),
                "hasMore": False,
            },
        }

    async def create_tag(self, user_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create a custom tag."""
        name = (data.get("name") or "").strip()
        color = (data.get("color") or "").strip()

        if not name:
            raise ValidationException(
                "标签名称不能为空",
                code="VALIDATION_ERROR",
                detail={"name": "标签名称不能为空"},
            )
        if len(name) > 50:
            raise ValidationException(
                "标签名称不能超过 50 字符",
                code="VALIDATION_ERROR",
                detail={"name": "标签名称长度必须在 1-50 字符之间"},
            )
        if not _HEX_PATTERN.match(color):
            raise ValidationException(
                "颜色值必须是有效的 HEX 格式",
                code="VALIDATION_ERROR",
                detail={"color": "颜色值必须是有效的 HEX 格式，如 #A78BFA"},
            )

        # Check name uniqueness (within user scope + presets)
        existing = await self.db.execute(
            select(Tag).where(
                Tag.name == name,
                Tag.deleted_at.is_(None),
                (Tag.user_uuid == user_uuid) | (Tag.is_preset.is_(True)),
            )
        )
        if existing.scalars().first() is not None:
            raise ConflictException(
                "标签名称已存在",
                code="TAG_NAME_CONFLICT",
                detail={"name": name},
            )

        tag = Tag(
            user_uuid=user_uuid,
            name=name,
            color=color,
            is_preset=False,
        )
        self.db.add(tag)
        await self.db.flush()
        await self.db.refresh(tag)

        return self._tag_to_out(tag)

    async def update_tag(
        self, uuid: str, user_uuid: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a custom tag (cannot edit presets)."""
        stmt = select(Tag).where(
            Tag.uuid == uuid,
            Tag.deleted_at.is_(None),
        )
        tag = (await self.db.execute(stmt)).scalar_one_or_none()
        if tag is None:
            raise NotFoundException("标签不存在", code="TAG_NOT_FOUND")

        # Preset tags are read-only for normal users
        if tag.is_preset:
            raise ValidationException(
                "预设标签不可修改",
                code="VALIDATION_ERROR",
                detail={"isPreset": "预设标签不可修改"},
            )

        # Only owner can update
        if tag.user_uuid != user_uuid:
            raise NotFoundException("标签不存在", code="TAG_NOT_FOUND")

        changed = False

        if "name" in data:
            name = (data["name"] or "").strip()
            if not name or len(name) > 50:
                raise ValidationException(
                    "标签名称长度必须在 1-50 字符之间",
                    code="VALIDATION_ERROR",
                    detail={"name": "标签名称长度必须在 1-50 字符之间"},
                )
            # Check uniqueness if name changed
            if name != tag.name:
                existing = await self.db.execute(
                    select(Tag).where(
                        Tag.name == name,
                        Tag.uuid != uuid,
                        Tag.deleted_at.is_(None),
                        (Tag.user_uuid == user_uuid) | (Tag.is_preset.is_(True)),
                    )
                )
                if existing.scalars().first() is not None:
                    raise ConflictException(
                        "标签名称已存在",
                        code="TAG_NAME_CONFLICT",
                        detail={"name": name},
                    )
                tag.name = name
                changed = True

        if "color" in data:
            color = (data["color"] or "").strip()
            if not _HEX_PATTERN.match(color):
                raise ValidationException(
                    "颜色值必须是有效的 HEX 格式",
                    code="VALIDATION_ERROR",
                    detail={"color": "颜色值必须是有效的 HEX 格式，如 #A78BFA"},
                )
            tag.color = color
            changed = True

        if changed:
            await self.db.flush()
            await self.db.refresh(tag)

        return self._tag_to_out(tag)

    async def delete_tag(self, uuid: str, user_uuid: str) -> None:
        """Soft-delete a custom tag (cannot delete presets)."""
        stmt = select(Tag).where(
            Tag.uuid == uuid,
            Tag.deleted_at.is_(None),
        )
        tag = (await self.db.execute(stmt)).scalar_one_or_none()
        if tag is None:
            raise NotFoundException("标签不存在", code="TAG_NOT_FOUND")

        if tag.is_preset:
            raise ValidationException(
                "预设标签不可删除",
                code="VALIDATION_ERROR",
                detail={"isPreset": "预设标签不可删除"},
            )

        if tag.user_uuid != user_uuid:
            raise NotFoundException("标签不存在", code="TAG_NOT_FOUND")

        tag.deleted_at = datetime.utcnow()
        await self.db.flush()


__all__ = ["TagService"]
