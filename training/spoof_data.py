"""Mô phỏng đòn tấn công giả mạo dựa trên vật lý.

Bộ dữ liệu giả mạo thật (CelebA-Spoof, NUAA, CASIA-FASD) đòi hỏi quay lại hàng
nghìn lần cảnh in ảnh ra rồi chụp lại — không thể tự thu thập trong phạm vi đồ án.
Module này mô phỏng lại **đúng những biến dạng vật lý** mà mỗi loại tấn công gây ra.

GIỚI HẠN PHẢI NÊU RÕ TRONG BÁO CÁO
-----------------------------------
Mô phỏng không thay thế được dữ liệu thật. Mô hình huấn luyện trên đây có thể học
đúng hiện tượng vật lý, nhưng cũng có thể học phải "dấu vân tay" của chính bộ mô
phỏng. Cách kiểm chứng trung thực là **thử chéo loại tấn công**: huấn luyện chỉ
trên tấn công in ấn rồi đo trên tấn công màn hình, và ngược lại. Nếu vẫn phát hiện
được thì mô hình đã học hiện tượng chung chứ không phải thuộc lòng mô phỏng.

Hai loại tấn công
-----------------
**Ảnh in** — mực in không tái tạo đủ dải màu; máy in dùng lưới nửa tông; giấy
phẳng nên ánh sáng đều; chụp lại làm mất chi tiết và thêm nhiễu cảm biến.

**Màn hình** — đây là loại tinh vi hơn. Lưới điểm ảnh của màn hình chồng với lưới
cảm biến của camera sinh ra **moiré**, mô phỏng đúng cách bằng cách vẽ lưới ở độ
phân giải cao rồi thu nhỏ với tỉ lệ không nguyên — chính hiện tượng răng cưa
(aliasing) tạo ra vân giao thoa, giống hệt ngoài đời.
"""
from __future__ import annotations

import cv2
import numpy as np

rng_global = np.random.default_rng(0)


# --------------------------------------------------------------- tiện ích chung
def _recapture(img: np.ndarray, rng) -> np.ndarray:
    """Biến dạng chung khi chụp lại một bề mặt phẳng bằng camera."""
    h, w = img.shape[:2]

    # Lệch phối cảnh nhẹ: bề mặt không bao giờ vuông góc tuyệt đối với ống kính.
    d = rng.uniform(0.004, 0.022) * w
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = src + rng.uniform(-d, d, size=(4, 2)).astype(np.float32)
    img = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (w, h),
                              borderMode=cv2.BORDER_REPLICATE)

    # Mất nét do lấy nét không hoàn hảo + giới hạn quang học.
    k = rng.choice([3, 3, 5])
    img = cv2.GaussianBlur(img, (int(k), int(k)), rng.uniform(0.4, 1.1))

    # Nhiễu cảm biến của lần chụp thứ hai.
    img = np.clip(img.astype(np.float32) + rng.normal(0, rng.uniform(1.5, 5.0), img.shape),
                  0, 255).astype(np.uint8)

    # Nén JPEG của lần lưu thứ hai.
    q = int(rng.integers(55, 92))
    ok, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
    if ok:
        img = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return img


def _flatten_lighting(img: np.ndarray, rng) -> np.ndarray:
    """Bề mặt phẳng → mất phản xạ chói cục bộ, thay bằng độ sáng gần đều."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    lum = lab[:, :, 0]
    # Kéo độ sáng về phía trung bình → giảm tương phản cục bộ của khối 3D.
    lab[:, :, 0] = lum * rng.uniform(0.72, 0.9) + lum.mean() * rng.uniform(0.12, 0.3)
    return cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


# ----------------------------------------------------------------- tấn công in
def print_attack(face_bgr: np.ndarray, rng=None) -> np.ndarray:
    """Mô phỏng: in ảnh ra giấy rồi giơ trước camera."""
    rng = rng or rng_global
    img = face_bgr.copy()
    h, w = img.shape[:2]

    # 1. Thu hẹp dải màu: mực CMYK không phủ hết dải màu da.
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] *= rng.uniform(0.62, 0.86)                  # bão hoà tụt
    hsv[:, :, 2] = 20 + hsv[:, :, 2] * rng.uniform(0.84, 0.95)   # đen không thật đen
    img = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)

    # 2. Lưới nửa tông: máy in tạo ảnh bằng các chấm mực đều đặn.
    period = float(rng.uniform(2.6, 4.4))
    angle = float(rng.uniform(0, np.pi))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    proj = xx * np.cos(angle) + yy * np.sin(angle)
    halftone = np.sin(2 * np.pi * proj / period)
    strength = rng.uniform(3.0, 8.0)
    img = np.clip(img.astype(np.float32) + halftone[..., None] * strength, 0, 255).astype(np.uint8)

    # 3. Vân giấy.
    grain = rng.normal(0, rng.uniform(1.5, 4.0), (h, w, 1)).astype(np.float32)
    img = np.clip(img.astype(np.float32) + grain, 0, 255).astype(np.uint8)

    # 4. Giấy phẳng → ánh sáng đều.
    img = _flatten_lighting(img, rng)
    return _recapture(img, rng)


# ------------------------------------------------------------ tấn công màn hình
def screen_attack(face_bgr: np.ndarray, rng=None) -> np.ndarray:
    """Mô phỏng: hiển thị ảnh trên màn hình điện thoại rồi giơ trước camera."""
    rng = rng or rng_global
    img = face_bgr.copy()
    h, w = img.shape[:2]

    # 1. Vẽ lưới điểm ảnh ở độ phân giải CAO rồi thu nhỏ với tỉ lệ KHÔNG NGUYÊN.
    #    Chính bước thu nhỏ này gây răng cưa và sinh ra moiré — đúng cơ chế vật lý
    #    khi lưới màn hình chồng lên lưới cảm biến camera.
    up = float(rng.uniform(2.7, 4.3))
    big = cv2.resize(img, (int(w * up), int(h * up)), interpolation=cv2.INTER_LINEAR)
    bh, bw = big.shape[:2]

    cell = int(rng.integers(3, 6))                # bề rộng một điểm ảnh màn hình
    grid = np.ones((bh, bw), np.float32)
    grid[:, ::cell] *= rng.uniform(0.80, 0.93)    # khe giữa các cột điểm ảnh
    grid[::cell, :] *= rng.uniform(0.85, 0.96)    # khe giữa các hàng
    big = np.clip(big.astype(np.float32) * grid[..., None], 0, 255).astype(np.uint8)

    # Cấu trúc điểm ảnh phụ RGB: mỗi cột thiên về một kênh màu.
    sub = np.ones((bh, bw, 3), np.float32)
    amt = rng.uniform(0.03, 0.09)
    for c in range(3):
        sub[:, c::3, c] += amt
    big = np.clip(big.astype(np.float32) * sub, 0, 255).astype(np.uint8)

    img = cv2.resize(big, (w, h), interpolation=cv2.INTER_LINEAR)   # aliasing -> moiré

    # 2. Ánh sáng nền: màn hình tự phát sáng, nâng đều toàn ảnh và giảm tương phản.
    glow = rng.uniform(6, 22)
    contrast = rng.uniform(0.80, 0.94)
    img = np.clip(img.astype(np.float32) * contrast + glow, 0, 255).astype(np.uint8)

    # 3. Ám màu của tấm nền (thường hơi xanh lam).
    tint = np.array([rng.uniform(1.00, 1.10), rng.uniform(0.97, 1.03),
                     rng.uniform(0.92, 1.00)], np.float32)
    img = np.clip(img.astype(np.float32) * tint, 0, 255).astype(np.uint8)

    # 4. Phản xạ trên mặt kính: một vệt sáng mờ.
    if rng.random() < 0.55:
        overlay = np.zeros((h, w), np.float32)
        cx, cy = rng.integers(0, w), rng.integers(0, h)
        cv2.ellipse(overlay, (int(cx), int(cy)),
                    (int(w * rng.uniform(.25, .6)), int(h * rng.uniform(.08, .22))),
                    float(rng.uniform(0, 180)), 0, 360, 1.0, -1)
        overlay = cv2.GaussianBlur(overlay, (0, 0), w * 0.06)
        img = np.clip(img.astype(np.float32) + overlay[..., None] * rng.uniform(8, 26),
                      0, 255).astype(np.uint8)

    img = _flatten_lighting(img, rng)
    return _recapture(img, rng)


ATTACKS = {"print": print_attack, "screen": screen_attack}


def make_attack(face_bgr: np.ndarray, kind: str | None = None, rng=None) -> tuple[np.ndarray, str]:
    rng = rng or rng_global
    if kind is None:
        kind = "print" if rng.random() < 0.5 else "screen"
    return ATTACKS[kind](face_bgr, rng), kind
