"""Nhận diện và điểm danh.

Hai điểm vào khác nhau về mục đích:

  • `/recognize` — chỉ trả về "ai đang trong ảnh", không ghi gì. Dùng cho trang
    xem thử và cho việc gỡ lỗi.

  • `/checkin` — nhận diện **và ghi vào sổ điểm danh**. Đòi hỏi khắt khe hơn hẳn:
    phải qua cổng chất lượng, qua chống giả mạo, và đạt ngưỡng tin cậy cao hơn
    ngưỡng hiển thị. Nhận nhầm ở đây tạo ra dữ liệu sai mà không ai phát hiện.
"""
from __future__ import annotations

import time
from datetime import datetime

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from engine.anh_io import ghi_anh
from engine.quality import hint_for

from ...core.config import get_settings
from ...db.base import get_db
from ...db.models import Person
from ...schemas import CheckinOut, FaceOut, PersonOut, RecognizeOut
from ...services import attendance as att_svc
from ...services.events import hub
from ...services import engine as engine_svc
from ..deps import require

router = APIRouter(prefix="/api", tags=["recognize"])


async def _decode(file: UploadFile) -> np.ndarray:
    data = await file.read()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Không đọc được ảnh")
    return img


def _face_out(face, ident) -> FaceOut:
    q = face.quality
    return FaceOut(box=[int(v) for v in face.box], label=ident.label,
                   person_id=ident.person_id, score=round(float(ident.score), 4),
                   liveness=None if face.liveness is None else round(float(face.liveness), 4),
                   quality=None if q is None else round(float(q.score), 4),
                   quality_ok=None if q is None else bool(q.passed),
                   quality_hint=None if q is None else hint_for(q),
                   is_known=ident.is_known)


@router.post("/recognize", response_model=RecognizeOut,
             summary="Nhận diện trên một ảnh (không ghi điểm danh)")
async def recognize(file: UploadFile = File(...), _=Depends(require("viewer"))):
    img = await _decode(file)
    pipe = engine_svc.get_pipeline()
    results = pipe.process_image(img)
    return RecognizeOut(faces=[_face_out(f, i) for f, i in results],
                        count=len(results),
                        timings_ms={k: round(v, 2) for k, v in pipe.timings.items()})


@router.post("/checkin", response_model=CheckinOut,
             summary="Nhận diện và GHI điểm danh")
async def checkin(file: UploadFile = File(...),
                  device_id: str | None = Form(None),
                  session_id: int | None = Form(None),
                  db: Session = Depends(get_db), _=Depends(require("operator"))):
    cfg = get_settings()
    img = await _decode(file)
    pipe = engine_svc.get_pipeline()
    results = pipe.process_image(img)

    if not results:
        return CheckinOut(recognized=False, message="Không thấy khuôn mặt nào trong ảnh")

    # Nhiều người trong khung thì lấy khuôn mặt lớn nhất — người đứng gần camera
    # nhất chính là người đang muốn điểm danh.
    face, ident = max(results, key=lambda r: r[0].detection.area)
    live = face.liveness
    now = datetime.now()

    def snap(prefix: str) -> str | None:
        try:
            path = cfg.snapshot_dir / f"{prefix}_{int(time.time()*1000)}.jpg"
            if not ghi_anh(path, img):
                return None
            return str(path)
        except Exception:                       # noqa: BLE001
            return None

    # live < 0 nghĩa là chưa đo được (mặt quá nhỏ), không phải giả mạo.
    if live is not None and 0 <= live < pipe.settings.liveness.threshold:
        att_svc.log_unknown(db, best_score=float(ident.score), liveness=float(live),
                            snapshot=snap("spoof"), device_id=device_id)
        return CheckinOut(recognized=False, liveness=round(float(live), 4),
                          confidence=round(float(ident.score), 4),
                          message="Nghi ngờ giả mạo — vui lòng nhìn thẳng vào camera")

    if face.quality is not None and not face.quality.passed:
        return CheckinOut(recognized=False, confidence=round(float(ident.score), 4),
                          liveness=None if live is None else round(float(live), 4),
                          message=hint_for(face.quality))

    if not ident.is_known or ident.score < cfg.min_confidence:
        ev = att_svc.log_unknown(db, best_score=float(ident.score),
                                 best_person_id=ident.person_id,
                                 liveness=None if live is None else float(live),
                                 snapshot=snap("unknown"), device_id=device_id)
        hub.publish("unknown", event_id=ev.id, device_id=device_id,
                    confidence=round(float(ident.score), 4))
        return CheckinOut(recognized=False, confidence=round(float(ident.score), 4),
                          liveness=None if live is None else round(float(live), 4),
                          message=f"Chưa nhận ra (đã ghi sự kiện #{ev.id})")

    person = db.execute(select(Person).where(Person.code == ident.label)).scalar_one_or_none()
    if person is None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Chỉ mục trả về '{ident.label}' nhưng không có trong CSDL — "
                            f"cần dựng lại chỉ mục")

    sess = db.get(__import__("backend.app.db.models", fromlist=["Session"]).Session,
                  session_id) if session_id else None
    rec, created = att_svc.check_in(db, person, confidence=float(ident.score),
                                   liveness=None if live is None else float(live),
                                   snapshot=snap(person.code), device_id=device_id,
                                   when=now, session=sess)
    msg = (f"Đã điểm danh — {'đi muộn ' + str(rec.late_minutes) + ' phút' if rec.status == 'late' else 'đúng giờ'}"
           if created else "Đã điểm danh trước đó")

    # Chỉ phát khi THỰC SỰ tạo bản ghi mới. Người đứng lại trước camera lần thứ
    # hai không tạo dòng nào trong sổ, nên cũng không được làm bảng trên web nhấp
    # nháy thêm một lần nữa.
    if created:
        hub.publish("attendance",
                    attendance_id=rec.id, person_id=person.id, code=person.code,
                    full_name=person.full_name, status=rec.status,
                    late_minutes=rec.late_minutes, device_id=device_id,
                    confidence=round(float(ident.score), 4),
                    session_id=rec.session_id)
    return CheckinOut(recognized=True, created=created,
                      person=PersonOut.model_validate(person, from_attributes=True),
                      attendance_id=rec.id, status=rec.status,
                      late_minutes=rec.late_minutes,
                      confidence=round(float(ident.score), 4),
                      liveness=None if live is None else round(float(live), 4),
                      message=msg)
