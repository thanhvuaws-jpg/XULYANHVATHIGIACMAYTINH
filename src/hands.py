"""Theo dõi bàn tay + nhận cử chỉ + vẽ trên không (MediaPipe Tasks HandLandmarker).

Dùng trong desktop_app.py (tab "Cử chỉ tay"). Tự tải model hand_landmarker.task nếu chưa có.

Cử chỉ:
  • 1 ngón trỏ        -> VẼ theo đầu ngón
  • chữ V (2 ngón)    -> di chuyển, KHÔNG vẽ
  • nắm tay           -> xoá toàn bộ nét
  • xoè cả bàn tay    -> đổi màu + bắn hiệu ứng hạt
  • pinch (cái+trỏ)   -> chấm 1 điểm + hiệu ứng
"""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from . import config

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")
MODEL_PATH = config.MODELS_DIR / "hand_landmarker.task"

# chỉ số landmark
WRIST, T_MCP, T_IP, T_TIP = 0, 2, 3, 4
I_MCP, I_PIP, I_TIP = 5, 6, 8
M_MCP, M_PIP, M_TIP = 9, 10, 12
R_PIP, R_TIP = 14, 16
P_MCP, P_PIP, P_TIP = 17, 18, 20

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]

# màu neon (BGR)
PALETTE = [
    (238, 210, 34),   # cyan  #22d3ee
    (250, 139, 167),  # tím   #a78bfa
    (153, 211, 52),   # lục   #34d399
    (36, 191, 251),   # hổ phách #fbbf24
    (133, 113, 244),  # hồng  #f472b6
    (248, 189, 56),   # sky   #38bdf8
]


def ensure_model() -> Path:
    if not MODEL_PATH.exists():
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


# --------------------------------------------------------------------------- tracker
class HandTracker:
    def __init__(self, num_hands: int = 1):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        ensure_model()
        self._mp = mp
        opts = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(MODEL_PATH)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._lm = vision.HandLandmarker.create_from_options(opts)

    def process(self, frame_bgr: np.ndarray, ts_ms: int) -> list[dict]:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        res = self._lm.detect_for_video(image, int(ts_ms))
        out = []
        for i, lms in enumerate(res.hand_landmarks):
            pts = np.array([[p.x * w, p.y * h] for p in lms], dtype=np.float32)
            handed = "?"
            if i < len(res.handedness) and res.handedness[i]:
                handed = res.handedness[i][0].category_name
            fingers = _fingers_up(pts)
            out.append({"pts": pts, "handed": handed, "fingers": fingers,
                        "gesture": _classify(pts, fingers)})
        return out

    def close(self):
        try:
            self._lm.close()
        except Exception:  # noqa: BLE001
            pass


def _dist(a, b) -> float:
    return float(np.linalg.norm(a - b))


def _fingers_up(p: np.ndarray) -> list[bool]:
    span = _dist(p[WRIST], p[M_MCP]) + 1e-6
    thumb = _dist(p[T_TIP], p[I_MCP]) > _dist(p[T_MCP], p[I_MCP]) * 1.15
    index = p[I_TIP][1] < p[I_PIP][1]
    middle = p[M_TIP][1] < p[M_PIP][1]
    ring = p[R_TIP][1] < p[R_PIP][1]
    pinky = p[P_TIP][1] < p[P_PIP][1]
    return [bool(thumb), bool(index), bool(middle), bool(ring), bool(pinky)]


def _classify(p: np.ndarray, f: list[bool]) -> str:
    t, i, m, r, k = f
    span = _dist(p[WRIST], p[M_MCP]) + 1e-6
    pinch = _dist(p[T_TIP], p[I_TIP]) / span < 0.35
    if pinch and not m and not r:
        return "pinch"
    if i and not m and not r and not k:
        return "draw"
    if i and m and not r and not k:
        return "move"
    if i and m and r and k:
        return "open"
    if not i and not m and not r and not k and not t:
        return "fist"
    return "none"


# --------------------------------------------------------------------------- FX / vẽ
class GestureFX:
    #: Cử chỉ nào gọi hiệu ứng nào. Đổi được lúc chạy từ giao diện; tên phải khớp
    #: tên thư mục trong `effects/`. Tên không tồn tại thì lặng lẽ bỏ qua, nên
    #: xoá một thư mục hiệu ứng không làm hỏng chương trình.
    GAN_MAC_DINH = {
        "open": "tia_lua",          # xoè bàn tay
        "pinch": "vong_nang_luong",  # chụm ngón
        "fist": "khoi",             # nắm tay (xoá nét)
    }

    def __init__(self):
        self.strokes: list[dict] = []     # {color, thick, pts:[(x,y)], r?}
        self._cur: dict | None = None
        self.color_i = 0
        self._cool = 0.0
        self._sm: np.ndarray | None = None
        self.status = "Đưa tay vào khung hình"
        self.gesture = "none"

        # Hiệu ứng dạng ảnh. Nạp lười và bao try/except: thiếu thư mục effects/
        # thì tính năng vẽ vẫn chạy bình thường, chỉ là không có hiệu ứng — một
        # phần phụ hỏng không được phép kéo theo phần chính.
        self.gan = dict(self.GAN_MAC_DINH)
        self._may_phat = None
        try:
            from .effects import BoHieuUng, MayPhat
            bo = BoHieuUng()
            if bo.ten:
                self._may_phat = MayPhat(bo)
        except Exception:                    # noqa: BLE001
            self._may_phat = None
        self._cu_chi_truoc = "none"

    # -- cập nhật theo kết quả tay --
    def update(self, hands: list[dict]):
        now = time.time()
        if not hands:
            self._cur = None
            self._sm = None
            self.gesture = "none"
            self.status = "Không thấy tay"
            return

        hnd = hands[0]
        g = hnd["gesture"]
        self.gesture = g
        p = hnd["pts"]
        tip = p[I_TIP]
        palm = tuple(p[M_MCP].astype(int))
        pinch_mid = tuple(((p[T_TIP] + p[I_TIP]) / 2).astype(int))

        if g == "draw":
            self._sm = tip if self._sm is None else 0.5 * self._sm + 0.5 * tip
            pt = tuple(self._sm.astype(int))
            if self._cur is None:
                self._cur = {"color": PALETTE[self.color_i], "thick": 6, "pts": [pt]}
                self.strokes.append(self._cur)
            else:
                self._cur["pts"].append(pt)
            self.status = "✍  Đang vẽ"
        else:
            self._cur = None
            self._sm = None

        if now > self._cool:
            if g == "fist":
                self.strokes.clear()
                self.status = "✊  Xoá hết nét"; self._cool = now + 0.6
            elif g == "open":
                self.color_i = (self.color_i + 1) % len(PALETTE)
                self.status = "🖐  Đổi màu"; self._cool = now + 0.5
            elif g == "pinch":
                self.strokes.append({"color": PALETTE[self.color_i], "thick": -1,
                                     "pts": [pinch_mid], "r": 13})
                self.status = "👌  Chấm điểm"; self._cool = now + 0.32
            elif g == "move":
                self.status = "✌  Di chuyển (không vẽ)"
        elif g == "draw":
            pass
        else:
            self.status = {"open": "🖐  Đổi màu", "fist": "✊  Xoá hết nét",
                           "pinch": "👌  Chấm điểm", "move": "✌  Di chuyển"}.get(g, self.status)

        # Bắn hiệu ứng khi cử chỉ VỪA ĐỔI, không bắn mỗi khung.
        #
        # Giữ nguyên bàn tay xoè trong hai giây là khoảng sáu mươi khung hình;
        # bắn mỗi khung sẽ sinh sáu mươi hiệu ứng chồng lên nhau và tốc độ khung
        # hình tụt thẳng. Chỉ khi cử chỉ đổi mới là một "lần kích hoạt".
        if self._may_phat is not None and g != self._cu_chi_truoc:
            ten_fx = self.gan.get(g)
            if ten_fx:
                self._may_phat.phat(ten_fx, float(tip[0]), float(tip[1]), ti_le=1.0)
        self._cu_chi_truoc = g

        # giới hạn bộ nhớ nét
        total = sum(len(s["pts"]) for s in self.strokes)
        while total > 7000 and len(self.strokes) > 1:
            total -= len(self.strokes.pop(0)["pts"])


    def clear(self):
        self.strokes.clear()
        self._cur = None
        if self._may_phat is not None:
            self._may_phat.xoa_het()

    # -- render lên frame --
    def render(self, frame: np.ndarray, hands: list[dict], show_skeleton: bool = True) -> np.ndarray:
        out = frame
        overlay = np.zeros_like(out)
        for s in self.strokes:
            col = s["color"]
            if s["thick"] == -1:
                cv2.circle(overlay, s["pts"][0], s.get("r", 12), col, -1, cv2.LINE_AA)
            else:
                for a, b in zip(s["pts"], s["pts"][1:]):
                    cv2.line(overlay, a, b, col, s["thick"], cv2.LINE_AA)
        out = cv2.addWeighted(out, 1.0, overlay, 0.92, 0)

        if show_skeleton:
            for hnd in hands:
                draw_hand_skeleton(out, hnd["pts"])

        # Hiệu ứng vẽ SAU cùng, đè lên cả nét vẽ lẫn khung xương bàn tay —
        # nó là lớp ánh sáng phía trước, không phải một nét vẽ nữa.
        if self._may_phat is not None:
            out = self._may_phat.ve(out)
        return out


def draw_hand_skeleton(img: np.ndarray, pts: np.ndarray):
    for a, b in HAND_CONNECTIONS:
        cv2.line(img, tuple(pts[a].astype(int)), tuple(pts[b].astype(int)),
                 (230, 230, 235), 2, cv2.LINE_AA)
    for i, (x, y) in enumerate(pts.astype(int)):
        cv2.circle(img, (int(x), int(y)), 5 if i in (4, 8, 12, 16, 20) else 3,
                   (255, 120, 180), -1, cv2.LINE_AA)
