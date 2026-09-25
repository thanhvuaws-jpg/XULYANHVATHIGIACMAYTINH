"""Chỉ mục vector — tra cứu "vector này giống ai nhất".

Hai backend cùng một giao diện:

  • **bruteforce** — nhân ma trận trên numpy. Chính xác tuyệt đối, đơn giản, đủ
    nhanh tới khoảng 10 000 vector. Dùng làm mốc đúng để kiểm chứng backend kia.
  • **hnsw** — đồ thị Hierarchical Navigable Small World. Xấp xỉ, nhưng độ trễ
    gần như không đổi khi số người tăng: ~0,3 ms ở mức 10 000 người.

Mỗi người có thể có nhiều vector (nhiều ảnh đăng ký). Điểm số của một người là
điểm của vector giống nhất — chứ không phải trung bình — vì trung bình bị kéo
xuống bởi những ảnh chụp ở tư thế khác.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from ..types import Identity


class VectorIndex(ABC):
    name: str = "base"

    def __init__(self, dim: int = 512):
        self.dim = dim
        self.labels: list[str] = []          # nhãn theo từng vector đã nạp
        self.person_ids: list[int | None] = []

    @abstractmethod
    def add(self, vectors: np.ndarray, labels: list[str],
            person_ids: list[int | None] | None = None) -> None:
        """Thêm các vector đã chuẩn hoá L2 vào chỉ mục."""

    @abstractmethod
    def search(self, vector: np.ndarray, k: int = 1) -> list[tuple[str, float, int | None]]:
        """Trả về k kết quả gần nhất: (nhãn, cosine similarity, person_id)."""

    @abstractmethod
    def reset(self) -> None:
        """Xoá sạch chỉ mục."""

    @abstractmethod
    def save(self, path: str | Path) -> None: ...

    @abstractmethod
    def load(self, path: str | Path) -> None: ...

    @property
    def size(self) -> int:
        return len(self.labels)

    @property
    def num_people(self) -> int:
        return len(set(self.labels))

    def identify(self, vector: np.ndarray, threshold: float) -> Identity:
        """Tra cứu rồi áp ngưỡng — dưới ngưỡng thì trả về Unknown."""
        hits = self.search(vector, k=1)
        if not hits:
            return Identity(label=Identity.UNKNOWN, score=-1.0)
        label, score, pid = hits[0]
        if score < threshold:
            return Identity(label=Identity.UNKNOWN, score=score)
        return Identity(label=label, score=score, person_id=pid)

    def identify_batch(self, vectors: np.ndarray, threshold: float) -> list[Identity]:
        return [self.identify(v, threshold) for v in np.atleast_2d(vectors)]


def build_index(settings, dim: int = 512) -> VectorIndex:
    """Factory: đọc IndexSettings và dựng chỉ mục tương ứng."""
    backend = settings.backend.lower()
    if backend == "bruteforce":
        from .bruteforce import BruteForceIndex
        return BruteForceIndex(dim=dim)
    if backend == "hnsw":
        from .hnsw import HnswIndex
        return HnswIndex(settings, dim=dim)
    raise ValueError(f"Index không hỗ trợ: {settings.backend!r} (bruteforce | hnsw)")
