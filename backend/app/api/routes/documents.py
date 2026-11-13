from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Annotation, AuditEvent, Evidence, Finding, Project, ProjectFile
from app.services import generate_id, get_current_user

router = APIRouter(tags=["documents"])


class AnnotationCreate(BaseModel):
    page_number: int = Field(ge=1)
    bbox: list[float] = Field(min_length=4, max_length=4)
    label: str = Field(min_length=1, max_length=500)
    supersedes_id: str | None = None


def _get_project_file(db: Session, project_id: str, file_id: str, username: str) -> ProjectFile:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == username).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    record = db.query(ProjectFile).filter(ProjectFile.id == file_id, ProjectFile.project_id == project_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    return record


def _safe_pdf_path(storage_key: str) -> Path:
    root = Path(settings.upload_dir).resolve()
    path = (root / storage_key).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="Stored PDF not found")
    return path


@router.get("/projects/{project_id}/files/{file_id}/pages/{page_number}/image")
def get_page_image(
    project_id: str, file_id: str, page_number: int,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
) -> Response:
    record = _get_project_file(db, project_id, file_id, current_user.username)
    if page_number < 1:
        raise HTTPException(status_code=400, detail="Page number must be positive")
    try:
        with fitz.open(_safe_pdf_path(record.storage_key)) as document:
            if document.needs_pass:
                raise HTTPException(status_code=422, detail="Encrypted PDF is not supported")
            if page_number > document.page_count:
                raise HTTPException(status_code=404, detail="Page not found")
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            return Response(
                content=pixmap.tobytes("png"), media_type="image/png",
                headers={"X-PDF-Page-Width": str(page.rect.width), "X-PDF-Page-Height": str(page.rect.height), "Cache-Control": "no-store"},
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Unable to render this PDF page") from exc


@router.get("/projects/{project_id}/files/{file_id}/pages/{page_number}/text")
def get_page_text(
    project_id: str, file_id: str, page_number: int,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
) -> dict[str, Any]:
    record = _get_project_file(db, project_id, file_id, current_user.username)
    try:
        with fitz.open(_safe_pdf_path(record.storage_key)) as document:
            if document.needs_pass:
                raise HTTPException(status_code=422, detail="Encrypted PDF is not supported")
            if page_number < 1 or page_number > document.page_count:
                raise HTTPException(status_code=404, detail="Page not found")
            page = document.load_page(page_number - 1)
            blocks = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                text = "".join(span.get("text", "") for line in block.get("lines", []) for span in line.get("spans", [])).strip()
                if text:
                    blocks.append({"text": text, "bbox": [round(float(value), 2) for value in block["bbox"]]})
            return {"file_id": file_id, "page_number": page_number, "width": page.rect.width, "height": page.rect.height, "rotation": page.rotation, "blocks": blocks}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Unable to extract page text") from exc


@router.get("/findings/{finding_id}/annotations")
def list_annotations(
    finding_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user),
) -> list[dict[str, Any]]:
    finding = db.query(Finding).join(Project, Project.id == Finding.project_id).filter(Finding.id == finding_id, Project.created_by == current_user.username).first()
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    rows = db.query(Annotation).filter(Annotation.finding_id == finding_id).order_by(Annotation.created_at.asc()).all()
    return [{"id": row.id, "file_id": row.file_id, "page_number": row.page_number, "bbox": row.bbox, "label": row.label, "source": row.source, "supersedes_id": row.supersedes_id, "created_at": row.created_at} for row in rows]


@router.post("/findings/{finding_id}/annotations", status_code=201)
def create_annotation(
    finding_id: str, payload: AnnotationCreate,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
) -> dict[str, Any]:
    finding = db.query(Finding).join(Project, Project.id == Finding.project_id).filter(Finding.id == finding_id, Project.created_by == current_user.username).first()
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    if finding.file_id is None:
        raise HTTPException(status_code=400, detail="Finding is not associated with a file")
    evidence = db.query(Evidence).filter(Evidence.finding_id == finding.id, Evidence.file_id == finding.file_id, Evidence.page_number == payload.page_number).first()
    file_record = db.query(ProjectFile).filter(ProjectFile.id == finding.file_id, ProjectFile.project_id == finding.project_id).first()
    if file_record is None or payload.page_number > file_record.page_count:
        raise HTTPException(status_code=422, detail="Page is outside the finding's file")
    if payload.supersedes_id:
        previous = db.query(Annotation).filter(Annotation.id == payload.supersedes_id, Annotation.finding_id == finding_id).first()
        if previous is None:
            raise HTTPException(status_code=404, detail="Annotation to supersede not found")
    values = payload.bbox
    if any(value < 0 for value in values) or values[2] <= values[0] or values[3] <= values[1]:
        raise HTTPException(status_code=422, detail="Bounding box must be [x0, y0, x1, y1] with positive area")
    annotation = Annotation(id=generate_id("annotation"), finding_id=finding.id, file_id=finding.file_id, page_number=payload.page_number, bbox=values, label=payload.label, source="manual", supersedes_id=payload.supersedes_id, created_by=current_user.id)
    db.add(annotation)
    db.add(AuditEvent(id=generate_id("audit"), actor_id=current_user.id, action="finding.annotation_created", resource_type="finding", resource_id=finding.id, metadata_json={"annotation_id": annotation.id, "page_number": payload.page_number, "supersedes_id": payload.supersedes_id}))
    db.commit()
    db.refresh(annotation)
    return {"id": annotation.id, "finding_id": annotation.finding_id, "file_id": annotation.file_id, "page_number": annotation.page_number, "bbox": annotation.bbox, "label": annotation.label, "source": annotation.source, "supersedes_id": annotation.supersedes_id, "created_at": annotation.created_at}
