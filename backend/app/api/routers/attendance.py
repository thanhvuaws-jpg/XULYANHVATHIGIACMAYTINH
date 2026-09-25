"""Tra cứu điểm danh, số liệu tổng hợp, xuất báo cáo."""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.base import get_db
from ...db.models import Attendance, Person
from ...db.models import Session as ClassSession
from ...db.models import UnknownEvent
from ...schemas import AttendanceOut, SummaryOut, UnknownOut
from ...services import attendance as att_svc
from ..deps import require

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


def _rows(db: Session, day_from, day_to, person_id, session_id, status_, limit, offset):
    stmt = (select(Attendance, Person, ClassSession)
            .join(Person, Person.id == Attendance.person_id)
            .outerjoin(ClassSession, ClassSession.id == Attendance.session_id))
    if day_from:
        stmt = stmt.where(Attendance.day >= day_from)
    if day_to:
        stmt = stmt.where(Attendance.day <= day_to)
    if person_id:
        stmt = stmt.where(Attendance.person_id == person_id)
    if session_id:
        stmt = stmt.where(Attendance.session_id == session_id)
    if status_:
        stmt = stmt.where(Attendance.status == status_)
    stmt = stmt.order_by(Attendance.check_in.desc()).limit(limit).offset(offset)
    return db.execute(stmt).all()


@router.get("", response_model=list[AttendanceOut], summary="Danh sách bản ghi điểm danh")
def list_attendance(day_from: str | None = Query(None, description="YYYY-MM-DD"),
                    day_to: str | None = None, person_id: int | None = None,
                    session_id: int | None = None, status: str | None = None,
                    limit: int = Query(200, le=2000), offset: int = 0,
                    db: Session = Depends(get_db), _=Depends(require("viewer"))):
    out = []
    for a, p, s in _rows(db, day_from, day_to, person_id, session_id, status, limit, offset):
        item = AttendanceOut.model_validate(a, from_attributes=True)
        item.person_code, item.person_name = p.code, p.full_name
        item.session_name = s.name if s else None
        out.append(item)
    return out


@router.get("/summary", response_model=SummaryOut, summary="Số liệu tổng hợp một ngày")
def summary(day: str | None = Query(None, description="Mặc định hôm nay"),
            db: Session = Depends(get_db), _=Depends(require("viewer"))):
    return att_svc.summary(db, day)


@router.get("/trend", summary="Xu hướng chuyên cần theo ngày")
def trend(days: int = Query(14, ge=1, le=180), db: Session = Depends(get_db),
          _=Depends(require("viewer"))):
    today = date.today()
    return [att_svc.summary(db, (today - timedelta(days=i)).isoformat())
            for i in range(days - 1, -1, -1)]


@router.get("/export.xlsx", summary="Xuất Excel có định dạng")
def export_excel(day_from: str | None = None, day_to: str | None = None,
                 db: Session = Depends(get_db), _=Depends(require("viewer"))):
    """Tệp .xlsx mở ra là dùng được ngay, không phải chỉnh cột.

    CSV vẫn giữ ở điểm cuối `/export` cho ai cần đưa dữ liệu sang công cụ khác,
    nhưng nó không mang được định dạng: Excel hiện ngày thành ###### và mọi tiêu
    đề bị cắt cụt.
    """
    from ...services.excel import xuat_diem_danh
    rows = list(_rows(db, day_from, day_to, None, None, None, 100000, 0))
    data = xuat_diem_danh(rows, day_from, day_to)
    name = f"diemdanh_{day_from or 'all'}_{day_to or 'all'}.xlsx"
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/export", summary="Xuất CSV (thô, cho công cụ khác)")
def export_csv(day_from: str | None = None, day_to: str | None = None,
               db: Session = Depends(get_db), _=Depends(require("viewer"))):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Ngay", "Ma", "Ho ten", "Ca", "Gio vao", "Gio ra",
                "Trang thai", "Phut muon", "Do tin cay", "Diem song", "Thiet bi"])
    for a, p, s in _rows(db, day_from, day_to, None, None, None, 100000, 0):
        w.writerow([a.day, p.code, p.full_name, s.name if s else "",
                    a.check_in.strftime("%H:%M:%S"),
                    a.check_out.strftime("%H:%M:%S") if a.check_out else "",
                    a.status, a.late_minutes, f"{a.confidence:.4f}",
                    "" if a.liveness_score is None else f"{a.liveness_score:.4f}",
                    a.device_id or ""])
    # BOM ở đầu file để Excel trên Windows đọc đúng tiếng Việt.
    payload = "﻿" + buf.getvalue()
    name = f"diemdanh_{day_from or 'all'}_{day_to or 'all'}.csv"
    return StreamingResponse(
        iter([payload]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/unknowns", response_model=list[UnknownOut], summary="Sự kiện người lạ")
def unknowns(resolved: bool | None = None, limit: int = Query(100, le=1000),
             db: Session = Depends(get_db), _=Depends(require("viewer"))):
    stmt = select(UnknownEvent).order_by(UnknownEvent.ts.desc()).limit(limit)
    if resolved is not None:
        stmt = stmt.where(UnknownEvent.resolved.is_(resolved))
    return db.execute(stmt).scalars().all()
