from datetime import datetime, timezone

import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def _get_serializer() -> URLSafeTimedSerializer:
    secret = settings.auth_secret
    if not secret:
        raise RuntimeError("AUTH_SECRET must be set in production")
    return URLSafeTimedSerializer(
        secret_key=secret,
        salt="sporafind-auth",
    )


def create_token(user_id: str, expires_in: int = 86400 * 30) -> str:
    s = _get_serializer()
    return s.dumps({"user_id": user_id})


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    s = _get_serializer()
    try:
        data = s.loads(credentials.credentials, max_age=86400 * 30)
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Token expired")
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is deactivated")

    return user


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
