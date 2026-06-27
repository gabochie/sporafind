from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.profile import Profile
from app.schemas.profile import ProfileResponse, ProfileList
from app.routers.auth_utils import verify_public_access

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=ProfileList)
@limiter.limit("30/minute")
async def list_profiles(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    segment: str | None = None,
    country: str | None = None,
    origin: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_public_access),
):
    query = select(Profile).where(Profile.is_active == True)
    count_query = select(func.count(Profile.id)).where(Profile.is_active == True)

    if segment:
        query = query.where(Profile.segment == segment)
        count_query = count_query.where(Profile.segment == segment)
    if country:
        query = query.where(Profile.country == country)
        count_query = count_query.where(Profile.country == country)
    if origin:
        query = query.where(Profile.origin == origin)
        count_query = count_query.where(Profile.origin == origin)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Profile.name)
    result = await db.execute(query)
    items = result.scalars().all()

    return ProfileList(
        items=[ProfileResponse.model_validate({**p.__dict__, "is_claimed": p.claimed_by is not None}) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{profile_id}", response_model=ProfileResponse)
@limiter.limit("30/minute")
async def get_profile(
    request: Request,
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_public_access),
):
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileResponse.model_validate({**profile.__dict__, "is_claimed": profile.claimed_by is not None})
