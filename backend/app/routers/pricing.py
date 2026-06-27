from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.pricing import PricingPlan
from app.routers.auth_utils import verify_public_access

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("")
@limiter.limit("30/minute")
async def get_pricing(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_public_access),
):
    rows = await db.execute(
        select(PricingPlan).order_by(PricingPlan.sort_order)
    )
    plans = rows.scalars().all()
    return {
        "plans": [
            {
                "id": p.id,
                "name": p.name,
                "display_name": p.display_name,
                "price_monthly": p.price_monthly,
                "price_yearly": p.price_yearly,
                "description": p.description,
                "features": p.features,
                "highlighted": p.highlighted,
                "sort_order": p.sort_order,
            }
            for p in plans
        ]
    }
