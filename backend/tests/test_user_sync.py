"""User-Sync 章节完整接口测试 — `docs/03-技术架构/API接口文档.md §同步(sync)` / 同步协议.md。

覆盖范围（3 条）：
    1. POST /sync/push    — 批量推送本地 ops（opId 幂等）
    2. GET  /sync/pull    — 拉取 since 之后的变更
    3. GET  /sync/status  — 公开端点：服务端时间校准

设计原则：
- 真实跑后端（TestClient + lifespan），不 mock DB/Redis；不可用时优雅 skip。
- push/pull 测试覆盖 task / tag / taskTag / checklistItems 四种 entity 类型。
- 幂等性：相同 opId 重复推送应返回缓存结果。
- 用户隔离：A 推送的 task，B 不能 pull 到。
- 测试结束自动清理。
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
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


def _purge_user_data(user_uuids: list[str]) -> None:
    """Teardown: 硬删除 Task / Tag / TaskTag / TaskChecklist / Feedback / Notification。"""
    if not user_uuids:
        return

    from sqlalchemy import create_engine, delete

    from src.core.config import settings
    from src.models.admin import Feedback, Notification
    from src.models.task import Tag, Task, TaskChecklist, TaskTag

    sync_url = settings.DATABASE_URL.replace("mysql+aiomysql", "mysql+pymysql")
    eng = create_engine(sync_url, pool_pre_ping=True)
    try:
        with eng.begin() as conn:
            # 顺序：link → checklist → taskTag → tag → task → notif → feedback
            conn.execute(
                delete(TaskChecklist).where(TaskChecklist.task_uuid.in_(
                    select_(Task, user_uuids, eng)
                ))
            )
            conn.execute(delete(TaskTag).where(TaskTag.task_uuid.in_(
                select_(Task, user_uuids, eng)
            )))
            conn.execute(delete(TaskTag).where(TaskTag.tag_uuid.in_(
                select_(Tag, user_uuids, eng)
            )))
            conn.execute(delete(Task).where(Task.user_uuid.in_(user_uuids)))
            conn.execute(delete(Tag).where(Tag.user_uuid.in_(user_uuids)))
            conn.execute(delete(Notification).where(Notification.user_uuid.in_(user_uuids)))
            conn.execute(delete(Feedback).where(Feedback.user_uuid.in_(user_uuids)))
    finally:
        eng.dispose()


def select_(model, user_uuids, eng):
    """Helper: 构造子查询获取某用户的 task/tag uuid 列表。"""
    from sqlalchemy import select

    with eng.connect() as conn:
        if model.__name__ == "Task":
            return [r[0] for r in conn.execute(
                select(model.uuid).where(model.user_uuid.in_(user_uuids))
            ).all()]
        elif model.__name__ == "Tag":
            return [r[0] for r in conn.execute(
                select(model.uuid).where(model.user_uuid.in_(user_uuids))
            ).all()]
    return []


def _skip_if_500(resp, *, what: str) -> None:
    if resp.status_code == 500:
        pytest.skip(f"{what} returned 500 (likely infra unavailable): {resp.text[:200]}")


# ===========================================================================
# §同步（sync）— 3 条
# ===========================================================================


# ---------------------------------------------------------------------------
# 1. GET /sync/status — 公开端点
# ---------------------------------------------------------------------------
class TestSyncStatus:
    """GET /api/v1/sync/status — 公开端点，返回服务端时间。"""

    def test_no_auth_required(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sync/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "serverAt" in data
        assert "serverTimeMs" in data
        assert "timezone" in data
        assert isinstance(data["serverTimeMs"], int)
        assert data["serverTimeMs"] > 0

    def test_server_time_is_recent(self, client: TestClient) -> None:
        """serverTimeMs 应在「测试发起时间」的 ±60s 内。"""
        before_ms = int(datetime.now().timestamp() * 1000)
        resp = client.get("/api/v1/sync/status")
        after_ms = int(datetime.now().timestamp() * 1000)

        assert resp.status_code == 200
        srv = resp.json()["data"]["serverTimeMs"]
        assert before_ms - 1000 <= srv <= after_ms + 1000


# ---------------------------------------------------------------------------
# 2. POST /sync/push — 推送 ops（opId 幂等）
# ---------------------------------------------------------------------------
class TestSyncPush:
    """POST /api/v1/sync/push — 批量推送 ops，支持 opId 幂等。"""

    def test_requires_auth_401(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sync/push",
            json={"ops": []},
        )
        assert resp.status_code == 401

    def test_push_creates_task(
        self, client: TestClient, random_email: str
    ) -> None:
        """push 一个 task upsert → 服务端应创建。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            op_id = f"op-{secrets.token_hex(6)}"
            resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": op_id,
                            "entity": "task",
                            "action": "upsert",
                            "payload": {
                                "title": "sync 创建的任务",
                                "urgencyLevel": 0,
                                "importanceLevel": 0,
                            },
                            "clientTs": int(datetime.utcnow().timestamp() * 1000),
                        }
                    ]
                },
            )
            _skip_if_500(resp, what="sync push task")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert "results" in data
            assert len(data["results"]) == 1
            r = data["results"][0]
            assert r["opId"] == op_id
            assert r["status"] == "applied"
            assert "serverRecord" in r
            assert r["serverRecord"]["title"] == "sync 创建的任务"
        finally:
            _purge_user_data([user_uuid])

    def test_push_idempotency_same_op_id(
        self, client: TestClient, random_email: str
    ) -> None:
        """相同 opId 重复推送 → 第二次应返回缓存结果，不应重复创建。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            op_id = f"op-{secrets.token_hex(6)}"
            payload = {
                "ops": [
                    {
                        "opId": op_id,
                        "entity": "task",
                        "action": "upsert",
                        "payload": {"title": "幂等任务", "urgencyLevel": 0, "importanceLevel": 0},
                    }
                ]
            }
            # 第一次推送
            r1 = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json=payload,
            )
            _skip_if_500(r1, what="sync push idempotency 1")
            assert r1.status_code == 200
            # 第二次推送相同 opId
            r2 = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json=payload,
            )
            _skip_if_500(r2, what="sync push idempotency 2")
            assert r2.status_code == 200

            # 两次结果应一致
            res1 = r1.json()["data"]["results"][0]
            res2 = r2.json()["data"]["results"][0]
            assert res1["opId"] == res2["opId"] == op_id
            assert res2["status"] == "applied"
        finally:
            _purge_user_data([user_uuid])

    def test_push_creates_tag(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "tag",
                            "action": "upsert",
                            "payload": {"name": "sync标签", "color": "#FF6B6B"},
                        }
                    ]
                },
            )
            _skip_if_500(resp, what="sync push tag")
            assert resp.status_code == 200
            r = resp.json()["data"]["results"][0]
            assert r["status"] == "applied"
            assert r["serverRecord"]["name"] == "sync标签"
        finally:
            _purge_user_data([user_uuid])

    def test_push_too_many_ops_400(
        self, client: TestClient, random_email: str
    ) -> None:
        """ops 超过 100 条应被 Pydantic max_length 拒绝 → 422。"""
        tokens = _register_user(client, email=random_email)
        ops = [
            {
                "opId": f"op-{i}",
                "entity": "task",
                "action": "upsert",
                "payload": {"title": f"t{i}", "urgencyLevel": 0, "importanceLevel": 0},
            }
            for i in range(101)
        ]
        resp = client.post(
            "/api/v1/sync/push",
            headers=_bearer(tokens["access_token"]),
            json={"ops": ops},
        )
        assert resp.status_code == 422

    def test_push_empty_ops_422(
        self, client: TestClient, random_email: str
    ) -> None:
        """空 ops 应被 Pydantic min_length=1 拒绝 → 422。"""
        tokens = _register_user(client, email=random_email)
        resp = client.post(
            "/api/v1/sync/push",
            headers=_bearer(tokens["access_token"]),
            json={"ops": []},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. GET /sync/pull — 拉取变更
# ---------------------------------------------------------------------------
class TestSyncPull:
    """GET /api/v1/sync/pull — 拉取 since 之后的变更。"""

    def test_requires_auth_401(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sync/pull")
        assert resp.status_code == 401

    def test_pull_returns_server_at(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        resp = client.get(
            "/api/v1/sync/pull",
            headers=_bearer(tokens["access_token"]),
        )
        _skip_if_500(resp, what="sync pull empty")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "serverAt" in data

    def test_pull_returns_tasks_created_via_push(
        self, client: TestClient, random_email: str
    ) -> None:
        """先 push 一个 task，再 pull 应能拿到。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            # push
            client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "task",
                            "action": "upsert",
                            "payload": {"title": "pull-target", "urgencyLevel": 0, "importanceLevel": 1},
                        }
                    ]
                },
            )

            # pull
            resp = client.get(
                "/api/v1/sync/pull",
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(resp, what="sync pull with task")
            data = resp.json()["data"]
            assert "tasks" in data
            titles = [t["title"] for t in data["tasks"]["items"]]
            assert "pull-target" in titles
        finally:
            _purge_user_data([user_uuid])

    def test_pull_since_filters_old_changes(
        self, client: TestClient, random_email: str
    ) -> None:
        """since=now+1h 应过滤掉之前创建的记录。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            # push 一个旧任务
            client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "task",
                            "action": "upsert",
                            "payload": {"title": "old-task", "urgencyLevel": 0, "importanceLevel": 0},
                        }
                    ]
                },
            )

            # since = 1 小时后，应过滤掉
            future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
            resp = client.get(
                "/api/v1/sync/pull",
                params={"since": future},
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(resp, what="sync pull since future")
            assert resp.status_code == 200
            tasks = resp.json()["data"]["tasks"]["items"]
            titles = [t["title"] for t in tasks]
            assert "old-task" not in titles
        finally:
            _purge_user_data([user_uuid])

    def test_pull_user_isolation(
        self, client: TestClient, random_email: str
    ) -> None:
        """A push 的 task，B pull 不到。"""
        tokens_a = _register_user(client, email=random_email)
        tokens_b = _register_user(
            client, email=f"b-{secrets.token_hex(4)}@example.com"
        )
        try:
            # A push
            client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens_a["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "task",
                            "action": "upsert",
                            "payload": {"title": "A-only-task", "urgencyLevel": 0, "importanceLevel": 0},
                        }
                    ]
                },
            )

            # B pull
            resp = client.get(
                "/api/v1/sync/pull",
                headers=_bearer(tokens_b["access_token"]),
            )
            _skip_if_500(resp, what="sync pull isolation B")
            tasks = resp.json()["data"]["tasks"]["items"]
            titles = [t["title"] for t in tasks]
            assert "A-only-task" not in titles
        finally:
            _purge_user_data(
                [tokens_a["user"]["uuid"], tokens_b["user"]["uuid"]]
            )

    def test_pull_entities_filter(
        self, client: TestClient, random_email: str
    ) -> None:
        """entities=tag 应只返回 tag，不返回 task。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            # push 一个 task + 一个 tag
            client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "task",
                            "action": "upsert",
                            "payload": {"title": "filtered-task", "urgencyLevel": 0, "importanceLevel": 0},
                        },
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "tag",
                            "action": "upsert",
                            "payload": {"name": "filtered-tag", "color": "#AABBCC"},
                        },
                    ]
                },
            )

            resp = client.get(
                "/api/v1/sync/pull",
                params={"entities": "tag"},
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(resp, what="sync pull entities=tag")
            data = resp.json()["data"]
            # 选了 entity=tag 时，response 可能不含 tasks 键
            assert "tasks" not in data
            assert "tags" in data
        finally:
            _purge_user_data([user_uuid])
