from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from redis import Redis
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import AuditEvent, Evidence, Finding, ProjectFile, ReviewRun, RuleVersion
from app.review_engine import execute_rules
from app.services import generate_id


def process_review(review_run_id: str) -> None:
    """RQ worker entry point. The worker owns its DB session and persists each stage."""
    db: Session = SessionLocal()
    run = None
    try:
        run = db.query(ReviewRun).filter(ReviewRun.id == review_run_id).first()
        if run is None or run.status in {"completed", "partial", "failed"}:
            return

        snapshot = run.config_snapshot or {}
        file_snapshots = snapshot.get("files", [])
        rule_snapshots = snapshot.get("rules", [])
        file_ids = [item.get("file_id") for item in file_snapshots if item.get("file_id")]
        files = db.query(ProjectFile).filter(ProjectFile.project_id == run.project_id, ProjectFile.id.in_(file_ids)).all()
        file_map = {item.id: item for item in files}
        if len(file_map) != len(file_ids):
            raise RuntimeError("A review input file is missing")
        for item in file_snapshots:
            if file_map[item["file_id"]].sha256 != item.get("sha256"):
                raise RuntimeError("A review input file hash changed")

        rule_ids = [item.get("id") for item in rule_snapshots if item.get("id")]
        rules = db.query(RuleVersion).filter(RuleVersion.id.in_(rule_ids)).all() if rule_ids else []
        rule_map = {rule.id: rule for rule in rules}
        # Evaluation uses the immutable JSON snapshot, not mutable current rule rows.
        snapshot_rules = []
        for item in rule_snapshots:
            if item.get("id") in rule_map:
                rule = rule_map[item["id"]]
                rule.parameters = item.get("parameters", {})
                rule.category = item.get("category", rule.category)
                rule.severity = item.get("severity", rule.severity)
                rule.message_template = item.get("message_template", rule.message_template)
                snapshot_rules.append(rule)

        run.status = "extracting"
        run.phase = "extracting"
        run.progress = 15
        db.commit()

        findings: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for index, file_snapshot in enumerate(file_snapshots):
            file_record = file_map[file_snapshot["file_id"]]
            file_findings, error = execute_rules(file_record, snapshot_rules)
            findings.extend(file_findings)
            if error:
                errors.append({"file_id": file_record.id, "message": error})
            run.status = "analyzing"
            run.phase = "analyzing"
            run.progress = min(90, 20 + int(70 * (index + 1) / max(1, len(file_snapshots))))
            db.commit()

        for item in findings:
            finding = Finding(
                id=item["id"], review_run_id=run.id, project_id=run.project_id,
                file_id=item["file_id"], rule_version_id=item.get("rule_version_id"),
                category=item["category"], message=item["message"], severity=item["severity"],
                machine_result=item["machine_result"], review_status=item["review_status"],
                confidence=item["confidence"], source=item["source"],
            )
            db.add(finding)
            db.flush()
            for evidence_item in item.get("evidence", []):
                db.add(Evidence(
                    id=generate_id("evidence"), finding_id=finding.id, file_id=item["file_id"],
                    page_number=evidence_item["page_number"], text_excerpt=evidence_item.get("text_excerpt"),
                    bbox=evidence_item.get("bbox", []), source=evidence_item["source"],
                    confidence=evidence_item["confidence"],
                ))

        run.config_snapshot = {**snapshot, "processing_errors": errors}
        run.phase = "completed"
        run.progress = 100
        run.status = "partial" if errors and findings else "failed" if errors else "completed"
        run.completed_at = datetime.now(timezone.utc)
        db.add(AuditEvent(
            id=generate_id("audit"), actor_id=run.created_by, action="review_run.completed",
            resource_type="review_run", resource_id=run.id,
            metadata_json={"status": run.status, "finding_count": len(findings), "error_count": len(errors)},
        ))
        db.commit()
    except Exception:
        db.rollback()
        if run is not None:
            run = db.query(ReviewRun).filter(ReviewRun.id == review_run_id).first()
            if run is not None:
                run.status = "failed"
                run.phase = "failed"
                run.completed_at = datetime.now(timezone.utc)
                run.config_snapshot = {**(run.config_snapshot or {}), "safe_error": "后台审查执行失败，请检查服务日志"}
                db.add(AuditEvent(
                    id=generate_id("audit"), actor_id=run.created_by, action="review_run.failed",
                    resource_type="review_run", resource_id=run.id,
                    metadata_json={"reason": "worker_error"},
                ))
                db.commit()
        raise
    finally:
        db.close()
