"""Re-export every model so ``alembic env.py`` and tests can import them
with ``from app.models import *`` and they all register on the metadata.
"""
from app.models.audit import AuditLog
from app.models.category import Category
from app.models.claim import Claim, ClaimAnswer, ClaimStatus
from app.models.item import Custody, FoundItem, ItemStatus, VerificationQuestion
from app.models.login_attempt import LoginAttempt
from app.models.lost_report import LostReport
from app.models.notification import Notification, NotificationKind
from app.models.photo import Photo
from app.models.place import Place
from app.models.recovery_code import RecoveryCode
from app.models.user import AccountStatus, User

__all__ = [
    "AccountStatus",
    "AuditLog",
    "Category",
    "Claim",
    "ClaimAnswer",
    "ClaimStatus",
    "Custody",
    "FoundItem",
    "ItemStatus",
    "LoginAttempt",
    "LostReport",
    "Notification",
    "NotificationKind",
    "Photo",
    "Place",
    "RecoveryCode",
    "User",
    "VerificationQuestion",
]
