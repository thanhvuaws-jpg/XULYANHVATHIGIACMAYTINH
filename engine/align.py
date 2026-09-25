"""Căn chỉnh khuôn mặt bằng phép biến đổi similarity từ 5 điểm mốc.

Đưa mọi khuôn mặt về cùng một tư thế chuẩn: hai mắt nằm ngang, ở đúng vị trí quy
ước — nhờ đó mạng trích đặc trưng không phải tự học cách bù trừ xoay và tỉ lệ.
Bỏ bước này thường làm accuracy tụt 5-15 %, đây là một ablation nên đưa vào báo cáo.
"""
from __future__ import annotations

import cv2
import numpy as np

from .types import REF_LANDMARKS_112, Detection


def reference_landmarks(size: int) -> np.ndarray:
    """Template 5 điểm, phóng từ chuẩn 112×112 sang kích thước mong muốn."""
    return REF_LANDMARKS_112 * (float(size) / 112.0)


def align_face(image_bgr: np.ndarray, landmarks: np.ndarray, size: int = 112) -> np.ndarray | None:
    """Cắt và nắn một khuôn mặt về ảnh vuông `size`×`size`.

    Trả về None nếu không ước lượng được phép biến đổi (landmark suy biến).
    """
    src = np.asarray(landmarks, dtype=np.float32).reshape(5, 2)
    dst = reference_landmarks(size)
    matrix, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.LMEDS)
    if matrix is None:
        return None
    return cv2.warpAffine(image_bgr, matrix, (size, size),
                          flags=cv2.INTER_LINEAR, borderValue=0)


def crop_face(image_bgr: np.ndarray, det: Detection, size: int = 112,
              margin: float = 0.0) -> np.ndarray | None:
    """Cắt theo hộp bao, KHÔNG căn chỉnh — dùng cho ablation 'tắt alignment'."""
    x1, y1, x2, y2 = det.box
    if margin:
        pad_x = int((x2 - x1) * margin / 2)
        pad_y = int((y2 - y1) * margin / 2)
        x1, y1, x2, y2 = x1 - pad_x, y1 - pad_y, x2 + pad_x, y2 + pad_y
    h, w = image_bgr.shape[:2]
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w, int(x2)), min(h, int(y2))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None
    return cv2.resize(image_bgr[y1:y2, x1:x2], (size, size), interpolation=cv2.INTER_LINEAR)


#: Hệ số quy đổi tỉ lệ lệch mũi sang độ. Hiệu chỉnh trên LFW (ảnh chính diện cho
#: tỉ lệ ~0.00-0.08) và ảnh nghiêng 45° (~0.35). 45 / 0.35 ≈ 130.
YAW_RATIO_TO_DEG = 130.0


def estimate_pose(landmarks: np.ndarray) -> tuple[float, float]:
    """Ước lượng (roll, yaw) của khuôn mặt, tính bằng độ.

    Phân biệt rõ hai loại vì chúng có hệ quả khác hẳn nhau:

      • **roll** — đầu nghiêng sang bên trong mặt phẳng ảnh. Phép biến đổi
        similarity ở `align_face` xoay lại được hoàn toàn, nên roll gần như KHÔNG
        làm giảm chất lượng nhận diện. Chỉ chặn ở mức cực đoan.

      • **yaw** — đầu quay ngang, để lộ một bên má nhiều hơn bên kia. Alignment
        2D không dựng lại được phần khuất, đây mới là thứ thực sự làm hỏng
        embedding.

    Yaw ước lượng bằng độ lệch của mũi so với trung điểm hai mắt, chiếu lên
    *đường nối hai mắt* — nhờ chiếu nên phép đo không bị roll làm nhiễu.
    """
    p = np.asarray(landmarks, dtype=np.float32).reshape(5, 2)
    eye_l, eye_r, nose, mouth_l, mouth_r = p[0], p[1], p[2], p[3], p[4]

    eye_vec = eye_r - eye_l
    eye_dist = float(np.linalg.norm(eye_vec)) + 1e-6
    roll = float(np.degrees(np.arctan2(eye_vec[1], eye_vec[0])))

    axis = eye_vec / eye_dist                      # hướng đơn vị dọc đường nối hai mắt
    eye_mid = (eye_l + eye_r) / 2.0
    mouth_mid = (mouth_l + mouth_r) / 2.0

    # Lấy trung bình hai chỉ báo (mũi và miệng) cho đỡ nhiễu landmark.
    nose_off = float(np.dot(nose - eye_mid, axis)) / eye_dist
    mouth_off = float(np.dot(mouth_mid - eye_mid, axis)) / eye_dist
    yaw = abs(nose_off * 0.65 + mouth_off * 0.35) * YAW_RATIO_TO_DEG

    return float(roll), float(yaw)


def estimate_pose_angle(landmarks: np.ndarray) -> float:
    """Tương thích ngược: trả về yaw, đại lượng thực sự quan trọng."""
    return estimate_pose(landmarks)[1]
