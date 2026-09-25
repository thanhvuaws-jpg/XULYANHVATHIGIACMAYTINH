"""Đặc trưng phân biệt khuôn mặt thật với ảnh in / màn hình.

Chọn đặc trưng thủ công thay vì để CNN tự học, vì hai lý do:

1. **Giải thích được.** Mỗi con số ứng với một hiện tượng vật lý cụ thể, nên khi
   hệ thống từ chối oan ai đó thì truy được nguyên nhân. Một CNN hộp đen chỉ nói
   "0,31" mà không nói vì sao.
2. **Cần rất ít dữ liệu.** Bộ dữ liệu giả mạo thật rất khó thu thập; 12 đặc trưng
   có ý nghĩa vật lý huấn luyện được bằng vài nghìn mẫu, trong khi CNN cần hàng
   trăm nghìn.

Bốn nhóm dấu vết vật lý mà đòn tấn công để lại
----------------------------------------------
**Moiré** — màn hình có lưới điểm ảnh đều đặn; chụp lại bằng camera có lưới cảm
biến cũng đều đặn. Hai lưới chồng nhau sinh ra vân giao thoa, hiện thành **đỉnh
nhọn ở tần số trung–cao** trong phổ Fourier. Da thật không có cấu trúc tuần hoàn
nên phổ trơn.

**Dải màu bị thu hẹp** — mực in và màn hình đều không tái tạo được toàn bộ dải màu
của da người. Sau một vòng in/hiển thị rồi chụp lại, độ bão hoà và phương sai màu
đều tụt.

**Ánh sáng phẳng** — da thật cong, tạo phản xạ chói cục bộ (mũi, trán, gò má). Ảnh
in phẳng lì; màn hình phát sáng đều toàn bề mặt. Phân bố điểm sáng nhất khác hẳn.

**Kết cấu bề mặt** — lỗ chân lông, sợi tóc, vân da tạo hoạ tiết vi mô ngẫu nhiên.
In ấn thay chúng bằng lưới nửa tông (halftone) đều đặn; màn hình thay bằng lưới
điểm ảnh. LBP (Local Binary Pattern) đo được khác biệt này.
"""
from __future__ import annotations

import cv2
import numpy as np

#: Kích thước chuẩn hoá trước khi trích đặc trưng — mọi khuôn mặt phải cùng cỡ
#: thì phổ tần số mới so sánh được với nhau.
PATCH = 128

FEATURE_NAMES = [
    "moire_peak",       # đỉnh nhọn nhất trong phổ tần số trung-cao
    "moire_ratio",      # tỉ lệ năng lượng tần số cao / tổng
    "spec_kurtosis",    # độ nhọn của phổ — cấu trúc tuần hoàn làm tăng
    "sat_mean",         # độ bão hoà màu trung bình
    "sat_std",          # biến thiên bão hoà
    "chroma_range",     # dải màu chiếm dụng trong không gian a*b*
    "spec_highlight",   # tỉ lệ điểm ảnh chói
    "highlight_spread", # độ phân tán không gian của vùng chói
    "lbp_uniformity",   # tỉ lệ mẫu LBP đồng nhất
    "lbp_entropy",      # entropy histogram LBP
    "edge_density",     # mật độ cạnh
    "color_moment3",    # độ lệch (skewness) của kênh sáng
]


def _to_patch(face_bgr: np.ndarray) -> np.ndarray:
    if face_bgr.shape[0] != PATCH or face_bgr.shape[1] != PATCH:
        face_bgr = cv2.resize(face_bgr, (PATCH, PATCH), interpolation=cv2.INTER_AREA)
    return face_bgr


# --------------------------------------------------------------------- moiré
def _spectrum_features(gray: np.ndarray) -> tuple[float, float, float]:
    """Phân tích phổ Fourier để tìm dấu vết lưới điểm ảnh."""
    win = gray.astype(np.float32) * np.outer(np.hanning(PATCH), np.hanning(PATCH))
    spec = np.abs(np.fft.fftshift(np.fft.fft2(win)))
    spec = np.log1p(spec)

    c = PATCH // 2
    y, x = np.ogrid[:PATCH, :PATCH]
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2)

    # Phổ theo bán kính: trung bình năng lượng trên từng vành khuyên.
    nbins = 40
    radial = np.array([spec[(r >= i * c / nbins) & (r < (i + 1) * c / nbins)].mean()
                       if np.any((r >= i * c / nbins) & (r < (i + 1) * c / nbins)) else 0.0
                       for i in range(nbins)])

    # Vùng tần số trung-cao là nơi moiré xuất hiện; bỏ 5 vành trong cùng (thành
    # phần một chiều và cấu trúc thô của khuôn mặt).
    mid = radial[8:32]
    baseline = np.median(mid) + 1e-6
    peak = float(mid.max() / baseline)                 # đỉnh nhọn so với nền

    total = radial[1:].sum() + 1e-6
    high_ratio = float(radial[20:].sum() / total)      # năng lượng dồn về tần số cao

    m = mid.mean()
    s = mid.std() + 1e-6
    kurt = float(((mid - m) ** 4).mean() / s ** 4)     # phổ càng "gai" càng nhọn
    return peak, high_ratio, kurt


# ----------------------------------------------------------------------- màu
def _color_features(patch: np.ndarray) -> tuple[float, float, float, float]:
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32) / 255.0
    lab = cv2.cvtColor(patch, cv2.COLOR_BGR2LAB).astype(np.float32)

    a, b = lab[:, :, 1], lab[:, :, 2]
    # Dải màu chiếm dụng: độ trải của phân bố trong mặt phẳng a*b*.
    chroma_range = float(np.sqrt(a.var() + b.var()))

    lum = lab[:, :, 0]
    mu, sd = lum.mean(), lum.std() + 1e-6
    skew = float(((lum - mu) ** 3).mean() / sd ** 3)
    return float(sat.mean()), float(sat.std()), chroma_range, skew


# ------------------------------------------------------------------- ánh sáng
def _highlight_features(gray: np.ndarray) -> tuple[float, float]:
    """Vùng chói: da thật cho vài đốm nhỏ tập trung; màn hình cho vùng sáng đều."""
    thr = np.percentile(gray, 97)
    mask = gray >= thr
    ratio = float(mask.mean())
    ys, xs = np.nonzero(mask)
    if len(xs) < 4:
        return ratio, 0.0
    # Độ phân tán không gian, chuẩn hoá theo cạnh ảnh.
    spread = float(np.sqrt(xs.var() + ys.var()) / PATCH)
    return ratio, spread


# ------------------------------------------------------------------ kết cấu
def _lbp_features(gray: np.ndarray) -> tuple[float, float]:
    """LBP 8 lân cận, bán kính 1 — tự cài để không thêm phụ thuộc scikit-image."""
    g = gray.astype(np.int16)
    code = np.zeros(g.shape, np.uint8)
    # 8 lân cận theo chiều kim đồng hồ, mỗi lân cận đóng góp 1 bit.
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
    for bit, (dy, dx) in enumerate(offsets):
        shifted = np.roll(np.roll(g, dy, axis=0), dx, axis=1)
        code |= ((shifted >= g).astype(np.uint8) << bit)
    inner = code[1:-1, 1:-1]

    hist = np.bincount(inner.ravel(), minlength=256).astype(np.float32)
    hist /= hist.sum() + 1e-6

    # "Đồng nhất" = mẫu có ≤2 lần chuyển 0↔1 khi đi vòng quanh. Da thật cho tỉ lệ
    # cao; lưới in/điểm ảnh tạo nhiều mẫu vụn không đồng nhất.
    def transitions(v: int) -> int:
        bits = [(v >> i) & 1 for i in range(8)]
        return sum(bits[i] != bits[(i + 1) % 8] for i in range(8))

    uniform_mask = np.array([transitions(v) <= 2 for v in range(256)])
    uniformity = float(hist[uniform_mask].sum())
    entropy = float(-(hist[hist > 0] * np.log2(hist[hist > 0])).sum())
    return uniformity, entropy


def extract(face_bgr: np.ndarray) -> np.ndarray:
    """Trích 12 đặc trưng từ một ảnh khuôn mặt đã cắt. Trả về vector float32."""
    patch = _to_patch(face_bgr)
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)

    peak, high_ratio, kurt = _spectrum_features(gray)
    sat_mean, sat_std, chroma, skew = _color_features(patch)
    hl_ratio, hl_spread = _highlight_features(gray)
    lbp_u, lbp_e = _lbp_features(gray)
    edges = float((cv2.Canny(gray, 60, 160) > 0).mean())

    return np.array([peak, high_ratio, kurt, sat_mean, sat_std, chroma,
                     hl_ratio, hl_spread, lbp_u, lbp_e, edges, skew],
                    dtype=np.float32)


def extract_batch(faces: list[np.ndarray]) -> np.ndarray:
    if not faces:
        return np.zeros((0, len(FEATURE_NAMES)), np.float32)
    return np.stack([extract(f) for f in faces])
