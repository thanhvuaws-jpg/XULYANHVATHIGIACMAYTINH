"""Chỉ mục duyệt toàn bộ — chính xác tuyệt đối, dùng làm mốc đúng.

Vì mọi vector đã chuẩn hoá L2, cosine similarity chính là tích vô hướng, nên toàn
bộ phép tìm kiếm rút gọn thành một phép nhân ma trận. Với vài nghìn vector thì
numpy thừa sức chạy dưới 1 ms.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

from .base import VectorIndex


class BruteForceIndex(VectorIndex):
    name = "bruteforce"

    def __init__(self, dim: int = 512):
        super().__init__(dim)
        self._matrix = np.zeros((0, dim), dtype=np.float32)

    def add(self, vectors: np.ndarray, labels: list[str],
            person_ids: list[int | None] | None = None) -> None:
        vectors = np.atleast_2d(np.asarray(vectors, dtype=np.float32))
        if vectors.shape[0] == 0:
            return
        if vectors.shape[1] != self.dim:
            raise ValueError(f"Số chiều không khớp: {vectors.shape[1]} != {self.dim}")
        if len(labels) != vectors.shape[0]:
            raise ValueError("Số nhãn phải bằng số vector")
        self._matrix = np.vstack([self._matrix, vectors])
        self.labels.extend(labels)
        self.person_ids.extend(person_ids or [None] * len(labels))

    def search(self, vector: np.ndarray, k: int = 1) -> list[tuple[str, float, int | None]]:
        if self._matrix.shape[0] == 0:
            return []
        sims = self._matrix @ np.asarray(vector, dtype=np.float32).ravel()

        # Gộp theo người: mỗi người chỉ giữ vector giống nhất.
        best: dict[str, tuple[float, int]] = {}
        for i, label in enumerate(self.labels):
            s = float(sims[i])
            if label not in best or s > best[label][0]:
                best[label] = (s, i)

        ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:k]
        return [(label, score, self.person_ids[idx]) for label, (score, idx) in ranked]

    def reset(self) -> None:
        self._matrix = np.zeros((0, self.dim), dtype=np.float32)
        self.labels.clear()
        self.person_ids.clear()

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"dim": self.dim, "matrix": self._matrix,
                         "labels": self.labels, "person_ids": self.person_ids}, f)

    def load(self, path: str | Path) -> None:
        with open(Path(path), "rb") as f:
            data = pickle.load(f)
        self.dim = int(data["dim"])
        self._matrix = np.asarray(data["matrix"], dtype=np.float32)
        self.labels = list(data["labels"])
        self.person_ids = list(data.get("person_ids") or [None] * len(self.labels))
