from __future__ import annotations

from threading import Lock
from typing import Any

_engine: Any | None = None
_lock = Lock()


def get_ocr_engine(engine_class: Any) -> Any:
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                from app.config import settings
                options: dict[str, Any] = {
                    "use_angle_cls": True,
                    "lang": settings.ocr_language,
                    "use_gpu": False,
                    "show_log": False,
                }
                if settings.ocr_model_dir:
                    options["det_model_dir"] = settings.ocr_model_dir
                _engine = engine_class(**options)
    return _engine
