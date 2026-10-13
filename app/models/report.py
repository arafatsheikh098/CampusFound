"""Report (a member's flag of a post or a claim)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class ReportTarget(str, Enum):
    FOUND_ITEM = "found_item"
    CLAIM = "claim"
    LOST_REPORT = "lost_report"
    USER = "user"


class Report(SQLModel, table=True):
    __tablename__ = "report"

    id: Optional[int] = Field(default=None, primary_key=True)
    reporter_id: int = Field(foreign_key="user.id", index=True)
    target_kind: ReportTarget = Field(default=ReportTarget.FOUND_ITEM, index=True)
    target_id: int = Field(index=True)
    reason: str = Field(max_length=300)
    resolved: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow(), index=True)
