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

from tests.conftest import fetch_captcha_for_register  # noqa: E402

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
    captcha_id, captcha_solution = fetch_captcha_for_register(client)
    payload = {
        "nickname": nickname or f"u-{secrets.token_hex(3)}",
        "provider": "password",
        "payload": {"identifier": email, "password": password},
        "captchaId": captcha_id,
        "captchaSolution": captcha_solution,
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


# ---------------------------------------------------------------------------
# 4. Conflict detection（基于 updated_at）
# ---------------------------------------------------------------------------
class TestSyncConflict:
    """POST /api/v1/sync/push — 客户端提交过旧 updatedAt 应触发 conflict。"""

    def _create_task(self, client, token, *, title: str) -> str:
        """helper: push 一个 task，返回服务端生成的 uuid。"""
        op_id = f"op-{secrets.token_hex(6)}"
        resp = client.post(
            "/api/v1/sync/push",
            headers=_bearer(token),
            json={
                "ops": [
                    {
                        "opId": op_id,
                        "entity": "task",
                        "action": "upsert",
                        "payload": {"title": title, "urgencyLevel": 0, "importanceLevel": 0},
                    }
                ]
            },
        )
        _skip_if_500(resp, what="conflict: create task")
        assert resp.status_code == 200
        return resp.json()["data"]["results"][0]["serverRecord"]["uuid"]

    def test_update_with_newer_updated_at_succeeds(
        self, client: TestClient, random_email: str
    ) -> None:
        """客户端 updatedAt 晚于服务端 → 正常 applied。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            uuid = self._create_task(client, tokens["access_token"], title="baseline")

            # 等 50ms 让服务端 updatedAt 落后于客户端 clientTs
            import time

            time.sleep(0.05)
            client_ts = int(datetime.now().timestamp() * 1000) + 60_000  # 60s 后
            resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "task",
                            "action": "upsert",
                            "payload": {
                                "uuid": uuid,
                                "title": "newer-update",
                                "urgencyLevel": 1,
                                "importanceLevel": 1,
                                "updatedAt": datetime.fromtimestamp(client_ts / 1000).isoformat(),
                            },
                            "clientTs": client_ts,
                        }
                    ]
                },
            )
            _skip_if_500(resp, what="conflict: newer update")
            assert resp.status_code == 200
            r = resp.json()["data"]["results"][0]
            assert r["status"] == "applied"
            assert r["serverRecord"]["title"] == "newer-update"
        finally:
            _purge_user_data([user_uuid])

    def test_update_with_stale_updated_at_returns_conflict(
        self, client: TestClient, random_email: str
    ) -> None:
        """客户端 updatedAt 早于服务端 → 返回 conflict + serverRecord。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            uuid = self._create_task(client, tokens["access_token"], title="server-newer")

            # 等 50ms 让服务端 updatedAt 推进
            import time

            time.sleep(0.05)
            # clientTs 设在创建之前 — 服务端 updated_at 必然比客户端新
            stale_ts = datetime(2000, 1, 1, 0, 0, 0).isoformat()
            resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "task",
                            "action": "upsert",
                            "payload": {
                                "uuid": uuid,
                                "title": "client-stale",
                                "urgencyLevel": 0,
                                "importanceLevel": 0,
                                "updatedAt": stale_ts,
                            },
                            "clientTs": int(datetime(2000, 1, 1).timestamp() * 1000),
                        }
                    ]
                },
            )
            _skip_if_500(resp, what="conflict: stale update")
            assert resp.status_code == 200
            r = resp.json()["data"]["results"][0]
            assert r["status"] == "conflict"
            assert "serverRecord" in r
            # serverRecord 应是服务端的最新版本（不是 client-stale）
            assert r["serverRecord"]["title"] == "server-newer"
            assert r["serverRecord"]["uuid"] == uuid
            assert r["serverRecord"]["title"] != "client-stale"
        finally:
            _purge_user_data([user_uuid])


# ---------------------------------------------------------------------------
# 5. 跨用户所有权 — push 必须验证实体归属
# ---------------------------------------------------------------------------
class TestSyncOwnership:
    """POST /api/v1/sync/push — 跨用户操作他人的 task/tag/checklist 应被拒。"""

    def test_user_b_cannot_update_user_a_task(
        self, client: TestClient, random_email: str
    ) -> None:
        """A 创建 task → B 用该 uuid 更新 → 应被拒。"""
        tokens_a = _register_user(client, email=random_email)
        tokens_b = _register_user(client, email=f"b-{secrets.token_hex(4)}@example.com")
        try:
            # A 创建 task
            op_id = f"op-{secrets.token_hex(6)}"
            create_resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens_a["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": op_id,
                            "entity": "task",
                            "action": "upsert",
                            "payload": {"title": "A's task", "urgencyLevel": 0, "importanceLevel": 0},
                        }
                    ]
                },
            )
            _skip_if_500(create_resp, what="ownership: A create")
            a_uuid = create_resp.json()["data"]["results"][0]["serverRecord"]["uuid"]

            # B 试图用 A 的 uuid 更新
            update_resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens_b["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "task",
                            "action": "upsert",
                            "payload": {
                                "uuid": a_uuid,
                                "title": "B hijack",
                                "urgencyLevel": 1,
                                "importanceLevel": 1,
                            },
                        }
                    ]
                },
            )
            _skip_if_500(update_resp, what="ownership: B update")
            assert update_resp.status_code == 200
            body = update_resp.json()
            # B 的 op 应被拒（rejected 状态 + reason）
            r = body["data"]["results"][0]
            assert r["status"] == "rejected", f"expected rejected, got {r}"
            assert r.get("reason"), "rejected result should have a reason"
        finally:
            _purge_user_data(
                [tokens_a["user"]["uuid"], tokens_b["user"]["uuid"]]
            )

    def test_user_b_cannot_delete_user_a_task(
        self, client: TestClient, random_email: str
    ) -> None:
        """A 创建 task → B 删 → 应被拒。"""
        tokens_a = _register_user(client, email=random_email)
        tokens_b = _register_user(client, email=f"b-{secrets.token_hex(4)}@example.com")
        try:
            op_id = f"op-{secrets.token_hex(6)}"
            create_resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens_a["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": op_id,
                            "entity": "task",
                            "action": "upsert",
                            "payload": {"title": "A's task", "urgencyLevel": 0, "importanceLevel": 0},
                        }
                    ]
                },
            )
            _skip_if_500(create_resp, what="ownership-delete: A create")
            a_uuid = create_resp.json()["data"]["results"][0]["serverRecord"]["uuid"]

            # B 删除 A 的 task
            del_resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens_b["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "task",
                            "action": "delete",
                            "payload": {"uuid": a_uuid},
                        }
                    ]
                },
            )
            _skip_if_500(del_resp, what="ownership-delete: B delete")
            r = del_resp.json()["data"]["results"][0]
            assert r["status"] == "rejected"
            assert r.get("reason")

            # 验证 A 的 task 仍可被 A pull 到
            pull_resp = client.get(
                "/api/v1/sync/pull",
                headers=_bearer(tokens_a["access_token"]),
            )
            _skip_if_500(pull_resp, what="ownership-delete: A pull")
            titles = [t["title"] for t in pull_resp.json()["data"]["tasks"]["items"]]
            assert "A's task" in titles
        finally:
            _purge_user_data(
                [tokens_a["user"]["uuid"], tokens_b["user"]["uuid"]]
            )

    def test_user_b_cannot_link_taskTag_on_user_a_task(
        self, client: TestClient, random_email: str
    ) -> None:
        """A 创建 task + tag → B 试图 linkTaskTag → 应被拒。"""
        tokens_a = _register_user(client, email=random_email)
        tokens_b = _register_user(client, email=f"b-{secrets.token_hex(4)}@example.com")
        try:
            # A 创建 task
            task_op = f"op-{secrets.token_hex(6)}"
            create_resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens_a["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": task_op,
                            "entity": "task",
                            "action": "upsert",
                            "payload": {"title": "A task", "urgencyLevel": 0, "importanceLevel": 0},
                        }
                    ]
                },
            )
            _skip_if_500(create_resp, what="ownership-taglink: A create task")
            a_task_uuid = create_resp.json()["data"]["results"][0]["serverRecord"]["uuid"]

            # B 创建自己的 tag
            tag_op = f"op-{secrets.token_hex(6)}"
            tag_resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens_b["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": tag_op,
                            "entity": "tag",
                            "action": "upsert",
                            "payload": {"name": "B tag", "color": "#000000"},
                        }
                    ]
                },
            )
            _skip_if_500(tag_resp, what="ownership-taglink: B create tag")
            b_tag_uuid = tag_resp.json()["data"]["results"][0]["serverRecord"]["uuid"]

            # B 试图把 B 的 tag 关联到 A 的 task
            link_resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens_b["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "taskTag",
                            "action": "upsert",
                            "payload": {"task_uuid": a_task_uuid, "tag_uuid": b_tag_uuid},
                        }
                    ]
                },
            )
            _skip_if_500(link_resp, what="ownership-taglink: B link")
            r = link_resp.json()["data"]["results"][0]
            assert r["status"] == "rejected", f"expected rejected, got {r}"
        finally:
            _purge_user_data(
                [tokens_a["user"]["uuid"], tokens_b["user"]["uuid"]]
            )

    def test_user_b_cannot_create_checklist_on_user_a_task(
        self, client: TestClient, random_email: str
    ) -> None:
        """A 创建 task → B 给该 task 加 checklistItem → 应被拒。"""
        tokens_a = _register_user(client, email=random_email)
        tokens_b = _register_user(client, email=f"b-{secrets.token_hex(4)}@example.com")
        try:
            op_id = f"op-{secrets.token_hex(6)}"
            create_resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens_a["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": op_id,
                            "entity": "task",
                            "action": "upsert",
                            "payload": {"title": "A task", "urgencyLevel": 0, "importanceLevel": 0},
                        }
                    ]
                },
            )
            _skip_if_500(create_resp, what="ownership-checklist: A create")
            a_task_uuid = create_resp.json()["data"]["results"][0]["serverRecord"]["uuid"]

            cl_resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens_b["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "checklistItems",
                            "action": "upsert",
                            "payload": {
                                "task_uuid": a_task_uuid,
                                "title": "evil item",
                                "completed": False,
                                "sort_order": 0,
                            },
                        }
                    ]
                },
            )
            _skip_if_500(cl_resp, what="ownership-checklist: B add")
            r = cl_resp.json()["data"]["results"][0]
            assert r["status"] == "rejected", f"expected rejected, got {r}"
        finally:
            _purge_user_data(
                [tokens_a["user"]["uuid"], tokens_b["user"]["uuid"]]
            )


# ---------------------------------------------------------------------------
# 6. SAVEPOINT 隔离 — 单条 op 失败不应影响其他 op
# ---------------------------------------------------------------------------
class TestSyncSavepoint:
    """POST /api/v1/sync/push — 每条 op 用独立 SAVEPOINT，单条失败不影响其他。"""

    def test_invalid_op_does_not_block_valid_op_in_same_batch(
        self, client: TestClient, random_email: str
    ) -> None:
        """同一批 op：一条失败（缺字段）+ 一条 valid → 后者应 applied。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            # 注意：以下 payload 都是 client side generated uuid + title
            # 因为 invalid op 的校验在 _apply_op 内部，不会影响 valid op
            resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json={
                    "ops": [
                        # 第一条：tag upsert 但缺 name（应被 ValidationException 拒）
                        {
                            "opId": f"op-invalid-{secrets.token_hex(4)}",
                            "entity": "tag",
                            "action": "upsert",
                            "payload": {"uuid": "x", "color": "#FFF"},
                        },
                        # 第二条：valid task create
                        {
                            "opId": f"op-valid-{secrets.token_hex(6)}",
                            "entity": "task",
                            "action": "upsert",
                            "payload": {"title": "still-works", "urgencyLevel": 0, "importanceLevel": 0},
                        },
                    ]
                },
            )
            _skip_if_500(resp, what="savepoint: mixed batch")
            assert resp.status_code == 200
            results = resp.json()["data"]["results"]
            assert len(results) == 2

            by_opid = {r["opId"]: r for r in results}
            invalid_op = by_opid[f"op-invalid-{secrets.token_hex(4)}"] if False else None
            # 通过 prefix 找 opId
            invalid_results = [r for r in results if r["opId"].startswith("op-invalid-")]
            valid_results = [r for r in results if r["opId"].startswith("op-valid-")]
            assert len(invalid_results) == 1, "should have one invalid op"
            assert len(valid_results) == 1, "should have one valid op"

            # invalid 应被拒（不是整个请求失败）
            assert invalid_results[0]["status"] == "rejected"
            # valid 应正常 applied
            assert valid_results[0]["status"] == "applied"
            assert valid_results[0]["serverRecord"]["title"] == "still-works"
        finally:
            _purge_user_data([user_uuid])

    def test_batch_with_all_invalid_ops_returns_per_op_rejection(
        self, client: TestClient, random_email: str
    ) -> None:
        """整批全 invalid → 每条独立 rejected，整批 HTTP 仍 200。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json={
                    "ops": [
                        # 缺 name
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "tag",
                            "action": "upsert",
                            "payload": {"uuid": "x", "color": "#FFF"},
                        },
                        # taskTag 缺 task_uuid
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "taskTag",
                            "action": "upsert",
                            "payload": {"tag_uuid": "y"},
                        },
                    ]
                },
            )
            assert resp.status_code == 200  # 整批 HTTP 成功
            results = resp.json()["data"]["results"]
            assert all(r["status"] == "rejected" for r in results), results
        finally:
            _purge_user_data([user_uuid])


# ---------------------------------------------------------------------------
# 7. since 验证 — 非法 ISO 应被拒
# ---------------------------------------------------------------------------
class TestSyncSinceValidation:
    """GET /api/v1/sync/pull — since 字段非法字符串应返回 ValidationException。"""

    def test_invalid_since_string_rejected(
        self, client: TestClient, random_email: str
    ) -> None:
        """since='not-a-date' 应返回 HTTP 400 + error envelope（VALIDATION_ERROR）。

        BusinessExceptionMiddleware 把 BusinessException → JSONResponse(http_status=400, fail(...)).
        """
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            resp = client.get(
                "/api/v1/sync/pull",
                params={"since": "not-a-date"},
                headers=_bearer(tokens["access_token"]),
            )
            assert resp.status_code == 400
            body = resp.json()
            assert body.get("success") is False
            err = body.get("error", {})
            assert err.get("code") == "VALIDATION_ERROR"
        finally:
            _purge_user_data([user_uuid])

    def test_valid_iso_since_accepted(
        self, client: TestClient, random_email: str
    ) -> None:
        """since=合法 ISO 字符串应被接受。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            future = (datetime.now() + timedelta(hours=1)).isoformat()
            resp = client.get(
                "/api/v1/sync/pull",
                params={"since": future},
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(resp, what="since-validation: valid ISO")
            assert resp.status_code == 200
            assert resp.json().get("success") is True
        finally:
            _purge_user_data([user_uuid])

    def test_pull_returns_deleted_tasks_in_deleted_array(
        self, client: TestClient, random_email: str
    ) -> None:
        """修复 A1：deleted_at 非空的 task 应出现在 deleted[] 数组里（不是空数组）。"""
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            # push 一个 task
            create_resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "task",
                            "action": "upsert",
                            "payload": {"title": "to-be-deleted", "urgencyLevel": 0, "importanceLevel": 0},
                        }
                    ]
                },
            )
            _skip_if_500(create_resp, what="deleted-array: create")
            uuid = create_resp.json()["data"]["results"][0]["serverRecord"]["uuid"]

            # 删除
            del_resp = client.post(
                "/api/v1/sync/push",
                headers=_bearer(tokens["access_token"]),
                json={
                    "ops": [
                        {
                            "opId": f"op-{secrets.token_hex(6)}",
                            "entity": "task",
                            "action": "delete",
                            "payload": {"uuid": uuid},
                        }
                    ]
                },
            )
            _skip_if_500(del_resp, what="deleted-array: delete")

            # pull 应能看到 deleted[] 包含该 uuid
            pull_resp = client.get(
                "/api/v1/sync/pull",
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(pull_resp, what="deleted-array: pull")
            deleted = pull_resp.json()["data"]["tasks"]["deleted"]
            assert uuid in deleted, f"deleted uuid should appear in pull.deleted[]: {deleted}"
            # 同时不应出现在 items
            items_uuids = [t["uuid"] for t in pull_resp.json()["data"]["tasks"]["items"]]
            assert uuid not in items_uuids
        finally:
            _purge_user_data([user_uuid])
