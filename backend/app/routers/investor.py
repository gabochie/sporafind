from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.user import User
from app.models.investor_profile import InvestorProfile
from app.models.investor_commitment import InvestorCommitment
from app.models.investor_message import InvestorMessage
from app.auth import verify_token

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/investor", tags=["investor"])


async def require_investor(user: User = Depends(verify_token)) -> User:
    if user.role != "investor":
        raise HTTPException(status_code=403, detail="Investor access required")
    return user


class ProfileUpdate(BaseModel):
    company: str | None = None
    investment_focus: str | None = None
    check_size_min: int | None = None
    check_size_max: int | None = None


class CommitmentRequest(BaseModel):
    amount: int | None = None
    tier: str | None = None
    notes: str | None = None


class MessageRequest(BaseModel):
    subject: str | None = None
    body: str


@router.get("/me")
@limiter.limit("30/minute")
async def get_investor_profile(
    request: Request,
    user: User = Depends(require_investor),
    db: AsyncSession = Depends(get_db),
):
    profile_result = await db.execute(
        select(InvestorProfile).where(InvestorProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()

    commit_result = await db.execute(
        select(InvestorCommitment).where(InvestorCommitment.user_id == user.id)
    )
    commitment = commit_result.scalar_one_or_none()

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        },
        "profile": {
            "company": profile.company if profile else None,
            "investment_focus": profile.investment_focus if profile else None,
            "check_size_min": profile.check_size_min if profile else None,
            "check_size_max": profile.check_size_max if profile else None,
            "status": profile.status if profile else "pending",
            "notes": profile.notes if profile else None,
        } if profile else None,
        "commitment": {
            "amount": commitment.amount if commitment else None,
            "tier": commitment.tier if commitment else None,
            "status": commitment.status if commitment else None,
        } if commitment else None,
    }


@router.patch("/profile")
@limiter.limit("10/minute")
async def update_investor_profile(
    request: Request,
    body: ProfileUpdate,
    user: User = Depends(require_investor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InvestorProfile).where(InvestorProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = InvestorProfile(user_id=user.id)
        db.add(profile)
    if body.company is not None:
        profile.company = body.company
    if body.investment_focus is not None:
        profile.investment_focus = body.investment_focus
    if body.check_size_min is not None:
        profile.check_size_min = body.check_size_min
    if body.check_size_max is not None:
        profile.check_size_max = body.check_size_max
    await db.commit()
    return {"status": "updated"}


@router.post("/commit")
@limiter.limit("5/minute")
async def commit_interest(
    request: Request,
    body: CommitmentRequest,
    user: User = Depends(require_investor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InvestorCommitment).where(InvestorCommitment.user_id == user.id)
    )
    commitment = result.scalar_one_or_none()
    if not commitment:
        commitment = InvestorCommitment(user_id=user.id)
        db.add(commitment)
    if body.amount is not None:
        commitment.amount = body.amount
    if body.tier is not None:
        commitment.tier = body.tier
    if body.notes is not None:
        commitment.notes = body.notes
    if commitment.status == "interested":
        commitment.status = "committed"
    await db.commit()
    return {
        "status": "ok",
        "commitment": {
            "amount": commitment.amount,
            "tier": commitment.tier,
            "status": commitment.status,
        },
    }


@router.post("/message")
@limiter.limit("10/minute")
async def send_message(
    request: Request,
    body: MessageRequest,
    user: User = Depends(require_investor),
    db: AsyncSession = Depends(get_db),
):
    admin_result = await db.execute(
        select(User.id).where(User.role == "admin").limit(1)
    )
    admin_user = admin_result.scalar_one_or_none()
    to_user_id = admin_user if admin_user else user.id

    msg = InvestorMessage(
        from_user_id=user.id,
        to_user_id=to_user_id,
        subject=body.subject,
        body=body.body,
    )
    db.add(msg)
    await db.commit()
    return {"status": "sent", "message_id": msg.id}


@router.get("/messages")
@limiter.limit("20/minute")
async def list_messages(
    request: Request,
    user: User = Depends(require_investor),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(InvestorMessage)
        .where(
            (InvestorMessage.from_user_id == user.id)
            | (InvestorMessage.to_user_id == user.id)
        )
        .order_by(InvestorMessage.created_at.desc())
        .limit(50)
    )
    items = rows.scalars().all()
    return {
        "messages": [
            {
                "id": m.id,
                "from_user_id": m.from_user_id,
                "to_user_id": m.to_user_id,
                "subject": m.subject,
                "body": m.body,
                "read_at": str(m.read_at) if m.read_at else None,
                "created_at": str(m.created_at),
            }
            for m in items
        ]
    }
