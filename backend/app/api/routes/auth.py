from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.db import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse
from app.services import authenticate_user, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user = authenticate_user(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    return {"access_token": create_access_token(user.username), "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: User = Depends(get_current_user)) -> None:
    # Bearer tokens are stateless; the client must discard its token. Server-side
    # revocation will be added with persisted sessions rather than implying this revokes it.
    return None


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict[str, str | bool]:
    return {"id": current_user.id, "username": current_user.username, "is_active": current_user.is_active}
