from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Evidence, Finding, Project, ProjectFile, ReviewRun
from app.review_engine import build_review_findings_for_file_ids
from app.schemas import FindingOut, ReviewRunOut
from app.services import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/{project_id}/reviews", response_model=ReviewRunOut)
def create_review(
    project_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ReviewRun:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    file_ids = payload.get("file_ids", [])
    run = ReviewRun(
        id=f"review_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        project_id=project_id,
        status="extracting",
        phase="extracting",
        progress=10,
        config_snapshot={"rule_set": payload.get("rule_set", "default"), "options": payload.get("options", {})},
        created_by=current_user.username,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    run.phase = "analyzing"
    run.progress = 60
    db.commit()

    findings_payload = build_review_findings_for_file_ids(file_ids, db)
    for item in findings_payload:
        finding = Finding(
            id=f"finding_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_{len(findings_payload)}",
            review_run_id=run.id,
            project_id=project_id,
            file_id=item["file_id"],
            category=item["category"],
            message=item["message"],
            severity=item["severity"],
            machine_result="uncertain",
            review_status="pending",
            confidence=item["confidence"],
            source=item["source"],
        )
        db.add(finding)
        db.commit()
        db.refresh(finding)
        for evidence_item in item.get("evidence", []):
            evidence = Evidence(
                id=f"ev_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_{len(item.get('evidence', []))}",
                finding_id=finding.id,
                file_id=item["file_id"],
                page_number=int(evidence_item.get("page_number", 1)),
                text_excerpt=evidence_item.get("text_excerpt"),
                bbox=evidence_item.get("bbox", []),
                source=evidence_item.get("source", "rule_engine_v1"),
                confidence=float(evidence_item.get("confidence", 0.0)),
            )
            db.add(evidence)

    run.phase = "completed"
    run.progress = 100
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


@router.get("/{project_id}/reviews/{review_id}/findings")
def list_findings(
    project_id: str,
    review_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[Finding]:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return db.query(Finding).filter(Finding.project_id == project_id, Finding.review_run_id == review_id).all()
