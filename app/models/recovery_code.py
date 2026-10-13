"""One-time recovery codes shown to the user and stored hashed.

When a user recovers, they enter a code; we hash it and look up a row.
Once matched, the row is removed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class RecoveryCode(SQLModel, table=True):
    __tablename__ = "recovery_code"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    code_hash: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    used_at: Optional[datetime] = Field(default=None)
