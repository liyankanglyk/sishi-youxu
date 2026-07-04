"""User-Tasks endpoint tests.

Covers the user-facing task CRUD endpoints (`/api/v1/tasks/...`).
These endpoints are what the web app now uses to load and display tasks,
so any regression here (route order, missing fields, wrong envelope, etc.)
breaks the home view.

Key invariants:
1. Static paths (`/batch`, `/restore`) are matched BEFORE `/{uuid}` (route order).
2. List endpoint returns the standard `{success, data}` envelope.
3. Tags appear in the list as a UUID array (frontend expects this).
4. CRUD round-trip preserves the user-issued UUID.
"""

from __future__ import annotations

import secrets
from typing import Any

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_ok_envelope(body, *, with_data=True):
    assert body.get("success") is True, f"expected success=True, got {body!r}"
    if with_data:
        assert "data" in body


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, *, email=None):
    from tests.conftest import fetch_captcha_for_register

    captcha_id, captcha_solution = fetch_captcha_for_register(client)
    payload = {
        "nickname": f"task-tester-{secrets.token_hex(3)}",
        "provider": "password",
        "payload": {
            "identifier": email or f"task-{secrets.token_hex(6)}@example.com",
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
        "title": overrides.pop("title", "test task"),
        "urgencyLevel": overrides.pop("urgencyLevel", 1),
        "importanceLevel": overrides.pop("importanceLevel", 1),
    }
    body.update(overrides)
    resp = client.post("/api/v1/tasks", json=body, headers=_bearer(token))
    # Backend declares status_code=201 on POST /tasks
    assert resp.status_code in (200, 201), f"create failed: {resp.status_code} {resp.text}"
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Route order: /batch must not be swallowed by /{uuid}
# ---------------------------------------------------------------------------


def test_batch_route_is_not_shadowed_by_uuid(client, skip_if_unavailable):
    """Regression: `POST /api/v1/tasks/batch` must hit the batch handler, not be
    interpreted as a uuid=batch GET/PATCH/DELETE."""
    if skip_if_unavailable():
        pytest.skip("backend not available")

    data = _register(client)
    headers = _bearer(data["access_token"])

    # Create one task so /batch has at least one valid UUID (backend requires min_length=1)
    created = _create_task(client, data["access_token"], title="for-batch")

    resp = client.post(
        "/api/v1/tasks/batch",
        json={
            "idempotencyKey": secrets.token_hex(8),
            "action": "complete",
            "taskUuids": [created["uuid"]],
        },
        headers=headers,
    )
    # Must NOT be 404 (which would mean /{uuid} ate the request)
    assert resp.status_code == 200, f"/batch returned {resp.status_code}: {resp.text}"
    _assert_ok_envelope(resp.json())


# ---------------------------------------------------------------------------
# List endpoint
# ---------------------------------------------------------------------------


def test_list_tasks_returns_envelope_and_meta(client, skip_if_unavailable):
    if skip_if_unavailable():
        pytest.skip("backend not available")

    data = _register(client)
    headers = _bearer(data["access_token"])
    _create_task(client, data["access_token"], title="alpha")
    _create_task(client, data["access_token"], title="beta")

    resp = client.get("/api/v1/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    _assert_ok_envelope(body)
    payload = body["data"]
    assert "items" in payload and isinstance(payload["items"], list)
    assert "meta" in payload
    assert payload["meta"]["total"] == 2


def test_list_tasks_tags_are_uuid_strings(client, skip_if_unavailable):
    """The list endpoint returns tags as a UUID array; the frontend builds the
    full tag list separately and joins client-side."""
    if skip_if_unavailable():
        pytest.skip("backend not available")

    data = _register(client)
    headers = _bearer(data["access_token"])
    _create_task(client, data["access_token"], title="tagged")

    resp = client.get("/api/v1/tasks", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert items, "expected at least one task"
    for t in items:
        assert "tags" in t
        assert isinstance(t["tags"], list)
        for tag_id in t["tags"]:
            assert isinstance(tag_id, str)


def test_list_tasks_filters_completed(client, skip_if_unavailable):
    if skip_if_unavailable():
        pytest.skip("backend not available")

    data = _register(client)
    headers = _bearer(data["access_token"])
    _create_task(client, data["access_token"], title="open")
    created = _create_task(client, data["access_token"], title="closed")
    # Mark the second as completed
    client.patch(
        f"/api/v1/tasks/{created['uuid']}",
        json={"completed": True, "completedAt": "2025-01-01T00:00:00"},
        headers=headers,
    )

    resp = client.get("/api/v1/tasks?completed=false", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    titles = {t["title"] for t in items}
    assert "open" in titles
    assert "closed" not in titles


# ---------------------------------------------------------------------------
# CRUD round-trip
# ---------------------------------------------------------------------------


def test_task_create_get_update_delete_roundtrip(client, skip_if_unavailable):
    if skip_if_unavailable():
        pytest.skip("backend not available")

    data = _register(client)
    headers = _bearer(data["access_token"])

    created = _create_task(
        client,
        data["access_token"],
        title="roundtrip",
        urgencyLevel=2,
        importanceLevel=-1,
    )
    assert created["title"] == "roundtrip"
    assert created["urgencyLevel"] == 2
    assert created["importanceLevel"] == -1

    # Get
    resp = client.get(f"/api/v1/tasks/{created['uuid']}", headers=headers)
    assert resp.status_code == 200
    fetched = resp.json()["data"]
    assert fetched["uuid"] == created["uuid"]

    # Update
    resp = client.patch(
        f"/api/v1/tasks/{created['uuid']}",
        json={"title": "renamed"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "renamed"

    # Delete
    resp = client.delete(f"/api/v1/tasks/{created['uuid']}", headers=headers)
    assert resp.status_code == 200

    # List should now be empty
    resp = client.get("/api/v1/tasks", headers=headers)
    assert resp.json()["data"]["meta"]["total"] == 0


def test_user_isolation_in_list(client, skip_if_unavailable):
    """User A's tasks must not appear in user B's list."""
    if skip_if_unavailable():
        pytest.skip("backend not available")

    a = _register(client)
    b = _register(client)
    _create_task(client, a["access_token"], title="A-only")

    resp = client.get("/api/v1/tasks", headers=_bearer(b["access_token"]))
    assert resp.status_code == 200
    assert resp.json()["data"]["meta"]["total"] == 0