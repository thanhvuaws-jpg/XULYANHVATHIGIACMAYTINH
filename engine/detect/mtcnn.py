"""MTCNN — bộ phát hiện cũ, giữ lại để đối chứng trong báo cáo.

Chính xác tương đương YuNet nhưng chậm hơn khoảng 10 lần vì chạy 3 mạng nối tiếp
trên nhiều tỉ lệ ảnh. Không dùng cho realtime, chỉ dùng để benchmark.
"""
from __future__ import annotations

import numpy as np

from ..settings import DetectSettings, resolve_device
from ..types import Detection
from .base import Detector


class MTCNNDetector(Detector):
    name = "mtcnn"

    def __init__(self, settings: DetectSettings | None = None, device: str = "auto"):
        from facenet_pytorch import MTCNN  # import chậm, để trong hàm
        self.s = settings or DetectSettings()
        self._net = MTCNN(keep_all=True, device=resolve_device(device), post_process=False)

    def detect(self, image_bgr: np.ndarray) -> list[Detection]:
        if image_bgr is None or image_bgr.size == 0:
            return []
        import cv2
        from PIL import Image

        pil = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
        boxes, probs, lms = self._net.detect(pil, landmarks=True)
        if boxes is None:
            return []

        h, w = image_bgr.shape[:2]
        out: list[Detection] = []
        for box, prob, lm in zip(boxes, probs, lms):
            if prob is None or prob < self.s.score_threshold:
                continue
            b = np.asarray(box, dtype=np.float32)
            b[0::2] = np.clip(b[0::2], 0, w - 1)
            b[1::2] = np.clip(b[1::2], 0, h - 1)
            out.append(Detection(box=b.astype(int), score=float(prob),
                                 landmarks=np.asarray(lm, dtype=np.float32).reshape(5, 2)))
        return out
