from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.profile import Profile
from app.models.org import Org
from app.routers.auth_utils import verify_public_access

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_public_access),
):
    try:
        profile_count = await db.execute(select(func.count(Profile.id)).where(Profile.is_active == True))
        org_count = await db.execute(select(func.count(Org.id)))
        country_count = await db.execute(
            select(func.count(func.distinct(Profile.country_of_residence)))
            .where(Profile.country_of_residence.isnot(None))
        )
        source_count = await db.execute(
            select(Profile.source, func.count(Profile.id))
            .group_by(Profile.source)
        )

        return {
            "total_profiles": profile_count.scalar() or 0,
            "total_orgs": org_count.scalar() or 0,
            "total_countries": country_count.scalar() or 0,
            "sources": {row[0]: row[1] for row in source_count.all()},
            "status": "healthy",
        }
    except Exception:
        return {
            "total_profiles": 0,
            "total_orgs": 0,
            "total_countries": 0,
            "sources": {},
            "status": "degraded",
        }
