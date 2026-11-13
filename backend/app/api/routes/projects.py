from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditEvent, Evidence, Finding, Project, ProjectFile, ReviewRun, RuleVersion
from app.review_engine import run_review
from app.services import generate_id, get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/{project_id}/reviews", response_model=dict)
def create_review(project_id: str, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> dict:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == current_user.username).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    file_ids = payload.get("file_ids", [])
    if not isinstance(file_ids, list) or not file_ids or len(file_ids) > 100:
        raise HTTPException(status_code=422, detail="file_ids must contain between 1 and 100 file IDs")
    if len(set(file_ids)) != len(file_ids):
        raise HTTPException(status_code=422, detail="file_ids must not contain duplicates")
    files = db.query(ProjectFile).filter(ProjectFile.project_id == project_id, ProjectFile.id.in_(file_ids)).all()
    if len(files) != len(file_ids):
        raise HTTPException(status_code=404, detail="One or more files were not found in this project")

    rules = db.query(RuleVersion).filter(RuleVersion.is_enabled.is_(True)).order_by(RuleVersion.rule_key.asc(), RuleVersion.version.desc()).all()
    # Keep one explicitly enabled version per stable key; previous versions remain immutable.
    active_by_key: dict[str, RuleVersion] = {}
    for rule in rules:
        active_by_key.setdefault(rule.rule_key, rule)
    rules = list(active_by_key.values())

    run = ReviewRun(
        id=generate_id("review"), project_id=project_id, status="extracting", phase="extracting", progress=10,
        started_at=datetime.now(timezone.utc), engine_version="deterministic-rules-v1",
        config_snapshot={
            "rule_set": payload.get("rule_set", "default"),
            "files": [{"file_id": file.id, "sha256": file.sha256, "file_type": file.file_type} for file in files],
            "rules": [{"id": rule.id, "key": rule.rule_key, "version": rule.version, "parameters": rule.parameters} for rule in rules],
        },
        created_by=current_user.username,
    )
    db.add(run)
    db.commit()

    try:
        run.phase = "analyzing"
        run.status = "analyzing"
        run.progress = 50
        db.commit()

        findings, errors = run_review(db, files, rules)
        for item in findings:
            finding = Finding(
                id=item["id"], review_run_id=run.id, project_id=project_id, file_id=item["file_id"],
                rule_version_id=item["rule_version_id"], category=item["category"], message=item["message"],
                severity=item["severity"], machine_result=item["machine_result"], review_status=item["review_status"],
                confidence=item["confidence"], source=item["source"],
            )
            db.add(finding)
            db.flush()
            for evidence_item in item["evidence"]:
                db.add(Evidence(
                    id=generate_id("evidence"), finding_id=finding.id, file_id=item["file_id"],
                    page_number=evidence_item["page_number"], text_excerpt=evidence_item["text_excerpt"],
                    bbox=evidence_item["bbox"], source=evidence_item["source"], confidence=evidence_item["confidence"],
                ))
        run.config_snapshot = {**run.config_snapshot, "processing_errors": errors}
        run.phase = "completed"
        run.progress = 100
        run.status = "partial" if errors and findings else "failed" if errors else "completed"
        run.completed_at = datetime.now(timezone.utc)
        db.add(AuditEvent(
            id=generate_id("audit"), actor_id=current_user.id, action="review_run.completed",
            resource_type="review_run", resource_id=run.id,
            metadata_json={"status": run.status, "finding_count": len(findings), "error_count": len(errors)},
        ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(run)
    return {
        "id": run.id, "project_id": run.project_id, "status": run.status, "phase": run.phase,
        "progress": run.progress, "started_at": run.started_at, "completed_at": run.completed_at,
        "engine_version": run.engine_version, "config_snapshot": run.config_snapshot, "created_by": run.created_by,
    }
