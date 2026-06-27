from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.user import User
from app.auth import create_token, verify_token

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    name: str | None = None


class TokenResponse(BaseModel):
    token: str
    user_id: str
    email: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    name: str | None
    plan_tier: str
    export_count: int
    created_at: str
    last_login: str | None


@router.post("/signup")
@limiter.limit("5/minute")
async def signup(req: SignupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == req.email))
    user = existing.scalar_one_or_none()
    if not user:
        user = User(email=req.email, name=req.name)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    token = create_token(user.id)
    return TokenResponse(token=token, user_id=user.id, email=user.email)


@router.get("/me", response_model=MeResponse)
async def get_me(user: User = Depends(verify_token)):
    return MeResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        plan_tier=user.plan_tier,
        export_count=user.export_count,
        created_at=str(user.created_at),
        last_login=str(user.last_login) if user.last_login else None,
    )
