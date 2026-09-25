"""Chống giả mạo — phân biệt khuôn mặt thật với ảnh in và màn hình điện thoại.

Vì sao đây là tầng bắt buộc
---------------------------
Không có tầng này, cả hệ thống điểm danh sụp đổ trước một trò rất đơn giản: giơ
ảnh chụp màn hình bạn mình lên trước camera. Toàn bộ công sức ở các tầng trước —
nhận diện chính xác 98 % — trở thành vô nghĩa, vì thứ hệ thống đang chống lại
không phải sự nhầm lẫn mà là sự gian lận có chủ đích.

Hai họ phương pháp
------------------
**Thụ động** (`texture.py`) — chỉ nhìn một khung hình. Dựa trên việc ảnh in và
màn hình để lại dấu vết vật lý: hoạ tiết moiré do lưới điểm ảnh, dải màu bị thu
hẹp sau khi qua máy in, ánh sáng nền phẳng thay vì phản xạ cục bộ trên da. Nhanh,
không đòi hỏi người dùng làm gì, nhưng có thể bị qua mặt bởi bản in chất lượng cao.

**Chủ động** (`blink.py`) — yêu cầu người dùng làm một việc mà ảnh tĩnh không làm
được: chớp mắt. Chậm hơn (cần vài giây) nhưng **về nguyên tắc không thể bị ảnh in
qua mặt**. Đây là lớp phòng thủ chắc chắn hơn.

Hệ thống dùng cả hai: thụ động chạy luôn, chủ động bật ở chế độ nghiêm ngặt.

Chỉ số đánh giá theo chuẩn ISO/IEC 30107-3
------------------------------------------
  APCER — tỉ lệ đòn tấn công lọt qua        (càng thấp càng an toàn)
  BPCER — tỉ lệ người thật bị từ chối oan   (càng thấp càng dễ dùng)
  ACER  — trung bình hai chỉ số trên
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ..types import Detection


class LivenessDetector(ABC):
    name: str = "base"
    #: True nếu cần nhiều khung hình liên tiếp mới kết luận được.
    temporal: bool = False

    @abstractmethod
    def score(self, image_bgr: np.ndarray, detections: list[Detection]) -> list[float]:
        """Điểm 0..1 cho mỗi khuôn mặt — càng cao càng có khả năng là người thật."""

    def reset(self) -> None:
        """Xoá trạng thái tích luỹ (dùng cho phương pháp chủ động)."""


class NullLiveness(LivenessDetector):
    """Không kiểm tra gì — luôn trả về 1.0. Dùng khi tắt tính năng."""

    name = "none"

    def score(self, image_bgr, detections):
        return [1.0] * len(detections)


def build_liveness(settings, models_dir=None) -> LivenessDetector:
    """Factory: đọc LivenessSettings và dựng bộ phát hiện tương ứng."""
    backend = (settings.backend or "none").lower()
    if backend in ("none", ""):
        return NullLiveness()
    if backend in ("texture", "minifas"):
        from .texture import TextureLiveness
        return TextureLiveness(settings, models_dir)
    if backend == "blink":
        from .blink import BlinkLiveness
        return BlinkLiveness(settings, models_dir)
    if backend == "combo":
        from .combo import ComboLiveness
        return ComboLiveness(settings, models_dir)
    raise ValueError(f"Liveness không hỗ trợ: {settings.backend!r} "
                     f"(none | texture | blink | combo)")
