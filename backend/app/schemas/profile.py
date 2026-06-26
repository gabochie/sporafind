from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class ProfileBase(BaseModel):
    name: str
    role: Optional[str] = None
    company_name: Optional[str] = None
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None
    locality: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    segment: Optional[str] = None
    tags: Optional[list[str]] = None
    origin: Optional[str] = None


class ProfileResponse(ProfileBase):
    id: str
    source: str
    source_id: Optional[str] = None
    company_number: Optional[str] = None
    is_active: bool
    claimed_by: Optional[str] = None
    is_claimed: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileList(BaseModel):
    items: list[ProfileResponse]
    total: int
    page: int
    page_size: int
