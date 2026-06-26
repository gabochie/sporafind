from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pricing import PricingPlan
from app.routers.auth_utils import verify_public_access

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("")
async def get_pricing(
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
