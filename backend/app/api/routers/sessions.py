"""Quản lý ca / buổi học."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.base import get_db
from ...db.models import AuditLog
from ...db.models import Session as ClassSession
from ...schemas import SessionIn, SessionOut
from ..deps import require

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionOut], summary="Danh sách ca")
def list_sessions(active_only: bool = False, db: Session = Depends(get_db),
                  _=Depends(require("viewer"))):
    stmt = select(ClassSession).order_by(ClassSession.start_time)
    if active_only:
        stmt = stmt.where(ClassSession.active.is_(True))
    return db.execute(stmt).scalars().all()


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED,
             summary="Tạo ca mới")
def create_session(body: SessionIn, db: Session = Depends(get_db),
                   user=Depends(require("operator"))):
    if body.end_time <= body.start_time:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Giờ kết thúc phải sau giờ bắt đầu")
    s = ClassSession(**body.model_dump())
    db.add(s)
    db.add(AuditLog(actor=user.username, action="session.create",
                    entity="session", entity_id=body.name))
    db.commit()
    db.refresh(s)
    return s


@router.patch("/{session_id}", response_model=SessionOut, summary="Sửa ca")
def update_session(session_id: int, body: SessionIn, db: Session = Depends(get_db),
                   user=Depends(require("operator"))):
    s = db.get(ClassSession, session_id)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy ca")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    db.add(AuditLog(actor=user.username, action="session.update",
                    entity="session", entity_id=str(session_id)))
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{session_id}", summary="Xoá ca")
def delete_session(session_id: int, db: Session = Depends(get_db),
                   user=Depends(require("admin"))):
    s = db.get(ClassSession, session_id)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy ca")
    name = s.name
    db.delete(s)
    db.add(AuditLog(actor=user.username, action="session.delete",
                    entity="session", entity_id=name))
    db.commit()
    return {"deleted": name}
