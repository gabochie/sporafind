from fastapi import Header, HTTPException

from app.config import settings


async def verify_public_access(x_api_key: str | None = Header(default=None)):
    if settings.public_api_key and x_api_key != settings.public_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True
