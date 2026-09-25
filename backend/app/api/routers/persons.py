"""Quản lý người và đăng ký khuôn mặt."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.base import get_db
from ...db.models import AuditLog, EnrollmentImage, FaceEmbedding, Person
from ...schemas import EnrollResult, PersonIn, PersonOut, PersonUpdate
from ...services import engine as engine_svc
from ...services import enrollment as enroll_svc
from ..deps import current_user, require

router = APIRouter(prefix="/api/persons", tags=["persons"])


def _to_out(db: Session, p: Person) -> PersonOut:
    tag = engine_svc.model_tag()
    nv = db.scalar(select(func.count()).select_from(FaceEmbedding)
                   .where(FaceEmbedding.person_id == p.id,
                          FaceEmbedding.model_tag == tag)) or 0
    ni = db.scalar(select(func.count()).select_from(EnrollmentImage)
                   .where(EnrollmentImage.person_id == p.id)) or 0
    return PersonOut(**{c.name: getattr(p, c.name) for c in Person.__table__.columns
                        if c.name in PersonOut.model_fields},
                     num_vectors=nv, num_images=ni)


@router.get("", response_model=list[PersonOut], summary="Danh sách người")
def list_persons(q: str | None = Query(None, description="Lọc theo tên hoặc mã"),
                 active_only: bool = True, limit: int = Query(200, le=1000),
                 offset: int = 0, db: Session = Depends(get_db),
                 _=Depends(require("viewer"))):
    stmt = select(Person)
    if active_only:
        stmt = stmt.where(Person.active.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Person.full_name.ilike(like) | Person.code.ilike(like))
    rows = db.execute(stmt.order_by(Person.full_name).limit(limit).offset(offset)).scalars().all()
    return [_to_out(db, p) for p in rows]


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED,
             summary="Thêm người mới")
def create_person(body: PersonIn, db: Session = Depends(get_db),
                  user=Depends(require("operator"))):
    if db.execute(select(Person).where(Person.code == body.code)).scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, f"Mã '{body.code}' đã tồn tại")
    p = Person(**body.model_dump())
    db.add(p)
    db.add(AuditLog(actor=user.username, action="person.create", entity="person",
                    entity_id=body.code))
    db.commit()
    db.refresh(p)
    return _to_out(db, p)


@router.get("/{person_id}", response_model=PersonOut, summary="Chi tiết một người")
def get_person(person_id: int, db: Session = Depends(get_db), _=Depends(require("viewer"))):
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người này")
    return _to_out(db, p)


@router.patch("/{person_id}", response_model=PersonOut, summary="Sửa thông tin")
def update_person(person_id: int, body: PersonUpdate, db: Session = Depends(get_db),
                  user=Depends(require("operator"))):
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người này")
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(p, k, v)
    db.add(AuditLog(actor=user.username, action="person.update", entity="person",
                    entity_id=str(person_id), meta=changes))
    db.commit()
    db.refresh(p)
    if "active" in changes:
        engine_svc.reload_index(db)      # người bị tắt phải biến khỏi chỉ mục ngay
    return _to_out(db, p)


@router.delete("/{person_id}", summary="Xoá người (kèm vector và ảnh đăng ký)")
def delete_person(person_id: int, db: Session = Depends(get_db),
                  user=Depends(require("admin"))):
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người này")
    code = p.code
    db.delete(p)
    db.add(AuditLog(actor=user.username, action="person.delete", entity="person",
                    entity_id=code))
    db.commit()
    engine_svc.reload_index(db)
    return {"deleted": code}


@router.post("/{person_id}/images", response_model=EnrollResult,
             summary="Tải ảnh lên và đăng ký khuôn mặt")
async def upload_images(person_id: int, files: list[UploadFile] = File(...),
                        strict: bool = Query(True, description="Bật cổng chất lượng"),
                        db: Session = Depends(get_db), user=Depends(require("operator"))):
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người này")

    saved = []
    for f in files:
        data = await f.read()
        if not data:
            continue
        suffix = Path(f.filename or "x.jpg").suffix.lower() or ".jpg"
        path, img = enroll_svc.save_upload(p, data, suffix)
        if img is None:
            path.unlink(missing_ok=True)
            continue
        saved.append((path, img))
    if not saved:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Không đọc được ảnh nào")

    result = enroll_svc.add_images(db, p, saved, strict=strict, actor=user.username)
    return EnrollResult(**result)


@router.get("/{person_id}/images", summary="Ảnh đăng ký của một người")
def list_images(person_id: int, db: Session = Depends(get_db), _=Depends(require("viewer"))):
    rows = db.execute(select(EnrollmentImage)
                      .where(EnrollmentImage.person_id == person_id)
                      .order_by(EnrollmentImage.created_at.desc())).scalars().all()
    return [{"id": r.id, "path": r.path, "quality": r.quality,
             "accepted": r.accepted, "reject_reason": r.reject_reason,
             "created_at": r.created_at} for r in rows]


@router.post("/{person_id}/reembed", summary="Trích đặc trưng lại từ ảnh gốc")
def reembed(person_id: int, db: Session = Depends(get_db), user=Depends(require("operator"))):
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người này")
    return enroll_svc.reembed_person(db, p, actor=user.username)
