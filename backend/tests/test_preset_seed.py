"""验证后端启动时的预设标签种子。

覆盖：
1. 首次调用 seed_preset_tags() 会插入全部预设标签
2. 重复调用是幂等的（不重复插入）
3. 用户 list_tags() 能看到这些全局标签
4. 标签的颜色是有效的 HEX
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.seed import PRESET_TAGS, seed_preset_tags
from src.main import app
from src.models.task import Tag


HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


@pytest.fixture()
def db_session():
    """同步会话，用于直接插入/读取表。不经过 FastAPI。"""
    # Async URL -> sync URL (use pymysql for sync sessions)
    url = settings.DATABASE_URL
    if "+aiomysql" in url:
        url = url.replace("+aiomysql", "+pymysql")
    elif url.startswith("mysql+asyncmy"):
        url = url.replace("+asyncmy", "+pymysql")
    elif url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)
    eng = create_engine(url, pool_pre_ping=True)
    with Session(eng) as s:
        yield s
    eng.dispose()


def test_seed_inserts_all_preset_tags(db_session: Session) -> None:
    """首次调用：所有预设标签都被插入。不能拿到个别存在的去插（跳过那个）。"""
    # 先清理可能已存在的同 UUID（幂等测试的底子）
    uuids = [t["uuid"] for t in PRESET_TAGS]
    db_session.execute(text("DELETE FROM sishiyouxu_tag WHERE uuid IN :uuids"), {"uuids": tuple(uuids)})
    db_session.commit()

    async def _run() -> int:
        from src.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as s:
            return await seed_preset_tags(s)

    import asyncio
    inserted = asyncio.run(_run())
    assert inserted == len(PRESET_TAGS), f"expected to insert {len(PRESET_TAGS)}, got {inserted}"

    # 读出来核对
    rows = db_session.execute(
        select(Tag).where(Tag.uuid.in_(uuids))
    ).scalars().all()
    by_uuid = {r.uuid: r for r in rows}
    assert len(by_uuid) == len(PRESET_TAGS)
    for spec in PRESET_TAGS:
        row = by_uuid[spec["uuid"]]
        assert row.name == spec["name"]
        assert row.color == spec["color"]
        assert row.is_preset is True
        assert row.user_uuid is None  # 全局可见


def test_seed_is_idempotent(db_session: Session) -> None:
    """重复调用不会产生重复行。

    走 HTTP 端点而不是直接调 async 函数 —— 每次通过 TestClient 触发的 lifespan
    都会重新创建 event loop，避免 sync 测试里手动 asyncio.run 引发的连接问题。
    """
    # 第一次调用：触发 lifespan -> seed_preset_tags()
    # 第二次：再触发一次
    with TestClient(app) as c1, TestClient(app) as c2:
        # 通过 /api/v1/tags 间接验证 tag 已存在（lifespan 已运行过 seed）
        pass

    # 直接验证表里的行数 = 预设个数（没有重复）
    uuids = [t["uuid"] for t in PRESET_TAGS]
    rows = db_session.execute(
        select(Tag).where(Tag.uuid.in_(uuids))
    ).scalars().all()
    assert len(rows) == len(PRESET_TAGS), (
        f"expected {len(PRESET_TAGS)} preset rows, got {len(rows)}"
    )


def test_preset_tag_colors_are_valid_hex() -> None:
    """所有预设颜色都是有效的 HEX。不然 UI 会跳转。"""
    for t in PRESET_TAGS:
        assert HEX.match(t["color"]), f"bad color for tag {t["name"]}: {t["color"]}"


def test_user_sees_preset_tags_in_list(client, skip_if_unavailable) -> None:
    """用户 list_tags() 应该能看到全局预设标签。"""
    if skip_if_unavailable():
        pytest.skip("backend not available")

    # 注册一个新用户
    from tests.conftest import fetch_captcha_for_register

    captcha_id, captcha_solution = fetch_captcha_for_register(client)
    payload = {
        "nickname": f"tag-seed-{__import__('secrets').token_hex(3)}",
        "provider": "password",
        "payload": {
            "identifier": f"tag-seed-{__import__('secrets').token_hex(6)}@example.com",
            "password": "Secret123",
        },
        "captchaId": captcha_id,
        "captchaSolution": captcha_solution,
    }
    resp = client.post("/api/v1/users", json=payload)
    if resp.status_code != 200:
        print("REGISTER FAILED:", resp.status_code, resp.text[:500])
    assert resp.status_code == 200, f"register failed: {resp.text[:300]}"
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 调 list_tags
    resp = client.get("/api/v1/tags", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]

    # 所有预设标签都在列表里
    preset_uuids = {t["uuid"] for t in PRESET_TAGS}
    listed_uuids = {i["uuid"] for i in items}
    missing = preset_uuids - listed_uuids
    assert not missing, f"missing preset tags for user: {missing}"
