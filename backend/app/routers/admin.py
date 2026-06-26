from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.profile import Profile
from app.models.org import Org

router = APIRouter(prefix="/admin", tags=["admin"])


async def verify_admin(x_admin_key: str = Header(...)):
    if x_admin_key != settings.admin_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    return True


class UpdateUserRequest(BaseModel):
    is_active: bool | None = None
    plan_tier: str | None = None


class UpdateProfileRequest(BaseModel):
    segment: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None
    origin: str | None = None


class UpdateOrgRequest(BaseModel):
    org_type: str | None = None
    tags: list[str] | None = None


@router.get("/verify")
async def admin_verify(admin: bool = Depends(verify_admin)):
    return {"status": "ok", "role": "admin"}


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    total = await db.execute(select(func.count(User.id)))
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(User).offset(offset).limit(page_size).order_by(User.created_at.desc())
    )
    users = rows.scalars().all()
    return {
        "items": [{"id": u.id, "email": u.email, "name": u.name, "is_active": u.is_active, "plan_tier": u.plan_tier, "export_count": u.export_count, "created_at": str(u.created_at), "last_login": str(u.last_login) if u.last_login else None} for u in users],
        "total": total.scalar() or 0,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.plan_tier is not None:
        user.plan_tier = body.plan_tier
    await db.commit()
    return {"status": "updated", "user_id": user_id}


@router.get("/analytics")
async def admin_analytics(
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    profile_count = await db.execute(select(func.count(Profile.id)))
    active_profiles = await db.execute(select(func.count(Profile.id)).where(Profile.is_active == True))
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
    origin_counts = await db.execute(
        select(Profile.origin, func.count(Profile.id))
        .where(Profile.origin.isnot(None))
        .group_by(Profile.origin)
    )

    return {
        "total_profiles": profile_count.scalar() or 0,
        "active_profiles": active_profiles.scalar() or 0,
        "total_orgs": org_count.scalar() or 0,
        "total_users": user_count.scalar() or 0,
        "total_countries": country_count.scalar() or 0,
        "segments": {row[0]: row[1] for row in segment_counts.all()},
        "origins": {row[0]: row[1] for row in origin_counts.all()},
    }


@router.get("/health")
async def admin_health(
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "api": "healthy",
        "database": "connected" if db_ok else "disconnected",
        "version": "0.1.0",
        "environment": settings.environment,
    }


@router.get("/profiles")
async def list_all_profiles(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    total = await db.execute(select(func.count(Profile.id)))
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(Profile).offset(offset).limit(page_size).order_by(Profile.created_at.desc())
    )
    items = rows.scalars().all()
    return {
        "items": [{"id": p.id, "name": p.name, "source": p.source, "segment": p.segment, "origin": p.origin, "country_of_residence": p.country_of_residence, "is_active": p.is_active, "created_at": str(p.created_at)} for p in items],
        "total": total.scalar() or 0,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/profiles/{profile_id}")
async def update_profile(
    profile_id: str,
    body: UpdateProfileRequest,
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if body.segment is not None:
        profile.segment = body.segment
    if body.tags is not None:
        profile.tags = body.tags
    if body.is_active is not None:
        profile.is_active = body.is_active
    if body.origin is not None:
        profile.origin = body.origin
    await db.commit()
    return {"status": "updated", "profile_id": profile_id}


@router.delete("/profiles/{profile_id}")
async def delete_profile(
    profile_id: str,
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.is_active = False
    await db.commit()
    return {"status": "deleted", "profile_id": profile_id}


@router.get("/orgs")
async def list_all_orgs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    total = await db.execute(select(func.count(Org.id)))
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(Org).offset(offset).limit(page_size).order_by(Org.created_at.desc())
    )
    items = rows.scalars().all()
    return {
        "items": [{"id": o.id, "name": o.name, "org_type": o.org_type, "status": o.status, "country": o.country, "profile_count": o.profile_count, "created_at": str(o.created_at)} for o in items],
        "total": total.scalar() or 0,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/orgs/{org_id}")
async def update_org(
    org_id: str,
    body: UpdateOrgRequest,
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Org).where(Org.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")
    if body.org_type is not None:
        org.org_type = body.org_type
    if body.tags is not None:
        org.tags = body.tags
    await db.commit()
    return {"status": "updated", "org_id": org_id}


@router.delete("/orgs/{org_id}")
async def delete_org(
    org_id: str,
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Org).where(Org.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")
    await db.delete(org)
    await db.commit()
    return {"status": "deleted", "org_id": org_id}


@router.post("/import/trigger")
async def trigger_import(
    admin: bool = Depends(verify_admin),
):
    return {"status": "accepted", "message": "Import triggered (backend job pending)"}


@router.get("/import/status")
async def import_status(
    admin: bool = Depends(verify_admin),
):
    return {"status": "idle", "last_run": None, "records_imported": 0}
