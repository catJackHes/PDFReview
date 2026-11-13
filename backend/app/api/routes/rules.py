from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RuleVersion
from app.services import generate_id, get_current_user

router = APIRouter(prefix="/rules", tags=["rules"])
SUPPORTED_CHECKS = {"required_keyword", "prohibited_keyword", "page_count_min", "page_count_max"}
SEVERITIES = {"low", "medium", "high", "critical"}


class RuleCreateRequest(BaseModel):
    rule_key: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="format", min_length=1, max_length=80)
    applies_to: str = Field(default="pdf", min_length=1, max_length=80)
    severity: str = "medium"
    message_template: str = Field(default="规则命中", min_length=1, max_length=2000)
    review_required: bool = True
    parameters: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rule(self) -> "RuleCreateRequest":
        if self.severity not in SEVERITIES:
            raise ValueError("unsupported severity")
        check_type = self.parameters.get("check_type")
        if check_type not in SUPPORTED_CHECKS:
            raise ValueError("parameters.check_type must be one of the supported check types")
        if check_type in {"required_keyword", "prohibited_keyword"}:
            keywords = self.parameters.get("keywords")
            if not isinstance(keywords, list) or not keywords or any(not isinstance(item, str) or not item.strip() for item in keywords):
                raise ValueError("keyword rules require a non-empty keywords list")
            if len(keywords) > 100 or any(len(item) > 200 for item in keywords):
                raise ValueError("keyword list exceeds limits")
        else:
            value = self.parameters.get("value")
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("page count rules require a positive integer value")
        return self


@router.get("")
def list_rules(
    enabled_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[RuleVersion]:
    query = db.query(RuleVersion)
    if enabled_only:
        query = query.filter(RuleVersion.is_enabled.is_(True))
    return query.order_by(RuleVersion.rule_key.asc(), RuleVersion.created_at.desc()).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: RuleCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> RuleVersion:
    existing = db.query(RuleVersion).filter(
        RuleVersion.rule_key == payload.rule_key,
        RuleVersion.version == payload.version,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Rule key/version already exists")
    rule = RuleVersion(
        id=generate_id("rule"), rule_key=payload.rule_key, version=payload.version,
        name=payload.name, category=payload.category, applies_to=payload.applies_to,
        severity=payload.severity, message_template=payload.message_template,
        review_required=payload.review_required, parameters=payload.parameters,
        is_enabled=True, created_by=current_user.id,
    )
    db.add(rule)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Rule key/version already exists") from exc
    db.refresh(rule)
    return rule


@router.patch("/{rule_id}/enabled")
def set_rule_enabled(
    rule_id: str,
    enabled: bool,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> RuleVersion:
    rule = db.query(RuleVersion).filter(RuleVersion.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_enabled = enabled
    db.commit()
    db.refresh(rule)
    return rule
