"""Audit log writer.

Tests confirm there is no UPDATE/DELETE against audit_log.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session

from app.models.audit import AuditLog


def write_audit(
    session: Session,
    *,
    actor_id: Optional[int],
    actor_label: str,
    action: str,
    target_kind: str,
    target_id: Optional[int] = None,
    extra: Optional[dict] = None,
    commit: bool = False,
) -> AuditLog:
    row = AuditLog(
        actor_id=actor_id,
        actor_label=actor_label[:120],
        action=action[:60],
        target_kind=target_kind[:30],
        target_id=target_id,
        extra_json=json.dumps(extra or {}, separators=(",", ":"))[:500],
        created_at=datetime.utcnow(),
    )
    session.add(row)
    if commit:
        session.commit()
    return row
