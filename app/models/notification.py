"""In-app notification.

The ``kind`` selects an i18n key. The ``payload`` carries minimal IDs (no
names, numbers, answers, item text). Generic Telegram messages are built
from the kind only.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class NotificationKind(str, Enum):
    NEW_CLAIM = "new_claim"
    CLAIM_APPROVED = "claim_approved"
    CLAIM_REJECTED = "claim_rejected"
    POSSIBLE_MATCH = "possible_match"
    ITEM_RETURNED = "item_returned"
    TELEGRAM_LINKED = "telegram_linked"


class Notification(SQLModel, table=True):
    __tablename__ = "notification"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    kind: NotificationKind = Field(default=NotificationKind.NEW_CLAIM, index=True)
    payload_json: str = Field(default="{}", max_length=500)  # only IDs, no PII
    is_read: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow(), index=True)
