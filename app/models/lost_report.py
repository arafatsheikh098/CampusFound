"""A member's "I lost this" report used to surface possible matches."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class LostReport(SQLModel, table=True):
    __tablename__ = "lost_report"

    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    place_id: int = Field(foreign_key="place.id", index=True)
    date_lost: date = Field(index=True)
    description: str = Field(max_length=300)
    private_note: str = Field(max_length=300, default="")
    is_open: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow(), index=True)
