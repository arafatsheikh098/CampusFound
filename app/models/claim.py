"""Claim model: a member's attempt to recover a found item."""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class ClaimStatus(str, Enum):
    OPEN = "open"  # created, awaiting custodian decision
    APPROVED = "approved"  # approved, awaiting handover
    REJECTED = "rejected"  # rejected (counts toward attempt limit)
    EXPIRED = "expired"  # approved but not handed over in time
    CANCELLED = "cancelled"  # claimant cancelled
    COMPLETED = "completed"  # handover complete, item returned


class Claim(SQLModel, table=True):
    __tablename__ = "claim"

    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="found_item.id", index=True)
    claimant_id: int = Field(foreign_key="user.id", index=True)
    note: str = Field(max_length=300, default="")
    status: ClaimStatus = Field(default=ClaimStatus.OPEN, index=True)
    reason: str = Field(max_length=300, default="")  # rejection reason
    decided_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    decided_at: Optional[datetime] = Field(default=None)
    approved_at: Optional[datetime] = Field(default=None)
    claimant_confirmed_returned_at: Optional[datetime] = Field(default=None)
    custodian_confirmed_returned_at: Optional[datetime] = Field(default=None)
    cancelled_at: Optional[datetime] = Field(default=None)
    expired_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow(), index=True)

    answers: List["ClaimAnswer"] = Relationship(
        back_populates="claim",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class ClaimAnswer(SQLModel, table=True):
    __tablename__ = "claim_answer"

    id: Optional[int] = Field(default=None, primary_key=True)
    claim_id: int = Field(foreign_key="claim.id", index=True)
    question_id: int = Field(foreign_key="verification_question.id", index=True)
    answer: str = Field(max_length=200)

    claim: Optional[Claim] = Relationship(back_populates="answers")
