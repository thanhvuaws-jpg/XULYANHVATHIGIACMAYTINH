"""Giao diện chung cho mọi bộ trích đặc trưng khuôn mặt.

Mọi embedder nhận danh sách chip đã căn chỉnh (BGR, vuông) và trả về ma trận
(N, D) đã chuẩn hoá L2 — nhờ chuẩn hoá sẵn nên so khớp chỉ còn là tích vô hướng.

Mỗi backend tự khai báo `image_size` mà nó cần; pipeline đọc thuộc tính này để
căn chỉnh đúng kích thước, thay vì hardcode ở nơi khác.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class Embedder(ABC):
    name: str = "base"
    image_size: int = 112      # cạnh ảnh vào mà backend này yêu cầu
    dim: int = 512             # số chiều vector ra

    @abstractmethod
    def embed(self, chips_bgr: list[np.ndarray]) -> np.ndarray:
        """Trả về (N, dim) float32, mỗi hàng đã chuẩn hoá L2."""

    def embed_one(self, chip_bgr: np.ndarray) -> np.ndarray:
        return self.embed([chip_bgr])[0]

    def close(self) -> None:
        """Giải phóng tài nguyên nếu backend cần."""


def l2_normalize(x: np.ndarray, eps: float = 1e-10) -> np.ndarray:
    """Chuẩn hoá từng hàng về độ dài 1."""
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        return x / (np.linalg.norm(x) + eps)
    return x / (np.linalg.norm(x, axis=1, keepdims=True) + eps)


def build_embedder(settings, models_dir=None) -> Embedder:
    """Factory: đọc EmbedSettings và dựng embedder tương ứng."""
    backend = settings.backend.lower()
    if backend == "facenet":
        from .facenet import FaceNetEmbedder
        return FaceNetEmbedder(settings)
    if backend == "onnx":
        from .onnx_arcface import OnnxArcFaceEmbedder
        return OnnxArcFaceEmbedder(settings)
    if backend == "torch":
        from .torch_arcface import TorchArcFaceEmbedder
        return TorchArcFaceEmbedder(settings)
    raise ValueError(f"Embedder không hỗ trợ: {settings.backend!r} (facenet | onnx | torch)")
