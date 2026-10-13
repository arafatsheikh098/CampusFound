"""Per-username login-attempt rate limiting.

A row per failure, plus an optional ``success_at`` reset. The 6th failure
within 15 minutes triggers 429.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class LoginAttempt(SQLModel, table=True):
    __tablename__ = "login_attempt"

    id: Optional[int] = Field(default=None, primary_key=True)
    username_or_mobile: str = Field(max_length=120, index=True)
    success: bool = Field(default=False)
    attempted_at: datetime = Field(default_factory=lambda: datetime.utcnow(), index=True)
    ip: Optional[str] = Field(default=None, max_length=64)
