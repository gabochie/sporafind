from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.user import User

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    name: str | None = None


class AuthResponse(BaseModel):
    user_id: str
    email: str
    message: str


@router.post("/signup", response_model=AuthResponse)
@limiter.limit("5/minute")
async def signup(req: SignupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        return AuthResponse(
            user_id="",
            email=req.email,
            message="Check your email for the magic link (already registered)",
        )

    from app.models.user import User
    user = User(email=req.email, name=req.name)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return AuthResponse(
        user_id=user.id,
        email=user.email,
        message="Check your email for the magic link to sign in",
    )


@router.post("/magic-link")
@limiter.limit("5/minute")
async def send_magic_link(request: Request, email: str):
    return {"message": "Magic link would be sent here (Better Auth integration pending)"}
