from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, func, text, or_
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.database import get_db, get_session
from app.models.user import User
from app.models.profile import Profile
from app.models.org import Org
from app.models.activity_log import ActivityLog
from app.models.import_run import ImportRun
from app.services.importer import run_import

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/admin", tags=["admin"])


async def log_action(action: str, detail: str, user_id: str | None = None):
    session = get_session()
    async with session() as db:
        entry = ActivityLog(action=action, detail=detail, user_id=user_id)
        db.add(entry)
        await db.commit()


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
@limiter.limit("20/minute")
async def admin_verify(request: Request, admin: bool = Depends(verify_admin)):
    return {"status": "ok", "role": "admin"}


@router.get("/activity")
@limiter.limit("20/minute")
async def get_activity(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
    )
    items = rows.scalars().all()
    return {
        "items": [
            {
                "action": a.action,
                "detail": a.detail,
                "user_id": a.user_id,
                "timestamp": a.created_at.isoformat(),
            }
            for a in items
        ]
    }


@router.get("/users")
@limiter.limit("20/minute")
async def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str = Query("", max_length=200),
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    count_query = select(func.count(User.id))
    if q:
        like = f"%{q}%"
        filters = [User.email.ilike(like), User.name.ilike(like)]
        query = query.where(or_(*filters))
        count_query = count_query.where(or_(*filters))
    total = await db.execute(count_query)
    offset = (page - 1) * page_size
    rows = await db.execute(
        query.offset(offset).limit(page_size).order_by(User.created_at.desc())
    )
    users = rows.scalars().all()
    return {
        "items": [{"id": u.id, "email": u.email, "name": u.name, "is_active": u.is_active, "plan_tier": u.plan_tier, "export_count": u.export_count, "created_at": str(u.created_at), "last_login": str(u.last_login) if u.last_login else None} for u in users],
        "total": total.scalar() or 0,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/users/{user_id}")
@limiter.limit("10/minute")
async def update_user(
    request: Request,
    user_id: str,
    body: UpdateUserRequest,
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    changes = []
    if body.is_active is not None:
        user.is_active = body.is_active
        changes.append(f"active={body.is_active}")
    if body.plan_tier is not None:
        user.plan_tier = body.plan_tier
        changes.append(f"plan={body.plan_tier}")
    await db.commit()
    await log_action("user_updated", f"User {user.email}: {', '.join(changes)}")
    return {"status": "updated", "user_id": user_id}


@router.get("/analytics")
@limiter.limit("20/minute")
async def admin_analytics(
    request: Request,
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
@limiter.limit("20/minute")
async def admin_health(
    request: Request,
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
        "uptime": "0.1.0",
    }


@router.get("/profiles")
@limiter.limit("20/minute")
async def list_all_profiles(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str = Query("", max_length=200),
    segment: str | None = None,
    origin: str | None = None,
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(Profile)
    count_query = select(func.count(Profile.id))
    if q:
        like = f"%{q}%"
        filters = [Profile.name.ilike(like), Profile.company_name.ilike(like), Profile.locality.ilike(like)]
        query = query.where(or_(*filters))
        count_query = count_query.where(or_(*filters))
    if segment:
        query = query.where(Profile.segment == segment)
        count_query = count_query.where(Profile.segment == segment)
    if origin:
        query = query.where(Profile.origin == origin)
        count_query = count_query.where(Profile.origin == origin)
    total = await db.execute(count_query)
    offset = (page - 1) * page_size
    rows = await db.execute(
        query.offset(offset).limit(page_size).order_by(Profile.created_at.desc())
    )
    items = rows.scalars().all()
    return {
        "items": [{"id": p.id, "name": p.name, "source": p.source, "segment": p.segment, "origin": p.origin, "country_of_residence": p.country_of_residence, "locality": p.locality, "is_active": p.is_active, "created_at": str(p.created_at)} for p in items],
        "total": total.scalar() or 0,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/profiles/{profile_id}")
@limiter.limit("10/minute")
async def update_profile(
    request: Request,
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
    await log_action("profile_updated", f"Profile {profile.name}: segment={body.segment}, active={body.is_active}")
    return {"status": "updated", "profile_id": profile_id}


@router.delete("/profiles/{profile_id}")
@limiter.limit("10/minute")
async def delete_profile(
    request: Request,
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
    await log_action("profile_deleted", f"Profile {profile.name} deactivated")
    return {"status": "deleted", "profile_id": profile_id}


class BatchProfileAction(BaseModel):
    ids: list[str]
    action: str
    value: str | None = None


@router.post("/profiles/batch")
@limiter.limit("10/minute")
async def batch_profile_action(
    request: Request,
    body: BatchProfileAction,
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.id.in_(body.ids)))
    profiles = result.scalars().all()
    count = 0
    for p in profiles:
        if body.action == "activate":
            p.is_active = True
        elif body.action == "deactivate":
            p.is_active = False
        elif body.action == "set_segment" and body.value:
            p.segment = body.value
        count += 1
    await db.commit()
    await log_action("batch_profiles", f"{count} profiles: {body.action}")
    return {"status": "ok", "affected": count}


@router.get("/orgs")
@limiter.limit("20/minute")
async def list_all_orgs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str = Query("", max_length=200),
    org_type: str | None = None,
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(Org)
    count_query = select(func.count(Org.id))
    if q:
        like = f"%{q}%"
        query = query.where(Org.name.ilike(like))
        count_query = count_query.where(Org.name.ilike(like))
    if org_type:
        query = query.where(Org.org_type == org_type)
        count_query = count_query.where(Org.org_type == org_type)
    total = await db.execute(count_query)
    offset = (page - 1) * page_size
    rows = await db.execute(
        query.offset(offset).limit(page_size).order_by(Org.created_at.desc())
    )
    items = rows.scalars().all()
    return {
        "items": [{"id": o.id, "name": o.name, "org_type": o.org_type, "status": o.status, "country": o.country, "locality": o.locality, "profile_count": o.profile_count, "created_at": str(o.created_at)} for o in items],
        "total": total.scalar() or 0,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/orgs/{org_id}")
@limiter.limit("10/minute")
async def update_org(
    request: Request,
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
    await log_action("org_updated", f"Org {org.name}: type={body.org_type}")
    return {"status": "updated", "org_id": org_id}


@router.delete("/orgs/{org_id}")
@limiter.limit("10/minute")
async def delete_org(
    request: Request,
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
    await log_action("org_deleted", f"Org {org.name} deleted")
    return {"status": "deleted", "org_id": org_id}


class BatchOrgAction(BaseModel):
    ids: list[str]
    action: str
    value: str | None = None


@router.post("/orgs/batch")
@limiter.limit("10/minute")
async def batch_org_action(
    request: Request,
    body: BatchOrgAction,
    admin: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Org).where(Org.id.in_(body.ids)))
    orgs = result.scalars().all()
    count = 0
    for o in orgs:
        if body.action == "set_type" and body.value:
            o.org_type = body.value
        count += 1
    await db.commit()
    await log_action("batch_orgs", f"{count} orgs: {body.action}")
    return {"status": "ok", "affected": count}


@router.post("/import/trigger")
@limiter.limit("5/minute")
async def trigger_import(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: bool = Depends(verify_admin),
):
    import_run_id = str(uuid4())
    run = ImportRun(id=import_run_id, status="queued")
    db.add(run)
    await db.commit()

    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.redis_url, decode_responses=True)
        await r.lpush("arq:queue", f"{import_run_id}")
        await r.aclose()
    except Exception:
        pass

    return {
        "status": "accepted",
        "import_run_id": import_run_id,
        "message": "Import queued for background processing",
    }


@router.get("/import/status")
@limiter.limit("20/minute")
async def import_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: bool = Depends(verify_admin),
):
    latest = await db.execute(
        select(ImportRun).order_by(ImportRun.created_at.desc()).limit(10)
    )
    runs = latest.scalars().all()
    return {
        "runs": [
            {
                "id": r.id,
                "status": r.status,
                "records_found": r.records_found,
                "records_imported": r.records_imported,
                "records_failed": r.records_failed,
                "orgs_found": r.orgs_found,
                "orgs_imported": r.orgs_imported,
                "error_message": r.error_message,
                "started_at": str(r.started_at) if r.started_at else None,
                "completed_at": str(r.completed_at) if r.completed_at else None,
                "created_at": str(r.created_at),
            }
            for r in runs
        ]
    }


@router.post("/import/start-sync")
@limiter.limit("2/minute")
async def start_import_sync(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: bool = Depends(verify_admin),
):
    import_run_id = str(uuid4())
    run = ImportRun(id=import_run_id, status="queued")
    db.add(run)
    await db.commit()
    await run_import(import_run_id, db)
    run = await db.get(ImportRun, import_run_id)
    return {
        "id": run.id,
        "status": run.status,
        "records_imported": run.records_imported,
        "records_failed": run.records_failed,
        "orgs_imported": run.orgs_imported,
        "error_message": run.error_message,
    }
