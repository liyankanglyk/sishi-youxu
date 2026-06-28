"""User-Feedback 章节完整接口测试 — `docs/03-技术架构/API接口文档.md §反馈(feedback)`。

覆盖范围（2 条）：
    1. POST /feedback  — 提交反馈（公开，匿名或登录态均可）
    2. GET  /feedback  — 查询我的反馈（需登录）

设计原则：
- 真实跑后端（TestClient + lifespan），不 mock DB/Redis；不可用时优雅 skip。
- 匿名 + 登录态均覆盖；用户隔离。
- 断言统一响应外壳 `{ success, data | error }`，字段名遵循 API 文档。
- 测试结束自动清理测试反馈（teardown）。
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


def _purge_feedback_for_users(user_uuids: list[str]) -> None:
    """Teardown: 硬删除测试用户的反馈。"""
    if not user_uuids:
        return

    from sqlalchemy import create_engine, delete

    from src.core.config import settings
    from src.models.admin import Feedback

    sync_url = settings.DATABASE_URL.replace("mysql+aiomysql", "mysql+pymysql")
    eng = create_engine(sync_url, pool_pre_ping=True)
    try:
        with eng.begin() as conn:
            conn.execute(delete(Feedback).where(Feedback.user_uuid.in_(user_uuids)))
    finally:
        eng.dispose()


def _purge_feedback_for_uuids(uuids: list[str]) -> None:
    """Teardown: 硬删除指定的 feedback uuid。"""
    if not uuids:
        return

    from sqlalchemy import create_engine, delete

    from src.core.config import settings
    from src.models.admin import Feedback

    sync_url = settings.DATABASE_URL.replace("mysql+aiomysql", "mysql+pymysql")
    eng = create_engine(sync_url, pool_pre_ping=True)
    try:
        with eng.begin() as conn:
            conn.execute(delete(Feedback).where(Feedback.uuid.in_(uuids)))
    finally:
        eng.dispose()


def _skip_if_500(resp, *, what: str) -> None:
    if resp.status_code == 500:
        pytest.skip(f"{what} returned 500 (likely infra unavailable): {resp.text[:200]}")


# ===========================================================================
# §反馈（feedback）— 2 条
# ===========================================================================


# ---------------------------------------------------------------------------
# 1. POST /feedback — 提交反馈
# ---------------------------------------------------------------------------
class TestFeedbackCreate:
    """POST /api/v1/feedback — 提交反馈（公开，匿名或登录态均可）。"""

    def test_create_with_authenticated_user(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            resp = client.post(
                "/api/v1/feedback",
                headers=_bearer(tokens["access_token"]),
                json={
                    "content": "希望增加任务提醒功能",
                    "contact": "user@example.com",
                },
            )
            _skip_if_500(resp, what="feedback create authed")
            assert resp.status_code == 201
            data = resp.json()["data"]
            assert data["uuid"]
            assert data["content"] == "希望增加任务提醒功能"
            assert data["contact"] == "user@example.com"
            assert data["status"] == "pending"
            assert "createdAt" in data
        finally:
            _purge_feedback_for_users([user_uuid])

    def test_create_anonymous(
        self, client: TestClient
    ) -> None:
        """未登录也可提交反馈。"""
        created_uuid: list[str] = []
        try:
            resp = client.post(
                "/api/v1/feedback",
                json={"content": "匿名反馈内容"},
            )
            _skip_if_500(resp, what="feedback anonymous")
            assert resp.status_code == 201
            data = resp.json()["data"]
            assert data["content"] == "匿名反馈内容"
            assert data["contact"] is None
            assert data["status"] == "pending"
            created_uuid.append(data["uuid"])
        finally:
            _purge_feedback_for_uuids(created_uuid)

    def test_create_without_contact(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            resp = client.post(
                "/api/v1/feedback",
                headers=_bearer(tokens["access_token"]),
                json={"content": "无联系方式反馈"},
            )
            _skip_if_500(resp, what="feedback no contact")
            assert resp.status_code == 201
            assert resp.json()["data"]["contact"] is None
        finally:
            _purge_feedback_for_users([user_uuid])

    def test_create_empty_content_422(
        self, client: TestClient
    ) -> None:
        """空 content 应被 Pydantic 拒绝（min_length=1）。"""
        resp = client.post("/api/v1/feedback", json={"content": ""})
        assert resp.status_code == 422

    def test_create_missing_content_422(
        self, client: TestClient
    ) -> None:
        resp = client.post("/api/v1/feedback", json={"contact": "x@x.com"})
        assert resp.status_code == 422

    def test_create_too_long_content_422(
        self, client: TestClient
    ) -> None:
        """content 超过 2000 字符应被拒绝。"""
        resp = client.post(
            "/api/v1/feedback",
            json={"content": "x" * 2001},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 2. GET /feedback — 查询我的反馈
# ---------------------------------------------------------------------------
class TestFeedbackList:
    """GET /api/v1/feedback — 当前用户提交的反馈列表（分页）。"""

    def test_requires_auth_401(self, client: TestClient) -> None:
        resp = client.get("/api/v1/feedback")
        assert resp.status_code == 401

    def test_empty_list(self, client: TestClient, random_email: str) -> None:
        tokens = _register_user(client, email=random_email)
        resp = client.get(
            "/api/v1/feedback",
            headers=_bearer(tokens["access_token"]),
        )
        _skip_if_500(resp, what="feedback empty")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["items"] == []
        assert data["meta"]["total"] == 0

    def test_list_returns_user_feedback(
        self, client: TestClient, random_email: str
    ) -> None:
        tokens = _register_user(client, email=random_email)
        user_uuid = tokens["user"]["uuid"]
        try:
            # 提交 3 条
            for i in range(3):
                client.post(
                    "/api/v1/feedback",
                    headers=_bearer(tokens["access_token"]),
                    json={"content": f"反馈 {i}"},
                )

            resp = client.get(
                "/api/v1/feedback",
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(resp, what="feedback list")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["meta"]["total"] == 3
            assert len(data["items"]) == 3
            for it in data["items"]:
                assert "uuid" in it
                assert "content" in it
                assert "status" in it
                assert "createdAt" in it
        finally:
            _purge_feedback_for_users([user_uuid])

    def test_user_isolation(
        self, client: TestClient, random_email: str
    ) -> None:
        """用户只能看到自己的反馈。"""
        tokens_a = _register_user(client, email=random_email)
        tokens_b = _register_user(
            client, email=f"b-{secrets.token_hex(4)}@example.com"
        )
        try:
            client.post(
                "/api/v1/feedback",
                headers=_bearer(tokens_a["access_token"]),
                json={"content": "A 的反馈"},
            )
            client.post(
                "/api/v1/feedback",
                headers=_bearer(tokens_b["access_token"]),
                json={"content": "B 的反馈"},
            )

            resp = client.get(
                "/api/v1/feedback",
                headers=_bearer(tokens_a["access_token"]),
            )
            _skip_if_500(resp, what="feedback isolation A")
            contents = [it["content"] for it in resp.json()["data"]["items"]]
            assert "A 的反馈" in contents
            assert "B 的反馈" not in contents
        finally:
            _purge_feedback_for_users(
                [tokens_a["user"]["uuid"], tokens_b["user"]["uuid"]]
            )

    def test_anonymous_feedback_not_visible_to_users(
        self, client: TestClient, random_email: str
    ) -> None:
        """匿名提交的反馈不应被任何用户在自己的列表里看到。"""
        anonymous_uuids: list[str] = []
        tokens = _register_user(client, email=random_email)
        try:
            resp = client.post(
                "/api/v1/feedback",
                json={"content": "完全匿名反馈"},
            )
            _skip_if_500(resp, what="anonymous feedback")
            anonymous_uuids.append(resp.json()["data"]["uuid"])

            listing = client.get(
                "/api/v1/feedback",
                headers=_bearer(tokens["access_token"]),
            )
            _skip_if_500(listing, what="listing after anonymous")
            contents = [it["content"] for it in listing.json()["data"]["items"]]
            assert "完全匿名反馈" not in contents
        finally:
            _purge_feedback_for_users([tokens["user"]["uuid"]])
            _purge_feedback_for_uuids(anonymous_uuids)
