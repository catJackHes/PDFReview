from __future__ import annotations

import hashlib
import hmac
import uuid
from pathlib import Path
from typing import Generator

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import decode_access_token
from app.config import settings
from app.db import get_db
from app.models import User

_password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
_bearer = HTTPBearer(auto_error=False)


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty")
    return _password_hasher.hash(password)


def _verify_password(stored_hash: str, password: str) -> tuple[bool, bool]:
    """Return (valid, needs_rehash); legacy SHA-256 is accepted only for migration."""
    if stored_hash.startswith("$argon2"):
        try:
            return _password_hasher.verify(stored_hash, password), _password_hasher.check_needs_rehash(stored_hash)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False, False
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(stored_hash, legacy), True


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        return None
    valid, needs_rehash = _verify_password(user.password_hash, password)
    if not valid:
        return None
    if needs_rehash:
        user.password_hash = hash_password(password)
        db.commit()
        db.refresh(user)
    return user


def ensure_admin_user(db: Session) -> User | None:
    """Create the initial single-user account only when explicitly configured."""
    username = settings.admin_username
    password = settings.admin_password
    if not username or not password:
        return None

    user = db.query(User).filter(User.username == username).first()
    if user is not None:
        return user
    user = User(
        id=generate_id("user"),
        username=username,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        username = decode_access_token(credentials.credentials)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc
    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive account")
    return user


def create_storage_dirs() -> None:
    for directory in (settings.upload_dir, settings.render_dir, settings.report_dir):
        Path(directory).mkdir(parents=True, exist_ok=True)
