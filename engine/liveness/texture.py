"""Phát hiện giả mạo thụ động — chỉ cần một khung hình.

Nạp bộ phân loại đã huấn luyện bởi `training/train_liveness.py` trên 12 đặc trưng
vật lý trong `features.py`. Không có mô hình thì tự chuyển sang luật ngưỡng đơn
giản dựa trên hai đặc trưng mạnh nhất, để hệ thống vẫn chạy được thay vì sập.

Ưu điểm: nhanh (~2 ms), người dùng không phải làm gì.
Hạn chế: bản in chất lượng cao trên giấy nhám, hoặc màn hình độ phân giải rất cao
có thể lọt. Với chế độ nghiêm ngặt, dùng kèm `blink.py`.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

from ..settings import ROOT
from ..types import Detection
from .base import LivenessDetector
from .features import extract_batch

DEFAULT_MODEL = "liveness_texture.pkl"


class TextureLiveness(LivenessDetector):
    name = "texture"
    temporal = False

    def __init__(self, settings=None, models_dir=None):
        self.s = settings
        models_dir = Path(models_dir) if models_dir else ROOT / "models"
        path = Path(settings.weights) if (settings and settings.weights) else models_dir / DEFAULT_MODEL

        self.model = None
        self.threshold = float(getattr(settings, "threshold", 0.55) or 0.55)
        if path.exists():
            with open(path, "rb") as f:
                blob = pickle.load(f)
            self.model = blob["model"]
            # Ngưỡng học được từ dữ liệu tin cậy hơn con số đặt tay.
            self.threshold = float(blob.get("threshold", self.threshold))
            self.trained_on = blob.get("results", {})
        else:
            self.trained_on = {}

    def _fallback(self, feats: np.ndarray) -> np.ndarray:
        """Luật dự phòng khi chưa huấn luyện mô hình.

        Dùng hai đặc trưng mạnh nhất đo được: độ bão hoà màu và mật độ cạnh — cả
        hai đều tụt rõ rệt sau khi ảnh đi qua một vòng in/hiển thị rồi chụp lại.
        """
        sat_mean, edge_density = feats[:, 3], feats[:, 10]
        score = 0.5 * np.clip(sat_mean / 0.34, 0, 1) + 0.5 * np.clip(edge_density / 0.06, 0, 1)
        return score.astype(np.float32)

    def score(self, image_bgr: np.ndarray, detections: list[Detection]) -> list[float]:
        if not detections:
            return []
        from ..quality import face_region

        faces = []
        for det in detections:
            region = face_region(image_bgr, det, pad=0.06)
            faces.append(region if region is not None else image_bgr)

        feats = extract_batch(faces)
        if self.model is None:
            return self._fallback(feats).tolist()
        return self.model.predict_proba(feats)[:, 1].astype(float).tolist()

    def describe(self) -> dict:
        return {"backend": self.name, "trained": self.model is not None,
                "threshold": self.threshold, **self.trained_on.get("basic", {})}
