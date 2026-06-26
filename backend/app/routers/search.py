from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database import get_db
from app.models.profile import Profile
from app.schemas.profile import ProfileResponse, ProfileList

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=ProfileList)
async def search_profiles(
    q: str = Query("", min_length=0, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    segment: str | None = None,
    country: str | None = None,
    origin: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Profile).where(Profile.is_active == True)
    count_query = select(func.count(Profile.id)).where(Profile.is_active == True)

    if q:
        like = f"%{q}%"
        filters = [
            Profile.name.ilike(like),
            Profile.role.ilike(like),
            Profile.company_name.ilike(like),
            Profile.locality.ilike(like),
            Profile.country.ilike(like),
            Profile.nationality.ilike(like),
            Profile.occupation.ilike(like),
        ]
        query = query.where(or_(*filters))
        count_query = count_query.where(or_(*filters))

    if segment:
        query = query.where(Profile.segment == segment)
        count_query = count_query.where(Profile.segment == segment)
    if country:
        query = query.where(Profile.country_of_residence == country)
        count_query = count_query.where(Profile.country_of_residence == country)
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
        items=[ProfileResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )
