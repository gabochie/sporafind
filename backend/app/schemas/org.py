from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OrgBase(BaseModel):
    name: str
    company_number: Optional[str] = None
    status: Optional[str] = None
    org_type: Optional[str] = None
    sic_codes: Optional[list[str]] = None
    locality: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    tags: Optional[list[str]] = None
    origin: Optional[str] = None


class OrgResponse(OrgBase):
    id: str
    source: str
    source_id: Optional[str] = None
    profile_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrgList(BaseModel):
    items: list[OrgResponse]
    total: int
    page: int
    page_size: int
