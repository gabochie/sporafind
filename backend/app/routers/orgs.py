from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.org import Org
from app.schemas.org import OrgResponse, OrgList

router = APIRouter(prefix="/orgs", tags=["orgs"])


@router.get("", response_model=OrgList)
async def list_orgs(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    org_type: str | None = None,
    country: str | None = None,
    origin: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Org)
    count_query = select(func.count(Org.id))

    if org_type:
        query = query.where(Org.org_type == org_type)
        count_query = count_query.where(Org.org_type == org_type)
    if country:
        query = query.where(Org.country == country)
        count_query = count_query.where(Org.country == country)
    if origin:
        query = query.where(Org.origin == origin)
        count_query = count_query.where(Org.origin == origin)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Org.name)
    result = await db.execute(query)
    items = result.scalars().all()

    return OrgList(
        items=[OrgResponse.model_validate(o) for o in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{org_id}", response_model=OrgResponse)
async def get_org(org_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Org).where(Org.id == org_id))
    org = result.scalar_one_or_none()
    return OrgResponse.model_validate(org)
