"""Claim lifecycle: open, review, approve, reject, cancel, complete,
expire. Implements the limits in F6 and the handover flow in F7.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from sqlmodel import Session, or_, select

from app.audit import write_audit
from app.config import get_settings
from app.models.claim import Claim, ClaimAnswer, ClaimStatus
from app.models.item import FoundItem, ItemStatus, VerificationQuestion
from app.models.user import User

# F6 limits
ATTEMPTS_PER_ITEM = 3
OPEN_CLAIMS_PER_MEMBER = 5

ANSWER_MAX = 200
NOTE_MAX = 300
REASON_MAX = 300


class ClaimError(ValueError):
    pass


def _count_attempts(session: Session, *, item_id: int, claimant_id: int) -> int:
    """Number of attempts this claimant has made on this item.

    Every claim (open, rejected, approved, completed, expired,
    cancelled) counts toward the 3-attempt cap.
    """
    rows = session.exec(
        select(Claim).where(
            Claim.item_id == item_id,
            Claim.claimant_id == claimant_id,
        )
    ).all()
    return len(rows)


def _count_open_claims(session: Session, *, claimant_id: int) -> int:
    rows = session.exec(
        select(Claim).where(
            Claim.claimant_id == claimant_id,
            Claim.status.in_((ClaimStatus.OPEN, ClaimStatus.APPROVED)),
        )
    ).all()
    return len(rows)


def _approved_count_for_item(session: Session, *, item_id: int) -> int:
    rows = session.exec(
        select(Claim).where(
            Claim.item_id == item_id,
            Claim.status == ClaimStatus.APPROVED,
        )
    ).all()
    return len(rows)


def _get_or_404(session: Session, item_id: int) -> FoundItem:
    item = session.get(FoundItem, item_id)
    if item is None or item.hidden:
        raise ClaimError("item not found")
    return item


def open_claim(
    session: Session,
    *,
    item_id: int,
    claimant: User,
    answers: List[str],
    note: str = "",
) -> Claim:
    """Create a new claim. Validates all F6 limits."""
    if claimant.status.value != "approved":
        raise ClaimError("only approved members can open a claim")
    item = _get_or_404(session, item_id)
    if item.finder_id == claimant.id:
        raise ClaimError("you cannot claim your own post")
    if item.status not in (ItemStatus.OPEN,):
        raise ClaimError("item is not open for claims")
    if _count_attempts(session, item_id=item_id, claimant_id=claimant.id) >= ATTEMPTS_PER_ITEM:
        raise ClaimError("you have used all your attempts on this item")
    if _count_open_claims(session, claimant_id=claimant.id) >= OPEN_CLAIMS_PER_MEMBER:
        raise ClaimError(f"you already have {OPEN_CLAIMS_PER_MEMBER} open claims")

    # Validate answers against item questions
    qs = sorted(item.questions, key=lambda q: q.position)
    if not qs:
        raise ClaimError("item has no verification questions")
    if len(answers) != len(qs):
        raise ClaimError(f"please answer all {len(qs)} question(s)")
    cleaned: List[str] = []
    for a in answers:
        a = (a or "").strip()[:ANSWER_MAX]
        if not a:
            raise ClaimError("answers cannot be empty")
        cleaned.append(a)
    note = (note or "").strip()[:NOTE_MAX]

    claim = Claim(
        item_id=item_id,
        claimant_id=claimant.id,
        note=note,
        status=ClaimStatus.OPEN,
    )
    session.add(claim)
    session.commit()
    session.refresh(claim)
    for q, a in zip(qs, cleaned):
        session.add(ClaimAnswer(claim_id=claim.id, question_id=q.id, answer=a))
    session.commit()
    session.refresh(claim)
    write_audit(
        session,
        actor_id=claimant.id,
        actor_label=claimant.full_name,
        action="claim_opened",
        target_kind="claim",
        target_id=claim.id,
        extra={"item_id": item_id},
    )
    session.commit()

    # Notify the finder that a new claim is awaiting their decision.
    from app.models.notification import NotificationKind
    from app.notifications import service as notif_svc

    finder = session.get(User, item.finder_id)
    notif_svc.create(
        session,
        user_id=item.finder_id,
        kind=NotificationKind.NEW_CLAIM,
        payload={"item_id": item.id, "claim_id": claim.id},
    )
    if finder and finder.telegram_chat_id:
        notif_svc.send_telegram(finder.telegram_chat_id, "CampusFound: new claim on your post.")
    return claim


def decide_claim(
    session: Session,
    *,
    claim_id: int,
    by: User,
    approve: bool,
    reason: str = "",
) -> Claim:
    """Custodian approves or rejects an open claim."""
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise ClaimError("claim not found")
    item = session.get(FoundItem, claim.item_id)
    if item is None:
        raise ClaimError("item not found")
    if not (by.id == item.finder_id or by.is_moderator):
        raise ClaimError("only the finder or a moderator can decide this claim")
    if claim.status != ClaimStatus.OPEN:
        raise ClaimError("claim has already been decided")

    if approve:
        if _approved_count_for_item(session, item_id=item.id) >= 1:
            raise ClaimError("another claim on this item is already approved")
        claim.status = ClaimStatus.APPROVED
        claim.approved_at = datetime.utcnow()
        claim.decided_at = claim.approved_at
        claim.decided_by_id = by.id
        claim.reason = ""
        item.status = ItemStatus.CLAIM_APPROVED
        item.approved_claim_id = claim.id
        session.add(item)
    else:
        claim.status = ClaimStatus.REJECTED
        claim.decided_at = datetime.utcnow()
        claim.decided_by_id = by.id
        claim.reason = (reason or "").strip()[:REASON_MAX]
    session.add(claim)
    session.commit()
    session.refresh(claim)
    write_audit(
        session,
        actor_id=by.id,
        actor_label=by.full_name,
        action="claim_approved" if approve else "claim_rejected",
        target_kind="claim",
        target_id=claim.id,
        extra={"item_id": item.id, "reason": claim.reason if not approve else ""},
    )
    session.commit()

    # Notify the claimant.
    from app.models.notification import NotificationKind
    from app.notifications import service as notif_svc

    claimant = session.get(User, claim.claimant_id)
    notif_svc.create(
        session,
        user_id=claim.claimant_id,
        kind=NotificationKind.CLAIM_APPROVED if approve else NotificationKind.CLAIM_REJECTED,
        payload={"item_id": item.id, "claim_id": claim.id},
    )
    if claimant and claimant.telegram_chat_id:
        msg = "CampusFound: claim approved." if approve else "CampusFound: claim rejected."
        notif_svc.send_telegram(claimant.telegram_chat_id, msg)
    return claim


def cancel_claim(session: Session, *, claim_id: int, by: User) -> Claim:
    """A claimant can cancel their own open or approved claim."""
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise ClaimError("claim not found")
    if claim.claimant_id != by.id:
        raise ClaimError("only the claimant can cancel")
    if claim.status not in (ClaimStatus.OPEN, ClaimStatus.APPROVED):
        raise ClaimError("claim cannot be cancelled")
    claim.status = ClaimStatus.CANCELLED
    claim.cancelled_at = datetime.utcnow()
    # If it was the approved claim, reopen the item.
    item = session.get(FoundItem, claim.item_id)
    if item is not None and item.approved_claim_id == claim.id:
        item.approved_claim_id = None
        item.status = ItemStatus.OPEN
        session.add(item)
    session.add(claim)
    session.commit()
    session.refresh(claim)
    write_audit(
        session,
        actor_id=by.id,
        actor_label=by.full_name,
        action="claim_cancelled",
        target_kind="claim",
        target_id=claim.id,
    )
    session.commit()
    return claim


def confirm_returned(
    session: Session,
    *,
    claim_id: int,
    by: User,
) -> Claim:
    """Either side confirms 'returned' (or moderator for office items)."""
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise ClaimError("claim not found")
    if claim.status != ClaimStatus.APPROVED:
        raise ClaimError("claim is not in approved state")
    item = session.get(FoundItem, claim.item_id)
    if item is None:
        raise ClaimError("item not found")
    is_claimant = by.id == claim.claimant_id
    is_finder = by.id == item.finder_id
    is_moderator = by.is_moderator
    if not (is_claimant or is_finder or is_moderator):
        raise ClaimError("not allowed to confirm handover")
    now = datetime.utcnow()
    if is_claimant:
        claim.claimant_confirmed_returned_at = now
    elif is_finder:
        claim.custodian_confirmed_returned_at = now
    else:  # moderator
        claim.claimant_confirmed_returned_at = now
        claim.custodian_confirmed_returned_at = now
    both = (
        claim.claimant_confirmed_returned_at is not None
        and claim.custodian_confirmed_returned_at is not None
    )
    if both:
        claim.status = ClaimStatus.COMPLETED
        item.status = ItemStatus.RETURNED
        item.returned_at = now
        session.add(item)
        # Photos for returned posts are deleted per F4.5 / F7.
        from app.photos.service import delete_photos_for_item

        delete_photos_for_item(session, item)
    session.add(claim)
    session.commit()
    session.refresh(claim)
    write_audit(
        session,
        actor_id=by.id,
        actor_label=by.full_name,
        action="claim_handover_confirmed" if not both else "item_returned",
        target_kind="claim",
        target_id=claim.id,
        extra={"item_id": item.id, "both": both},
    )
    session.commit()
    if both:
        from app.models.notification import NotificationKind
        from app.notifications import service as notif_svc

        finder = session.get(User, item.finder_id)
        claimant = session.get(User, claim.claimant_id)
        for u in (finder, claimant):
            if u is None:
                continue
            notif_svc.create(
                session,
                user_id=u.id,
                kind=NotificationKind.ITEM_RETURNED,
                payload={"item_id": item.id, "claim_id": claim.id},
            )
            if u.telegram_chat_id:
                notif_svc.send_telegram(u.telegram_chat_id, "CampusFound: item returned.")
    return claim


def sweep_expired(session: Session) -> int:
    """Expire approved claims that have waited too long (F7)."""
    cutoff = datetime.utcnow() - timedelta(days=get_settings().days_claim_expiry)
    rows = session.exec(
        select(Claim).where(
            Claim.status == ClaimStatus.APPROVED,
            Claim.approved_at < cutoff,
        )
    ).all()
    count = 0
    for c in rows:
        c.status = ClaimStatus.EXPIRED
        c.expired_at = datetime.utcnow()
        item = session.get(FoundItem, c.item_id)
        if item is not None and item.approved_claim_id == c.id:
            item.approved_claim_id = None
            item.status = ItemStatus.OPEN
            session.add(item)
        session.add(c)
        count += 1
    if count:
        session.commit()
    return count


def claim_view_for(claim: Claim, by: User, item: FoundItem) -> dict:
    """Return what ``by`` is allowed to see for ``claim``."""
    is_custodian = (by.id == item.finder_id) or by.is_moderator
    is_claimant = by.id == claim.claimant_id
    return {
        "claim": claim,
        "item": item,
        "is_custodian": is_custodian,
        "is_claimant": is_claimant,
    }
