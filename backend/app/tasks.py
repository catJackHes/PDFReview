from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from redis import Redis
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import AuditEvent, Evidence, Finding, ProjectFile, ReviewRun, RuleVersion
from app.review_engine import execute_rules, persist_extracted_pages
from app.ocr_service import extract_pdf_pages
from app.services import generate_id


def process_review(review_run_id: str) -> None:
    db: Session = SessionLocal()
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
            raise RuntimeError("Review input file missing")
        for item in file_snapshots:
            if file_map[item["file_id"]].sha256 != item.get("sha256"):
                raise RuntimeError("Review input hash changed")
        rule_ids = [item.get("id") for item in rule_snapshots if item.get("id")]
        rules = db.query(RuleVersion).filter(RuleVersion.id.in_(rule_ids)).all() if rule_ids else []
        rule_map = {item.id: item for item in rules}
        snapshot_rules = []
        for item in rule_snapshots:
            if item.get("id") in rule_map:
                rule = rule_map[item["id"]]
                rule.parameters = item.get("parameters", {})
                rule.category = item.get("category", rule.category)
                rule.severity = item.get("severity", rule.severity)
                rule.message_template = item.get("message_template", rule.message_template)
                snapshot_rules.append(rule)

        run.status, run.phase, run.progress = "extracting", "extracting", 10
        db.commit()
        findings: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for index, file_snapshot in enumerate(file_snapshots):
            file = file_map[file_snapshot["file_id"]]
            pages, page_errors = extract_pdf_pages(file.storage_key)
            persist_extracted_pages(db, file, pages)
            findings_for_file, rule_error = execute_rules(file, snapshot_rules, pages)
            findings.extend(findings_for_file)
            errors.extend({"file_id": file.id, "page_number": str(e["page_number"]), "message": e["message"]} for e in page_errors)
            if rule_error:
                errors.append({"file_id": file.id, "message": rule_error})
            run.status, run.phase = "analyzing", "analyzing"
            run.progress = min(90, 15 + int(75 * (index + 1) / max(1, len(file_snapshots))))
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
            for item_evidence in item.get("evidence", []):
                db.add(Evidence(
                    id=generate_id("evidence"), finding_id=finding.id, file_id=item["file_id"],
                    page_number=item_evidence["page_number"], text_excerpt=item_evidence.get("text_excerpt"),
                    bbox=item_evidence.get("bbox", []), source=item_evidence.get("source", "unknown"),
                    confidence=item_evidence.get("confidence", 0.0),
                ))
        run.config_snapshot = {**snapshot, "processing_errors": errors, "ocr": {"enabled": settings.ocr_enabled, "language": settings.ocr_language, "dpi": settings.ocr_dpi}}
        run.phase, run.progress = "completed", 100
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
        run = db.query(ReviewRun).filter(ReviewRun.id == review_run_id).first()
        if run:
            run.status, run.phase = "failed", "failed"
            run.completed_at = datetime.now(timezone.utc)
            run.config_snapshot = {**(run.config_snapshot or {}), "safe_error": "后台 PDF/OCR 审查失败，请检查服务状态"}
            db.add(AuditEvent(id=generate_id("audit"), actor_id=run.created_by, action="review_run.failed", resource_type="review_run", resource_id=run.id, metadata_json={"reason": "worker_error"}))
            db.commit()
        raise
    finally:
        db.close()
