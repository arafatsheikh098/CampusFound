"""User and account models.

Three account statuses: ``pending``, ``approved``, ``rejected``, ``suspended``.
The ``is_moderator`` flag grants moderator privileges.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AccountStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str = Field(max_length=120, index=True)
    department: str = Field(max_length=120, index=True)
    batch_or_session: str = Field(max_length=60, index=True)
    mobile: str = Field(max_length=20, unique=True, index=True)
    password_hash: str = Field(max_length=255)
    is_member_confirmed: bool = Field(default=False)
    is_adult_confirmed: bool = Field(default=False)
    status: AccountStatus = Field(default=AccountStatus.PENDING, index=True)
    is_moderator: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    approved_at: Optional[datetime] = Field(default=None)
    approved_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    suspended_at: Optional[datetime] = Field(default=None)
    telegram_chat_id: Optional[int] = Field(default=None, index=True)
    telegram_link_code: Optional[str] = Field(default=None, max_length=20, index=True)

    # Display name for audit entries when the user is deleted
    display_name_snapshot: Optional[str] = Field(default=None, max_length=120)
