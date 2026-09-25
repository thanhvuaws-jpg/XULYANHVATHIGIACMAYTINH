"""Chỉ mục HNSW — tra cứu xấp xỉ, độ trễ gần như không đổi khi dữ liệu lớn dần.

hnswlib lưu khoảng cách cosine dưới dạng `distance = 1 − cosine_similarity`, nên
mọi kết quả trả ra đều được đổi ngược lại thành similarity cho khớp với phần còn
lại của hệ thống.

Chỉ mục là thứ **dựng lại được**: nguồn sự thật là bảng `face_embeddings` trong
cơ sở dữ liệu. Mất file chỉ mục thì chỉ cần nạp lại, không mất dữ liệu.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np

from ..settings import IndexSettings
from .base import VectorIndex


class HnswIndex(VectorIndex):
    name = "hnsw"

    def __init__(self, settings: IndexSettings | None = None, dim: int = 512):
        super().__init__(dim)
        self.s = settings or IndexSettings(backend="hnsw")
        self._index = None
        self._init_index()

    def _init_index(self):
        import hnswlib
        self._index = hnswlib.Index(space="cosine", dim=self.dim)
        self._index.init_index(max_elements=self.s.max_elements,
                               ef_construction=self.s.ef_construction, M=self.s.m)
        self._index.set_ef(self.s.ef_search)

    def add(self, vectors: np.ndarray, labels: list[str],
            person_ids: list[int | None] | None = None) -> None:
        vectors = np.atleast_2d(np.asarray(vectors, dtype=np.float32))
        if vectors.shape[0] == 0:
            return
        if vectors.shape[1] != self.dim:
            raise ValueError(f"Số chiều không khớp: {vectors.shape[1]} != {self.dim}")

        start = len(self.labels)
        needed = start + vectors.shape[0]
        if needed > self._index.get_max_elements():
            self._index.resize_index(max(needed, self._index.get_max_elements() * 2))

        self._index.add_items(vectors, np.arange(start, needed))
        self.labels.extend(labels)
        self.person_ids.extend(person_ids or [None] * len(labels))

    def search(self, vector: np.ndarray, k: int = 1) -> list[tuple[str, float, int | None]]:
        if not self.labels:
            return []
        # Lấy dư kết quả rồi mới gộp theo người, vì nhiều vector đầu bảng có thể
        # cùng thuộc một người.
        probe = min(len(self.labels), max(k * 8, 16))
        ids, dists = self._index.knn_query(np.asarray(vector, dtype=np.float32).ravel(), k=probe)

        best: dict[str, tuple[float, int]] = {}
        for idx, dist in zip(ids[0], dists[0]):
            idx = int(idx)
            sim = 1.0 - float(dist)
            label = self.labels[idx]
            if label not in best or sim > best[label][0]:
                best[label] = (sim, idx)

        ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:k]
        return [(label, score, self.person_ids[idx]) for label, (score, idx) in ranked]

    def reset(self) -> None:
        self.labels.clear()
        self.person_ids.clear()
        self._init_index()

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._index.save_index(str(path.with_suffix(".hnsw")))
        with open(path.with_suffix(".meta"), "wb") as f:
            pickle.dump({"dim": self.dim, "labels": self.labels,
                         "person_ids": self.person_ids,
                         "settings": self.s.__dict__}, f)

    def load(self, path: str | Path) -> None:
        import hnswlib
        path = Path(path)
        with open(path.with_suffix(".meta"), "rb") as f:
            meta = pickle.load(f)
        self.dim = int(meta["dim"])
        self.labels = list(meta["labels"])
        self.person_ids = list(meta.get("person_ids") or [None] * len(self.labels))
        self._index = hnswlib.Index(space="cosine", dim=self.dim)
        self._index.load_index(str(path.with_suffix(".hnsw")),
                               max_elements=max(self.s.max_elements, len(self.labels)))
        self._index.set_ef(self.s.ef_search)
