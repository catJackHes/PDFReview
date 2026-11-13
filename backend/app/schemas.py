from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    subject_company_id: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    subject_company_id: Optional[str] = None
    status: Optional[str] = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    subject_company_id: Optional[str]
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class FileUploadResponse(BaseModel):
    id: str
    project_id: str
    file_type: str
    display_name: str
    storage_key: str
    sha256: str
    size_bytes: int
    page_count: int
    pdf_type: str
    status: str
    created_at: datetime


class ReviewRequest(BaseModel):
    file_ids: list[str] = Field(default_factory=list)
    rule_set: str = "default"
    options: dict[str, Any] = Field(default_factory=dict)


class RuleVersionOut(BaseModel):
    id: str
    rule_key: str
    version: str
    name: str
    category: str
    applies_to: str
    severity: str
    message_template: str
    review_required: bool
    parameters: dict[str, Any]
    created_at: datetime


class EvidenceOut(BaseModel):
    id: str
    finding_id: str
    file_id: Optional[str]
    page_number: int
    text_excerpt: Optional[str]
    bbox: list[float]
    source: str
    confidence: float
    created_at: datetime


class ReviewRunOut(BaseModel):
    id: str
    project_id: str
    status: str
    phase: str
    progress: int
    started_at: datetime
    completed_at: Optional[datetime]
    engine_version: str
    config_snapshot: dict[str, Any]
    created_by: str


class FindingOut(BaseModel):
    id: str
    review_run_id: str
    project_id: str
    file_id: Optional[str]
    category: str
    status: str
    severity: str
    machine_result: str
    review_status: str
    message: str
    confidence: float
    source: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str = "ok"
