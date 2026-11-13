import hashlib
import os
import uuid
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, UploadFile, status

from app.config import settings


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
