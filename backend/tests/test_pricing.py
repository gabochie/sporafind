from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.pricing import PricingPlan


@pytest.mark.asyncio
async def test_get_pricing_empty(client):
    resp = await client.get("/pricing")
    assert resp.status_code == 200
    body = resp.json()
    assert body["plans"] == []


@pytest.mark.asyncio
async def test_get_pricing_with_plans(client, db_session):
    plans = [
        PricingPlan(
            id=str(uuid4()), name="free", display_name="Free",
            price_monthly=0, price_yearly=0,
            description="Free plan", features=["Basic search"],
            highlighted=False, sort_order=1,
        ),
        PricingPlan(
            id=str(uuid4()), name="pro", display_name="Pro",
            price_monthly=29, price_yearly=290,
            description="Pro plan", features=["Advanced search", "Export"],
            highlighted=True, sort_order=2,
        ),
    ]
    for p in plans:
        db_session.add(p)
    await db_session.commit()

    resp = await client.get("/pricing")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["plans"]) == 2
    assert body["plans"][0]["name"] == "free"
    assert body["plans"][1]["name"] == "pro"
    assert body["plans"][1]["highlighted"] is True
    assert body["plans"][0]["sort_order"] < body["plans"][1]["sort_order"]


@pytest.mark.asyncio
async def test_pricing_without_auth(client, db_session):
    plan = PricingPlan(
        id=str(uuid4()), name="basic", display_name="Basic",
        price_monthly=10, price_yearly=100,
        description="Basic", features=["Search"],
        highlighted=False, sort_order=1,
    )
    db_session.add(plan)
    await db_session.commit()

    resp = await client.get("/pricing", headers={"X-API-Key": "invalid"})
    assert resp.status_code == 200
