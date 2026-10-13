"""Password hashing and session signing."""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from itsdangerous import BadSignature, URLSafeSerializer

from app.config import get_settings

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, stored_hash: str) -> bool:
    """Constant-time verify. Returns False on any error (bad hash, etc.)."""
    try:
        return _hasher.verify(stored_hash, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().secret_key, salt="cf-session")


def sign_session(payload: dict) -> str:
    return _serializer().dumps(payload)


def unsign_session(token: str) -> dict | None:
    try:
        return _serializer().loads(token)
    except BadSignature:
        return None
