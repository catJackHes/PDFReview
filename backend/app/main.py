from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.companies import router as companies_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.rules import router as rules_router
from app.config import settings
from app.db import SessionLocal
from app.services import ensure_admin_user

app = FastAPI(title="PDF 招投标审查系统", version="0.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    expose_headers=["X-PDF-Page-Width", "X-PDF-Page-Height"],
)


@app.on_event("startup")
def startup_event() -> None:
    # Schema is managed by Alembic at container startup, not create_all.
    db = SessionLocal()
    try:
        ensure_admin_user(db)
    finally:
        db.close()


for route in (health_router, auth_router, projects_router, companies_router, rules_router, reviews_router, documents_router):
    app.include_router(route, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "PDF 招投标审查系统 API 已启动"}
