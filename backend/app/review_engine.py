from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ProjectFile, RuleVersion
from app.services import generate_id

SUPPORTED_CHECKS = {"required_keyword", "prohibited_keyword", "page_count_min", "page_count_max"}


def _pdf_path(storage_key: str) -> Path:
    root = Path(settings.upload_dir).resolve()
    path = (root / storage_key).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise FileNotFoundError("Stored PDF not found")
    return path


def _page_text(document: fitz.Document) -> list[str]:
    return [(page.get_text("text") or "").strip() for page in document]


def _bbox_for_term(page: fitz.Page, term: str) -> list[float] | None:
    rectangles = page.search_for(term, quads=False)
    if not rectangles:
        return None
    rect = rectangles[0]
    return [round(float(rect.x0), 2), round(float(rect.y0), 2), round(float(rect.x1), 2), round(float(rect.y1), 2)]


def _rule_applies(rule: RuleVersion, file: ProjectFile) -> bool:
    applies = (rule.applies_to or "pdf").strip().lower()
    return applies in {"pdf", "all", file.file_type.lower()}


def _finding(rule: RuleVersion, file: ProjectFile, message: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": generate_id("finding"),
        "file_id": file.id,
        "rule_version_id": rule.id,
        "category": rule.category,
        "message": message,
        "severity": rule.severity,
        "machine_result": "detected",
        "review_status": "pending",
        "confidence": 1.0 if evidence else 0.0,
        "source": f"rule:{rule.rule_key}@{rule.version}",
        "evidence": evidence,
    }


def execute_rules(file: ProjectFile, rules: list[RuleVersion]) -> tuple[list[dict[str, Any]], str | None]:
    """Run only the explicitly supported, parameterized checks; never evaluate user code."""
    path = _pdf_path(file.storage_key)
    findings: list[dict[str, Any]] = []
    try:
        with fitz.open(path) as document:
            if document.needs_pass:
                return [], "加密 PDF 无法解析"
            pages = list(document)
            texts = _page_text(document)

            for rule in rules:
                if not _rule_applies(rule, file):
                    continue
                params = rule.parameters or {}
                check_type = params.get("check_type")
                if check_type not in SUPPORTED_CHECKS:
                    continue

                if check_type in {"required_keyword", "prohibited_keyword"}:
                    terms = params.get("keywords", [])
                    if not isinstance(terms, list):
                        continue
                    for term in terms:
                        if not isinstance(term, str) or not term.strip():
                            continue
                        matches: list[dict[str, Any]] = []
                        for index, page in enumerate(pages):
                            bbox = _bbox_for_term(page, term)
                            if bbox:
                                matches.append({
                                    "page_number": index + 1,
                                    "text_excerpt": term,
                                    "bbox": bbox,
                                    "source": "pymupdf_text_search",
                                    "confidence": 1.0,
                                })
                        violated = (check_type == "required_keyword" and not matches) or (check_type == "prohibited_keyword" and bool(matches))
                        if violated:
                            message = rule.message_template.format(keyword=term, file=file.display_name)
                            findings.append(_finding(rule, file, message, matches))
                elif check_type == "page_count_min":
                    minimum = params.get("value")
                    if isinstance(minimum, int) and not isinstance(minimum, bool) and len(pages) < minimum:
                        findings.append(_finding(rule, file, rule.message_template.format(value=minimum, actual=len(pages)), []))
                elif check_type == "page_count_max":
                    maximum = params.get("value")
                    if isinstance(maximum, int) and not isinstance(maximum, bool) and len(pages) > maximum:
                        findings.append(_finding(rule, file, rule.message_template.format(value=maximum, actual=len(pages)), []))
            return findings, None
    except Exception:
        return [], "PDF 解析失败，请人工检查文件"


def run_review(db: Session, files: list[ProjectFile], rules: list[RuleVersion]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    findings: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for file in files:
        file_findings, error = execute_rules(file, rules)
        findings.extend(file_findings)
        if error:
            errors.append({"file_id": file.id, "message": error})
    return findings, errors
