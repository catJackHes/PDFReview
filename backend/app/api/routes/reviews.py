from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditEvent, Evidence, Finding, Project, ReviewAction, ReviewRun
from app.services import generate_id, get_current_user

router = APIRouter(tags=["review-workflow"])


class ReviewActionRequest(BaseModel):
    action: Literal["confirmed_issue", "confirmed_ok", "unable_to_judge"]
    remark: str | None = Field(default=None, max_length=4000)


def _get_owned_finding(db: Session, finding_id: str, username: str) -> Finding:
    finding = (
        db.query(Finding)
        .join(Project, Project.id == Finding.project_id)
        .filter(Finding.id == finding_id, Project.created_by == username)
        .first()
    )
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")
    return finding


def _write_audit(db: Session, actor_id: str, action: str, resource_type: str, resource_id: str, details: dict[str, Any]) -> None:
    db.add(
        AuditEvent(
            id=generate_id("audit"),
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=details,
        )
    )


@router.post("/findings/{finding_id}/actions")
def create_review_action(
    finding_id: str,
    payload: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, Any]:
    finding = _get_owned_finding(db, finding_id, current_user.username)
    previous = finding.review_status
    finding.review_status = payload.action
    action = ReviewAction(
        id=generate_id("action"),
        finding_id=finding.id,
        actor_id=current_user.id,
        action=payload.action,
        previous_status=previous,
        new_status=payload.action,
        remark=payload.remark,
    )
    db.add(action)
    _write_audit(
        db,
        current_user.id,
        "finding.reviewed",
        "finding",
        finding.id,
        {"action": payload.action, "previous_status": previous},
    )
    db.commit()
    db.refresh(action)
    return {
        "id": action.id,
        "finding_id": action.finding_id,
        "action": action.action,
        "previous_status": action.previous_status,
        "new_status": action.new_status,
        "remark": action.remark,
        "created_at": action.created_at,
    }


@router.get("/findings/{finding_id}/history")
def get_finding_history(
    finding_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[dict[str, Any]]:
    finding = _get_owned_finding(db, finding_id, current_user.username)
    actions = db.query(ReviewAction).filter(ReviewAction.finding_id == finding.id).order_by(ReviewAction.created_at.asc()).all()
    return [
        {
            "id": item.id,
            "action": item.action,
            "previous_status": item.previous_status,
            "new_status": item.new_status,
            "remark": item.remark,
            "actor_id": item.actor_id,
            "created_at": item.created_at,
        }
        for item in actions
    ]


@router.get("/findings/{finding_id}/evidence")
def get_finding_evidence(
    finding_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[dict[str, Any]]:
    finding = _get_owned_finding(db, finding_id, current_user.username)
    evidence = db.query(Evidence).filter(Evidence.finding_id == finding.id).order_by(Evidence.page_number.asc()).all()
    return [
        {
            "id": item.id,
            "finding_id": item.finding_id,
            "file_id": item.file_id,
            "page_number": item.page_number,
            "text_excerpt": item.text_excerpt,
            "bbox": item.bbox,
            "source": item.source,
            "confidence": item.confidence,
            "created_at": item.created_at,
        }
        for item in evidence
    ]


@router.get("/reports/{run_id}")
def get_review_report(
    run_id: str,
    format: Literal["json", "html"] = Query(default="json"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    run = (
        db.query(ReviewRun)
        .join(Project, Project.id == ReviewRun.project_id)
        .filter(ReviewRun.id == run_id, Project.created_by == current_user.username)
        .first()
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review run not found")

    findings = db.query(Finding).filter(Finding.review_run_id == run.id).order_by(Finding.created_at.asc()).all()
    report_findings = []
    for finding in findings:
        evidence = db.query(Evidence).filter(Evidence.finding_id == finding.id).order_by(Evidence.page_number.asc()).all()
        report_findings.append({
            "id": finding.id,
            "file_id": finding.file_id,
            "category": finding.category,
            "machine_result": finding.machine_result,
            "review_status": finding.review_status,
            "severity": finding.severity,
            "message": finding.message,
            "confidence": finding.confidence,
            "source": finding.source,
            "evidence": [
                {
                    "page_number": item.page_number,
                    "text_excerpt": item.text_excerpt,
                    "bbox": item.bbox,
                    "source": item.source,
                    "confidence": item.confidence,
                }
                for item in evidence
            ],
        })

    report = {
        "review_run": {
            "id": run.id,
            "project_id": run.project_id,
            "status": run.status,
            "engine_version": run.engine_version,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "config_snapshot": run.config_snapshot,
        },
        "disclaimer": "自动检测仅供辅助审查；低置信度或无证据结果需由业务人员核验，不构成法律意见。",
        "findings": report_findings,
    }
    if format == "json":
        return JSONResponse(content=json.loads(json.dumps(report, default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value))))

    rows = []
    for finding in report_findings:
        evidence_text = "<br>".join(
            escape(f"第{item['page_number']}页：{item.get('text_excerpt') or '无文本证据'}")
            for item in finding["evidence"]
        ) or "无证据定位，请人工核验"
        rows.append(
            "<tr>"
            f"<td>{escape(finding['category'])}</td>"
            f"<td>{escape(finding['severity'])}</td>"
            f"<td>{escape(finding['machine_result'])}</td>"
            f"<td>{escape(finding['review_status'])}</td>"
            f"<td>{escape(finding['message'])}</td>"
            f"<td>{evidence_text}</td>"
            "</tr>"
        )
    html = (
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
        "<title>审查报告</title><body><h1>PDF 招投标审查报告</h1>"
        f"<p>运行：{escape(run.id)} | 状态：{escape(run.status)} | 引擎：{escape(run.engine_version)}</p>"
        f"<p>{escape(report['disclaimer'])}</p>"
        "<table border='1' cellspacing='0' cellpadding='6'><thead><tr>"
        "<th>类别</th><th>严重程度</th><th>机器结果</th><th>人工复核</th><th>说明</th><th>证据</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></body></html>"
    )
    return HTMLResponse(content=html)
