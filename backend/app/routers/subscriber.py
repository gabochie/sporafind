from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.user import User
from app.models.profile import Profile
from app.models.org import Org
from app.models.saved_list import SavedList
from app.models.export_session import ExportSession
from app.models.activity_log import ActivityLog
from app.auth import verify_token
from app.schemas.profile import ProfileResponse
from app.schemas.org import OrgResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/workspace", tags=["workspace"])


async def require_subscriber(user: User = Depends(verify_token)) -> User:
    if user.role not in ("subscriber", "admin"):
        raise HTTPException(status_code=403, detail="Subscriber access required")
    return user


class ListCreate(BaseModel):
    name: str
    description: str | None = None
    item_ids: list[str] = []


class ListUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    item_ids: list[str] | None = None


class ExportRequest(BaseModel):
    export_type: str
    filters: dict = {}


PLAN_EXPORT_LIMITS = {
    "free": 100,
    "pro": 1000,
    "enterprise": 100000,
}


def _plan_limit(user: User) -> int:
    # Active Stripe subscription overrides stored tier
    if (user.subscription_status or "").lower() in ("active", "trialing"):
        return PLAN_EXPORT_LIMITS["pro"]
    return PLAN_EXPORT_LIMITS.get((user.plan_tier or "free").lower(), 100)


async def log_activity(db: AsyncSession, user_id: str, action: str, detail: str):
    db.add(ActivityLog(user_id=user_id, action=action, detail=detail))
    await db.commit()


@router.get("/me")
@limiter.limit("30/minute")
async def get_workspace_profile(
    request: Request,
    user: User = Depends(require_subscriber),
):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "plan_tier": user.plan_tier,
        "created_at": str(user.created_at),
        "last_login": str(user.last_login) if user.last_login else None,
    }


@router.get("/search")
@limiter.limit("60/minute")
async def workspace_search(
    request: Request,
    q: str = Query("", max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    segment: str | None = None,
    country: str | None = None,
    origin: str | None = None,
    sector: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscriber),
):
    profiles_query = select(Profile).where(Profile.is_active == True)
    profiles_count = select(func.count(Profile.id)).where(Profile.is_active == True)
    orgs_query = select(Org)
    orgs_count = select(func.count(Org.id))

    if q:
        like = f"%{q}%"
        pfilters = [
            Profile.name.ilike(like),
            Profile.role.ilike(like),
            Profile.company_name.ilike(like),
            Profile.locality.ilike(like),
            Profile.country.ilike(like),
            Profile.nationality.ilike(like),
            Profile.occupation.ilike(like),
        ]
        profiles_query = profiles_query.where(or_(*pfilters))
        profiles_count = profiles_count.where(or_(*pfilters))
        ofilters = [
            Org.name.ilike(like),
            Org.locality.ilike(like),
            Org.country.ilike(like),
            Org.registered_address.ilike(like),
        ]
        orgs_query = orgs_query.where(or_(*ofilters))
        orgs_count = orgs_count.where(or_(*ofilters))

    if segment:
        profiles_query = profiles_query.where(Profile.segment == segment)
        profiles_count = profiles_count.where(Profile.segment == segment)
    if country:
        profiles_query = profiles_query.where(Profile.country_of_residence == country)
        profiles_count = profiles_count.where(Profile.country_of_residence == country)
        orgs_query = orgs_query.where(Org.country == country)
        orgs_count = orgs_count.where(Org.country == country)
    if origin:
        profiles_query = profiles_query.where(Profile.origin == origin)
        profiles_count = profiles_count.where(Profile.origin == origin)
        orgs_query = orgs_query.where(Org.origin == origin)
        orgs_count = orgs_count.where(Org.origin == origin)

    total_profiles = (await db.execute(profiles_count)).scalar() or 0
    total_orgs = (await db.execute(orgs_count)).scalar() or 0

    offset = (page - 1) * page_size
    profiles = (await db.execute(profiles_query.offset(offset).limit(page_size).order_by(Profile.name))).scalars().all()
    orgs = (await db.execute(orgs_query.offset(offset).limit(page_size).order_by(Org.name))).scalars().all()

    await log_activity(db, user.id, "search", json.dumps({"q": q, "segment": segment, "country": country}))

    return {
        "profiles": [ProfileResponse.model_validate(p) for p in profiles],
        "orgs": [OrgResponse.model_validate(o) for o in orgs],
        "total_profiles": total_profiles,
        "total_orgs": total_orgs,
        "page": page,
        "page_size": page_size,
    }


@router.get("/lists")
@limiter.limit("30/minute")
async def list_lists(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscriber),
):
    rows = await db.execute(
        select(SavedList).where(SavedList.user_id == user.id).order_by(SavedList.updated_at.desc())
    )
    items = rows.scalars().all()
    return {
        "lists": [
            {
                "id": lst.id,
                "name": lst.name,
                "description": lst.description,
                "item_ids": json.loads(lst.item_ids) if lst.item_ids else [],
                "item_type": lst.item_type,
                "item_count": len(json.loads(lst.item_ids)) if lst.item_ids else 0,
                "created_at": str(lst.created_at),
                "updated_at": str(lst.updated_at),
            }
            for lst in items
        ]
    }


@router.post("/lists")
@limiter.limit("20/minute")
async def create_list(
    request: Request,
    body: ListCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscriber),
):
    lst = SavedList(
        user_id=user.id,
        name=body.name,
        description=body.description,
        item_ids=json.dumps(body.item_ids),
    )
    db.add(lst)
    await db.commit()
    await db.refresh(lst)
    await log_activity(db, user.id, "create_list", json.dumps({"list_id": lst.id, "name": lst.name}))
    return {
        "id": lst.id,
        "name": lst.name,
        "description": lst.description,
        "item_ids": body.item_ids,
        "item_count": len(body.item_ids),
        "created_at": str(lst.created_at),
    }


@router.get("/lists/{list_id}")
@limiter.limit("30/minute")
async def get_list(
    request: Request,
    list_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscriber),
):
    row = await db.execute(select(SavedList).where(SavedList.id == list_id, SavedList.user_id == user.id))
    lst = row.scalar_one_or_none()
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")
    return {
        "id": lst.id,
        "name": lst.name,
        "description": lst.description,
        "item_ids": json.loads(lst.item_ids) if lst.item_ids else [],
        "item_type": lst.item_type,
        "item_count": len(json.loads(lst.item_ids)) if lst.item_ids else 0,
        "created_at": str(lst.created_at),
        "updated_at": str(lst.updated_at),
    }


@router.patch("/lists/{list_id}")
@limiter.limit("20/minute")
async def update_list(
    request: Request,
    list_id: str,
    body: ListUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscriber),
):
    row = await db.execute(select(SavedList).where(SavedList.id == list_id, SavedList.user_id == user.id))
    lst = row.scalar_one_or_none()
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")
    if body.name is not None:
        lst.name = body.name
    if body.description is not None:
        lst.description = body.description
    if body.item_ids is not None:
        lst.item_ids = json.dumps(body.item_ids)
    await db.commit()
    await log_activity(db, user.id, "update_list", json.dumps({"list_id": lst.id, "name": lst.name}))
    return {"status": "updated"}


@router.delete("/lists/{list_id}")
@limiter.limit("20/minute")
async def delete_list(
    request: Request,
    list_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscriber),
):
    row = await db.execute(select(SavedList).where(SavedList.id == list_id, SavedList.user_id == user.id))
    lst = row.scalar_one_or_none()
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")
    await db.delete(lst)
    await db.commit()
    return {"status": "deleted"}


@router.get("/exports")
@limiter.limit("30/minute")
async def list_exports(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscriber),
):
    rows = await db.execute(
        select(ExportSession).where(ExportSession.user_id == user.id).order_by(ExportSession.created_at.desc()).limit(50)
    )
    items = rows.scalars().all()
    return {
        "exports": [
            {
                "id": exp.id,
                "export_type": exp.export_type,
                "item_count": exp.item_count,
                "status": exp.status,
                "created_at": str(exp.created_at),
                "completed_at": str(exp.completed_at) if exp.completed_at else None,
            }
            for exp in items
        ]
    }


@router.post("/exports")
@limiter.limit("10/minute")
async def create_export(
    request: Request,
    body: ExportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscriber),
):
    limit = _plan_limit(user)
    filters = body.filters or {}
    q = str(filters.get("q", ""))[:200]
    segment = filters.get("segment")
    country = filters.get("country")
    origin = filters.get("origin")

    query = select(Profile).where(Profile.is_active == True)
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(
                Profile.name.ilike(like),
                Profile.role.ilike(like),
                Profile.company_name.ilike(like),
                Profile.locality.ilike(like),
                Profile.country.ilike(like),
                Profile.nationality.ilike(like),
                Profile.occupation.ilike(like),
            )
        )
    if segment:
        query = query.where(Profile.segment == segment)
    if country:
        query = query.where(Profile.country_of_residence == country)
    if origin:
        query = query.where(Profile.origin == origin)

    rows = (await db.execute(query.order_by(Profile.name).limit(limit + 1))).scalars().all()
    truncated = len(rows) > limit
    rows = rows[:limit]

    exp = ExportSession(
        user_id=user.id,
        export_type=body.export_type,
        filters=json.dumps({**filters, "limit": limit}),
        item_count=len(rows),
        status="completed",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(exp)
    user.export_count = (user.export_count or 0) + 1
    await db.commit()
    await db.refresh(exp)
    await log_activity(db, user.id, "export", json.dumps({"export_id": exp.id, "type": body.export_type, "count": len(rows)}))
    return {
        "id": exp.id,
        "export_type": exp.export_type,
        "item_count": len(rows),
        "limit": limit,
        "truncated": truncated,
        "status": exp.status,
        "created_at": str(exp.created_at),
        "download_url": f"/workspace/exports/{exp.id}/download",
    }


@router.get("/exports/{export_id}/download")
@limiter.limit("10/minute")
async def download_export(
    request: Request,
    export_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscriber),
):
    import csv
    import io
    from fastapi.responses import StreamingResponse

    row = await db.execute(
        select(ExportSession).where(ExportSession.id == export_id, ExportSession.user_id == user.id)
    )
    exp = row.scalar_one_or_none()
    if not exp:
        raise HTTPException(status_code=404, detail="Export not found")
    if exp.status != "completed":
        raise HTTPException(status_code=409, detail="Export not ready")

    filters = json.loads(exp.filters or "{}")
    limit = int(filters.get("limit", _plan_limit(user)))
    q = str(filters.get("q", ""))[:200]

    query = select(Profile).where(Profile.is_active == True)
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(
                Profile.name.ilike(like),
                Profile.role.ilike(like),
                Profile.company_name.ilike(like),
                Profile.locality.ilike(like),
                Profile.country.ilike(like),
                Profile.nationality.ilike(like),
                Profile.occupation.ilike(like),
            )
        )
    if filters.get("segment"):
        query = query.where(Profile.segment == filters["segment"])
    if filters.get("country"):
        query = query.where(Profile.country_of_residence == filters["country"])
    if filters.get("origin"):
        query = query.where(Profile.origin == filters["origin"])

    profiles = (await db.execute(query.order_by(Profile.name).limit(limit))).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "role", "company_name", "country_of_residence", "locality", "segment", "origin", "source"])
    for p in profiles:
        writer.writerow([p.name, p.role or "", p.company_name or "", p.country_of_residence or "", p.locality or "", p.segment or "", p.origin or "", p.source or ""])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sporafind-export-{exp.id}.csv"},
    )


@router.get("/activity")
@limiter.limit("30/minute")
async def list_activity(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscriber),
):
    rows = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.user_id == user.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )
    items = rows.scalars().all()
    return {
        "activity": [
            {
                "id": a.id,
                "action": a.action,
                "detail": a.detail,
                "created_at": str(a.created_at),
            }
            for a in items
        ]
    }
