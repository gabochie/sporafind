from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth import verify_token
from app.config import settings
from app.database import get_db
from app.logger import logger
from app.models.user import User
from app.routers.subscriber import require_subscriber

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/billing", tags=["billing"])

PRICE_TO_PLAN: dict[str, str] = {}


def _init_stripe():
    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key
        PRICE_TO_PLAN.clear()
        if settings.stripe_price_pro_monthly:
            PRICE_TO_PLAN[settings.stripe_price_pro_monthly] = "pro"
        if settings.stripe_price_pro_yearly:
            PRICE_TO_PLAN[settings.stripe_price_pro_yearly] = "pro"
        if settings.stripe_price_enterprise_monthly:
            PRICE_TO_PLAN[settings.stripe_price_enterprise_monthly] = "enterprise"
        if settings.stripe_price_enterprise_yearly:
            PRICE_TO_PLAN[settings.stripe_price_enterprise_yearly] = "enterprise"
        return True
    return False


class CheckoutRequest(BaseModel):
    price_id: str
    success_url: str = "https://www.sporafind.com/workspace/app#account"
    cancel_url: str = "https://www.sporafind.com/workspace/app#account"


@router.post("/create-checkout-session")
@limiter.limit("10/minute")
async def create_checkout_session(
    body: CheckoutRequest,
    request: Request,
    user: User = Depends(require_subscriber),
    db: AsyncSession = Depends(get_db),
):
    if not _init_stripe():
        raise HTTPException(status_code=503, detail="Billing not configured")

    try:
        params: dict = {
            "mode": "subscription",
            "line_items": [{"price": body.price_id, "quantity": 1}],
            "success_url": body.success_url,
            "cancel_url": body.cancel_url,
            "subscription_data": {"trial_period_days": 14},
        }

        if user.stripe_customer_id:
            params["customer"] = user.stripe_customer_id
        else:
            params["customer_email"] = user.email
            params["customer_creation"] = "always"

        session = stripe.checkout.Session.create(**params)

        if not user.stripe_customer_id and session.customer:
            user.stripe_customer_id = session.customer
            await db.commit()

        return {"url": session.url}
    except stripe.StripeError as e:
        logger.error("Stripe checkout error", exc_info=e)
        raise HTTPException(status_code=502, detail=str(e.user_message or e))


@router.post("/portal")
@limiter.limit("10/minute")
async def billing_portal(
    request: Request,
    user: User = Depends(require_subscriber),
):
    if not _init_stripe():
        raise HTTPException(status_code=503, detail="Billing not configured")
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No customer record found")

    try:
        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url="https://www.sporafind.com/workspace/app#account",
        )
        return {"url": session.url}
    except stripe.StripeError as e:
        logger.error("Stripe portal error", exc_info=e)
        raise HTTPException(status_code=502, detail=str(e.user_message or e))


@router.get("/status")
@limiter.limit("30/minute")
async def billing_status(
    request: Request,
    user: User = Depends(require_subscriber),
):
    return {
        "plan_tier": user.plan_tier,
        "subscription_status": user.subscription_status,
        "period_end": user.subscription_period_end.isoformat() if user.subscription_period_end else None,
        "stripe_customer_id": user.stripe_customer_id,
    }


@router.post("/webhook")
@limiter.limit("50/minute")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not _init_stripe():
        raise HTTPException(status_code=503, detail="Billing not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header or not settings.stripe_webhook_secret:
        raise HTTPException(status_code=400, detail="Missing signature or webhook secret")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError) as e:
        logger.warning("Stripe webhook signature invalid", exc_info=e)
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})

    logger.info("Stripe webhook: %s", event_type, extra={"event_type": event_type})

    try:
        if event_type == "checkout.session.completed":
            await _handle_checkout_completed(data, db)
        elif event_type == "customer.subscription.updated":
            await _handle_subscription_updated(data, db)
        elif event_type == "customer.subscription.deleted":
            await _handle_subscription_deleted(data, db)
        elif event_type == "invoice.payment_failed":
            await _handle_payment_failed(data, db)
    except Exception as e:
        logger.error("Webhook handler error", exc_info=e)

    return {"status": "ok"}


async def _handle_checkout_completed(data: dict, db: AsyncSession):
    customer_id = data.get("customer")
    subscription_id = data.get("subscription")
    customer_email = data.get("customer_details", {}).get("email")
    line_items = data.get("line_items", {})
    price_id = None

    if not customer_id or not subscription_id:
        return

    if line_items:
        for item in line_items.get("data", []):
            price_id = item.get("price", {}).get("id")
            break

    if not price_id:
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            price_id = sub.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
        except Exception:
            return

    plan_tier = PRICE_TO_PLAN.get(price_id, "free")

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()

    if not user and customer_email:
        result = await db.execute(
            select(User).where(User.email == customer_email)
        )
        user = result.scalar_one_or_none()

    if user:
        user.stripe_customer_id = customer_id
        user.stripe_subscription_id = subscription_id
        user.plan_tier = plan_tier
        user.subscription_status = "active"
        if user.role == "user":
            user.role = "subscriber"
        await db.commit()


async def _handle_subscription_updated(data: dict, db: AsyncSession):
    sub_id = data.get("id")
    customer_id = data.get("customer")
    status = data.get("status")
    period_end = data.get("current_period_end")

    if not sub_id:
        return

    result = await db.execute(
        select(User).where(User.stripe_subscription_id == sub_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
    if not user:
        return

    user.subscription_status = status

    if period_end:
        user.subscription_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

    if status == "active":
        items = data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
            plan = PRICE_TO_PLAN.get(price_id, "free")
            user.plan_tier = plan
        if user.role == "user":
            user.role = "subscriber"

    await db.commit()


async def _handle_subscription_deleted(data: dict, db: AsyncSession):
    sub_id = data.get("id")
    if not sub_id:
        return
    result = await db.execute(
        select(User).where(User.stripe_subscription_id == sub_id)
    )
    user = result.scalar_one_or_none()
    if user:
        user.plan_tier = "free"
        user.subscription_status = "canceled"
        user.stripe_subscription_id = None
        user.subscription_period_end = None
        await db.commit()


async def _handle_payment_failed(data: dict, db: AsyncSession):
    sub_id = data.get("subscription")
    if not sub_id:
        return
    result = await db.execute(
        select(User).where(User.stripe_subscription_id == sub_id)
    )
    user = result.scalar_one_or_none()
    if user:
        user.subscription_status = "past_due"
        await db.commit()
