"""Kết hợp thụ động + chủ động.

Hai phương pháp bù trừ cho nhau: thụ động bắt được ngay từ khung đầu nhưng có thể
bị bản in tốt qua mặt; chủ động thì chắc chắn hơn nhưng cần vài giây và người dùng
phải hợp tác.

Cách gộp điểm: **lấy điểm cao nhất trong vài giây đầu, sau đó lấy điểm thấp nhất.**
Lý do: lúc mới vào khung hình chưa kịp chớp mắt nên điểm chủ động luôn bằng 0 —
nếu lấy min ngay thì không ai qua được. Sau thời gian ân hạn, đòi hỏi cả hai cùng
đạt, nên kẻ tấn công phải qua mặt được đồng thời cả hai lớp.
"""
from __future__ import annotations

import time

import numpy as np

from ..types import Detection
from .base import LivenessDetector

GRACE_SEC = 4.0          # thời gian ân hạn để người dùng kịp chớp mắt


class ComboLiveness(LivenessDetector):
    name = "combo"
    temporal = True

    def __init__(self, settings=None, models_dir=None):
        from .blink import BlinkLiveness
        from .texture import TextureLiveness
        self.texture = TextureLiveness(settings, models_dir)
        self.blink = BlinkLiveness(settings, models_dir)
        self._start = time.time()

    def score(self, image_bgr, detections: list[Detection]) -> list[float]:
        if not detections:
            return []
        st = self.texture.score(image_bgr, detections)
        sb = self.blink.score(image_bgr, detections)
        in_grace = (time.time() - self._start) < GRACE_SEC
        if in_grace:
            return [float(max(a, b)) for a, b in zip(st, sb)]
        return [float(min(a, b)) for a, b in zip(st, sb)]

    def reset(self) -> None:
        self.texture.reset()
        self.blink.reset()
        self._start = time.time()
