"""Dịch vụ engine — một thể hiện FacePipeline duy nhất cho cả tiến trình.

Vì sao là singleton: nạp mô hình mất khoảng một giây và chiếm vài trăm MB. Nếu mỗi
request tự nạp lại thì API sẽ chậm không dùng được. Ở đây nạp một lần lúc khởi
động, sau đó mọi request dùng chung.

Vì sao chỉ mục dựng từ cơ sở dữ liệu: bảng `face_embeddings` là nguồn sự thật.
Chỉ mục chỉ là cấu trúc tăng tốc, dựng lại được bất cứ lúc nào — nên không cần
sao lưu nó, và đổi mô hình chỉ là chuyện trích đặc trưng lại.
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from engine.pipeline import FacePipeline
from engine.settings import EngineSettings

from ..core.config import get_settings
from ..db.models import FaceEmbedding, Person

_lock = threading.Lock()
_pipeline: FacePipeline | None = None
_model_tag: str = ""


def model_tag() -> str:
    """Định danh mô hình đang dùng — dùng để lọc vector tương thích."""
    return _model_tag


def _build_settings() -> tuple[EngineSettings, str]:
    cfg = get_settings()
    s = EngineSettings()
    s.detect.backend = cfg.detect_backend
    s.embed.backend = cfg.embed_backend
    s.embed.weights = cfg.embed_weights
    s.index.backend = cfg.index_backend
    s.match_threshold = cfg.match_threshold
    s.models_dir = cfg.models_dir
    s.liveness.enabled = cfg.liveness_backend not in ("none", "")
    s.liveness.backend = cfg.liveness_backend or "none"

    tag = cfg.embed_backend
    if cfg.embed_weights:
        tag = f"{cfg.embed_backend}:{Path(cfg.embed_weights).stem}"
    return s, tag


def get_pipeline() -> FacePipeline:
    global _pipeline, _model_tag
    if _pipeline is None:
        with _lock:
            if _pipeline is None:
                s, tag = _build_settings()
                _pipeline = FacePipeline(s)
                _model_tag = tag
    return _pipeline


def reload_index(db: Session) -> dict:
    """Nạp lại toàn bộ vector từ cơ sở dữ liệu vào chỉ mục tra cứu.

    Chỉ lấy vector do **đúng mô hình đang dùng** sinh ra. Vector của mô hình khác
    có số chiều hoặc không gian khác nên trộn vào sẽ cho kết quả sai một cách âm
    thầm — đây là lý do `FaceEmbedding.model_tag` tồn tại.
    """
    pipe = get_pipeline()
    pipe.index.reset()

    rows = db.execute(
        select(FaceEmbedding, Person.code, Person.id)
        .join(Person, Person.id == FaceEmbedding.person_id)
        .where(FaceEmbedding.model_tag == _model_tag, Person.active.is_(True))
    ).all()

    dim = pipe.embedder.dim
    skipped = 0
    for emb, code, pid in rows:
        if emb.dim != dim:
            skipped += 1
            continue
        vec = np.frombuffer(emb.vector, dtype=np.float32)
        pipe.add_to_index(vec.reshape(1, -1), code, pid)

    total_any = db.execute(select(FaceEmbedding)).scalars().all()
    return {"model_tag": _model_tag, "loaded": pipe.index.size,
            "people": pipe.index.num_people, "skipped_dim_mismatch": skipped,
            "total_in_db": len(total_any),
            "other_model_vectors": len(total_any) - len(rows)}


def reset_pipeline() -> None:
    """Buộc nạp lại engine ở lần dùng tiếp theo — gọi khi đổi cấu hình mô hình."""
    global _pipeline
    with _lock:
        _pipeline = None


def pack_vector(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).ravel().tobytes()


def unpack_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)
