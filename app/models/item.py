"""Found-item post.

`custody` is either `finder` (a member holds the item) or `office` (routed
to the office because the category is sensitive or the finder chose office).

Private verification questions/answers live in ``VerificationQuestion`` so
they are easy to keep out of the default item SELECT.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class Custody(str, Enum):
    FINDER = "finder"
    OFFICE = "office"


class ItemStatus(str, Enum):
    OPEN = "open"
    CLAIM_APPROVED = "claim_approved"
    RETURNED = "returned"
    WITHDRAWN = "withdrawn"
    UNCLAIMED = "unclaimed"  # older than 60 days without a claim, routed to office


class FoundItem(SQLModel, table=True):
    __tablename__ = "found_item"

    id: Optional[int] = Field(default=None, primary_key=True)
    finder_id: int = Field(foreign_key="user.id", index=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    place_id: int = Field(foreign_key="place.id", index=True)
    date_found: date = Field(index=True)
    description: str = Field(max_length=300)
    handover_note: str = Field(max_length=150, default="")
    custody: Custody = Field(default=Custody.FINDER, index=True)
    status: ItemStatus = Field(default=ItemStatus.OPEN, index=True)
    hidden: bool = Field(default=False, index=True)  # moderator-hide

    created_at: datetime = Field(default_factory=lambda: datetime.utcnow(), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    returned_at: Optional[datetime] = Field(default=None)
    unclaimed_at: Optional[datetime] = Field(default=None)
    withdrawn_at: Optional[datetime] = Field(default=None)

    # The currently approved claim (only one at a time per item)
    approved_claim_id: Optional[int] = Field(default=None, foreign_key="claim.id")

    questions: List["VerificationQuestion"] = Relationship(
        back_populates="item",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class VerificationQuestion(SQLModel, table=True):
    __tablename__ = "verification_question"

    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="found_item.id", index=True)
    position: int = Field(default=1)  # 1..3
    question: str = Field(max_length=120)
    answer: str = Field(max_length=120)  # private: visible only to finder + moderators

    item: Optional[FoundItem] = Relationship(back_populates="questions")
