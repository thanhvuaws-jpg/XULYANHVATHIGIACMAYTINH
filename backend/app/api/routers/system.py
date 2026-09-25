"""Thông tin hệ thống, sức khoẻ, quản lý chỉ mục và mô hình."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...db.base import engine as db_engine
from ...db.base import get_db
from ...db.models import Attendance, AuditLog, FaceEmbedding, Person, UnknownEvent
from ...schemas import HealthOut, SystemInfoOut
from ...services import engine as engine_svc
from ...services import enrollment as enroll_svc
from ..deps import require

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health", response_model=HealthOut, summary="Kiểm tra sức khoẻ (không cần đăng nhập)")
def health():
    cfg = get_settings()
    try:
        with db_engine.connect() as c:
            c.execute(text("SELECT 1"))
        db_ok = "ok"
    except Exception as e:                      # noqa: BLE001
        db_ok = f"lỗi: {e}"
    return HealthOut(status="ok", version=cfg.version, database=db_ok,
                     engine_loaded=engine_svc._pipeline is not None)


@router.get("/info", response_model=SystemInfoOut, summary="Cấu hình và trạng thái engine")
def info(_=Depends(require("viewer"))):
    cfg = get_settings()
    pipe = engine_svc.get_pipeline()
    d = pipe.describe()
    return SystemInfoOut(
        engine={"detector": d["detector"], "embedder": d["embedder"],
                "embed_dim": d["embed_dim"], "chip_size": d["chip_size"],
                "model_tag": engine_svc.model_tag(),
                "quality_gate": d["quality_gate"], "tracking": d["tracking"],
                "liveness": d["liveness"]},
        index={"backend": d["index"], "vectors": d["index_size"], "people": d["people"]},
        settings={"match_threshold": cfg.match_threshold,
                  "min_confidence": cfg.min_confidence,
                  "checkin_cooldown_minutes": cfg.checkin_cooldown_minutes,
                  "liveness_backend": cfg.liveness_backend})


@router.get("/stats", summary="Thống kê nhanh toàn hệ thống")
def stats(db: Session = Depends(get_db), _=Depends(require("viewer"))):
    def n(model):
        return db.scalar(select(func.count()).select_from(model)) or 0
    return {"persons": n(Person), "persons_active": db.scalar(
                select(func.count()).select_from(Person).where(Person.active.is_(True))) or 0,
            "embeddings": n(FaceEmbedding), "attendance": n(Attendance),
            "unknown_events": n(UnknownEvent), "audit_entries": n(AuditLog)}


@router.post("/reindex", summary="Dựng lại chỉ mục tra cứu từ cơ sở dữ liệu")
def reindex(db: Session = Depends(get_db), _=Depends(require("operator"))):
    return engine_svc.reload_index(db)


@router.post("/reembed-all", summary="Trích đặc trưng lại toàn bộ từ ảnh gốc")
def reembed_all(db: Session = Depends(get_db), user=Depends(require("admin"))):
    return enroll_svc.reembed_all(db, actor=user.username)


@router.get("/models", summary="Các mô hình trích đặc trưng có sẵn")
def models(_=Depends(require("viewer"))):
    cfg = get_settings()
    skip = ("face_detection", "yunet", "hand_landmarker", "face_landmarker")
    out = []

    # FaceNet chạy bằng PyTorch. Container triển khai cố tình không cài torch
    # (image nhẹ hơn khoảng bốn lần), nên ở đó mô hình này không dùng được. Liệt
    # kê nó ra là mời người dùng chọn một thứ chắc chắn hỏng — chỉ hiện khi thật
    # sự nạp được.
    if importlib.util.find_spec("torch") is not None:
        out.append({"label": "FaceNet (pretrained)", "backend": "facenet", "weights": "",
                    "size_mb": 107.0, "current": cfg.embed_backend == "facenet"})

    for f in sorted(Path(cfg.models_dir).glob("*.onnx")):
        if any(k in f.stem.lower() for k in skip):
            continue
        out.append({"label": f.stem, "backend": "onnx", "weights": str(f),
                    "size_mb": round(f.stat().st_size / 1e6, 1),
                    "current": cfg.embed_weights == str(f)})
    return out


@router.get("/audit", summary="Nhật ký thao tác")
def audit(limit: int = 100, db: Session = Depends(get_db), _=Depends(require("admin"))):
    rows = db.execute(select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit)).scalars().all()
    return [{"ts": r.ts, "actor": r.actor, "action": r.action,
             "entity": r.entity, "entity_id": r.entity_id, "meta": r.meta} for r in rows]
