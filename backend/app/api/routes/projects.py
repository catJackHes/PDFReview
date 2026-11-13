from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from redis import Redis
from rq import Queue
from rq.exceptions import RedisError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import AuditEvent, Evidence, Finding, Project, ProjectFile, ReviewRun, RuleVersion
from app.services import generate_id, get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


class ReviewRequest(BaseModel):
    file_ids: list[str] = Field(min_length=1, max_length=100)
    rule_set: str = Field(default="default", min_length=1, max_length=100)
    options: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def as_schema(cls):
        return cls


def _owned_project(db: Session, project_id: str, username: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.created_by == username).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/reviews", status_code=status.HTTP_202_ACCEPTED)
def create_review(
    project_id: str,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    project = _owned_project(db, project_id, current_user.username)
    if len(set(payload.file_ids)) != len(payload.file_ids):
        raise HTTPException(status_code=422, detail="file_ids must not contain duplicates")

    files = db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id,
        ProjectFile.id.in_(payload.file_ids),
    ).all()
    if len(files) != len(payload.file_ids):
        raise HTTPException(status_code=404, detail="One or more files were not found in this project")

    enabled_rules = db.query(RuleVersion).filter(RuleVersion.is_enabled.is_(True)).order_by(
        RuleVersion.rule_key.asc(), RuleVersion.created_at.desc()
    ).all()
    active_rules: dict[str, RuleVersion] = {}
    for rule in enabled_rules:
        active_rules.setdefault(rule.rule_key, rule)
    rules = list(active_rules.values())

    run = ReviewRun(
        id=generate_id("review"), project_id=project_id, status="queued", phase="queued", progress=0,
        started_at=datetime.now(timezone.utc), engine_version="deterministic-rules-v1",
        config_snapshot={
            "rule_set": payload.rule_set,
            "options": payload.options,
            "idempotency_key": idempotency_key,
            "files": [{"file_id": f.id, "sha256": f.sha256, "file_type": f.file_type} for f in files],
            "rules": [{"id": r.id, "key": r.rule_key, "version": r.version, "parameters": r.parameters,
                       "category": r.category, "severity": r.severity, "message_template": r.message_template}
                      for r in rules],
        },
        created_by=current_user.username,
    )
    db.add(run)
    db.flush()
    db.add(AuditEvent(
        id=generate_id("audit"), actor_id=current_user.id, action="review_run.queued",
        resource_type="review_run", resource_id=run.id,
        metadata_json={"file_count": len(files), "rule_count": len(rules)},
    ))
    db.commit()
    db.refresh(run)

    try:
        redis = Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=3)
        redis.ping()
        queue = Queue(settings.queue_name, connection=redis, default_timeout=settings.review_job_timeout_seconds)
        queue.enqueue("app.tasks.process_review", run.id, job_id=f"review-{run.id}", result_ttl=86400, failure_ttl=604800)
    except Exception as exc:
        run.status = "failed"
        run.phase = "queueing"
        run.completed_at = datetime.now(timezone.utc)
        run.config_snapshot = {**(run.config_snapshot or {}), "safe_error": "后台队列不可用，审查任务未执行"}
        db.add(AuditEvent(
            id=generate_id("audit"), actor_id=current_user.id, action="review_run.enqueue_failed",
            resource_type="review_run", resource_id=run.id, metadata_json={"reason": "queue_unavailable"},
        ))
        db.commit()
        db.refresh(run)
    return {
        "id": run.id, "project_id": run.project_id, "status": run.status,
        "phase": run.phase, "progress": run.progress, "started_at": run.started_at,
        "completed_at": run.completed_at, "engine_version": run.engine_version,
        "config_snapshot": run.config_snapshot, "created_by": run.created_by,
    }


@router.get("/{project_id}/reviews")
def list_reviews(project_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> list[ReviewRun]:
    _owned_project(db, project_id, current_user.username)
    return db.query(ReviewRun).filter(ReviewRun.project_id == project_id).order_by(ReviewRun.started_at.desc()).all()


@router.get("/{project_id}/reviews/{review_id}")
def get_review(project_id: str, review_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> ReviewRun:
    _owned_project(db, project_id, current_user.username)
    run = db.query(ReviewRun).filter(ReviewRun.id == review_id, ReviewRun.project_id == project_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Review run not found")
    return run


@router.get("/{project_id}/reviews/{review_id}/findings")
def list_findings(project_id: str, review_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> list[Finding]:
    _owned_project(db, project_id, current_user.username)
    run = db.query(ReviewRun).filter(ReviewRun.id == review_id, ReviewRun.project_id == project_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Review run not found")
    return db.query(Finding).filter(Finding.project_id == project_id, Finding.review_run_id == review_id).order_by(Finding.created_at.asc()).all()
