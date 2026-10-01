"""Web Push endpoints (VAPID) for PWA notifications."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.models.push_subscription import PushSubscription
from app.auth import verify_token_optional
from app.routers.auth_utils import verify_admin


limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/push", tags=["push"])


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: dict


class SendRequest(BaseModel):
    title: str = "Sporafind"
    body: str = "New update from Sporafind."
    url: str = "/"
    user_id: str | None = None


def _vapid_configured() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


@router.get("/vapid-key")
@limiter.limit("30/minute")
async def get_vapid_key(request: Request):
    if not settings.vapid_public_key:
        raise HTTPException(status_code=503, detail="Push not configured")
    return {"publicKey": settings.vapid_public_key}


@router.post("/subscribe")
@limiter.limit("20/minute")
async def subscribe(
    body: SubscribeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(verify_token_optional),
):
    keys = body.keys or {}
    if not body.endpoint or not keys.get("p256dh") or not keys.get("auth"):
        raise HTTPException(status_code=400, detail="Invalid subscription")
    existing = await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    )
    sub = existing.scalar_one_or_none()
    if sub:
        sub.user_id = user.id if user else sub.user_id
        sub.p256dh = keys["p256dh"]
        sub.auth = keys["auth"]
    else:
        sub = PushSubscription(
            user_id=user.id if user else None,
            endpoint=body.endpoint,
            p256dh=keys["p256dh"],
            auth=keys["auth"],
        )
        db.add(sub)
    await db.commit()
    return {"status": "subscribed"}


@router.post("/unsubscribe")
@limiter.limit("20/minute")
async def unsubscribe(
    body: SubscribeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    )
    sub = result.scalar_one_or_none()
    if sub:
        await db.delete(sub)
        await db.commit()
    return {"status": "unsubscribed"}


@router.post("/send")
@limiter.limit("10/minute")
async def send_push(
    body: SendRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin),
):
    if not _vapid_configured():
        raise HTTPException(status_code=503, detail="Push not configured")
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        raise HTTPException(status_code=503, detail="Push library not installed")

    query = select(PushSubscription)
    if body.user_id:
        query = query.where(PushSubscription.user_id == body.user_id)
    subs = (await db.execute(query)).scalars().all()

    import json as _json

    payload = _json.dumps({"title": body.title, "body": body.body, "url": body.url})
    sent, failed = 0, 0
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_contact or "mailto:admin@sporafind.com"},
            )
            sent += 1
        except WebPushException as e:
            failed += 1
            # Dead subscription (uninstalled/expired) — prune it.
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                await db.delete(sub)
        except Exception:
            failed += 1
    await db.commit()
    return {"sent": sent, "failed": failed, "total": len(subs)}
