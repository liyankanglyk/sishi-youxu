"""跨用户数据访问 + 同步 payload 契约的回归测试。

覆盖两类已修复的缺陷：

1. **检查项接口缺少归属校验** —— `list/update/delete checklist` 之前只按
   `task_uuid + item_uuid` 过滤，不校验 task 是否属于当前用户，
   任意登录用户拿到别人的 task uuid 就能列/改/删其检查项。
2. **同步 payload 字段名不一致** —— 客户端本地实体用 camelCase
   （`LocalTaskTag.taskUuid` / `LocalChecklistItem.taskUuid`），
   服务端只认 snake_case，于是 taskTag / checklistItems 的 op 一律被判
   "task_uuid required" 而 rejected，检查项与标签关联根本同步不上去。

第 2 类里的纯函数部分不依赖数据库，可以直接跑；带数据库的部分在 MySQL/Redis
不可用时按仓库既有约定 skip。
"""

from __future__ import annotations

import asyncio
import secrets

import pytest

from src.apps.user.api.v1.sync import _apply_op, _payload_str
from src.core.exceptions import ValidationException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, *, email=None):
    from tests.conftest import fetch_captcha_for_register

    captcha_id, captcha_solution = fetch_captcha_for_register(client)
    payload = {
        "nickname": f"chk-tester-{secrets.token_hex(3)}",
        "provider": "password",
        "payload": {
            "identifier": email or f"chk-{secrets.token_hex(6)}@example.com",
            "password": "Secret123",
        },
        "captchaId": captcha_id,
        "captchaSolution": captcha_solution,
    }
    resp = client.post("/api/v1/users", json=payload)
    assert resp.status_code == 200, f"register failed: {resp.status_code} {resp.text}"
    return resp.json()["data"]


def _create_task(client, token, **overrides):
    body = {
        "title": overrides.pop("title", "checklist owner task"),
        "urgencyLevel": overrides.pop("urgencyLevel", 1),
        "importanceLevel": overrides.pop("importanceLevel", 1),
    }
    body.update(overrides)
    resp = client.post("/api/v1/tasks", json=body, headers=_bearer(token))
    assert resp.status_code in (200, 201), f"create failed: {resp.status_code} {resp.text}"
    return resp.json()["data"]


class _StubResult:
    """只实现 apply_op 用到的那一个方法。"""

    def scalar_one_or_none(self):
        return None


class _StubDb:
    """最小 DB 替身：查不到任何记录，用来观察 op 走到了哪一步的校验。"""

    async def execute(self, *args, **kwargs):
        return _StubResult()

    async def flush(self):
        return None


# ---------------------------------------------------------------------------
# 同步 payload 字段名契约（不依赖数据库）
# ---------------------------------------------------------------------------


def test_payload_str_prefers_camel_case():
    assert _payload_str({"taskUuid": "a", "task_uuid": "b"}, "taskUuid", "task_uuid") == "a"


def test_payload_str_accepts_snake_case_fallback():
    assert _payload_str({"task_uuid": "b"}, "taskUuid", "task_uuid") == "b"


def test_payload_str_empty_when_absent():
    assert _payload_str({}, "taskUuid", "task_uuid") == ""
    assert _payload_str({"taskUuid": ""}, "taskUuid", "task_uuid") == ""


@pytest.mark.parametrize(
    "payload",
    [
        {"taskUuid": "task-1", "tagUuid": "tag-1"},
        {"task_uuid": "task-1", "tag_uuid": "tag-1"},
    ],
)
def test_task_tag_op_accepts_both_payload_spellings(payload):
    """camelCase（客户端现状）与 snake_case（旧客户端）都必须通过字段校验，
    继续走到归属校验，而不是被当成缺字段拒绝。"""
    with pytest.raises(ValidationException) as exc:
        asyncio.run(
            _apply_op(
                _StubDb(), None, "user-1", "taskTag", "upsert", payload,
            )
        )
    assert "task_uuid" not in str(exc.value), "payload 被误判为缺少字段"
    assert "任务不存在" in str(exc.value)


def test_checklist_op_accepts_camel_case_task_uuid():
    """检查项 op 的 taskUuid 也要走 camelCase。"""
    with pytest.raises(ValidationException) as exc:
        asyncio.run(
            _apply_op(
                _StubDb(), None, "user-1", "checklistItems", "upsert",
                {"uuid": "item-1", "taskUuid": "task-1", "title": "x"},
            )
        )
    assert "task_uuid" not in str(exc.value), "camelCase payload 被误判为缺少字段"


# ---------------------------------------------------------------------------
# 检查项归属校验（需要数据库）
# ---------------------------------------------------------------------------


def test_list_checklist_rejects_other_user(client, skip_if_unavailable):
    """别的用户的 task uuid 不能列出检查项。"""
    if skip_if_unavailable():
        pytest.skip("backend not available")

    owner = _register(client)
    intruder = _register(client)

    task = _create_task(client, owner["access_token"])
    created = client.post(
        f"/api/v1/tasks/{task['uuid']}/checklist",
        json={"title": "private step"},
        headers=_bearer(owner["access_token"]),
    )
    assert created.status_code in (200, 201), created.text

    resp = client.get(
        f"/api/v1/tasks/{task['uuid']}/checklist",
        headers=_bearer(intruder["access_token"]),
    )
    assert resp.status_code in (403, 404), f"越权读取未被拦截: {resp.status_code} {resp.text}"


def test_update_checklist_rejects_other_user(client, skip_if_unavailable):
    """别的用户不能改我的检查项。"""
    if skip_if_unavailable():
        pytest.skip("backend not available")

    owner = _register(client)
    intruder = _register(client)

    task = _create_task(client, owner["access_token"])
    created = client.post(
        f"/api/v1/tasks/{task['uuid']}/checklist",
        json={"title": "private step"},
        headers=_bearer(owner["access_token"]),
    )
    assert created.status_code in (200, 201), created.text
    item_uuid = created.json()["data"]["uuid"]

    resp = client.patch(
        f"/api/v1/tasks/{task['uuid']}/checklist/{item_uuid}",
        json={"completed": True},
        headers=_bearer(intruder["access_token"]),
    )
    assert resp.status_code in (403, 404), f"越权修改未被拦截: {resp.status_code} {resp.text}"


def test_delete_checklist_rejects_other_user(client, skip_if_unavailable):
    """别的用户不能删我的检查项。"""
    if skip_if_unavailable():
        pytest.skip("backend not available")

    owner = _register(client)
    intruder = _register(client)

    task = _create_task(client, owner["access_token"])
    created = client.post(
        f"/api/v1/tasks/{task['uuid']}/checklist",
        json={"title": "private step"},
        headers=_bearer(owner["access_token"]),
    )
    assert created.status_code in (200, 201), created.text
    item_uuid = created.json()["data"]["uuid"]

    resp = client.delete(
        f"/api/v1/tasks/{task['uuid']}/checklist/{item_uuid}",
        headers=_bearer(intruder["access_token"]),
    )
    assert resp.status_code in (403, 404), f"越权删除未被拦截: {resp.status_code} {resp.text}"
