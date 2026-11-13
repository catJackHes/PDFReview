from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, ProjectFile, ReviewRun, Finding
from app.pdf_service import extract_pdf_metadata
from app.services import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/{project_id}/files/{file_id}")
def get_file_metadata(
    project_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ProjectFile:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    file_record = db.query(ProjectFile).filter(ProjectFile.id == file_id, ProjectFile.project_id == project_id).first()
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return file_record


@router.get("/{project_id}/files/{file_id}/pages")
def get_file_pages(
    project_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    file_record = db.query(ProjectFile).filter(ProjectFile.id == file_id, ProjectFile.project_id == project_id).first()
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    file_path = Path("./storage/uploads") / file_record.storage_key
    metadata = extract_pdf_metadata(file_path)
    return {"file_id": file_id, "page_count": file_record.page_count, "pdf_type": file_record.pdf_type, "pages": metadata.get("pages", [])}


@router.get("/{project_id}/reviews/{review_id}")
def get_review_run(
    project_id: str,
    review_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ReviewRun:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    review_run = db.query(ReviewRun).filter(ReviewRun.id == review_id, ReviewRun.project_id == project_id).first()
    if review_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review run not found")
    return review_run
