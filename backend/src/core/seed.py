"""应用启动时的幂等性种子数据。

不依赖 scripts/seed.sql；调用者可以完全靠这里的 seed_preset_tags()。
重复调用是安全的：冷启动、热重载、代码演练都不会产生重复行。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.models.task import Tag

logger = get_logger(__name__)

# 4 个全局预设标签。UUID 固定以便于跨环境对齐；user_uuid=NULL 代表全局可见。
# 颜色选择中性中、饱和度中高、互补色，便于一眼区分。
PRESET_TAGS: list[dict] = [
    {
        "uuid": "00000000-0000-0000-0000-000000000001",
        "name": "工作",
        "color": "#3B82F6",  # blue
    },
    {
        "uuid": "00000000-0000-0000-0000-000000000002",
        "name": "学习",
        "color": "#22C55E",  # green
    },
    {
        "uuid": "00000000-0000-0000-0000-000000000003",
        "name": "生活",
        "color": "#F97316",  # orange
    },
    {
        "uuid": "00000000-0000-0000-0000-000000000004",
        "name": "健康",
        "color": "#EF4444",  # red
    },
    {
        "uuid": "00000000-0000-0000-0000-000000000005",
        "name": "财务",
        "color": "#A855F7",  # purple
    },
    {
        "uuid": "00000000-0000-0000-0000-000000000006",
        "name": "社交",
        "color": "#EC4899",  # pink
    },
]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def seed_preset_tags(db: AsyncSession) -> int:
    """确保 4 个全局预设标签存在。

    以 UUID 为唯一键：如果某个 UUID 已存在，跳过；
    如果名称被用户占用，也保持现有记录不动。

    Returns:本次新插入的标签数量。
    """
    now = _now()
    inserted = 0

    # 预查已存在的 UUID，避免不必要的描述
    existing_uuids = set(
        (
            await db.execute(
                select(Tag.uuid).where(
                    Tag.uuid.in_([t["uuid"] for t in PRESET_TAGS])
                )
            )
        )
        .scalars()
        .all()
    )

    for spec in PRESET_TAGS:
        if spec["uuid"] in existing_uuids:
            continue
        db.add(
            Tag(
                uuid=spec["uuid"],
                user_uuid=None,  # NULL = 全局可见
                name=spec["name"],
                color=spec["color"],
                is_preset=True,
                created_at=now,
                updated_at=now,
            )
        )
        inserted += 1

    if inserted:
        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.warning("seed_preset_tags commit failed: %s", exc)
            return 0
        logger.info("seeded %d preset tag(s)", inserted)
    return inserted


__all__ = ["PRESET_TAGS", "seed_preset_tags"]
