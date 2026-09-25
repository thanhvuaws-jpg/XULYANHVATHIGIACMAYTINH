"""Nghiệp vụ đăng ký khuôn mặt.

Luồng: ảnh tải lên → cổng chất lượng → căn chỉnh → trích đặc trưng → lưu cả **ảnh
gốc** lẫn **vector** → dựng lại chỉ mục.

Vì sao phải giữ ảnh gốc: khi đổi mô hình, vector cũ trở thành vô dụng. Còn ảnh gốc
thì chỉ cần chạy lại `reembed_person` là khôi phục được. Không giữ ảnh gốc đồng
nghĩa với việc mỗi lần nâng cấp mô hình phải gọi từng người đến chụp lại.
"""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from engine.anh_io import doc_anh

from ..core.config import get_settings
from ..db.models import AuditLog, EnrollmentImage, FaceEmbedding, Person
from . import engine as engine_svc


def save_upload(person: Person, data: bytes, suffix: str = ".jpg") -> tuple[Path, np.ndarray | None]:
    """Ghi ảnh tải lên xuống đĩa, trả về (đường dẫn, ảnh đã giải mã)."""
    cfg = get_settings()
    folder = cfg.enrolled_dir / person.code
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{person.code}_{int(time.time()*1000)}{suffix}"
    path.write_bytes(data)
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return path, img


def add_images(db: DbSession, person: Person, images: list[tuple[Path, np.ndarray]],
               *, strict: bool = True, actor: str = "api") -> dict:
    """Chấm chất lượng, trích đặc trưng và lưu cho một loạt ảnh của MỘT người."""
    pipe = engine_svc.get_pipeline()
    tag = engine_svc.model_tag()

    arrays = [img for _, img in images]
    vectors, reports = pipe.embed_for_enrollment(arrays, strict=strict)

    accepted, rejected = [], []
    vec_i = 0
    for (path, _img), rep in zip(images, reports):
        row = EnrollmentImage(person_id=person.id, path=str(path),
                              quality=rep.get("quality"), accepted=bool(rep["ok"]),
                              reject_reason=None if rep["ok"] else rep.get("reason"),
                              quality_detail={k: v for k, v in rep.items() if k != "index"})
        db.add(row)
        db.flush()
        if rep["ok"]:
            db.add(FaceEmbedding(person_id=person.id,
                                 vector=engine_svc.pack_vector(vectors[vec_i]),
                                 dim=int(vectors[vec_i].shape[-1]), model_tag=tag,
                                 quality=rep.get("quality"), source_image_id=row.id))
            vec_i += 1
            accepted.append(str(path.name))
        else:
            rejected.append({"file": path.name, "reason": rep.get("reason")})

    db.add(AuditLog(actor=actor, action="person.enroll", entity="person",
                    entity_id=str(person.id),
                    meta={"accepted": len(accepted), "rejected": len(rejected),
                          "model_tag": tag}))
    db.commit()
    engine_svc.reload_index(db)
    return {"person_id": person.id, "code": person.code,
            "accepted": len(accepted), "rejected": len(rejected),
            "rejected_detail": rejected, "model_tag": tag,
            "total_vectors": count_vectors(db, person.id, tag)}


def count_vectors(db: DbSession, person_id: int, tag: str | None = None) -> int:
    q = select(FaceEmbedding).where(FaceEmbedding.person_id == person_id)
    if tag:
        q = q.where(FaceEmbedding.model_tag == tag)
    return len(db.execute(q).scalars().all())


def reembed_person(db: DbSession, person: Person, *, actor: str = "api") -> dict:
    """Trích đặc trưng lại từ ảnh gốc — dùng sau khi đổi mô hình."""
    pipe = engine_svc.get_pipeline()
    tag = engine_svc.model_tag()

    rows = db.execute(
        select(EnrollmentImage).where(EnrollmentImage.person_id == person.id)
    ).scalars().all()
    images = []
    for row in rows:
        img = doc_anh(row.path)
        if img is not None:
            images.append((Path(row.path), img))
    if not images:
        return {"person_id": person.id, "code": person.code, "accepted": 0,
                "rejected": 0, "note": "không còn ảnh gốc trên đĩa"}

    # Chỉ xoá vector của ĐÚNG mô hình này; vector của mô hình khác giữ nguyên để
    # còn quay lại được nếu cần.
    db.execute(delete(FaceEmbedding).where(FaceEmbedding.person_id == person.id,
                                           FaceEmbedding.model_tag == tag))
    vectors, reports = pipe.embed_for_enrollment([im for _, im in images], strict=True)
    vec_i = 0
    for (path, _), rep in zip(images, reports):
        if not rep["ok"]:
            continue
        db.add(FaceEmbedding(person_id=person.id,
                             vector=engine_svc.pack_vector(vectors[vec_i]),
                             dim=int(vectors[vec_i].shape[-1]), model_tag=tag,
                             quality=rep.get("quality")))
        vec_i += 1
    db.add(AuditLog(actor=actor, action="person.reembed", entity="person",
                    entity_id=str(person.id), meta={"vectors": vec_i, "model_tag": tag}))
    db.commit()
    engine_svc.reload_index(db)
    return {"person_id": person.id, "code": person.code, "accepted": vec_i,
            "rejected": len(images) - vec_i, "model_tag": tag}


def reembed_all(db: DbSession, *, actor: str = "api") -> dict:
    people = db.execute(select(Person).where(Person.active.is_(True))).scalars().all()
    out = [reembed_person(db, p, actor=actor) for p in people]
    return {"people": len(out), "vectors": sum(o["accepted"] for o in out),
            "detail": out}
