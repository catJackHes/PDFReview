from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import fitz
from sqlalchemy.orm import Session

from app.config import settings
from app.models import FilePage, ProjectFile, RuleVersion, TextBlock
from app.ocr_service import extract_pdf_pages
from app.services import generate_id

SUPPORTED_CHECKS = {"required_keyword", "prohibited_keyword", "page_count_min", "page_count_max"}


def _pdf_path(storage_key: str):
    from pathlib import Path
    root = Path(settings.upload_dir).resolve()
    path = (root / storage_key).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise FileNotFoundError("Stored PDF not found")
    return path


def _rule_applies(rule: RuleVersion, file: ProjectFile) -> bool:
    return (rule.applies_to or "pdf").strip().lower() in {"pdf", "all", file.file_type.lower()}


def _finding(rule: RuleVersion, file: ProjectFile, message: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": generate_id("finding"), "file_id": file.id, "rule_version_id": rule.id,
        "category": rule.category, "message": message, "severity": rule.severity,
        "machine_result": "detected", "review_status": "pending",
        "confidence": max((item.get("confidence", 0.0) or 0.0 for item in evidence), default=0.0),
        "source": f"rule:{rule.rule_key}@{rule.version}", "evidence": evidence,
    }


def _term_evidence(term: str, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    needle = term.casefold()
    for page in pages:
        for block in page.get("blocks", []):
            if needle in str(block.get("text", "")).casefold():
                evidence.append({
                    "page_number": page["page_number"], "text_excerpt": block["text"][:500],
                    "bbox": block["bbox"], "source": block.get("source", "unknown"),
                    "confidence": block.get("confidence") if block.get("confidence") is not None else 1.0,
                })
    return evidence


def execute_rules(file: ProjectFile, rules: list[RuleVersion], extracted_pages: list[dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], str | None]:
    """Run only supported checks against native text and OCR text blocks."""
    try:
        if extracted_pages is None:
            extracted_pages, _ = extract_pdf_pages(file.storage_key)
        findings: list[dict[str, Any]] = []
        uncertain_required = any(page.get("ocr_status") in {"disabled", "failed", "no_text"} for page in extracted_pages)
        page_count = len(extracted_pages)

        for rule in rules:
            if not _rule_applies(rule, file):
                continue
            params = rule.parameters or {}
            check_type = params.get("check_type")
            if check_type not in SUPPORTED_CHECKS:
                continue
            if check_type in {"required_keyword", "prohibited_keyword"}:
                keywords = params.get("keywords", [])
                if not isinstance(keywords, list):
                    continue
                for keyword in keywords:
                    if not isinstance(keyword, str) or not keyword.strip():
                        continue
                    evidence = _term_evidence(keyword, extracted_pages)
                    if check_type == "prohibited_keyword" and evidence:
                        findings.append(_finding(rule, file, rule.message_template.format(keyword=keyword, file=file.display_name), evidence))
                    elif check_type == "required_keyword" and not evidence and not uncertain_required:
                        findings.append(_finding(rule, file, rule.message_template.format(keyword=keyword, file=file.display_name), []))
            elif check_type == "page_count_min":
                value = params.get("value")
                if isinstance(value, int) and not isinstance(value, bool) and value > 0 and page_count < value:
                    findings.append(_finding(rule, file, rule.message_template.format(value=value, actual=page_count), []))
            elif check_type == "page_count_max":
                value = params.get("value")
                if isinstance(value, int) and not isinstance(value, bool) and value > 0 and page_count > value:
                    findings.append(_finding(rule, file, rule.message_template.format(value=value, actual=page_count), []))
        return findings, None
    except Exception:
        return [], "PDF 文本/OCR 解析失败，请人工检查文件"


def persist_extracted_pages(db: Session, file: ProjectFile, pages: list[dict[str, Any]]) -> None:
    for page_data in pages:
        row = db.query(FilePage).filter(FilePage.file_id == file.id, FilePage.page_number == page_data["page_number"]).first()
        if row is None:
            row = FilePage(
                id=generate_id("page"), file_id=file.id, page_number=page_data["page_number"],
                width_pt=page_data["width_pt"], height_pt=page_data["height_pt"],
                rotation=page_data["rotation"], native_text_chars=page_data["native_text_chars"],
                text_quality=page_data["text_quality"], ocr_status=page_data["ocr_status"],
                parser_version="pymupdf", ocr_version="paddleocr-2.9.1" if page_data["ocr_status"] in {"completed", "no_text", "failed"} else None,
            )
            db.add(row)
            db.flush()
        else:
            for key in ("width_pt", "height_pt", "rotation", "native_text_chars", "text_quality", "ocr_status"):
                setattr(row, key, page_data[key])
            row.updated_at = datetime.now(timezone.utc)
            db.query(TextBlock).filter(TextBlock.file_page_id == row.id).delete(synchronize_session=False)
        for block in page_data.get("blocks", []):
            db.add(TextBlock(
                id=generate_id("text"), file_page_id=row.id, text=block["text"], bbox=block["bbox"],
                source=block["source"], confidence=block.get("confidence"),
            ))


def run_review(db: Session, files: list[ProjectFile], rules: list[RuleVersion]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    findings: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for file in files:
        try:
            pages, page_errors = extract_pdf_pages(file.storage_key)
            persist_extracted_pages(db, file, pages)
            for error in page_errors:
                errors.append({"file_id": file.id, "page_number": str(error["page_number"]), "message": error["message"]})
            file_findings, error_message = execute_rules(file, rules, pages)
            findings.extend(file_findings)
            if error_message:
                errors.append({"file_id": file.id, "message": error_message})
        except Exception:
            errors.append({"file_id": file.id, "message": "文件解析失败，需人工核验"})
    return findings, errors
