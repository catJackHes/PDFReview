from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Company
from app.services import get_current_user

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("")
def list_companies(db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> list[Company]:
    return db.query(Company).all()


@router.post("")
def create_company(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> Company:
    name = payload.get("canonical_name")
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="canonical_name is required")
    company = Company(id=f"company_{len(db.query(Company).all()) + 1}", canonical_name=name, is_active=True)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company
