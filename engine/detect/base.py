"""Giao diện chung cho mọi bộ phát hiện khuôn mặt.

Mọi detector nhận ảnh BGR và trả về danh sách `Detection` với toạ độ tính trên
ảnh gốc — bất kể bên trong nó có thu nhỏ ảnh để chạy nhanh hay không.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ..types import Detection


class Detector(ABC):
    name: str = "base"

    @abstractmethod
    def detect(self, image_bgr: np.ndarray) -> list[Detection]:
        """Tìm mọi khuôn mặt trong ảnh. Trả về list rỗng nếu không thấy."""

    def detect_largest(self, image_bgr: np.ndarray) -> Detection | None:
        """Khuôn mặt lớn nhất — dùng khi đăng ký, mỗi ảnh chỉ lấy 1 người."""
        dets = self.detect(image_bgr)
        return max(dets, key=lambda d: d.area) if dets else None

    def close(self) -> None:
        """Giải phóng tài nguyên nếu backend cần."""


def build_detector(settings) -> Detector:
    """Factory: đọc DetectSettings và dựng detector tương ứng."""
    backend = settings.backend.lower()
    if backend == "yunet":
        from .yunet import YuNetDetector
        return YuNetDetector(settings)
    if backend == "mtcnn":
        from .mtcnn import MTCNNDetector
        return MTCNNDetector(settings)
    raise ValueError(f"Detector không hỗ trợ: {settings.backend!r} (yunet | mtcnn)")
