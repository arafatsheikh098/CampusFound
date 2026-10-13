"""Append-only audit log.

Write via ``app.audit.write_audit``. Tests confirm there are no UPDATE or
DELETE statements against this table.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    actor_id: Optional[int] = Field(default=None, index=True)  # user id, nullable for system
    actor_label: str = Field(max_length=120)  # snapshot of name (or "deleted-user")
    action: str = Field(max_length=60, index=True)
    target_kind: str = Field(max_length=30, index=True)
    target_id: Optional[int] = Field(default=None, index=True)
    extra_json: str = Field(default="{}", max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow(), index=True)
