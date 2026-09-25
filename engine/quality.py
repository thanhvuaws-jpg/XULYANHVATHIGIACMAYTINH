"""Cổng chất lượng ảnh khuôn mặt.

Lọc bỏ ảnh không đủ tốt TRƯỚC khi đăng ký hoặc nhận diện. Đây là thứ tách một hệ
thống dùng được khỏi một demo: ảnh mờ và ảnh quay ngang là nguyên nhân số một gây
nhận nhầm, và chúng phát hiện được rẻ hơn nhiều so với việc chữa hậu quả.

Bốn tiêu chí, mỗi tiêu chí quy về 0..1 rồi lấy trung bình có trọng số.

Ba điểm cần lưu ý về phương pháp — cả ba đều là lỗi kinh điển:

1. **Độ nét phải chuẩn hoá.** Phương sai Laplacian thô phụ thuộc cả độ tương phản
   lẫn kích thước ảnh, nên một ảnh tương phản cao dù mờ vẫn cho điểm cao. Ở đây
   dùng `lap_var / gray_var`: tỉ lệ năng lượng nằm ở tần số cao trên tổng năng
   lượng. Làm mờ kéo tỉ lệ này xuống rõ rệt bất kể ảnh sáng tối ra sao.

2. **Không đo độ nét trên chip đã căn chỉnh.** `warpAffine` lấy mẫu lại ảnh và tự
   sinh ra tần số cao do răng cưa, che gần hết dấu hiệu mờ. Đo trên chip chỉ phát
   hiện được 28 % mức mờ; đo trên vùng mặt ở độ phân giải gốc rồi thu về kích
   thước cố định bằng `INTER_AREA` phát hiện được 83 %. Số liệu đo thực tế trên
   ảnh LFW làm mờ Gauss 31×31.

3. **Roll không phải lỗi.** Đầu nghiêng trong mặt phẳng ảnh được `align_face`
   xoay lại hoàn toàn. Chỉ có **yaw** — quay ngang, che mất một bên mặt — mới làm
   hỏng embedding. Gộp chung hai thứ sẽ loại oan ảnh tốt và cho lọt ảnh xấu.
"""
from __future__ import annotations

import cv2
import numpy as np

from .align import estimate_pose
from .settings import QualitySettings
from .types import Detection, QualityReport

# Trọng số tổng hợp. Độ nét và yaw được ưu tiên vì hại nhiều nhất.
WEIGHTS = {"sharpness": 0.35, "brightness": 0.18, "size": 0.17, "pose": 0.30}

#: Kích thước chuẩn hoá để đo độ nét. Mọi khuôn mặt đều được đưa về kích thước
#: này bằng INTER_AREA trước khi đo, nên điểm số so sánh được giữa các ảnh.
MEASURE_SIZE = 128


def face_region(image_bgr: np.ndarray, det: Detection, pad: float = 0.0) -> np.ndarray | None:
    """Cắt vùng khuôn mặt ở ĐỘ PHÂN GIẢI GỐC, không lấy mẫu lại."""
    x1, y1, x2, y2 = (int(v) for v in det.box)
    if pad:
        px, py = int((x2 - x1) * pad), int((y2 - y1) * pad)
        x1, y1, x2, y2 = x1 - px, y1 - py, x2 + px, y2 + py
    h, w = image_bgr.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None
    return image_bgr[y1:y2, x1:x2]


def sharpness_score(region_bgr: np.ndarray) -> float:
    """Độ nét chuẩn hoá = phương sai Laplacian / phương sai ảnh xám.

    Nhận VÙNG MẶT GỐC (chưa căn chỉnh). Bên trong tự thu về `MEASURE_SIZE` bằng
    `INTER_AREA` — phép thu này có lọc thông thấp đúng cách nên giữ nguyên dấu
    hiệu mờ, khác với `INTER_LINEAR` hay `warpAffine` vốn gây răng cưa.

    Giá trị tham chiếu đo trên LFW: ảnh nét ~0.06, mờ nhẹ ~0.037,
    mờ Gauss 21×21 ~0.016, mờ 31×31 ~0.010.
    """
    if region_bgr is None or region_bgr.size == 0:
        return 0.0
    small = cv2.resize(region_bgr, (MEASURE_SIZE, MEASURE_SIZE), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float64)
    gray_var = float(gray.var())
    if gray_var < 1e-6:                     # ảnh phẳng lì
        return 0.0
    return float(cv2.Laplacian(gray, cv2.CV_64F).var()) / gray_var


def brightness_score(region_bgr: np.ndarray) -> float:
    """Độ sáng trung bình 0..255."""
    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    return float(gray.mean())


def _ramp(value: float, lo: float, hi: float) -> float:
    """Chuẩn hoá tuyến tính về 0..1, kẹp hai đầu."""
    if hi <= lo:
        return 0.0
    return float(np.clip((value - lo) / (hi - lo), 0.0, 1.0))


def _brightness_to_score(value: float, lo: float, hi: float) -> float:
    """Điểm cao nhất ở giữa dải cho phép, giảm dần về hai biên."""
    mid = (lo + hi) / 2.0
    half = (hi - lo) / 2.0
    if half <= 0:
        return 0.0
    return float(np.clip(1.0 - abs(value - mid) / half, 0.0, 1.0))


def assess(image_bgr: np.ndarray, det: Detection,
           settings: QualitySettings | None = None) -> QualityReport:
    """Chấm chất lượng một khuôn mặt.

    Nhận ẢNH GỐC cùng kết quả phát hiện — không nhận chip đã căn chỉnh, vì phép
    căn chỉnh phá hỏng phép đo độ nét (xem ghi chú đầu file).
    """
    s = settings or QualitySettings()

    region = face_region(image_bgr, det)
    if region is None:
        return QualityReport(score=0.0, sharpness=0.0, brightness=0.0, face_size=0,
                             pose_yaw=0.0, pose_roll=0.0, passed=False,
                             reasons=["hộp bao không hợp lệ"])

    sharp = sharpness_score(region)
    bright = brightness_score(region)
    face_size = int(min(det.width, det.height))
    roll, yaw = estimate_pose(det.landmarks)

    # Quy từng tiêu chí về 0..1.
    sc_sharp = _ramp(sharp, s.min_sharpness * 0.6, s.min_sharpness * 4.0)
    sc_bright = _brightness_to_score(bright, s.min_brightness, s.max_brightness)
    sc_size = _ramp(float(face_size), s.min_face_size * 0.6, s.min_face_size * 2.2)
    sc_pose = 1.0 - _ramp(yaw, 0.0, s.max_pose_angle)

    score = (WEIGHTS["sharpness"] * sc_sharp
             + WEIGHTS["brightness"] * sc_bright
             + WEIGHTS["size"] * sc_size
             + WEIGHTS["pose"] * sc_pose)

    reasons: list[str] = []
    if sharp < s.min_sharpness:
        reasons.append("ảnh mờ")
    if bright < s.min_brightness:
        reasons.append("thiếu sáng")
    elif bright > s.max_brightness:
        reasons.append("cháy sáng")
    if face_size < s.min_face_size:
        reasons.append("mặt quá nhỏ")
    if yaw > s.max_pose_angle:
        reasons.append("quay ngang quá nhiều")
    if abs(roll) > s.max_roll_angle:
        reasons.append("nghiêng đầu quá nhiều")
    if score < s.min_score and not reasons:
        reasons.append("chất lượng tổng thể thấp")

    return QualityReport(
        score=float(score),
        sharpness=sharp,
        brightness=bright,
        face_size=face_size,
        pose_yaw=yaw,
        pose_roll=roll,
        passed=(not reasons) and score >= s.min_score,
        reasons=reasons,
    )


def hint_for(report: QualityReport) -> str:
    """Câu nhắc hiển thị cho người đứng trước camera."""
    if report.passed:
        return "Tốt rồi"
    mapping = {
        "ảnh mờ": "Giữ yên máy, đừng cử động",
        "thiếu sáng": "Cần thêm ánh sáng",
        "cháy sáng": "Tránh ngược sáng",
        "mặt quá nhỏ": "Mời lại gần camera",
        "quay ngang quá nhiều": "Nhìn thẳng vào camera",
        "nghiêng đầu quá nhiều": "Giữ đầu thẳng",
        "chất lượng tổng thể thấp": "Điều chỉnh lại tư thế và ánh sáng",
    }
    return mapping.get(report.reasons[0], "Điều chỉnh lại tư thế")
