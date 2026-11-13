from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import create_storage_dirs, ensure_project_dir, generate_id, sha256_bytes, validate_pdf
from app.db import get_db
from app.models import Project, ProjectFile, ReviewRun, Finding
from app.schemas import (
    FileUploadResponse,
    FindingOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    ReviewRequest,
    ReviewRunOut,
)
from app.services import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> list[Project]:
    return db.query(Project).filter(Project.created_by == current_user.username).order_by(Project.created_at.desc()).all()


@router.post("", response_model=ProjectOut)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Project:
    project = Project(
        id=generate_id("project"),
        name=payload.name,
        description=payload.description,
        subject_company_id=payload.subject_company_id,
        status="active",
        created_by=current_user.username,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(project, field, value)
    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/files", response_model=FileUploadResponse)
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    file_type: str = Form("contract"),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ProjectFile:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    validate_pdf(file, project_id)
    create_storage_dirs()

    content = await file.read()
    digest = sha256_bytes(content)
    storage_dir = ensure_project_dir(project_id)
    storage_name = f"{generate_id('file')}.pdf"
    final_path = storage_dir / storage_name
    final_path.write_bytes(content)

    record = ProjectFile(
        id=generate_id("file_record"),
        project_id=project_id,
        file_type=file_type,
        display_name=file.filename or storage_name,
        storage_key=f"{project_id}/{storage_name}",
        sha256=digest,
        size_bytes=len(content),
        page_count=1,
        pdf_type="native",
        status="uploaded",
        created_by=current_user.username,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{project_id}/files", response_model=list[FileUploadResponse])
def list_files(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> list[ProjectFile]:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return db.query(ProjectFile).filter(ProjectFile.project_id == project_id).all()


@router.post("/{project_id}/reviews", response_model=ReviewRunOut)
def create_review(
    project_id: str,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ReviewRun:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    run = ReviewRun(
        id=generate_id("review"),
        project_id=project_id,
        status="queued",
        started_at=datetime.now(timezone.utc),
        config_snapshot={"rule_set": payload.rule_set, "options": payload.options},
        created_by=current_user.username,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    from app.auth import build_mock_review_findings

    findings = build_mock_review_findings(payload.file_ids or [])
    for finding in findings:
        db.add(
            Finding(
                id=generate_id("finding"),
                review_run_id=run.id,
                project_id=project_id,
                file_id=finding["file_id"],
                category=finding["category"],
                message=finding["message"],
                severity=finding["severity"],
                machine_result="uncertain",
                review_status="pending",
                confidence=finding["confidence"],
                source=finding["source"],
            )
        )
    db.commit()
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


@router.get("/{project_id}/reviews", response_model=list[ReviewRunOut])
def list_reviews(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> list[ReviewRun]:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return db.query(ReviewRun).filter(ReviewRun.project_id == project_id).order_by(ReviewRun.started_at.desc()).all()


@router.get("/{project_id}/reviews/{review_id}/findings", response_model=list[FindingOut])
def list_findings(
    project_id: str,
    review_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> list[Finding]:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return db.query(Finding).filter(Finding.project_id == project_id, Finding.review_run_id == review_id).all()
