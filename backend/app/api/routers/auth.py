"""Đăng nhập và thông tin tài khoản."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.security import create_access_token, verify_password
from ...db.base import get_db
from ...db.models import AuditLog, User
from ...schemas import LoginIn, TokenOut
from ..deps import current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut, summary="Đăng nhập, nhận JWT")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if not user or not user.active or not verify_password(body.password, user.password_hash):
        # Thông báo chung cho cả hai trường hợp để không lộ tài khoản nào tồn tại.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sai tài khoản hoặc mật khẩu")
    db.add(AuditLog(actor=user.username, action="auth.login"))
    db.commit()
    cfg = get_settings()
    return TokenOut(access_token=create_access_token(user.username, user.role),
                    role=user.role, username=user.username,
                    expires_in_minutes=cfg.access_token_expire_minutes)


@router.get("/me", summary="Thông tin tài khoản đang đăng nhập")
def me(user: User = Depends(current_user)):
    return {"username": user.username, "role": user.role,
            "full_name": user.full_name, "active": user.active}
