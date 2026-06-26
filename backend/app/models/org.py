from uuid import uuid4
from datetime import datetime

from sqlalchemy import String, DateTime, Text, Integer, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = mapped_column(String(50), default="companies_house")
    source_id: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sic_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    registered_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    locality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    incorporation_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    org_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(10), nullable=True)
    profile_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
