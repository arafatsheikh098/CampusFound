"""Campus place managed by moderators (library, dept building, hall, ...)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Place(SQLModel, table=True):
    __tablename__ = "place"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=120, unique=True, index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
