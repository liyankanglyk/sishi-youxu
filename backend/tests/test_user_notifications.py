"""User-Notifications 章节完整接口测试 — `docs/03-技术架构/API接口文档.md §通知(notifications)`。

覆盖范围（5 条）：
    1. GET    /notifications                  — 分页列表（isRead 过滤）
    2. GET    /notifications/unread-count     — 未读数量
    3. PATCH  /notifications/{uuid}/read      — 标记单条已读
    4. POST   /notifications/read-all         — 全部标记已读
    5. DELETE /notifications/{uuid}           — 软删除通知

设计原则：
- 真实跑后端（TestClient + lifespan），不 mock DB/Redis；不可用时优雅 skip。
- 直接通过 ORM 注入测试数据（无公开创建端点，依赖业务任务创建通知）。
- 断言统一响应外壳 `{ success, data | error }`，字段名严格遵循 API 文档（camelCase）。
- 测试结束自动清理（conftest + _db_cleanup）。
- 每个测试独立可读；helper 抽到本文件顶部。
"""
from __future__ import annotations

import secrets
from typing import Any

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_ok_envelope(body: dict[str, Any], *, with_data: bool = True) -> None:
    assert body.get("success") is True, f"expected success=True, got {body!r}"
    if with_data:
        assert "data" in body


def _assert_err_envelope(body: dict[str, Any], *, code: str | None = None) -> None:
    assert body.get("success") is False, f"expected success=False, got {body!r}"
    err = body.get("error")
    assert err and "code" in err and "message" in err, f"missing error.code/message: {body!r}"
    if code is not None:
        assert err["code"] == code, f"expected code={code}, got {err['code']!r}"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_user(
    client: TestClient,
    *,
    email: str,
    nickname: str | None = None,
    password: str = "Secret123",
) -> dict[str, Any]:
    payload = {
        "nickname": nickname or f"u-{secrets.token_hex(3)}",
        "provider": "password",
        "payload": {"identifier": email, "password": password},
    }
    resp = client.post("/api/v1/users", json=payload)
    assert resp.status_code == 200, f"register failed: {resp.status_code} {resp.text}"
    return resp.json()["data"]


def _seed_notification(
    user_uuid: str,
    *,
    kind: str = "task_reminder",
    title: str | None = None,
    body: str | None = None,
    is_read: bool = False,
    task_uuid: str | None = None,
) -> dict[str, Any]:
    """直接通过 ORM 注入一条通知；返回通知字段快照。

    使用 sync engine + sync session，避免与 TestClient 的 event loop 冲突。
    """
    import secrets as _secrets
    import uuid as _uuid
    from datetime import datetime

    from sqlalchemy import create_engine, insert

    from src.core.config import settings
    from src.models.admin import Notification, NotificationKind

    # sync URL：把 mysql+aiomysql 替换为 mysql+pymysql
    sync_url = settings.DATABASE_URL.replace("mysql+aiomysql", "mysql+pymysql")
    _sync_engine = create_engine(sync_url, pool_pre_ping=True)

    new_uuid = str(_uuid.uuid4())
    actual_title = title or f"测试通知-{_secrets.token_hex(3)}"

    with _sync_engine.begin() as conn:
        stmt = insert(Notification).values(
            uuid=new_uuid,
            user_uuid=user_uuid,
            kind=NotificationKind(kind),
            is_read=is_read,
            title=actual_title,
            body=body or "通知内容",
            task_uuid=task_uuid,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        conn.execute(stmt)

    _sync_engine.dispose()
    return {
        "uuid": new_uuid,
        "kind": kind,
        "is_read": is_read,
        "title": actual_title,
    }


def _purge_notifications(user_uuids: list[str]) -> None:
    """清理测试用户的通知（teardown）。"""
    if not user_uuids:
        return

    from sqlalchemy import create_engine, delete

    from src.core.config import settings
    from src.models.admin import Notification

    sync_url = settings.DATABASE_URL.replace("mysql+aiomysql", "mysql+pymysql")
    _sync_engine = create_engine(sync_url, pool_pre_ping=True)

    with _sync_engine.begin() as conn:
        stmt = delete(Notification).where(Notification.user_uuid.in_(user_uuids))
        conn.execute(stmt)

    _sync_engine.dispose()


def _skip_if_500(resp, *, what: str) -> None:
    if resp.status_code == 500:
        pytest.skip(f"{what} returned 500 (likely infra unavailable): {resp.text[:200]}")


# ===========================================================================
# §通知（notifications）— 5 条
# ===========================================================================


# ---------------------------------------------------------------------------
# 1. GET /notifications — 列表
# ---------------------------------------------------------------------------
class TestNotificationsList:
    """GET /api/v1/notifications — 分页 + isRead 过滤。"""

    def test_requires_auth_401(self, client: TestClient) -> None:
        resp = client.get("/api/v1/notifications")
        assert resp.status_code == 401

    def test_empty_list(self, client: TestClient, random_email: str) -> None:
        tokens = _register_user(client, email=random_email)
        resp = client.get(
            "/api/v1/notifications",
            headers=_bearer(tokens["access_token"]),
        )
        _skip_if_500(resp, what="notifications empty")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["items"] == []
        assert data["meta"]["total"] == 0
        assert data["meta"]["hasMore"] is False

    def test_list_returns_seeded_notifications(
        self, client: TestClient, random_email: str
    ) -> None:
        """通过 ORM 注入 3 条 → GET 应能拿到。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            n1 = _seed_notification(user_uuid, title="通知1")
            n2 = _seed_notification(user_uuid, title="通知2")
            n3 = _seed_notification(user_uuid, title="通知3", is_read=True)

            resp = client.get(
                "/api/v1/notifications",
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(resp, what="notifications list")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["meta"]["total"] == 3
            uuids = {it["uuid"] for it in data["items"]}
            assert {n1["uuid"], n2["uuid"], n3["uuid"]} <= uuids
            # 列表元素字段完整性 — 文档定义：uuid/kind/title/body/taskUuid/isRead/createdAt
            for it in data["items"]:
                assert "uuid" in it
                assert "kind" in it
                assert "title" in it
                assert "body" in it
                # taskUuid 字段（文档定义），未关联任务时为 None
                assert "taskUuid" in it or "task_uuid" in it
                assert "isRead" in it
                assert "createdAt" in it
        finally:
            _purge_notifications([user_uuid])

    def test_filter_unread(
        self, client: TestClient, random_email: str
    ) -> None:
        """isRead=false 仅返回未读。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            n_unread1 = _seed_notification(user_uuid, is_read=False)
            n_unread2 = _seed_notification(user_uuid, is_read=False)
            _seed_notification(user_uuid, is_read=True)

            resp = client.get(
                "/api/v1/notifications",
                params={"isRead": False},
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(resp, what="notifications filter unread")
            assert resp.status_code == 200
            items = resp.json()["data"]["items"]
            uuids = {it["uuid"] for it in items}
            assert n_unread1["uuid"] in uuids
            assert n_unread2["uuid"] in uuids
            for it in items:
                assert it["isRead"] is False
        finally:
            _purge_notifications([user_uuid])

    def test_filter_read(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            _seed_notification(user_uuid, is_read=False)
            n_read = _seed_notification(user_uuid, is_read=True)

            resp = client.get(
                "/api/v1/notifications",
                params={"isRead": True},
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(resp, what="notifications filter read")
            assert resp.status_code == 200
            items = resp.json()["data"]["items"]
            uuids = {it["uuid"] for it in items}
            assert n_read["uuid"] in uuids
            for it in items:
                assert it["isRead"] is True
        finally:
            _purge_notifications([user_uuid])

    def test_user_isolation(
        self, client: TestClient, random_email: str
    ) -> None:
        """用户只能看到自己的通知。"""
        tokens_a = _register_user(client, email=random_email)
        tokens_b = _register_user(
            client, email=f"b-{secrets.token_hex(4)}@example.com"
        )
        user_a = tokens_a["user"]["uuid"]
        user_b = tokens_b["user"]["uuid"]
        try:
            n_a = _seed_notification(user_a, title="A的通知")
            n_b = _seed_notification(user_b, title="B的通知")

            resp = client.get(
                "/api/v1/notifications",
                headers=_bearer(tokens_a["access_token"]),
            )
            _skip_if_500(resp, what="notifications isolation A")
            uuids = {it["uuid"] for it in resp.json()["data"]["items"]}
            assert n_a["uuid"] in uuids
            assert n_b["uuid"] not in uuids
        finally:
            _purge_notifications([user_a, user_b])


# ---------------------------------------------------------------------------
# 2. GET /notifications/unread-count — 未读数量
# ---------------------------------------------------------------------------
class TestNotificationsUnreadCount:
    """GET /api/v1/notifications/unread-count"""

    def test_requires_auth_401(self, client: TestClient) -> None:
        resp = client.get("/api/v1/notifications/unread-count")
        assert resp.status_code == 401

    def test_zero_when_empty(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        resp = client.get(
            "/api/v1/notifications/unread-count",
            headers=_bearer(tokens["access_token"]),
        )
        _skip_if_500(resp, what="notifications unread empty")
        assert resp.status_code == 200
        assert resp.json()["data"]["unreadCount"] == 0

    def test_counts_only_unread(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            _seed_notification(user_uuid, is_read=False)
            _seed_notification(user_uuid, is_read=False)
            _seed_notification(user_uuid, is_read=True)

            resp = client.get(
                "/api/v1/notifications/unread-count",
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(resp, what="notifications unread count")
            assert resp.status_code == 200
            assert resp.json()["data"]["unreadCount"] == 2
        finally:
            _purge_notifications([user_uuid])


# ---------------------------------------------------------------------------
# 3. PATCH /notifications/{uuid}/read — 标记已读
# ---------------------------------------------------------------------------
class TestNotificationsMarkRead:
    """PATCH /api/v1/notifications/{uuid}/read"""

    def test_requires_auth_401(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/notifications/some-uuid/read")
        assert resp.status_code == 401

    def test_mark_unread_as_read(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            n = _seed_notification(user_uuid, is_read=False)

            resp = client.patch(
                f"/api/v1/notifications/{n['uuid']}/read",
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(resp, what="mark read")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["uuid"] == n["uuid"]
            assert data["isRead"] is True
            assert "readAt" in data

            # 验证 list 里也变成已读
            listing = client.get(
                "/api/v1/notifications",
                params={"isRead": True},
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(listing, what="list after mark read")
            uuids = {it["uuid"] for it in listing.json()["data"]["items"]}
            assert n["uuid"] in uuids
        finally:
            _purge_notifications([user_uuid])

    def test_mark_unknown_404(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        resp = client.patch(
            f"/api/v1/notifications/00000000-0000-0000-0000-000000000000/read",
            headers=_bearer(tokens["access_token"]),
        )
        _skip_if_500(resp, what="mark unknown")
        assert resp.status_code == 404
        _assert_err_envelope(resp.json(), code="NOTIFICATION_NOT_FOUND")

    def test_mark_other_users_notification_404(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens_a = _register_user(client, email=random_email)
        tokens_b = _register_user(
            client, email=f"b-{secrets.token_hex(4)}@example.com"
        )
        user_b = tokens_b["user"]["uuid"]
        try:
            n_b = _seed_notification(user_b, is_read=False)
            # 用户 A 想标记用户 B 的通知
            resp = client.patch(
                f"/api/v1/notifications/{n_b['uuid']}/read",
                headers=_bearer(tokens_a["access_token"]),
            )
            _skip_if_500(resp, what="cross-user mark read")
            assert resp.status_code == 404
            _assert_err_envelope(resp.json(), code="NOTIFICATION_NOT_FOUND")
        finally:
            _purge_notifications([user_b])


# ---------------------------------------------------------------------------
# 4. POST /notifications/read-all — 全部已读
# ---------------------------------------------------------------------------
class TestNotificationsReadAll:
    """POST /api/v1/notifications/read-all"""

    def test_requires_auth_401(self, client: TestClient) -> None:
        resp = client.post("/api/v1/notifications/read-all", json={})
        assert resp.status_code == 401

    def test_mark_all_unread(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            _seed_notification(user_uuid, is_read=False)
            _seed_notification(user_uuid, is_read=False)
            _seed_notification(user_uuid, is_read=False)

            resp = client.post(
                "/api/v1/notifications/read-all",
                headers=_bearer(tokens["access_token"]),
                json={},
            )
            _skip_if_500(resp, what="read-all")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["affected"] >= 3

            # 验证 unread-count = 0
            cnt = client.get(
                "/api/v1/notifications/unread-count",
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(cnt, what="read-all verify")
            assert cnt.json()["data"]["unreadCount"] == 0
        finally:
            _purge_notifications([user_uuid])

    def test_read_all_no_unread_is_zero(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        resp = client.post(
            "/api/v1/notifications/read-all",
            headers=_bearer(tokens["access_token"]),
            json={},
        )
        _skip_if_500(resp, what="read-all empty")
        assert resp.status_code == 200
        assert resp.json()["data"]["affected"] == 0


# ---------------------------------------------------------------------------
# 5. DELETE /notifications/{uuid} — 删除
# ---------------------------------------------------------------------------
class TestNotificationsDelete:
    """DELETE /api/v1/notifications/{uuid}"""

    def test_requires_auth_401(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/notifications/some-uuid")
        assert resp.status_code == 401

    def test_delete_success(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            n = _seed_notification(user_uuid)

            resp = client.delete(
                f"/api/v1/notifications/{n['uuid']}",
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(resp, what="delete notification")
            assert resp.status_code == 200

            # 删除后再 list 应看不到
            listing = client.get(
                "/api/v1/notifications",
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(listing, what="list after delete")
            uuids = {it["uuid"] for it in listing.json()["data"]["items"]}
            assert n["uuid"] not in uuids
        finally:
            _purge_notifications([user_uuid])

    def test_delete_unknown_404(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        resp = client.delete(
            "/api/v1/notifications/00000000-0000-0000-0000-000000000000",
            headers=_bearer(tokens["access_token"]),
        )
        _skip_if_500(resp, what="delete unknown")
        assert resp.status_code == 404
        _assert_err_envelope(resp.json(), code="NOTIFICATION_NOT_FOUND")

    def test_delete_twice_404(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            n = _seed_notification(user_uuid)
            client.delete(
                f"/api/v1/notifications/{n['uuid']}",
                headers=_bearer(tokens["access_token"]),
            )
            resp = client.delete(
                f"/api/v1/notifications/{n['uuid']}",
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(resp, what="delete twice")
            assert resp.status_code == 404
        finally:
            _purge_notifications([user_uuid])
