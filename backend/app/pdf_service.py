from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import fitz  # type: ignore
except Exception:  # pragma: no cover - optional dependency for local environments
    fitz = None


def _estimate_page_count(file_path: Path) -> int:
    try:
        size = file_path.stat().st_size
        if size <= 0:
            return 0
        return max(1, int(size / 50000))
    except OSError:
        return 0


def extract_pdf_metadata(file_path: Path) -> dict[str, Any]:
    """Extract light-weight PDF metadata for the review pipeline.

    This keeps the implementation simple and robust in local/dev environments even if
    PyMuPDF is not installed yet. It returns page count, pdf type and basic page
    information used by the API and frontend.
    """
    result: dict[str, Any] = {"page_count": 0, "pdf_type": "unknown", "pages": []}

    if fitz is None:
        page_count = _estimate_page_count(file_path)
        result["page_count"] = page_count
        result["pdf_type"] = "native" if page_count else "unknown"
        for page_number in range(1, page_count + 1):
            result["pages"].append({
                "page_number": page_number,
                "width": 595,
                "height": 842,
                "text_chars": 0,
                "text_quality": "unknown",
            })
        return result

    try:
        doc = fitz.open(file_path)
        page_count = doc.page_count
        result["page_count"] = page_count

        if page_count == 0:
            result["pdf_type"] = "unknown"
            return result

        text_pages = 0
        for page_index in range(page_count):
            page = doc[page_index]
            width = round(float(page.rect.width), 2)
            height = round(float(page.rect.height), 2)
            text = page.get_text("text") or ""
            text_chars = len(text.strip())
            if text_chars > 0:
                text_pages += 1
            result["pages"].append({
                "page_number": page_index + 1,
                "width": width,
                "height": height,
                "text_chars": text_chars,
                "text_quality": "good" if text_chars > 200 else "mixed" if text_chars > 0 else "scanned",
            })

        if text_pages == page_count:
            result["pdf_type"] = "native"
        elif text_pages > 0:
            result["pdf_type"] = "mixed"
        else:
            result["pdf_type"] = "scanned"

        doc.close()
        return result
    except Exception:
        page_count = _estimate_page_count(file_path)
        result["page_count"] = page_count
        result["pdf_type"] = "native" if page_count else "unknown"
        for page_number in range(1, page_count + 1):
            result["pages"].append({
                "page_number": page_number,
                "width": 595,
                "height": 842,
                "text_chars": 0,
                "text_quality": "unknown",
            })
        return result
