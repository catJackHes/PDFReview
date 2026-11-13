from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RuleVersion
from app.services import get_current_user

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleCreateRequest(BaseModel):
    rule_key: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    category: str = Field(default="seal")
    applies_to: str = Field(default="pdf")
    severity: str = Field(default="medium")
    message_template: str = Field(default="规则命中")
    review_required: bool = True
    parameters: dict = Field(default_factory=dict)


@router.get("")
def list_rules(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[RuleVersion]:
    return db.query(RuleVersion).order_by(RuleVersion.created_at.desc()).all()


@router.post("")
def create_rule(
    payload: RuleCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> RuleVersion:
    rule = RuleVersion(
        id=f"rule_{len(db.query(RuleVersion).all()) + 1}",
        rule_key=payload.rule_key,
        version=payload.version,
        name=payload.name,
        category=payload.category,
        applies_to=payload.applies_to,
        severity=payload.severity,
        message_template=payload.message_template,
        review_required=payload.review_required,
        parameters=payload.parameters,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule
