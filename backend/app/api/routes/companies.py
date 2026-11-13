from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import fitz
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Project, ProjectFile
from app.schemas import FileUploadResponse, ProjectCreate, ProjectOut, ProjectUpdate
from app.services import get_current_user, generate_id

router = APIRouter(prefix="/projects", tags=["projects"])
ALLOWED_FILE_TYPES = {"contract", "tender_document", "bid_document", "template", "supplement", "other"}
CHUNK_SIZE = 1024 * 1024


def _project_for_user(db: Session, project_id: str, username: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _read_pdf_metadata(path: Path) -> dict[str, Any]:
    try:
        with fitz.open(path) as document:
            if document.needs_pass:
                raise HTTPException(status_code=422, detail="Encrypted PDF is not supported")
            count = document.page_count
            if count < 1:
                raise HTTPException(status_code=422, detail="PDF contains no pages")
            if count > settings.max_pages:
                raise HTTPException(status_code=413, detail="PDF exceeds page limit")
            pages_with_text = 0
            for page in document:
                if (page.get_text("text") or "").strip():
                    pages_with_text += 1
            pdf_type = "native" if pages_with_text == count else "mixed" if pages_with_text else "scanned"
            return {"page_count": count, "pdf_type": pdf_type}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid or unreadable PDF") from exc


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> list[Project]:
    return db.query(Project).filter(Project.created_by == current_user.username).order_by(Project.created_at.desc()).all()


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> Project:
    project = Project(id=generate_id("project"), name=payload.name, description=payload.description,
                      subject_company_id=payload.subject_company_id, status="active", created_by=current_user.username)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> Project:
    return _project_for_user(db, project_id, current_user.username)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> Project:
    project = _project_for_user(db, project_id, current_user.username)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/files", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    file_type: str = Form("contract"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProjectFile:
    _project_for_user(db, project_id, current_user.username)
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Only files with a .pdf extension are accepted")
    if file_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported file_type")

    project_dir = (Path(settings.upload_dir).resolve() / project_id).resolve()
    root = Path(settings.upload_dir).resolve()
    if not project_dir.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Invalid project storage location")
    project_dir.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    final_path: Path | None = None
    digest = hashlib.sha256()
    total = 0
    prefix = bytearray()
    try:
        with tempfile.NamedTemporaryFile(prefix="upload-", suffix=".part", dir=project_dir, delete=False) as temp:
            temp_path = Path(temp.name)
            while chunk := await file.read(CHUNK_SIZE):
                total += len(chunk)
                if total > settings.max_file_size:
                    raise HTTPException(status_code=413, detail="File exceeds size limit")
                if len(prefix) < 1024:
                    prefix.extend(chunk[:1024 - len(prefix)])
                digest.update(chunk)
                temp.write(chunk)
        if not bytes(prefix).lstrip().startswith(b"%PDF-"):
            raise HTTPException(status_code=415, detail="Uploaded content is not a PDF")
        metadata = _read_pdf_metadata(temp_path)
        storage_name = f"{uuid.uuid4().hex}.pdf"
        final_path = project_dir / storage_name
        os.replace(temp_path, final_path)
        temp_path = None
        record = ProjectFile(
            id=generate_id("file"), project_id=project_id, file_type=file_type,
            display_name=Path(file.filename).name[:255], storage_key=f"{project_id}/{storage_name}",
            sha256=digest.hexdigest(), size_bytes=total, page_count=metadata["page_count"],
            pdf_type=metadata["pdf_type"], status="uploaded", created_by=current_user.username,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to store uploaded PDF") from exc
    finally:
        await file.close()
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        # If persistence failed after the atomic rename, do not leave an orphaned upload.
        if final_path and final_path.exists():
            stored = db.query(ProjectFile).filter(ProjectFile.storage_key == f"{project_id}/{final_path.name}").first()
            if stored is None:
                final_path.unlink(missing_ok=True)


@router.get("/{project_id}/files", response_model=list[FileUploadResponse])
def list_files(project_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> list[ProjectFile]:
    _project_for_user(db, project_id, current_user.username)
    return db.query(ProjectFile).filter(ProjectFile.project_id == project_id).order_by(ProjectFile.created_at.desc()).all()
