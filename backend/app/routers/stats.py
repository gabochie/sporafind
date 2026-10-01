from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.profile import Profile
from app.models.org import Org
from app.models.blog import BlogPost
from app.models.user import User
from app.models.pricing import PricingPlan

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
@limiter.limit("30/minute")
async def get_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
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


@router.get("/public-metrics")
@limiter.limit("30/minute")
async def get_public_metrics(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        profile_count = await db.execute(select(func.count(Profile.id)).where(Profile.is_active == True))
        org_count = await db.execute(select(func.count(Org.id)))
        user_count = await db.execute(select(func.count(User.id)))
        country_count = await db.execute(
            select(func.count(func.distinct(Profile.country_of_residence)))
            .where(Profile.country_of_residence.isnot(None))
        )
        segment_counts = await db.execute(
            select(Profile.segment, func.count(Profile.id))
            .where(Profile.segment.isnot(None))
            .group_by(Profile.segment)
        )
        blog_count = await db.execute(
            select(func.count(BlogPost.id)).where(BlogPost.status == "published")
        )
        blog_views = await db.execute(
            select(func.coalesce(func.sum(BlogPost.views), 0)).where(BlogPost.status == "published")
        )
        tier_count = await db.execute(select(func.count(PricingPlan.id)))

        return {
            "total_profiles": profile_count.scalar() or 0,
            "total_orgs": org_count.scalar() or 0,
            "total_users": user_count.scalar() or 0,
            "total_countries": country_count.scalar() or 0,
            "segments": {row[0]: row[1] for row in segment_counts.all()},
            "blog_posts": blog_count.scalar() or 0,
            "blog_views": blog_views.scalar() or 0,
            "pricing_tiers": tier_count.scalar() or 0,
            "deployment": "Vercel",
            "tests": 35,
            "ci_cd": True,
            "status": "healthy",
        }
    except Exception:
        return {
            "total_profiles": 0,
            "total_orgs": 0,
            "total_users": 0,
            "total_countries": 0,
            "segments": {},
            "blog_posts": 0,
            "blog_views": 0,
            "pricing_tiers": 0,
            "deployment": "Vercel",
            "tests": 35,
            "ci_cd": True,
            "status": "degraded",
        }
