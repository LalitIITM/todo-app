"""Password hashing and bearer-token authentication."""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .database import get_db

# How long a signed-in session stays valid.
SESSION_LIFETIME = timedelta(days=30)
# Emailed links.
VERIFY_LIFETIME = timedelta(hours=24)
RESET_LIFETIME = timedelta(hours=1)

VERIFY_PURPOSE = "verify"
RESET_PURPOSE = "reset"

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def _encode(password: str) -> bytes:
    """bcrypt only uses the first 72 bytes; pre-hash longer passwords."""
    raw = password.encode("utf-8")
    if len(raw) > 72:
        raw = base64.b64encode(hashlib.sha256(raw).digest())
    return raw


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_encode(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_session(db: Session, user: models.User) -> models.AuthSession:
    session = models.AuthSession(
        token=secrets.token_urlsafe(32),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + SESSION_LIFETIME,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _as_aware(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat them as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_email_token(
    db: Session, user: models.User, purpose: str, lifetime: timedelta
) -> str:
    """Create a single-use token, store its hash, and return the raw token."""
    token = secrets.token_urlsafe(32)
    db.add(
        models.EmailToken(
            user_id=user.id,
            token_hash=_hash_token(token),
            purpose=purpose,
            expires_at=datetime.now(timezone.utc) + lifetime,
        )
    )
    db.commit()
    return token


def load_email_token(
    db: Session, token: str, purpose: str
) -> models.EmailToken | None:
    """Return a usable (unused, unexpired) token row, or None."""
    row = db.scalar(
        select(models.EmailToken).where(
            models.EmailToken.token_hash == _hash_token(token),
            models.EmailToken.purpose == purpose,
        )
    )
    if row is None or row.used_at is not None:
        return None
    if _as_aware(row.expires_at) < datetime.now(timezone.utc):
        return None
    return row


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _UNAUTHORIZED

    token = authorization[7:].strip()
    session = db.scalar(
        select(models.AuthSession).where(models.AuthSession.token == token)
    )
    if session is None:
        raise _UNAUTHORIZED

    if _as_aware(session.expires_at) < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return session.user
