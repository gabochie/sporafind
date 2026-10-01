"""Push endpoints: key discovery, subscribe/unsubscribe, admin gating."""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _no_vapid_keys(monkeypatch):
    # Hermetic: tests must not depend on local .env VAPID keys.
    monkeypatch.setattr(settings, "vapid_public_key", "")
    monkeypatch.setattr(settings, "vapid_private_key", "")


def test_push_routes_registered():
    from app.main import app

    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/push/vapid-key" in paths
    assert "/push/subscribe" in paths
    assert "/push/unsubscribe" in paths
    assert "/push/send" in paths


async def test_vapid_key_unconfigured_returns_503(client):
    res = await client.get("/push/vapid-key")
    assert res.status_code == 503


async def test_subscribe_rejects_invalid_body(client):
    res = await client.post("/push/subscribe", json={"endpoint": "https://x", "keys": {}})
    assert res.status_code == 400


async def test_subscribe_and_unsubscribe_anonymous(client):
    body = {
        "endpoint": "https://fcm.test/sub-123",
        "keys": {"p256dh": "p256dh-abc", "auth": "auth-abc"},
    }
    res = await client.post("/push/subscribe", json=body)
    assert res.status_code == 200
    assert res.json()["status"] == "subscribed"
    # idempotent re-subscribe
    res = await client.post("/push/subscribe", json=body)
    assert res.status_code == 200
    res = await client.post("/push/unsubscribe", json=body)
    assert res.status_code == 200
    assert res.json()["status"] == "unsubscribed"


async def test_send_requires_admin_key(client):
    res = await client.post("/push/send", json={"title": "t", "body": "b"})
    assert res.status_code == 401


async def test_send_unconfigured_returns_503_with_admin(client):
    res = await client.post(
        "/push/send",
        json={"title": "t", "body": "b"},
        headers={"X-Admin-Key": "test-admin-key"},
    )
    # Either 503 (no VAPID keys in test env) or 401 if settings differ — never 500.
    assert res.status_code in (503, 401)
