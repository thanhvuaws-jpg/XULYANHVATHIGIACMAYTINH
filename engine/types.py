"""Kiểu dữ liệu dùng chung cho toàn bộ engine.

Tất cả các tầng của pipeline trao đổi với nhau qua các dataclass ở đây, nên đổi
implementation của một tầng không ảnh hưởng các tầng khác.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# Template 5 điểm mốc chuẩn ArcFace, định nghĩa trên ảnh 112x112.
# Thứ tự: mắt trái, mắt phải, mũi, khoé miệng trái, khoé miệng phải.
REF_LANDMARKS_112 = np.array(
    [[38.2946, 51.6963],
     [73.5318, 51.5014],
     [56.0252, 71.7366],
     [41.5493, 92.3655],
     [70.7299, 92.2041]],
    dtype=np.float32,
)


@dataclass
class Detection:
    """Một khuôn mặt do detector tìm thấy, chưa qua căn chỉnh."""
    box: np.ndarray              # (4,) int  -> x1, y1, x2, y2
    score: float                 # độ tin cậy của detector, 0..1
    landmarks: np.ndarray        # (5, 2) float32, toạ độ pixel trên ảnh gốc

    @property
    def width(self) -> int:
        return int(self.box[2] - self.box[0])

    @property
    def height(self) -> int:
        return int(self.box[3] - self.box[1])

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return (float(self.box[0] + self.box[2]) / 2.0,
                float(self.box[1] + self.box[3]) / 2.0)


@dataclass
class QualityReport:
    """Kết quả chấm chất lượng một khuôn mặt đã cắt."""
    score: float                 # tổng hợp 0..1, càng cao càng tốt
    sharpness: float             # độ nét CHUẨN HOÁ: nl_var = lap_var / gray_var
    brightness: float            # độ sáng trung bình 0..255
    face_size: int               # cạnh nhỏ nhất của hộp bao, pixel
    pose_yaw: float              # quay ngang, độ — alignment KHÔNG sửa được
    pose_roll: float             # nghiêng đầu, độ — alignment sửa được
    passed: bool                 # có vượt ngưỡng tối thiểu không
    reasons: list[str] = field(default_factory=list)   # lý do bị loại

    def __str__(self) -> str:
        state = "đạt" if self.passed else "loại: " + ", ".join(self.reasons)
        return f"quality={self.score:.2f} ({state})"


@dataclass
class Face:
    """Một khuôn mặt đã đi qua detect + align, sẵn sàng để trích đặc trưng."""
    detection: Detection
    chip: np.ndarray                        # ảnh BGR đã căn chỉnh, (S, S, 3)
    quality: Optional[QualityReport] = None
    embedding: Optional[np.ndarray] = None  # (D,) float32, đã chuẩn hoá L2
    liveness: Optional[float] = None        # 0..1, càng cao càng "thật"

    @property
    def box(self) -> np.ndarray:
        return self.detection.box


@dataclass
class Identity:
    """Kết quả so khớp một khuôn mặt với cơ sở dữ liệu."""
    label: str                   # tên người, hoặc UNKNOWN
    score: float                 # cosine similarity với vector gần nhất
    person_id: Optional[int] = None

    UNKNOWN = "Unknown"

    @property
    def is_known(self) -> bool:
        return self.label != self.UNKNOWN


@dataclass
class TrackedFace:
    """Một khuôn mặt đang được bám vết qua nhiều khung hình."""
    track_id: int
    face: Face
    identity: Identity
    votes: int = 0               # số phiếu cho nhãn hiện tại
    total_votes: int = 0         # tổng số lần đã bỏ phiếu
    age: int = 0                 # số khung hình đã tồn tại
    confirmed: bool = False      # đã đủ tin cậy để ghi nhận sự kiện chưa

    @property
    def vote_ratio(self) -> float:
        return self.votes / self.total_votes if self.total_votes else 0.0
