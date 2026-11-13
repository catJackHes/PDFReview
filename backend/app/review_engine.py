from __future__ import annotations

from typing import Any

from app.models import ProjectFile


def build_review_findings_for_file_ids(file_ids: list[str], db: Any) -> list[dict[str, Any]]:
    """Generate deterministic mock review findings aligned to the phase 2 review workflow.

    Each finding includes a small evidence list for the frontend to render and for the API to
    persist as a traceable result.
    """
    findings: list[dict[str, Any]] = []
    for index, file_id in enumerate(file_ids, start=1):
        file_record = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
        page_count = file_record.page_count if file_record else 1
        category = "seal" if index % 2 == 1 else "format"
        severity = "medium" if index % 2 == 1 else "low"
        message = (
            "检测到疑似印章/签署区缺失，建议人工核验。"
            if category == "seal"
            else "文档结构或关键信息存在异常，建议人工确认。"
        )
        findings.append(
            {
                "file_id": file_id,
                "category": category,
                "severity": severity,
                "message": message,
                "confidence": 0.72 if category == "seal" else 0.61,
                "source": "rule_engine_v1",
                "evidence": [
                    {
                        "page_number": max(1, min(page_count, 1)),
                        "text_excerpt": "签章/关键字段定位线索",
                        "bbox": [80, 200, 240, 320],
                        "source": "rule_engine_v1",
                        "confidence": 0.7,
                    }
                ],
            }
        )
    return findings
