from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

security = HTTPBearer(auto_error=False)


def hash_password(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_storage_dirs() -> None:
    for directory in [settings.upload_dir, settings.render_dir, settings.report_dir]:
        Path(directory).mkdir(parents=True, exist_ok=True)


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def validate_pdf(file: UploadFile, project_id: str) -> None:
    if file.filename is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing file name")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are allowed")
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File exceeds size limit")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_project_dir(project_id: str) -> Path:
    root = Path(settings.upload_dir) / project_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_mock_review_findings(file_ids: Iterable[str]) -> list[dict]:
    findings: list[dict] = []
    for index, file_id in enumerate(file_ids, start=1):
        findings.append(
            {
                "file_id": file_id,
                "category": "seal" if index % 2 == 1 else "format",
                "message": "检测到潜在签章或格式问题，需人工复核。" if index % 2 == 1 else "文档缺少必要的页面信息或结构特征，建议人工确认。",
                "severity": "medium" if index % 2 == 1 else "low",
                "confidence": 0.72 if index % 2 == 1 else 0.61,
                "source": "mock_rules",
            }
        )
    return findings


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    from app.auth import decode_access_token

    try:
        subject = decode_access_token(credentials.credentials)
    except Exception as exc:
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
    from app.config import settings

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
