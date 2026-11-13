from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.auth import hash_password
from app.models import User
from app.schemas import LoginRequest

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    from app.auth import decode_access_token

    try:
        subject = decode_access_token(credentials.credentials)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = db.query(User).filter(User.username == subject).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    stored_user = db.query(User).filter(User.username == username).first()
    if not stored_user:
        return None
    if stored_user.password_hash != hash_password(password):
        return None
    return stored_user


def ensure_admin_user(db: Session) -> None:
    user = db.query(User).filter(User.username == settings.admin_username).first()
    if user is None:
        db.add(
            User(
                id=f"user_{settings.admin_username}",
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                is_active=True,
            )
        )
        db.commit()
