"""Ứng dụng desktop nhận diện khuôn mặt — FaceID Studio (PySide6).

    python desktop_app.py

Yêu cầu: pip install PySide6-Essentials

Bốn khu vực (thanh trái):
  • Trực tiếp        - camera chạy liên tục, có mặt trong khung là nhận diện ngay
  • Nhận diện ảnh    - mở 1 ảnh bất kỳ
  • Đăng ký người    - tạo FOLDER theo tên người, chụp / thêm ảnh vào folder, rồi nạp vào nhận diện
  • Bảng điều khiển  - thống kê, đổi model/ngưỡng, dựng DB, chạy đánh giá, xem báo cáo
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer, QByteArray, QRectF
from PySide6.QtGui import QImage, QPixmap, QFont, QIcon, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
                               QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPlainTextEdit, QPushButton, QSpinBox, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
                               QGridLayout, QHeaderView, QSizePolicy, QProgressDialog,
                               QInputDialog, QDialog)

from src import config
from src.face_utils import draw_results, load_db, save_db

from engine.anh_io import doc_anh, ghi_anh
from engine.pipeline import FacePipeline
from engine.settings import EngineSettings

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# ---------------------------------------------------------------- palette
C_BG = "#0b0e18"; C_CARD = "#161b2d"; C_LINE = "#2b3350"
C_TEXT = "#eef1f8"; C_MUT = "#99a1b7"
ACCENT = "#8b5cf6"
CY = "#22d3ee"; VI = "#a78bfa"; EM = "#34d399"; AM = "#fbbf24"
PK = "#f472b6"; RS = "#fb7185"; SL = "#cbd5e1"

# ---------------------------------------------------------------- SVG icons (Feather-style, outline)
_SVG = {
    "live": '<path d="M15 10l4.55-2.28A1 1 0 0121 8.62v6.76a1 1 0 01-1.45.9L15 14M3 8a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.8"/><path d="M21 15l-5-5L5 21"/>',
    "userplus": '<path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
    "dashboard": '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    "camera": '<path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/><circle cx="12" cy="13" r="4"/>',
    "cameraoff": '<path d="M1 1l22 22M21 21H3a2 2 0 01-2-2V8a2 2 0 012-2h3m4-3h6l2 3h4a2 2 0 012 2v9.34M12 17a4 4 0 01-3.5-6"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "folder": '<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>',
    "folderplus": '<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/><path d="M12 10v6M9 13h6"/>',
    "trash": '<path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"/><path d="M10 11v6M14 11v6"/>',
    "save": '<path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/>',
    "upload": '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><path d="M17 8l-5-5-5 5M12 3v12"/>',
    "download": '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><path d="M7 10l5 5 5-5M12 15V3"/>',
    "play": '<path d="M6 4l14 8-14 8V4z"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    "refresh": '<path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.5 9a9 9 0 0114.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0020.5 15"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M7 15l4-4 4 4 5-6"/>',
    "x": '<path d="M18 6L6 18M6 6l12 12"/>',
    "check": '<path d="M20 6L9 17l-5-5"/>',
    "apply": '<path d="M12 2a10 10 0 100 20 10 10 0 000-20z"/><path d="M8 12l3 3 5-6"/>',
    "kiosk": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/><circle cx="12" cy="10" r="3"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/>',
    "hand": '<path d="M18 11V6a2 2 0 00-4 0M14 10V4a2 2 0 00-4 0v2M10 10.5V6a2 2 0 00-4 0v8M18 8a2 2 0 014 0v6a8 8 0 01-8 8h-2c-2.8 0-4.5-.86-6.42-2.78l-3.3-3.3a2.05 2.05 0 012.9-2.9L10 15"/>',
}


def make_icon(name: str, color: str = C_TEXT, size: int = 20) -> QIcon:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
           f'{_SVG[name]}</svg>')
    r = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    r.render(p, QRectF(0, 0, size, size))
    p.end()
    return QIcon(pm)


def btn(text: str, icon: str, color: str = SL, primary: bool = False,
        danger: bool = False) -> QPushButton:
    b = QPushButton("  " + text)
    b.setIcon(make_icon(icon, "#ffffff" if primary else color, 18))
    b.setIconSize(QSize(18, 18))
    if primary:
        b.setObjectName("Primary")
    elif danger:
        b.setObjectName("Danger")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


# ---------------------------------------------------------------- QSS
QSS = f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; color: {C_TEXT}; font-size: 13px; }}
QMainWindow, #Root {{ background: {C_BG}; }}
#Nav {{ background: #0e1220; border-right: 1px solid #1d2336; }}
#Brand {{ font-size: 15px; font-weight: 800; padding: 18px 18px 2px; color: #fff; }}
#BrandSub {{ font-size: 9px; color: {ACCENT}; padding: 0 18px 14px; letter-spacing:.22em; font-weight:700; }}
QListWidget#NavList {{ background: transparent; border: 0; padding: 6px 6px; outline: 0; }}
QListWidget#NavList::item {{ padding: 11px 12px; border-radius: 11px; margin: 3px 6px; color:#aeb4c6; }}
QListWidget#NavList::item:selected {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(139,92,246,.30), stop:1 rgba(244,114,182,.14));
    color: #ffffff; border-left: 3px solid {VI};
}}
QListWidget#NavList::item:hover {{ background: rgba(255,255,255,.06); }}
#Header {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6d5efc, stop:.55 #9b5cf6, stop:1 #f472b6);
           border-radius: 16px; }}
#HeaderTitle {{ font-size: 18px; font-weight: 800; color: #fff; }}
#HeaderSub   {{ font-size: 11px; color: rgba(255,255,255,.9); }}
#Card {{ background: {C_CARD}; border: 1px solid {C_LINE}; border-radius: 16px; }}
#Stat {{ background: {C_CARD}; border: 1px solid {C_LINE}; border-radius: 14px; }}
#StatV {{ font-size: 22px; font-weight: 800; color:#fff; }}
#StatK {{ font-size: 11px; color:{C_MUT}; }}
#Video {{ background: #05070e; border: 1px solid {C_LINE}; border-radius: 14px; }}
QLabel#Hint {{ color: {C_MUT}; font-size: 12px; }}
QPushButton {{
    background: #1b2136; border: 1px solid #313a58; border-radius: 10px;
    padding: 9px 15px; color: {SL}; font-weight: 600;
}}
QPushButton:hover {{ background: #232b47; }}
QPushButton:disabled {{ color:#5a6178; background:#161b2b; border-color:#242b41; }}
QPushButton#Primary {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6d5efc, stop:1 #b16cff);
    border: 0; color: #fff;
}}
QPushButton#Primary:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #5b4df0, stop:1 #9f57f5); }}
QPushButton#Danger {{ background:#3a1c2c; border-color:#7a2c4b; color:#ffb3cf; }}
QPushButton#Danger:hover {{ background:#48213640; background:#4a2338; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
    background: #101529; border: 1px solid #303a55; border-radius: 9px; padding: 8px 11px; color:{C_TEXT};
    selection-background-color:{ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color:{VI}; }}
QComboBox::drop-down {{ border:0; width:20px; }}
QComboBox QAbstractItemView {{ background:#141a2c; border:1px solid #303a55; selection-background-color:#3a2d6b; }}
QTableWidget {{ background:#101529; border:1px solid {C_LINE}; border-radius:10px; gridline-color:#1e2439; }}
QHeaderView::section {{ background:#141a2c; color:{C_MUT}; border:0; padding:7px 8px; font-weight:700; }}
QTableWidget::item:selected {{ background:#33285f; }}
QListWidget#Tray, QListWidget#FolderGrid {{ background:#101529; border:1px solid {C_LINE}; border-radius:10px; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:2px; }}
QScrollBar::handle:vertical {{ background:#313a58; border-radius:5px; min-height:24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
#Pill {{ background: rgba(139,92,246,.20); color:#d6c8ff; border-radius:999px; padding:4px 13px; font-size:11px; font-weight:700; }}
#PillGood {{ background: rgba(52,211,153,.18); color:#6ee7b7; border-radius:999px; padding:4px 13px; font-size:11px; font-weight:700; }}
"""


# ---------------------------------------------------------------- utils
def bgr_to_qimage(bgr: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    return QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()


def qimage_to_bgr(qimg: QImage) -> np.ndarray:
    qimg = qimg.convertToFormat(QImage.Format.Format_RGB888)
    w, h = qimg.width(), qimg.height()
    ptr = qimg.constBits()
    arr = np.frombuffer(ptr, np.uint8).reshape(h, qimg.bytesPerLine())[:, : w * 3].reshape(h, w, 3)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _khong_dau(s: str) -> str:
    """Bỏ dấu tiếng Việt để vẽ được bằng cv2.putText.

    OpenCV chỉ vẽ được phông Hershey vốn không có ký tự Unicode ngoài ASCII; đưa
    chữ có dấu vào sẽ ra một chuỗi dấu hỏi. Đây cũng là lý do nhãn trên khung
    hình viết "Chua nhan ra" chứ không phải "Chưa nhận ra".
    """
    import unicodedata
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def draw_faces(img_bgr: np.ndarray, items: list[dict], live_thr: float = 0.4) -> np.ndarray:
    """Vẽ kết quả lên khung hình, phân biệt rõ ba trạng thái bằng màu.

    Xanh lá = người đã đăng ký · Cam = chưa nhận ra · Đỏ = nghi giả mạo.
    Màu đỏ được ưu tiên tuyệt đối: dù vector có khớp đến mấy, nghi giả mạo là
    không cho qua.
    """
    out = img_bgr.copy()
    for it in items:
        x1, y1, x2, y2 = (int(v) for v in it["box"])
        live = it.get("liveness")
        # live == -1.0 nghia la CHUA DO DUOC (mat qua nho), khong phai gia mao.
        chua_do = live is not None and live < 0
        spoof = live is not None and not chua_do and live < live_thr
        # Ba trạng thái, ba màu — thứ tự ưu tiên có chủ đích:
        #   ĐỎ   giả mạo   — đã xét đủ và kết luận là giả
        #   VÀNG đang xét  — chưa đủ bằng chứng, CHƯA kết luận gì
        #   XANH đạt       — vừa nhận ra người thật
        #
        # Trạng thái vàng là thứ bản đầu thiếu: khuôn mặt vừa bước vào khung hình
        # bị gắn ngay nhãn GIẢ MẠO trong khi hệ thống chưa quan sát được gì. Kết
        # tội trước khi xét vừa sai vừa làm người dùng hoang mang.
        if spoof:
            color, text = (60, 60, 235), "GIA MAO"
        elif chua_do:
            # KHÔNG hiện tên khi chưa xác minh xong sự sống.
            #
            # Trước đây khung vàng vẫn in tên người khớp nhất, nên khi giơ video
            # một người hoàn toàn khác lên màn hình điện thoại, màn hình vẫn hiện
            # tên người đã đăng ký. Kết quả đó chưa được xác nhận mà lại trình bày
            # y như một kết luận — người xem không có cách nào biết nó chưa chắc.
            #
            # Danh tính chỉ được nêu tên khi đã qua CẢ HAI cửa: khớp vector và
            # chứng minh là người sống.
            color = (60, 190, 245)                       # vàng: đang thu bằng chứng
            text = "Dang kiem tra..."
        elif it.get("label", "Unknown") != "Unknown":
            color = (95, 200, 95)
            text = f"{it['label']} {it.get('score', 0):.2f}"
        else:
            color, text = (60, 165, 245), "Chua nhan ra"
        if live is not None and not spoof and not chua_do:
            text += f"  live {live:.2f}"

        cv2.rectangle(out, (x1, y1), (x2, y2), color, 3 if spoof else 2)
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(out, (x1, y1 - th - 10), (x1 + tw + 8, y1), color, -1)
        cv2.putText(out, text, (x1 + 4, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (255, 255, 255), 2)

        # Khung hình trượt cổng chất lượng thì nói rõ phải sửa gì. "Chưa nhận ra"
        # trần trụi là câu vô dụng nhất có thể hiển thị: hệ thống biết chính xác
        # vấn đề nằm ở đâu mà lại im lặng, còn người đứng trước camera thì chỉ
        # biết thử lại một cách mù mờ.
        hint = _khong_dau(it.get("hint", ""))
        if hint:
            (hw, hh), _ = cv2.getTextSize(hint, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(out, (x1, y2 + 4), (x1 + hw + 8, y2 + hh + 14), color, -1)
            cv2.putText(out, hint, (x1 + 4, y2 + hh + 9), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 255, 255), 1)
    return out


def card(*items, margins=(16, 16, 16, 16), spacing=10) -> QFrame:
    f = QFrame(); f.setObjectName("Card")
    lay = QVBoxLayout(f); lay.setContentsMargins(*margins); lay.setSpacing(spacing)
    for w in items:
        lay.addWidget(w) if isinstance(w, QWidget) else lay.addLayout(w)
    return f


def header(title: str, sub: str) -> QFrame:
    f = QFrame(); f.setObjectName("Header"); f.setFixedHeight(76)
    lay = QVBoxLayout(f); lay.setContentsMargins(22, 12, 22, 12); lay.setSpacing(2)
    t = QLabel(title); t.setObjectName("HeaderTitle")
    s = QLabel(sub); s.setObjectName("HeaderSub")
    lay.addWidget(t); lay.addWidget(s)
    return f


def sanitize(name: str) -> str:
    return name.strip().replace(" ", "_")


# ---------------------------------------------------------------- engine
#: Model ONNX KHÔNG phải bộ trích đặc trưng — chúng nằm chung thư mục `models/`
#: nhưng thuộc tầng khác của pipeline, chọn nhầm là hỏng.
_NOT_EMBEDDERS = ("face_detection", "yunet", "hand_landmarker", "antispoof", "minifas")


def available_models() -> list[tuple[str, str, str]]:
    """Các mô hình trích đặc trưng dùng được: (nhãn hiển thị, backend, weights)."""
    out = [("FaceNet — pretrained, chính xác nhất (107 MB)", "facenet", "")]
    for onnx in sorted(config.MODELS_DIR.glob("*.onnx")):
        if any(k in onnx.stem.lower() for k in _NOT_EMBEDDERS):
            continue
        mb = onnx.stat().st_size / 1e6
        out.append((f"{onnx.stem} — tự train ({mb:.1f} MB, nhanh)", "onnx", str(onnx)))
    return out


class Engine:
    """Lớp bọc quanh `engine.pipeline.FacePipeline` cho giao diện.

    Toàn bộ phần AI nằm trong gói `engine/` — thư viện thuần, không biết gì về Qt.
    Lớp này chỉ dịch qua lại giữa API của thư viện và thứ các trang giao diện cần.
    """

    def __init__(self):
        self.backbone = "facenet"
        self.weights = ""
        self.db_path = str(config.DB_PATH)
        self.pipeline: FacePipeline | None = None
        self.db: dict = {}
        self._settings = EngineSettings()
        self._settings.detect.backend = "yunet"      # nhanh hơn MTCNN 6.8 lần
        self._settings.quality.enabled = True
        self._settings.track.enabled = True
        # Chống giả mạo BẬT SẴN bằng phát hiện chớp mắt.
        #
        # Trước đây dòng này tắt cứng liveness và để người dùng tự bật trong giao
        # diện. Nghe thì linh hoạt, nhưng với một sản phẩm điểm danh thì đó là
        # chọn mặc định sai: chốt an ninh quan trọng nhất bị tắt mỗi lần mở ứng
        # dụng, và người vận hành phải nhớ bật lại — không nhớ thì giơ ảnh trong
        # điện thoại là điểm danh hộ được, đúng như đã đo (APCER 100%).
        #
        # Mặc định an toàn thì phải là BẬT; ai cần tắt để trình diễn thì tắt có ý
        # thức trong giao diện.
        self._settings.liveness.enabled = True
        self._settings.liveness.backend = "blink"   # ACER 0% trên tấn công thật

    # ------------------------------------------------------------- vòng đời
    def load(self):
        self._build_pipeline()
        self.reload_db()

    def _build_pipeline(self):
        s = self._settings
        s.embed.backend = self.backbone
        s.embed.weights = self.weights
        self.pipeline = FacePipeline(s)

    def set_backbone(self, backbone: str, weights: str = ""):
        self.backbone, self.weights = backbone, weights
        self._build_pipeline()
        self.reload_db()

    @property
    def threshold(self) -> float:
        return self._settings.match_threshold

    @threshold.setter
    def threshold(self, v: float):
        self._settings.match_threshold = float(v)

    @property
    def detector(self):
        return self.pipeline.detector if self.pipeline else None

    def describe(self) -> dict:
        return self.pipeline.describe() if self.pipeline else {}

    # ------------------------------------------------------------ cơ sở dữ liệu
    def reload_db(self):
        """Nạp `embeddings.pkl` rồi dựng lại chỉ mục tra cứu.

        File pickle là nguồn sự thật; chỉ mục chỉ là bản dựng lại được, nên đổi
        mô hình hay mất file chỉ mục đều không mất dữ liệu đăng ký.
        """
        self.db = load_db(self.db_path)
        if not self.pipeline:
            return
        self.pipeline.index.reset()
        dim = self.pipeline.embedder.dim
        for name, mat in self.db.items():
            mat = np.atleast_2d(np.asarray(mat, dtype=np.float32))
            if mat.shape[1] != dim:
                continue          # vector cũ khác số chiều -> cần dựng lại DB
            self.pipeline.add_to_index(mat, name)

    def db_matches_model(self) -> bool:
        """DB có khớp số chiều của mô hình đang chọn không."""
        if not self.pipeline or not self.db:
            return True
        dim = self.pipeline.embedder.dim
        return all(np.atleast_2d(m).shape[1] == dim for m in self.db.values())

    # ------------------------------------------------------------- nhận diện
    def recognize_items(self, frame_bgr: np.ndarray, downscale: int = 0):
        """Nhận diện một ảnh rời rạc. Trả về list dict cho giao diện vẽ."""
        img, scale = frame_bgr, 1.0
        if downscale:
            h, w = img.shape[:2]
            if w > downscale:
                scale = downscale / w
                img = cv2.resize(img, (int(w * scale), int(h * scale)))
        items = []
        for face, ident in self.pipeline.process_image(img):
            box = (np.asarray(face.box, dtype=float) / scale).astype(int)
            items.append({"box": box, "label": ident.label, "score": ident.score,
                          "quality": face.quality, "liveness": face.liveness})
        return items

    def track_frame(self, frame_bgr: np.ndarray, downscale: int = 0):
        """Nhận diện một khung video CÓ bám vết và bỏ phiếu.

        Khác `recognize_items` ở hai điểm quan trọng: nhãn được lấy theo đa số
        của nhiều khung nên không nhấp nháy, và mạng trích đặc trưng chỉ chạy lại
        mỗi vài khung trên mỗi người nên nhẹ hơn nhiều.
        """
        img, scale = frame_bgr, 1.0
        if downscale:
            h, w = img.shape[:2]
            if w > downscale:
                scale = downscale / w
                img = cv2.resize(img, (int(w * scale), int(h * scale)))
        items = []
        for tr in self.pipeline.process_frame(img):
            # Vẫn vẽ vết còn sống dù khung này phát hiện hụt.
            #
            # Trước đây bỏ qua mọi vết có misses > 0, nên chỉ cần một khung hụt là
            # khung bao biến mất rồi hiện lại ở khung sau — nhìn như đèn nhấp nháy
            # liên tục. Bộ bám vết vốn đã giữ vết sống tới `max_age` khung chính
            # là để vượt qua những lần hụt như vậy; vứt đi ở đây là phá bỏ đúng
            # thứ nó sinh ra để làm.
            #
            # Hụt quá vài khung thì mới thôi vẽ, để hộp không còn treo lại ở chỗ
            # người đã rời đi.
            if tr.misses > 3:
                continue
            box = (np.asarray(tr.box, dtype=float) / scale).astype(int)
            items.append({"box": box, "label": tr.identity.label,
                          "score": tr.identity.score, "track_id": tr.track_id,
                          "confirmed": tr.confirmed, "votes": tr.vote_ratio,
                          "liveness": tr.liveness, "hint": tr.hint})
        return items

    def reset_tracker(self):
        if self.pipeline:
            self.pipeline.tracker.reset()

    def newly_confirmed(self):
        """Các vết vừa đủ tin cậy — mỗi vết chỉ phát đúng một lần.

        Đây là tín hiệu để kiosk gửi bản ghi điểm danh: một người đứng trước
        camera 30 giây chỉ tạo ra đúng một sự kiện.
        """
        return self.pipeline.newly_confirmed() if self.pipeline else []

    # ---------------------------------------------------------- chống giả mạo
    LIVENESS_MODES = [
        ("Tắt", "none"),
        ("Thụ động — kết cấu ảnh", "texture"),
        ("Chủ động — chớp mắt", "blink"),
        ("Kết hợp cả hai", "combo"),
    ]

    def set_liveness(self, backend: str):
        """Đổi phương pháp chống giả mạo. Dựng lại pipeline vì tầng này nằm trong đó."""
        self._settings.liveness.enabled = backend not in ("none", "")
        self._settings.liveness.backend = backend or "none"
        self._build_pipeline()
        self.reload_db()

    @property
    def liveness_backend(self) -> str:
        return (self._settings.liveness.backend
                if self._settings.liveness.enabled else "none")

    @property
    def liveness_threshold(self) -> float:
        det = self.pipeline.liveness if self.pipeline else None
        return float(getattr(det, "threshold", self._settings.liveness.threshold))

    def liveness_score(self, frame_bgr: np.ndarray) -> list[float]:
        """Chấm điểm sống cho mọi khuôn mặt trong khung — dùng cho trang kiểm thử."""
        if not self.pipeline or self.pipeline.liveness is None:
            return []
        dets = self.pipeline.detector.detect(frame_bgr)
        if not dets:
            return []
        return [float(s) for s in self.pipeline.liveness.score(frame_bgr, dets)]

    # ---- folder-based data management ----
    @staticmethod
    def folders() -> list[str]:
        d = config.ENROLLED_DIR
        return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.exists() else []

    @staticmethod
    def folder_images(name: str) -> list[Path]:
        d = config.ENROLLED_DIR / name
        return sorted(p for p in d.iterdir() if p.suffix.lower() in IMG_EXT) if d.exists() else []

    @staticmethod
    def make_folder(name: str) -> Path:
        d = config.ENROLLED_DIR / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def add_images_to_folder(name: str, imgs_bgr: list[np.ndarray]) -> int:
        """Ghi ảnh vào folder, trả về **số ảnh ghi được thật sự**.

        Bản cũ trả về `len(imgs_bgr)` — số ảnh *được yêu cầu ghi* — nên khi
        `imwrite` hỏng toàn bộ, giao diện vẫn báo "đã thêm N ảnh". Đếm theo kết
        quả thật thì nơi gọi mới có cái để so và báo lỗi cho người dùng.
        """
        d = Engine.make_folder(name)
        ts = int(time.time() * 1000)
        so_ghi = 0
        for j, im in enumerate(imgs_bgr):
            if ghi_anh(d / f"{name}_{ts}_{j:02d}.jpg", im):
                so_ghi += 1
        return so_ghi

    def commit_folder(self, name: str, strict: bool = True):
        """Nạp toàn bộ ảnh trong folder vào DB nhận diện.

        Đi qua **cổng chất lượng**: ảnh mờ, thiếu sáng hay quay ngang quá đà bị
        loại thay vì lặng lẽ vào gallery — một ảnh kém lọt vào đây sẽ gây nhận
        nhầm về sau mà rất khó truy ra nguyên nhân.

        Trả về (số vector nạp được, số ảnh bị loại, danh sách lý do).
        """
        imgs = [doc_anh(p) for p in self.folder_images(name)]
        imgs = [im for im in imgs if im is not None]
        if not imgs:
            return 0, 0, []

        vectors, reports = self.pipeline.embed_for_enrollment(imgs, strict=strict)
        rejected = [r for r in reports if not r["ok"]]
        if len(vectors) == 0:
            return 0, len(rejected), [r.get("reason", "?") for r in rejected]

        db = load_db(self.db_path)
        db[name] = np.asarray(vectors, dtype=np.float32)   # thay toàn bộ = đúng nội dung folder
        save_db(db, self.db_path)
        self.db = db
        self.reload_db()
        return len(vectors), len(rejected), [r.get("reason", "?") for r in rejected]

    def remove_from_db(self, name: str):
        db = load_db(self.db_path)
        db.pop(name, None)
        save_db(db, self.db_path)
        self.reload_db()


# ---------------------------------------------------------------- threads
def doc_khung(cap):
    """Đọc một khung từ camera và lật ngang kiểu gương.

    Webcam trả về ảnh như máy ảnh chụp: giơ tay phải thì tay hiện bên trái màn
    hình. Người đứng trước camera lại quen nhìn như soi gương, nên ảnh thô trông
    "ngược". Trước đây chỉ tab Cử chỉ tay lật ảnh, các tab khác không, nên cùng
    một camera mà mỗi tab một chiều.

    Lật ngay lúc đọc — trước khi nhận diện và vẽ khung — để chữ vẽ lên không bị
    ngược theo. Lật không làm hỏng nhận diện với ảnh đã đăng ký trước đó (chưa
    lật): đo trên 12 ảnh THANHVU, vector của ảnh lật và ảnh gốc giống nhau
    cosine tối thiểu 0,910, trung bình 0,956 — cao xa ngưỡng nhận 0,68.
    """
    ok, frame = cap.read()
    if ok:
        frame = cv2.flip(frame, 1)
    return ok, frame


class CameraThread(QThread):
    frame_ready = Signal(QImage, list)
    failed = Signal(str)

    def __init__(self, engine: Engine, cam_index: int = 0, every: int = 6, recognize: bool = True):
        super().__init__()
        self.engine = engine
        self.cam_index = cam_index
        self.every = every
        self.recognize = recognize
        self._run = True
        self._i = 0
        self._items: list = []

    def stop(self):
        self._run = False
        self.wait(2000)

    def run(self):
        cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.failed.emit(f"Không mở được camera (index {self.cam_index}). Thử đổi index.")
            return
        while self._run:
            ok, frame = doc_khung(cap)
            if not ok:
                self.failed.emit("Mất tín hiệu camera.")
                break
            self._i += 1
            if self.recognize:
                # Bám vết chạy MỖI khung: phát hiện chỉ tốn ~4 ms, còn mạng trích
                # đặc trưng thì pipeline tự giãn ra mỗi `embed_every` khung trên
                # từng người. Nhờ vậy hộp bao bám mượt mà máy vẫn nhẹ.
                try:
                    self._items = self.engine.track_frame(frame, downscale=640)
                except Exception:  # noqa: BLE001
                    self._items = []
            shown = (draw_faces(frame, self._items, self.engine.liveness_threshold)
                     if self.recognize else frame)
            self.frame_ready.emit(bgr_to_qimage(shown), list(self._items))
            self.msleep(12)
        cap.release()


class GestureThread(QThread):
    frame_ready = Signal(QImage, str)
    failed = Signal(str)

    def __init__(self, engine: Engine, cam_index: int = 0, with_face: bool = False,
                 show_skeleton: bool = True):
        super().__init__()
        self.engine = engine
        self.cam_index = cam_index
        self.with_face = with_face
        self.show_skeleton = show_skeleton
        self._run = True
        self._clear_req = False
        self._i = 0
        self._face_items: list = []
        self.fx = None                     # gán trong run(), giao diện đọc tới

    def request_clear(self):
        self._clear_req = True

    def stop(self):
        self._run = False
        self.wait(3000)

    def run(self):
        try:
            from src.hands import HandTracker, GestureFX
            tracker = HandTracker(num_hands=1)
            # Phơi ra thành thuộc tính để giao diện đổi được bảng gán hiệu ứng
            # ngay lúc đang chạy, không phải dừng camera rồi bật lại.
            fx = self.fx = GestureFX()
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"Không khởi tạo được hand tracking: {e}")
            return
        cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.failed.emit(f"Không mở được camera (index {self.cam_index}).")
            tracker.close()
            return
        t0 = time.time()
        while self._run:
            ok, frame = doc_khung(cap)
            if not ok:
                self.failed.emit("Mất tín hiệu camera.")
                break
            self._i += 1
            if self._clear_req:
                fx.clear(); self._clear_req = False
            try:
                hands = tracker.process(frame, int((time.time() - t0) * 1000))
            except Exception:  # noqa: BLE001
                hands = []
            fx.update(hands)
            out = fx.render(frame, hands, self.show_skeleton)
            if self.with_face and self._i % 6 == 0:
                try:
                    self._face_items = self.engine.recognize_items(frame, downscale=640)
                except Exception:  # noqa: BLE001
                    self._face_items = []
            if self.with_face and self._face_items:
                out = draw_results(out, self._face_items)
            self.frame_ready.emit(bgr_to_qimage(out), fx.status)
            self.msleep(8)
        tracker.close()
        cap.release()


class CmdThread(QThread):
    line = Signal(str)
    done = Signal(int)

    def __init__(self, args: list[str]):
        super().__init__()
        self.args = args

    def run(self):
        try:
            # Ép UTF-8 ở CẢ HAI ĐẦU của đường ống.
            #
            # Thiếu việc này thì `text=True` để Python tự chọn bảng mã theo vùng
            # miền của Windows (cp1252), trong khi tiến trình con in chữ Việt có
            # dấu ở UTF-8 — đọc tới ký tự đầu tiên có dấu là vỡ với thông báo
            # "'charmap' codec can't decode byte 0x81". Lệnh vẫn chạy đúng trong
            # nền, chỉ là giao diện không đọc nổi kết quả và báo lỗi oan.
            #
            #   encoding ở đây   : phía ĐỌC — cách giao diện giải mã dòng nhận được
            #   PYTHONIOENCODING : phía GHI — ép tiến trình con in ra UTF-8
            #
            # Chỉ đặt một trong hai vẫn hỏng, vì hai đầu phải nói cùng một bảng mã.
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
            p = subprocess.Popen([sys.executable, "-m", *self.args], cwd=str(config.ROOT),
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace", env=env)
            for ln in p.stdout:  # type: ignore[union-attr]
                self.line.emit(ln.rstrip())
            p.wait()
            self.done.emit(p.returncode)
        except Exception as e:  # noqa: BLE001
            self.line.emit(f"{type(e).__name__}: {e}")
            self.done.emit(-1)


# ---------------------------------------------------------------- pages
class LivePage(QWidget):
    def __init__(self, engine: Engine):
        super().__init__()
        self.engine = engine
        self.cam: CameraThread | None = None

        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(14)
        root.addWidget(header("Nhận diện trực tiếp",
                              "Camera chạy liên tục — có người trong khung là nhận diện ngay"))

        ctl = QHBoxLayout()
        self.b_start = btn("Bắt đầu", "play", primary=True)
        self.b_start.clicked.connect(self.toggle)
        self.cam_idx = QSpinBox(); self.cam_idx.setRange(0, 8); self.cam_idx.setPrefix("cam ")
        self.every = QSpinBox(); self.every.setRange(1, 15); self.every.setValue(6)
        self.every.setPrefix("mỗi "); self.every.setSuffix(" khung")
        self.thr = QDoubleSpinBox(); self.thr.setRange(0, 1); self.thr.setSingleStep(0.01)
        self.thr.setValue(engine.threshold); self.thr.setPrefix("ngưỡng ")
        self.thr.valueChanged.connect(lambda v: setattr(self.engine, "threshold", float(v)))
        # Nút gạt hai trạng thái thay cho danh sách bốn lựa chọn.
        #
        # Ở màn hình thử nghiệm này, câu hỏi người dùng thực sự đặt ra chỉ có hai:
        # "nhận tất cả xem nó bắt được ai" hay "chặn giả mạo xem nó có chặn đúng".
        # Bốn lựa chọn kỹ thuật (none/texture/blink/combo) là cách nghĩ của người
        # viết engine, không phải của người đang đứng trước camera. Các tab khác
        # giữ nguyên danh sách đầy đủ cho ai cần chọn sâu.
        self.b_live = QPushButton()
        self.b_live.setCheckable(True)
        self.b_live.setChecked(True)          # mặc định an toàn là BẬT
        self.b_live.setMinimumWidth(230)
        self.b_live.clicked.connect(self._doi_che_do_song)
        self._ve_nut_song()
        for w in (self.b_start, self.cam_idx, self.every, self.thr, self.b_live):
            ctl.addWidget(w)
        ctl.addStretch(1)
        root.addLayout(ctl)

        self.video = QLabel("Camera đang tắt"); self.video.setObjectName("Video")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(720, 460)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self.video, 1)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Mã vết", "Tên", "Cosine", "Phiếu bầu", "Điểm sống"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumHeight(150)
        root.addWidget(self.table)

    def _set_liveness(self):
        """Đổi phương pháp chống giả mạo — phải dựng lại pipeline nên dừng camera."""
        was_running = bool(self.cam and self.cam.isRunning())
        if was_running:
            self.toggle()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.engine.set_liveness("blink" if self.b_live.isChecked() else "none")
        finally:
            QApplication.restoreOverrideCursor()
        if was_running:
            self.toggle()

    def _ve_nut_song(self):
        """Nhãn và màu của nút phải nói rõ HỆ QUẢ, không chỉ tên chế độ.

        "Chống giả mạo: Tắt" không cho người dùng biết điều gì đang thực sự xảy
        ra. "Nhận tất cả — kể cả ảnh, video" thì nói thẳng.
        """
        if self.b_live.isChecked():
            self.b_live.setText("  Chống giả mạo: BẬT (chớp mắt)")
            self.b_live.setIcon(make_icon("shield", "#fff", 17))
            self.b_live.setStyleSheet(
                f"background:{EM}; color:#06251c; font-weight:700;")
        else:
            self.b_live.setText("  Nhận tất cả — kể cả ảnh, video")
            self.b_live.setIcon(make_icon("image", "#fff", 17))
            self.b_live.setStyleSheet(
                f"background:{AM}; color:#2b1a00; font-weight:700;")

    def _doi_che_do_song(self):
        self._ve_nut_song()
        self._set_liveness()

    def toggle(self):
        if self.cam and self.cam.isRunning():
            self.cam.stop(); self.cam = None
            self.b_start.setText("  Bắt đầu")
            self.b_start.setIcon(make_icon("play", "#fff", 18))
            self.video.setText("Camera đang tắt")
            return
        if not self.engine.db:
            QMessageBox.warning(self, "Chưa có dữ liệu", "Database rỗng — hãy đăng ký người trước.")
            return
        self.engine._settings.track.embed_every = self.every.value()
        self.engine.reset_tracker()
        self.cam = CameraThread(self.engine, self.cam_idx.value(), self.every.value(), recognize=True)
        self.cam.frame_ready.connect(self.on_frame)
        self.cam.failed.connect(self.on_fail)
        self.cam.start()
        self.b_start.setText("  Dừng")
        self.b_start.setIcon(make_icon("stop", "#fff", 18))

    def on_frame(self, qimg: QImage, items: list):
        self.video.setPixmap(QPixmap.fromImage(qimg).scaled(
            self.video.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.table.setRowCount(len(items))
        for r, it in enumerate(items):
            votes = it.get("votes", 0.0)
            mark = "  ✓" if it.get("confirmed") else ""
            self.table.setItem(r, 0, QTableWidgetItem(f"#{it.get('track_id', '-')}"))
            self.table.setItem(r, 1, QTableWidgetItem(str(it["label"]) + mark))
            self.table.setItem(r, 2, QTableWidgetItem(f"{it['score']:.3f}"))
            self.table.setItem(r, 3, QTableWidgetItem(f"{votes*100:.0f}%"))
            live = it.get("liveness")
            self.table.setItem(r, 4, QTableWidgetItem(
                "—" if live is None else
                ("đang kiểm tra" if live < 0 else
                 f"{live:.2f}" + ("  GIẢ MẠO" if live < self.engine.liveness_threshold else ""))))

    def on_fail(self, msg: str):
        if self.cam:
            self.cam.stop(); self.cam = None
        self.b_start.setText("  Bắt đầu"); self.b_start.setIcon(make_icon("play", "#fff", 18))
        self.video.setText(msg)

    def closeEvent(self, e):
        if self.cam:
            self.cam.stop()
        super().closeEvent(e)


class ImagePage(QWidget):
    def __init__(self, engine: Engine):
        super().__init__()
        self.engine = engine
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(14)
        root.addWidget(header("Nhận diện ảnh", "Mở một ảnh và xem hệ thống nhận ra ai"))

        top = QHBoxLayout()
        b = btn("Chọn ảnh", "image", primary=True); b.clicked.connect(self.pick)
        top.addWidget(b); top.addStretch(1)
        root.addLayout(top)

        body = QHBoxLayout(); body.setSpacing(14)
        self.canvas = QLabel("Chưa có ảnh"); self.canvas.setObjectName("Video")
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setMinimumSize(640, 460)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Tên", "cosine"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumWidth(340)
        body.addWidget(self.canvas, 1)
        body.addWidget(self.table)
        root.addLayout(body, 1)

    def pick(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh", "", "Ảnh (*.jpg *.jpeg *.png *.bmp *.webp)")
        if not fn:
            return
        img = doc_anh(fn)
        if img is None:
            QMessageBox.warning(self, "Lỗi", "Không đọc được ảnh."); return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            items = self.engine.recognize_items(img, downscale=0)
        finally:
            QApplication.restoreOverrideCursor()
        shown = draw_results(img, items)
        self.canvas.setPixmap(QPixmap.fromImage(bgr_to_qimage(shown)).scaled(
            self.canvas.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.table.setRowCount(len(items))
        for r, it in enumerate(items):
            self.table.setItem(r, 0, QTableWidgetItem(str(it["label"])))
            self.table.setItem(r, 1, QTableWidgetItem(f"{it['score']:.3f}"))
        if not items:
            QMessageBox.information(self, "Kết quả", "Không phát hiện khuôn mặt.")


class GesturePage(QWidget):
    HINTS = [("draw", CY, "1 ngón trỏ", "vẽ theo đầu ngón"),
             ("move", VI, "chữ V (2 ngón)", "di chuyển, không vẽ"),
             ("fist", RS, "nắm tay", "xoá hết nét"),
             ("open", EM, "xoè cả bàn tay", "đổi màu + hiệu ứng"),
             ("pinch", AM, "chụm cái + trỏ", "chấm 1 điểm")]

    def __init__(self, engine: Engine):
        super().__init__()
        self.engine = engine
        self.th: GestureThread | None = None

        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(14)
        root.addWidget(header("Cử chỉ tay", "Vẽ trên không bằng ngón tay — kèm hiệu ứng, có thể bật nhận diện mặt cùng lúc"))

        ctl = QHBoxLayout()
        self.b_start = btn("Bắt đầu", "play", primary=True); self.b_start.clicked.connect(self.toggle)
        self.cam_idx = QSpinBox(); self.cam_idx.setRange(0, 8); self.cam_idx.setPrefix("cam ")
        self.chk_face = QCheckBox("Kèm nhận diện mặt"); self.chk_face.toggled.connect(self._sync)
        self.chk_skel = QCheckBox("Hiện khớp tay"); self.chk_skel.setChecked(True); self.chk_skel.toggled.connect(self._sync)
        self.b_clear = btn("Xoá nét", "trash", color=RS); self.b_clear.clicked.connect(self._clear)
        for w in (self.b_start, self.cam_idx, self.chk_face, self.chk_skel, self.b_clear):
            ctl.addWidget(w)
        ctl.addStretch(1)

        # Gán cử chỉ -> hiệu ứng ngay trong giao diện. Danh sách hiệu ứng quét từ
        # thư mục effects/ lúc khởi động, nên thả thêm thư mục con vào là có thêm
        # lựa chọn, không phải sửa mã.
        self.chon_fx: dict[str, QComboBox] = {}
        try:
            from src.effects import BoHieuUng
            ten_fx = ["(không)"] + BoHieuUng().ten
        except Exception:                        # noqa: BLE001
            ten_fx = ["(không)"]
        from src.hands import GestureFX
        nhan_cu_chi = {"open": "Xoè tay", "pinch": "Chụm ngón", "fist": "Nắm tay"}
        for ma, nhan in nhan_cu_chi.items():
            cb = QComboBox(); cb.addItems(ten_fx); cb.setMinimumWidth(150)
            mac_dinh = GestureFX.GAN_MAC_DINH.get(ma, "(không)")
            i = cb.findText(mac_dinh)
            cb.setCurrentIndex(i if i >= 0 else 0)
            cb.currentTextChanged.connect(self._doi_hieu_ung)
            self.chon_fx[ma] = cb
            l = QLabel(nhan); l.setObjectName("Hint")
            ctl.addWidget(l); ctl.addWidget(cb)
        ctl.addStretch(1)
        self.status = QLabel("—"); self.status.setObjectName("Pill")
        ctl.addWidget(self.status)
        root.addLayout(ctl)

        self.video = QLabel("Camera đang tắt"); self.video.setObjectName("Video")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(720, 460)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self.video, 1)

        legend = QHBoxLayout(); legend.setSpacing(16)
        for _, col, name, desc in self.HINTS:
            dot = QLabel("●"); dot.setStyleSheet(f"color:{col}; font-size:15px;")
            txt = QLabel(f"<b>{name}</b> — {desc}"); txt.setObjectName("Hint")
            cell = QHBoxLayout(); cell.setSpacing(6); cell.addWidget(dot); cell.addWidget(txt)
            legend.addLayout(cell)
        legend.addStretch(1)
        root.addWidget(card(legend, margins=(14, 10, 14, 10)))

    def _sync(self):
        if self.th:
            self.th.with_face = self.chk_face.isChecked()
            self.th.show_skeleton = self.chk_skel.isChecked()

    def _doi_hieu_ung(self):
        """Cập nhật bảng gán ngay khi người dùng đổi lựa chọn.

        Sửa thẳng vào `fx.gan` của luồng đang chạy nên có hiệu lực lập tức, không
        phải dừng camera rồi bật lại.
        """
        gan = {ma: (cb.currentText() if cb.currentText() != "(không)" else None)
               for ma, cb in self.chon_fx.items()}
        gan = {k: v for k, v in gan.items() if v}
        if self.th is not None and getattr(self.th, "fx", None) is not None:
            self.th.fx.gan = gan

    def _clear(self):
        if self.th:
            self.th.request_clear()

    def toggle(self):
        if self.th and self.th.isRunning():
            self.th.stop(); self.th = None
            self.b_start.setText("  Bắt đầu"); self.b_start.setIcon(make_icon("play", "#fff", 18))
            self.video.setText("Camera đang tắt"); self.status.setText("—")
            return
        self.th = GestureThread(self.engine, self.cam_idx.value(),
                                self.chk_face.isChecked(), self.chk_skel.isChecked())
        # Áp bảng gán người dùng đang chọn ngay khi luồng vừa dựng xong FX.
        self.th.started.connect(lambda: QTimer.singleShot(400, self._doi_hieu_ung))
        self.th.frame_ready.connect(self.on_frame)
        self.th.failed.connect(self.on_fail)
        self.th.start()
        self.b_start.setText("  Dừng"); self.b_start.setIcon(make_icon("stop", "#fff", 18))
        self.video.setText("Đang mở camera + tải model bàn tay...")

    def on_frame(self, qimg: QImage, status: str):
        self.video.setPixmap(QPixmap.fromImage(qimg).scaled(
            self.video.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.status.setText(status)

    def on_fail(self, msg: str):
        if self.th:
            self.th.stop(); self.th = None
        self.b_start.setText("  Bắt đầu"); self.b_start.setIcon(make_icon("play", "#fff", 18))
        self.video.setText(msg)

    def closeEvent(self, e):
        if self.th:
            self.th.stop()
        super().closeEvent(e)


class KioskThread(QThread):
    """Camera cho chế độ kiosk.

    Chạy engine ở local để phản hồi tức thì, và phát tín hiệu mỗi khi một người
    được **xác nhận** (đủ số phiếu qua nhiều khung hình) — đó là lúc gửi bản ghi
    điểm danh lên server, chứ không phải mỗi khung hình nhận ra ai đó.
    """
    frame_ready = Signal(QImage, list)
    confirmed = Signal(str, float, bytes)      # nhãn, độ tin cậy, ảnh JPEG
    spoofed = Signal(str, float)               # nhãn, điểm sống — bị chặn vì nghi giả mạo
    failed = Signal(str)

    def __init__(self, engine: Engine, cam_index: int = 0):
        super().__init__()
        self.engine = engine
        self.cam_index = cam_index
        self._run = True
        self._bao_gia_mao: dict[str, float] = {}   # chống ngập nhật ký

    def stop(self):
        self._run = False
        self.wait(3000)

    def run(self):
        cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.failed.emit(f"Không mở được camera {self.cam_index}."); return
        while self._run:
            ok, frame = doc_khung(cap)
            if not ok:
                self.failed.emit("Mất tín hiệu camera."); break
            try:
                items = self.engine.track_frame(frame, downscale=640)
                for tr in self.engine.newly_confirmed():
                    # Chặn giả mạo NGAY TẠI KIOSK, trước khi gửi đi.
                    #
                    # Máy chủ không thể làm thay việc này: nó chỉ nhận được MỘT
                    # tấm ảnh, trong khi phát hiện chớp mắt vốn là tín hiệu theo
                    # thời gian, phải có chuỗi khung hình mới đo được. Liveness
                    # vì vậy bắt buộc phải nằm ở nơi có luồng video — tức là ở
                    # đây. Thiếu chốt này thì giơ ảnh trong điện thoại là điểm
                    # danh hộ được, đúng như đã đo.
                    nguong = self.engine.liveness_threshold
                    # Chưa đo xong sự sống thì CHỜ THÊM — và quan trọng là phải
                    # TRẢ LẠI quyền phát cho vết.
                    #
                    # `newly_confirmed()` đánh dấu vết là "đã phát" ngay lúc trả
                    # về. Nếu ở đây chỉ `continue` thì vết bị đốt vĩnh viễn: người
                    # dùng bước vào, vết được xác nhận sau ~0,2 giây trong khi
                    # liveness còn đang đo, thế là mất luôn cơ hội — chớp mắt xong
                    # điểm sống lên 1,00 cũng không bao giờ ghi sổ được nữa.
                    #
                    # Đây đúng là hiện tượng quan sát được: khung xanh, live 1.00,
                    # mà nhật ký không có dòng điểm danh nào.
                    if tr.liveness is not None and tr.liveness < 0:
                        tr.announced = False      # cho phép phát lại khi đo xong
                        continue
                    if tr.liveness is not None and tr.liveness < nguong:
                        # Cũng trả lại quyền phát: một người thật có thể bị chấm
                        # dưới ngưỡng trong lúc chưa chớp lại, và nếu đốt vết ở
                        # đây thì họ chớp mắt xong cũng không điểm danh được nữa.
                        # Chỉ báo ra tối đa 3 giây một lần để khỏi ngập nhật ký.
                        gio = time.time()
                        if gio - self._bao_gia_mao.get(tr.identity.label, 0) > 3.0:
                            self._bao_gia_mao[tr.identity.label] = gio
                            self.spoofed.emit(tr.identity.label, float(tr.liveness))
                        tr.announced = False
                        continue
                    ok_enc, buf = cv2.imencode(".jpg", frame,
                                               [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                    if ok_enc:
                        self.confirmed.emit(tr.identity.label,
                                            float(tr.identity.score), buf.tobytes())
            except Exception:                       # noqa: BLE001
                items = []
            shown = draw_faces(frame, items, self.engine.liveness_threshold)
            self.frame_ready.emit(bgr_to_qimage(shown), items)
            self.msleep(10)
        cap.release()


class CheckinWorker(QThread):
    """Gửi một bản ghi điểm danh lên server ở luồng riêng.

    Bắt buộc phải tách luồng: một vòng mạng chậm sẽ làm đứng hình camera nếu gọi
    thẳng trong luồng giao diện.
    """
    done = Signal(object)

    def __init__(self, client, jpeg: bytes, session_id):
        super().__init__()
        self.client, self.jpeg, self.session_id = client, jpeg, session_id

    def run(self):
        self.done.emit(self.client.checkin(self.jpeg, self.session_id))


class KioskPage(QWidget):
    """Màn hình đặt tại cửa lớp — người đi qua là tự điểm danh."""

    def __init__(self, engine: Engine):
        super().__init__()
        from desktop_api import ApiClient, QueueSyncer
        self.engine = engine
        self.client = ApiClient()
        self.syncer = QueueSyncer(self.client)
        self.syncer.start()
        self.cam: KioskThread | None = None
        self.workers: list = []
        self.session_id = None
        self._recent: dict[str, float] = {}      # chống gửi trùng ở phía kiosk

        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(14)
        root.addWidget(header("Kiosk điểm danh",
                              "Đặt màn hình ở cửa lớp — có người trong khung là tự ghi nhận"))

        # --- hàng kết nối máy chủ ---
        conn = QHBoxLayout()
        self.ed_url = QLineEdit(os.environ.get("FACEID_API_URL", "http://localhost:8090")); self.ed_url.setMaximumWidth(230)
        self.ed_user = QLineEdit("admin"); self.ed_user.setMaximumWidth(110)
        self.ed_pass = QLineEdit(); self.ed_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_pass.setPlaceholderText("mật khẩu"); self.ed_pass.setMaximumWidth(130)
        self.ed_device = QLineEdit("kiosk-A101"); self.ed_device.setMaximumWidth(130)
        b_conn = btn("Kết nối", "refresh", color=CY); b_conn.clicked.connect(self.connect)
        self.lbl_conn = QLabel("Chưa kết nối"); self.lbl_conn.setObjectName("Pill")
        for w in (QLabel("Máy chủ"), self.ed_url, QLabel("Tài khoản"), self.ed_user,
                  self.ed_pass, QLabel("Mã máy"), self.ed_device, b_conn):
            conn.addWidget(w)
        conn.addStretch(1); conn.addWidget(self.lbl_conn)
        root.addWidget(card(conn, margins=(14, 10, 14, 10)))

        # --- hàng điều khiển ---
        ctl = QHBoxLayout()
        self.b_start = btn("Bắt đầu điểm danh", "play", primary=True)
        self.b_start.clicked.connect(self.toggle)
        self.cam_idx = QSpinBox(); self.cam_idx.setRange(0, 8); self.cam_idx.setPrefix("cam ")
        self.cb_session = QComboBox(); self.cb_session.setMinimumWidth(210)
        self.cb_session.addItem("Tự chọn ca theo giờ", None)
        self.lbl_queue = QLabel("Hàng đợi: 0"); self.lbl_queue.setObjectName("Pill")
        b_flush = btn("Đồng bộ ngay", "upload", color=AM); b_flush.clicked.connect(self.flush)
        for w in (self.b_start, self.cam_idx, self.cb_session, b_flush):
            ctl.addWidget(w)
        ctl.addStretch(1); ctl.addWidget(self.lbl_queue)
        root.addLayout(ctl)

        # --- khung hình + thẻ kết quả ---
        body = QHBoxLayout(); body.setSpacing(14)
        self.video = QLabel("Camera đang tắt"); self.video.setObjectName("Video")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(640, 460)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.video, 3)

        right = QVBoxLayout(); right.setSpacing(10)
        self.card_name = QLabel("—")
        self.card_name.setStyleSheet(f"font-size:26px; font-weight:800; color:{C_TEXT};")
        self.card_name.setWordWrap(True)
        self.card_state = QLabel("Chờ người bước vào khung hình")
        self.card_state.setObjectName("Hint"); self.card_state.setWordWrap(True)
        self.card_time = QLabel(""); self.card_time.setObjectName("Pill")
        for w in (self.card_name, self.card_state, self.card_time):
            right.addWidget(w)
        right.addSpacing(8)

        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 9)); self.log.setMinimumHeight(240)
        right.addWidget(QLabel("Nhật ký phiên làm việc"), 0)
        right.addWidget(self.log, 1)

        rc = QFrame(); rc.setObjectName("Card")
        rl = QVBoxLayout(rc); rl.setContentsMargins(18, 18, 18, 18); rl.addLayout(right)
        body.addWidget(rc, 2)
        root.addLayout(body, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(3000)

    # ------------------------------------------------------------ máy chủ
    def connect(self):
        from desktop_api import ApiClient
        self.client.base_url = self.ed_url.text().strip().rstrip("/")
        self.client.device_id = self.ed_device.text().strip() or "kiosk"
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok, msg = self.client.login(self.ed_user.text().strip(), self.ed_pass.text())
        finally:
            QApplication.restoreOverrideCursor()
        self.write(msg)
        if ok:
            self.load_sessions()
        self.refresh_status()

    def load_sessions(self):
        import requests
        self.cb_session.clear()
        self.cb_session.addItem("Tự chọn ca theo giờ", None)
        try:
            r = requests.get(f"{self.client.base_url}/api/sessions",
                             headers={"Authorization": f"Bearer {self.client.token}"}, timeout=6)
            for s in (r.json() if r.ok else []):
                self.cb_session.addItem(
                    f"{s['name']} ({s['start_time'][:5]}-{s['end_time'][:5]})", s["id"])
        except Exception:                           # noqa: BLE001
            pass

    def refresh_status(self):
        n = self.client.queue_size()
        self.lbl_queue.setText(f"Hàng đợi: {n}")
        self.lbl_queue.setObjectName("Pill" if n == 0 else "PillGood")
        self.lbl_conn.setText("Đã kết nối · " + self.client.username
                              if self.client.connected else "Chưa kết nối")

    def flush(self):
        r = self.client.flush_queue()
        self.write(f"Đồng bộ: gửi {r['sent']} · lỗi {r['failed']} · còn {r['remaining']}")
        self.refresh_status()

    # ------------------------------------------------------------- camera
    def toggle(self):
        if self.cam and self.cam.isRunning():
            self.cam.stop(); self.cam = None
            self.b_start.setText("  Bắt đầu điểm danh")
            self.b_start.setIcon(make_icon("play", "#fff", 18))
            self.video.setText("Camera đang tắt"); return
        if not self.engine.db:
            QMessageBox.warning(self, "Chưa có dữ liệu",
                                "Chưa đăng ký ai — hệ thống sẽ không nhận ra người nào."); return
        # Kiosk chạy mà tắt chống giả mạo chính là lỗ hổng đã đo được: giơ ảnh
        # trong điện thoại là ghi sổ điểm danh hộ. Không chặn cứng — có lúc cần
        # tắt để trình diễn — nhưng phải bắt người vận hành xác nhận có ý thức.
        if self.engine.liveness_backend == "none":
            tra_loi = QMessageBox.warning(
                self, "Chống giả mạo đang TẮT",
                "Kiosk sẽ ghi nhận điểm danh cho bất cứ khuôn mặt nào nhận ra được, "
                "kể cả ảnh giơ trên màn hình điện thoại.\n\n"
                "Đo thực tế: 100% đòn tấn công bằng ảnh điện thoại lọt qua khi tắt "
                "tầng này.\n\nVẫn chạy?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if tra_loi != QMessageBox.StandardButton.Yes:
                return
        self.session_id = self.cb_session.currentData()
        self.engine.reset_tracker()
        self._recent.clear()
        self.cam = KioskThread(self.engine, self.cam_idx.value())
        self.cam.frame_ready.connect(self.on_frame)
        self.cam.confirmed.connect(self.on_confirmed)
        self.cam.spoofed.connect(self.on_spoofed)
        self.cam.failed.connect(self.on_fail)
        self.cam.start()
        self.b_start.setText("  Dừng")
        self.b_start.setIcon(make_icon("stop", "#fff", 18))
        self.write(f"Bắt đầu — máy {self.client.device_id}, "
                   f"ca: {self.cb_session.currentText()}")

    def on_frame(self, qimg: QImage, _items):
        self.video.setPixmap(QPixmap.fromImage(qimg).scaled(
            self.video.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def on_fail(self, msg: str):
        if self.cam:
            self.cam.stop(); self.cam = None
        self.b_start.setText("  Bắt đầu điểm danh")
        self.b_start.setIcon(make_icon("play", "#fff", 18))
        self.video.setText(msg)

    # ---------------------------------------------------------- điểm danh
    def on_confirmed(self, label: str, score: float, jpeg: bytes):
        if label == "Unknown":
            return
        # Chống gửi trùng ngay tại kiosk: cùng một người trong 60 giây thì bỏ qua,
        # đỡ tạo lưu lượng vô ích (server vẫn có chốt chặn riêng của nó).
        now = time.time()
        if now - self._recent.get(label, 0) < 60:
            return
        self._recent[label] = now

        self.card_name.setText(label)
        self.card_state.setText("Đang gửi lên máy chủ…")
        self.card_time.setText(time.strftime("%H:%M:%S"))

        w = CheckinWorker(self.client, jpeg, self.session_id)
        w.done.connect(lambda res, ww=w: self.on_checkin(res, ww))
        self.workers.append(w)
        w.start()

    def on_spoofed(self, label: str, live: float):
        """Bị chặn vì nghi giả mạo — KHÔNG gửi gì lên máy chủ.

        Hiển thị rõ để người đứng trước camera biết mình bị từ chối vì lý do gì,
        và để ghi vào nhật ký phiên làm việc phục vụ việc rà soát sau này.
        """
        self.card_name.setText(label)
        self.card_state.setText(f"Nghi giả mạo — không ghi nhận (điểm sống {live:.2f})")
        self.card_time.setText(time.strftime("%H:%M:%S"))
        for w in (self.card_name, self.card_state):
            w.setStyleSheet(f"color:{RS};" + ("font-size:26px; font-weight:800;"
                                              if w is self.card_name else ""))
        self.write(f"CHẶN giả mạo: {label} · điểm sống {live:.2f}")

    def on_checkin(self, res, worker):
        if worker in self.workers:
            self.workers.remove(worker)
        name = res.name or self.card_name.text()
        self.card_name.setText(name)

        if res.queued:
            colour, state = AM, "Đã ghi nhận — chờ đồng bộ khi có mạng"
        elif not res.ok:
            colour, state = RS, res.message
        elif not res.recognized:
            colour, state = RS, res.message
        elif res.status == "late":
            colour, state = AM, f"Đi muộn {res.late_minutes} phút"
        else:
            colour, state = EM, ("Đúng giờ" if res.created else "Đã điểm danh trước đó")

        self.card_name.setStyleSheet(f"font-size:26px; font-weight:800; color:{colour};")
        self.card_state.setText(state)
        self.write(f"{time.strftime('%H:%M:%S')}  {res.code or name:<12} {state}"
                   + (f"  (tin cậy {res.confidence:.3f})" if res.confidence else ""))
        self.refresh_status()

    def write(self, line: str):
        self.log.appendPlainText(line)

    def closeEvent(self, e):
        if self.cam:
            self.cam.stop()
        self.syncer.stop()
        super().closeEvent(e)


class SpoofTestThread(QThread):
    """Luồng camera chỉ để chấm điểm sống — dùng cho trang kiểm thử."""
    frame_ready = Signal(QImage, list)
    failed = Signal(str)

    def __init__(self, engine: Engine, cam_index: int = 0):
        super().__init__()
        self.engine = engine
        self.cam_index = cam_index
        self._run = True

    def stop(self):
        self._run = False
        self.wait(2000)

    def run(self):
        cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.failed.emit(f"Không mở được camera {self.cam_index}."); return
        while self._run:
            ok, frame = doc_khung(cap)
            if not ok:
                self.failed.emit("Mất tín hiệu camera."); break
            try:
                scores = self.engine.liveness_score(frame)
                dets = self.engine.pipeline.detector.detect(frame)
            except Exception:                          # noqa: BLE001
                scores, dets = [], []
            items = [{"box": d.box, "label": "Unknown", "score": 0.0, "liveness": s}
                     for d, s in zip(dets, scores)]
            shown = draw_faces(frame, items, self.engine.liveness_threshold)
            self.frame_ready.emit(bgr_to_qimage(shown), list(scores))
            self.msleep(15)
        cap.release()


class SpoofTestPage(QWidget):
    """Đo hiệu quả chống giả mạo bằng ĐÒN TẤN CÔNG THẬT.

    Mọi số liệu chống giả mạo trước đó đều đo trên tấn công **mô phỏng**. Mô phỏng
    dựa trên vật lý đúng, nhưng không thay thế được thực tế. Trang này để tự thu
    số liệu thật: ngồi trước camera ghi mẫu thật, rồi giơ ảnh trên điện thoại và
    ảnh in ra ghi mẫu giả — sau đó tính APCER/BPCER/ACER theo ISO/IEC 30107-3.

    Đây là con số nên đưa vào báo cáo, vì nó đo đúng thứ hệ thống phải chống lại.
    """

    def __init__(self, engine: Engine):
        super().__init__()
        self.engine = engine
        self.th: SpoofTestThread | None = None
        self.samples: dict[str, list[float]] = {"real": [], "print": [], "screen": []}
        self.recording: str | None = None
        self._phuong_phap_dang_ghi: str | None = None
        self.target = 60

        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(14)
        root.addWidget(header("Kiểm thử chống giả mạo",
                              "Đo bằng đòn tấn công THẬT — ảnh in và màn hình điện thoại"))

        ctl = QHBoxLayout()
        self.b_start = btn("Bật camera", "camera", primary=True); self.b_start.clicked.connect(self.toggle)
        self.cam_idx = QSpinBox(); self.cam_idx.setRange(0, 8); self.cam_idx.setPrefix("cam ")
        self.sp_n = QSpinBox(); self.sp_n.setRange(20, 300); self.sp_n.setValue(60)
        self.sp_n.setPrefix("ghi "); self.sp_n.setSuffix(" khung")
        # Bộ chọn phương pháp ngay tại trang đo. Trước đây trang này tự ép về
        # "texture", nên không có cách nào đo phương pháp chớp mắt — đúng thứ cần
        # đo nhất sau khi phân tích kết cấu ảnh tỏ ra vô dụng trước tấn công thật.
        self.cb_method = QComboBox()
        for label, backend in Engine.LIVENESS_MODES:
            if backend != "none":
                self.cb_method.addItem(label, backend)
        self.cb_method.currentIndexChanged.connect(self._doi_phuong_phap)
        self.lbl_state = QLabel("Chưa ghi"); self.lbl_state.setObjectName("Pill")
        for w in (self.b_start, self.cam_idx, self.sp_n, QLabel("Phương pháp"), self.cb_method):
            ctl.addWidget(w)
        ctl.addStretch(1); ctl.addWidget(self.lbl_state)
        root.addLayout(ctl)

        body = QHBoxLayout(); body.setSpacing(14)
        self.video = QLabel("Camera đang tắt"); self.video.setObjectName("Video")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(560, 400)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.video, 3)

        right = QVBoxLayout(); right.setSpacing(10)
        steps = QLabel(
            "<b>Cách đo</b><br>"
            "1. Bật camera, ngồi bình thường → <b>Ghi mẫu THẬT</b><br>"
            "2. Mở ảnh mặt bạn trên điện thoại, giơ trước camera → <b>Ghi màn hình</b><br>"
            "3. In một tấm ảnh mặt bạn ra giấy, giơ lên → <b>Ghi ảnh in</b><br>"
            "4. Bấm <b>Tính kết quả</b>")
        steps.setObjectName("Hint"); steps.setWordWrap(True)
        right.addWidget(steps)

        self.b_real = btn("Ghi mẫu THẬT", "check", color=EM)
        self.b_real.clicked.connect(lambda: self.start_record("real"))
        self.b_screen = btn("Ghi mẫu MÀN HÌNH", "live", color=AM)
        self.b_screen.clicked.connect(lambda: self.start_record("screen"))
        self.b_print = btn("Ghi mẫu ẢNH IN", "image", color=AM)
        self.b_print.clicked.connect(lambda: self.start_record("print"))
        for b in (self.b_real, self.b_screen, self.b_print):
            right.addWidget(b)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Loại mẫu", "Số khung", "Điểm TB", "Nhỏ/Lớn nhất"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumHeight(140)
        right.addWidget(self.table)

        row = QHBoxLayout()
        b_calc = btn("Tính kết quả", "chart", primary=True); b_calc.clicked.connect(self.compute)
        b_clr = btn("Xoá hết", "trash", danger=True); b_clr.clicked.connect(self.clear)
        row.addWidget(b_calc); row.addWidget(b_clr)
        right.addLayout(row)

        self.out = QPlainTextEdit(); self.out.setReadOnly(True)
        self.out.setFont(QFont("Consolas", 9)); self.out.setMinimumHeight(170)
        right.addWidget(self.out, 1)

        rc = QFrame(); rc.setObjectName("Card")
        rl = QVBoxLayout(rc); rl.setContentsMargins(16, 16, 16, 16); rl.addLayout(right)
        body.addWidget(rc, 2)
        root.addLayout(body, 1)
        self.refresh_table()

    # ------------------------------------------------------- đổi phương pháp
    def _doi_phuong_phap(self):
        """Đổi phương pháp thì PHẢI xoá mẫu cũ, không được trộn.

        Điểm sống của hai phương pháp nằm trên hai thang hoàn toàn khác nhau:
        phân tích kết cấu chấm theo độ "giống bề mặt phẳng", còn chớp mắt chấm
        theo chuyển động mí mắt. Gộp mẫu thật đo bằng cách này với mẫu giả mạo đo
        bằng cách kia rồi tính APCER/BPCER sẽ ra một con số trông rất chính đáng
        nhưng hoàn toàn vô nghĩa — và không có gì trên màn hình gợi ý rằng nó sai.
        """
        co_mau = any(self.samples.values())
        if co_mau:
            tra_loi = QMessageBox.question(
                self, "Xoá mẫu đã ghi?",
                "Đổi phương pháp sẽ xoá toàn bộ mẫu đã ghi.\n\n"
                "Điểm sống của hai phương pháp nằm trên hai thang khác nhau, trộn "
                "vào nhau sẽ cho ra chỉ số vô nghĩa.\n\nTiếp tục?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if tra_loi != QMessageBox.StandardButton.Yes:
                # Quay lại lựa chọn cũ mà không kích hoạt lại chính hàm này.
                self.cb_method.blockSignals(True)
                i = self.cb_method.findData(self._phuong_phap_dang_ghi or "texture")
                if i >= 0:
                    self.cb_method.setCurrentIndex(i)
                self.cb_method.blockSignals(False)
                return
        self.clear()
        if self.th and self.th.isRunning():
            self.toggle()      # tắt camera để lần bật sau dựng lại pipeline mới

    # --------------------------------------------------------------- camera
    def toggle(self):
        if self.th and self.th.isRunning():
            self.th.stop(); self.th = None
            self.b_start.setText("  Bật camera"); self.b_start.setIcon(make_icon("camera", "#fff", 18))
            self.video.setText("Camera đang tắt"); return
        can_dung = self.cb_method.currentData()
        if self.engine.liveness_backend != can_dung:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self.engine.set_liveness(can_dung)
            finally:
                QApplication.restoreOverrideCursor()
        self.th = SpoofTestThread(self.engine, self.cam_idx.value())
        self.th.frame_ready.connect(self.on_frame)
        self.th.failed.connect(self.on_fail)
        self.th.start()
        self.b_start.setText("  Tắt camera"); self.b_start.setIcon(make_icon("cameraoff", "#fff", 18))

    def on_fail(self, msg: str):
        if self.th:
            self.th.stop(); self.th = None
        self.b_start.setText("  Bật camera"); self.b_start.setIcon(make_icon("camera", "#fff", 18))
        self.video.setText(msg)

    def on_frame(self, qimg: QImage, scores: list):
        self.video.setPixmap(QPixmap.fromImage(qimg).scaled(
            self.video.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        if self.recording and scores:
            bucket = self.samples[self.recording]
            bucket.append(float(scores[0]))       # chỉ lấy khuôn mặt đầu tiên
            done, total = len(bucket), self.target
            self.lbl_state.setText(f"Đang ghi '{self.recording}': {done}/{total}")
            if done >= total:
                self.recording = None
                self.lbl_state.setText("Ghi xong")
                self.refresh_table()

    # -------------------------------------------------------------- ghi mẫu
    def start_record(self, kind: str):
        if not (self.th and self.th.isRunning()):
            QMessageBox.warning(self, "Chưa bật camera", "Bật camera trước khi ghi mẫu."); return
        self.target = self.sp_n.value()
        self.samples[kind] = []
        self.recording = kind
        # Nhớ phương pháp đã dùng để ghi, để nếu người dùng đổi giữa chừng thì
        # còn quay lại được lựa chọn cũ khi họ bấm Huỷ.
        self._phuong_phap_dang_ghi = self.engine.liveness_backend
        self.lbl_state.setText(f"Đang ghi '{kind}': 0/{self.target}")

    def clear(self):
        for k in self.samples:
            self.samples[k] = []
        self.recording = None
        self.out.clear(); self.lbl_state.setText("Chưa ghi"); self.refresh_table()

    def refresh_table(self):
        names = {"real": "THẬT", "screen": "Màn hình", "print": "Ảnh in"}
        rows = [(names[k], v) for k, v in self.samples.items()]
        self.table.setRowCount(len(rows))
        for r, (label, vals) in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(label))
            self.table.setItem(r, 1, QTableWidgetItem(str(len(vals))))
            self.table.setItem(r, 2, QTableWidgetItem(f"{np.mean(vals):.3f}" if vals else "—"))
            self.table.setItem(r, 3, QTableWidgetItem(
                f"{min(vals):.2f} / {max(vals):.2f}" if vals else "—"))

    # ------------------------------------------------------------ tính toán
    def compute(self):
        real = np.array(self.samples["real"], dtype=float)
        attacks = np.array(self.samples["screen"] + self.samples["print"], dtype=float)
        if len(real) < 10 or len(attacks) < 10:
            QMessageBox.warning(self, "Chưa đủ mẫu",
                                "Cần ít nhất 10 khung mẫu THẬT và 10 khung mẫu giả mạo.")
            return

        y = np.concatenate([np.ones(len(real)), np.zeros(len(attacks))])
        s = np.concatenate([real, attacks])
        grid = np.linspace(s.min(), s.max(), 400)

        def m(thr):
            live = s >= thr
            apcer = float(live[y == 0].mean())
            bpcer = float((~live[y == 1]).mean())
            return apcer, bpcer

        gaps = [(abs(a - b), t, a, b) for t in grid for a, b in [m(t)]]
        _, thr, apcer, bpcer = min(gaps)
        cur = self.engine.liveness_threshold
        a_cur, b_cur = m(cur)

        lines = [
            f"Phương pháp   : {self.engine.liveness_backend}",
            f"Mẫu           : {len(real)} khung THẬT · {len(attacks)} khung giả mạo",
            f"                ({len(self.samples['screen'])} màn hình, {len(self.samples['print'])} ảnh in)",
            "",
            f"Điểm sống TB  : thật {real.mean():.3f}   giả mạo {attacks.mean():.3f}",
            "",
            "--- Tại ngưỡng đang dùng trong hệ thống ---",
            f"  ngưỡng      : {cur:.3f}",
            f"  APCER       : {a_cur*100:6.2f}%   (tấn công lọt qua)",
            f"  BPCER       : {b_cur*100:6.2f}%   (người thật bị chặn oan)",
            f"  ACER        : {(a_cur+b_cur)/2*100:6.2f}%",
            "",
            "--- Tại ngưỡng tối ưu cho dữ liệu này ---",
            f"  ngưỡng      : {thr:.3f}",
            f"  APCER       : {apcer*100:6.2f}%",
            f"  BPCER       : {bpcer*100:6.2f}%",
            f"  ACER        : {(apcer+bpcer)/2*100:6.2f}%",
        ]
        for kind in ("screen", "print"):
            v = np.array(self.samples[kind], dtype=float)
            if len(v):
                lines.append(f"  {kind:<10}  lọt {float((v >= cur).mean())*100:5.1f}% "
                             f"(điểm TB {v.mean():.3f})")
        self.out.setPlainText("\n".join(lines))

        import json
        payload = {"backend": self.engine.liveness_backend,
                   "threshold_system": cur, "threshold_optimal": float(thr),
                   "apcer_at_system": a_cur, "bpcer_at_system": b_cur,
                   "apcer_optimal": apcer, "bpcer_optimal": bpcer,
                   "samples": {k: v for k, v in self.samples.items()}}
        out = config.REPORTS_DIR / "liveness_thuc_te.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.out.appendPlainText(f"\n-> đã lưu {out}")

    def closeEvent(self, e):
        if self.th:
            self.th.stop()
        super().closeEvent(e)


class EnrollPage(QWidget):
    def __init__(self, engine: Engine, on_change=None):
        super().__init__()
        self.engine = engine
        self.on_change = on_change
        self.tray: list[np.ndarray] = []          # ảnh tạm, chưa ghi đĩa
        self.cam: CameraThread | None = None
        self._last_frame: np.ndarray | None = None

        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(14)
        root.addWidget(header("Đăng ký người",
                              "Tạo folder theo tên người → chụp/thêm ảnh vào folder → nạp vào nhận diện"))

        # --- hàng tạo / chọn folder ---
        top = QHBoxLayout()
        self.name = QLineEdit(); self.name.setPlaceholderText("Tên người (không dấu, không khoảng trắng), vd: nam")
        self.b_new = btn("Tạo folder", "folderplus", color=EM, primary=True)
        self.b_new.clicked.connect(self.create_folder)
        top.addWidget(self.name, 1); top.addWidget(self.b_new)
        root.addLayout(top)

        pick = QHBoxLayout()
        lb = QLabel("Folder đang chọn:"); lb.setObjectName("Hint")
        self.cb_folder = QComboBox(); self.cb_folder.currentTextChanged.connect(self.on_folder_changed)
        self.lbl_count = QLabel("—"); self.lbl_count.setObjectName("Pill")
        pick.addWidget(lb); pick.addWidget(self.cb_folder, 1); pick.addWidget(self.lbl_count)
        root.addLayout(pick)

        body = QHBoxLayout(); body.setSpacing(14)

        # --- trái: camera ---
        self.preview = QLabel("Bật camera để chụp"); self.preview.setObjectName("Video")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(430, 340)
        self.b_cam = btn("Bật camera", "camera", color=CY); self.b_cam.clicked.connect(self.toggle_cam)
        self.b_shot = btn("Chụp vào khay", "plus", primary=True); self.b_shot.setEnabled(False)
        self.b_shot.clicked.connect(self.snap)
        self.b_files = btn("Thêm ảnh từ máy", "upload", color=VI); self.b_files.clicked.connect(self.add_files)
        cam_btns = QHBoxLayout()
        for w in (self.b_cam, self.b_shot, self.b_files):
            cam_btns.addWidget(w)
        body.addWidget(card(self.preview, cam_btns), 3)

        # --- phải: khay tạm + nội dung folder ---
        right = QVBoxLayout(); right.setSpacing(10)
        h1 = QHBoxLayout()
        t1 = QLabel("Khay tạm (chưa lưu)"); t1.setObjectName("Hint")
        self.lbl_tray = QLabel("0 ảnh"); self.lbl_tray.setObjectName("Pill")
        h1.addWidget(t1); h1.addStretch(1); h1.addWidget(self.lbl_tray)
        self.tray_w = QListWidget(); self.tray_w.setObjectName("Tray")
        self.tray_w.setViewMode(QListWidget.ViewMode.IconMode)
        self.tray_w.setIconSize(QSize(84, 84)); self.tray_w.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.tray_w.setSpacing(6); self.tray_w.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.tray_w.setMaximumHeight(150)
        tb = QHBoxLayout()
        b_rm = btn("Bỏ ảnh chọn", "x", color=RS); b_rm.clicked.connect(self.remove_selected)
        b_clr = btn("Xoá khay", "trash", color=RS); b_clr.clicked.connect(self.clear_tray)
        self.b_addfolder = btn("Thêm khay vào folder", "download", primary=True)
        self.b_addfolder.clicked.connect(self.tray_to_folder)
        tb.addWidget(b_rm); tb.addWidget(b_clr); tb.addStretch(1); tb.addWidget(self.b_addfolder)

        h2 = QHBoxLayout()
        t2 = QLabel("Ảnh trong folder"); t2.setObjectName("Hint")
        h2.addWidget(t2); h2.addStretch(1)
        self.folder_w = QListWidget(); self.folder_w.setObjectName("FolderGrid")
        self.folder_w.setViewMode(QListWidget.ViewMode.IconMode)
        self.folder_w.setIconSize(QSize(84, 84)); self.folder_w.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.folder_w.setSpacing(6)
        fb = QHBoxLayout()
        self.b_rmdb = btn("Xoá folder khỏi nhận diện", "trash", danger=True)
        self.b_rmdb.clicked.connect(self.remove_folder_from_db)
        self.b_commit = btn("Nạp folder vào nhận diện", "check", primary=True)
        self.b_commit.clicked.connect(self.commit_folder)
        # Ứng dụng và máy chủ giữ hai kho riêng (kiosk phải chạy được khi mất
        # mạng). Nút này là đường nối giữa hai kho: đăng ký một lần ở đây rồi đẩy
        # sang, khỏi phải nhập lại người đó trên web.
        self.b_push = btn("Đẩy lên máy chủ", "upload", color=CY)
        self.b_push.clicked.connect(self.push_to_server)
        fb.addWidget(self.b_rmdb); fb.addStretch(1)
        fb.addWidget(self.b_push); fb.addWidget(self.b_commit)

        for x in (h1,):
            right.addLayout(x)
        right.addWidget(self.tray_w)
        right.addLayout(tb)
        sep = QFrame(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{C_LINE};")
        right.addWidget(sep)
        right.addLayout(h2)
        right.addWidget(self.folder_w, 1)
        right.addLayout(fb)
        rc = QFrame(); rc.setObjectName("Card")
        rcl = QVBoxLayout(rc); rcl.setContentsMargins(16, 16, 16, 16); rcl.addLayout(right)
        body.addWidget(rc, 2)

        root.addLayout(body, 1)
        self.refresh_folders()

    # ----- folders -----
    def create_folder(self):
        nm = sanitize(self.name.text())
        if not nm:
            QMessageBox.warning(self, "Thiếu tên", "Nhập tên người rồi bấm Tạo folder."); return
        self.engine.make_folder(nm)
        self.refresh_folders(select=nm)
        if self.on_change:
            self.on_change()

    def refresh_folders(self, select: str | None = None):
        cur = select or self.cb_folder.currentText()
        self.cb_folder.blockSignals(True)
        self.cb_folder.clear()
        self.cb_folder.addItems(self.engine.folders())
        if cur and cur in self.engine.folders():
            self.cb_folder.setCurrentText(cur)
        self.cb_folder.blockSignals(False)
        self.on_folder_changed(self.cb_folder.currentText())

    def active(self) -> str:
        return self.cb_folder.currentText().strip()

    def on_folder_changed(self, name: str):
        self.folder_w.clear()
        imgs = self.engine.folder_images(name) if name else []
        for p in imgs[:80]:
            im = doc_anh(p)
            if im is None:
                continue
            self.folder_w.addItem(QListWidgetItem(
                QIcon(QPixmap.fromImage(bgr_to_qimage(cv2.resize(im, (84, 84))))), ""))
        in_db = name in self.engine.db
        self.lbl_count.setText(f"{len(imgs)} ảnh" + ("  ·  đã nạp" if in_db else "  ·  chưa nạp"))
        self.lbl_count.setObjectName("PillGood" if in_db else "Pill")
        self.lbl_count.style().unpolish(self.lbl_count); self.lbl_count.style().polish(self.lbl_count)

    # ----- camera -----
    def toggle_cam(self):
        if self.cam and self.cam.isRunning():
            self.cam.stop(); self.cam = None
            self.b_cam.setText("  Bật camera"); self.b_cam.setIcon(make_icon("camera", CY, 18))
            self.b_shot.setEnabled(False); self.preview.setText("Camera đang tắt")
            return
        self.cam = CameraThread(self.engine, 0, every=6, recognize=False)
        self.cam.frame_ready.connect(self._preview)
        self.cam.failed.connect(lambda m: (self.preview.setText(m), self.toggle_cam()))
        self.cam.start()
        self.b_cam.setText("  Tắt camera"); self.b_cam.setIcon(make_icon("cameraoff", RS, 18))
        self.b_shot.setEnabled(True)

    def _preview(self, qimg: QImage, _items):
        self._last_frame = qimage_to_bgr(qimg)
        self.preview.setPixmap(QPixmap.fromImage(qimg).scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    # ----- tray -----
    def snap(self):
        if self._last_frame is not None:
            self._add(self._last_frame.copy())

    def add_files(self):
        fns, _ = QFileDialog.getOpenFileNames(self, "Chọn ảnh", "", "Ảnh (*.jpg *.jpeg *.png *.bmp *.webp)")
        for fn in fns:
            im = doc_anh(fn)
            if im is not None:
                self._add(im)

    def _add(self, img_bgr: np.ndarray):
        self.tray.append(img_bgr)
        thumb = cv2.resize(img_bgr, (84, 84))
        self.tray_w.addItem(QListWidgetItem(QIcon(QPixmap.fromImage(bgr_to_qimage(thumb))), ""))
        self.lbl_tray.setText(f"{len(self.tray)} ảnh")

    def remove_selected(self):
        for r in sorted((self.tray_w.row(i) for i in self.tray_w.selectedItems()), reverse=True):
            self.tray_w.takeItem(r); del self.tray[r]
        self.lbl_tray.setText(f"{len(self.tray)} ảnh")

    def clear_tray(self):
        self.tray.clear(); self.tray_w.clear(); self.lbl_tray.setText("0 ảnh")

    def tray_to_folder(self):
        nm = self.active()
        if not nm:
            QMessageBox.warning(self, "Chưa có folder", "Tạo hoặc chọn folder trước."); return
        if not self.tray:
            QMessageBox.warning(self, "Khay rỗng", "Chụp hoặc thêm ảnh vào khay trước."); return
        yeu_cau = len(self.tray)
        n = self.engine.add_images_to_folder(nm, list(self.tray))
        if n < yeu_cau:
            # Giữ nguyên khay khi ghi hỏng: xoá khay ở đây thì người dùng mất
            # sạch ảnh vừa chụp mà chẳng được gì — đúng cái đã xảy ra với folder
            # tên có dấu, khi mọi lần ghi đều hỏng nhưng vẫn báo thành công.
            QMessageBox.critical(
                self, "Không ghi được ảnh",
                f"Chỉ ghi được {n}/{yeu_cau} ảnh vào folder '{nm}'.\n\n"
                f"Thư mục: {config.ENROLLED_DIR / nm}\n\n"
                "Kiểm tra dung lượng đĩa và quyền ghi. Ảnh vẫn còn trong khay.")
            return
        self.clear_tray()
        self.on_folder_changed(nm)
        QMessageBox.information(self, "Đã thêm", f"Đã thêm {n} ảnh vào folder '{nm}'.")
        if self.on_change:
            self.on_change()

    # ----- commit / remove -----
    def commit_folder(self):
        nm = self.active()
        if not nm:
            QMessageBox.warning(self, "Chưa có folder", "Chọn folder trước."); return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            n, rejected, reasons = self.engine.commit_folder(nm)
        finally:
            QApplication.restoreOverrideCursor()
        if n == 0:
            detail = ("\n\nLý do: " + ", ".join(sorted(set(reasons))[:4])) if reasons else ""
            QMessageBox.warning(self, "Không nạp được",
                                "Folder rỗng, hoặc mọi ảnh đều không qua được cổng chất lượng."
                                + detail); return
        msg = f"Đã nạp folder '{nm}' vào nhận diện: {n} vector."
        if rejected:
            from collections import Counter
            top = ", ".join(f"{k} ({v})" for k, v in Counter(reasons).most_common(3))
            msg += f"\n\nLoại {rejected} ảnh — {top}"
        QMessageBox.information(self, "Xong", msg)
        self.on_folder_changed(nm)
        if self.on_change:
            self.on_change()

    def push_to_server(self):
        """Đẩy folder đang chọn lên cơ sở dữ liệu của máy chủ.

        Không có bước này thì phải đăng ký hai lần cho cùng một người — một lần ở
        ứng dụng để kiosk nhận ra, một lần trên web để máy chủ ghi sổ — và nếu
        quên một bên thì kiosk hiện đúng tên nhưng báo "chưa nhận ra", một biểu
        hiện rất khó đoán ra nguyên nhân.
        """
        nm = self.active()
        if not nm:
            QMessageBox.warning(self, "Chưa có folder", "Chọn folder trước."); return
        anh = self.engine.folder_images(nm)
        if not anh:
            QMessageBox.warning(self, "Folder rỗng", "Chưa có ảnh nào trong folder."); return

        from desktop_api import ApiClient, day_len_may_chu
        url, ok = QInputDialog.getText(
            self, "Máy chủ", "Địa chỉ máy chủ:",
            text=os.environ.get("FACEID_API_URL", "http://localhost:8090"))
        if not ok or not url.strip():
            return
        user, ok = QInputDialog.getText(self, "Đăng nhập", "Tài khoản:", text="admin")
        if not ok:
            return
        pw, ok = QInputDialog.getText(self, "Đăng nhập", "Mật khẩu:",
                                      QLineEdit.EchoMode.Password)
        if not ok:
            return

        client = ApiClient(base_url=url.strip())
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            dang_nhap_ok, msg = client.login(user.strip(), pw)
            if not dang_nhap_ok:
                QMessageBox.critical(self, "Không đăng nhập được", msg); return
            kq = day_len_may_chu(client, nm, anh, ho_ten=nm)
        finally:
            QApplication.restoreOverrideCursor()

        if kq["ok"]:
            QMessageBox.information(
                self, "Đã đồng bộ",
                f"{kq['message']}\n\nMã trên máy chủ: {kq['code']}\n"
                f"Từ giờ kiosk điểm danh cho '{nm}' sẽ được máy chủ ghi nhận.")
        else:
            QMessageBox.critical(self, "Không đẩy được", kq["message"])

    def remove_folder_from_db(self):
        nm = self.active()
        if not nm or nm not in self.engine.db:
            QMessageBox.information(self, "Chưa nạp", f"'{nm}' chưa có trong nhận diện."); return
        self.engine.remove_from_db(nm)
        self.on_folder_changed(nm)
        QMessageBox.information(self, "Đã xoá",
                               f"Đã bỏ '{nm}' khỏi nhận diện. Ảnh trong folder vẫn còn trên đĩa.")
        if self.on_change:
            self.on_change()

    def closeEvent(self, e):
        if self.cam:
            self.cam.stop()
        super().closeEvent(e)


class XemAnh(QDialog):
    """Cửa sổ xem một ảnh báo cáo ở cỡ lớn.

    Biểu đồ đánh giá nhồi vào khung cao 210 px thì mọi con số bên trong đều không
    đọc nổi — chúng chỉ còn là hình trang trí. Bấm vào ảnh mở cửa sổ này để xem
    đúng kích thước thật, và có nút mở bằng trình xem ảnh của hệ điều hành cho ai
    muốn phóng to thêm.
    """

    def __init__(self, duong_dan: Path, cha=None):
        super().__init__(cha)
        self.duong_dan = Path(duong_dan)
        self.setWindowTitle(f"Báo cáo — {self.duong_dan.name}")
        self.setMinimumSize(900, 560)
        self.resize(1280, 800)

        lay = QVBoxLayout(self); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(10)
        self.anh = QLabel(); self.anh.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.anh.setObjectName("Video")
        self.anh.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self.anh, 1)

        hang = QHBoxLayout()
        ten = QLabel(self.duong_dan.name); ten.setObjectName("Hint")
        b_mo = btn("Mở bằng trình xem ảnh", "image", color=CY)
        b_mo.clicked.connect(self._mo_ngoai)
        b_dong = btn("Đóng", "x", primary=True); b_dong.clicked.connect(self.accept)
        hang.addWidget(ten); hang.addStretch(1); hang.addWidget(b_mo); hang.addWidget(b_dong)
        lay.addLayout(hang)

        self._goc = QPixmap(str(self.duong_dan))
        self._ve()

    def _ve(self):
        if self._goc.isNull():
            self.anh.setText("Không đọc được ảnh"); return
        self.anh.setPixmap(self._goc.scaled(
            self.anh.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, e):        # noqa: N802
        super().resizeEvent(e)
        self._ve()

    def _mo_ngoai(self):
        try:
            os.startfile(str(self.duong_dan))       # noqa: S606
        except Exception as e:                      # noqa: BLE001
            QMessageBox.warning(self, "Không mở được", str(e))


class AnhBamDuoc(QLabel):
    """Ảnh xem trước, bấm vào thì mở cửa sổ xem cỡ lớn."""

    def __init__(self):
        super().__init__()
        self.duong_dan: Path | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def dat_anh(self, duong_dan: Path | None, mo_ta: str):
        self.duong_dan = duong_dan
        if duong_dan and duong_dan.exists():
            self.setPixmap(QPixmap(str(duong_dan)).scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            self.setToolTip(f"{mo_ta}\n{duong_dan.name}\n\nBấm để xem cỡ lớn")
        else:
            self.clear()
            self.setText(f"{mo_ta}\n(chưa có)")
            self.setToolTip("")

    def mousePressEvent(self, e):    # noqa: N802
        if self.duong_dan and self.duong_dan.exists():
            XemAnh(self.duong_dan, self).exec()


class DashboardPage(QWidget):
    def __init__(self, engine: Engine, on_change=None):
        super().__init__()
        self.engine = engine
        self.on_change = on_change
        self.cmd: CmdThread | None = None

        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(14)
        root.addWidget(header("Bảng điều khiển", "Dữ liệu · mô hình · dựng DB · đánh giá · báo cáo"))

        self.stats = QHBoxLayout(); self.stats.setSpacing(12)
        root.addLayout(self.stats)

        s = QGridLayout(); s.setHorizontalSpacing(10); s.setVerticalSpacing(8)
        self.models = available_models()
        self.cb_backbone = QComboBox()
        for label, backend, weights in self.models:
            self.cb_backbone.addItem(label, (backend, weights))
        for i, (_, backend, weights) in enumerate(self.models):
            if backend == engine.backbone and weights == engine.weights:
                self.cb_backbone.setCurrentIndex(i); break
        self.ed_weights = QLineEdit(engine.weights); self.ed_weights.setReadOnly(True)
        self.sp_thr = QDoubleSpinBox(); self.sp_thr.setRange(0, 1); self.sp_thr.setSingleStep(0.01)
        self.sp_thr.setValue(engine.threshold)
        self.ed_db = QLineEdit(engine.db_path)
        b_apply = btn("Áp dụng", "apply", primary=True); b_apply.clicked.connect(self.apply)
        s.addWidget(QLabel("Backbone"), 0, 0); s.addWidget(self.cb_backbone, 0, 1)
        s.addWidget(QLabel("Tệp trọng số"), 0, 2); s.addWidget(self.ed_weights, 0, 3)
        s.addWidget(QLabel("Ngưỡng cosine"), 1, 0); s.addWidget(self.sp_thr, 1, 1)
        s.addWidget(QLabel("Database"), 1, 2); s.addWidget(self.ed_db, 1, 3)
        s.addWidget(b_apply, 2, 3)
        huong_dan = QLabel(
            "<b>Đổi mô hình nhận diện.</b> Chọn Backbone → bấm <b>Áp dụng</b> → rồi "
            "bấm <b>Dựng lại database</b> ở dưới.<br>"
            "Bỏ bước dựng lại thì vector cũ và mô hình mới không cùng một không gian, "
            "hệ thống sẽ nhận sai một cách âm thầm.<br>"
            "<b>Ngưỡng cosine</b>: cao hơn thì ít nhận nhầm người lạ nhưng hay bắt thử "
            "lại; 0,68 là mức đo được cân bằng nhất cho điểm danh.")
        huong_dan.setObjectName("Hint"); huong_dan.setWordWrap(True)
        s.addWidget(huong_dan, 3, 0, 1, 4)
        root.addWidget(card(s))

        self.tbl_models = QTableWidget(0, 6)
        self.tbl_models.setHorizontalHeaderLabels(["Tệp", "Dạng", "Loss", "val_ver", "Epoch", "MB"])
        hh = self.tbl_models.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_models.verticalHeader().setVisible(False)
        self.tbl_models.setAlternatingRowColors(True)
        # Cao 300 thay vì 150: dự án có mười tệp mô hình, giới hạn cũ chỉ lọt
        # đúng MỘT dòng nên bảng trông như chỉ có một mô hình duy nhất.
        self.tbl_models.setMinimumHeight(230)
        self.tbl_models.setMaximumHeight(300)
        nhan_mh = QLabel(
            "<b>Mô hình đã có</b> — <span style='color:#99a1b7'>ONNX là bản dùng để "
            "chạy (nhanh, nhẹ); PyTorch là bản dùng để huấn luyện. "
            "val_ver = tỉ lệ xác thực đúng trên người chưa từng thấy lúc học.</span>")
        nhan_mh.setWordWrap(True)
        root.addWidget(card(nhan_mh, self.tbl_models))

        ops = QHBoxLayout()
        b_db = btn("Dựng lại database", "refresh", color=CY)
        b_db.clicked.connect(self._rebuild_db)
        b_ev = btn("Chạy đánh giá", "chart", color=AM)
        b_ev.clicked.connect(lambda: self.run_cmd(self._args_eval(), "evaluate"))
        ops.addWidget(b_db); ops.addWidget(b_ev); ops.addStretch(1)
        nhan_ops = QLabel(
            "<b>Dựng lại database</b>: đọc lại ảnh gốc trong data/enrolled/ rồi trích "
            "đặc trưng lại bằng mô hình đang chọn. Bắt buộc làm sau khi đổi mô hình.<br>"
            "<b>Chạy đánh giá</b>: chấm mô hình trên tập kiểm tra và vẽ biểu đồ — kết "
            "quả hiện ở khung Báo cáo bên dưới.")
        nhan_ops.setObjectName("Hint"); nhan_ops.setWordWrap(True)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(170)
        self.log.setFont(QFont("Consolas", 9))
        root.addWidget(card(ops, nhan_ops, self.log))

        rep = QHBoxLayout()
        self.cb_tag = QComboBox(); self.cb_tag.currentTextChanged.connect(self.show_reports)
        rep.addWidget(QLabel("Báo cáo:")); rep.addWidget(self.cb_tag)
        goi_y = QLabel("bấm vào ảnh để xem cỡ lớn"); goi_y.setObjectName("Hint")
        rep.addWidget(goi_y); rep.addStretch(1)
        self.rep_imgs = [AnhBamDuoc(), AnhBamDuoc(), AnhBamDuoc()]
        rr = QHBoxLayout()
        for l in self.rep_imgs:
            l.setObjectName("Video"); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setMinimumHeight(260); l.setWordWrap(True); rr.addWidget(l, 1)
        root.addWidget(card(rep, rr))
        root.addStretch(1)
        self.refresh()

    def _rebuild_db(self):
        """Tạo lại toàn bộ database bằng mô hình đang chọn.

        Đọc lại ảnh gốc trong `data/enrolled/<tên>/` rồi trích đặc trưng lại —
        nên đổi mô hình lúc nào cũng khôi phục được, miễn còn giữ ảnh gốc.
        """
        folders = self.engine.folders()
        if not folders:
            QMessageBox.information(self, "Chưa có ai", "Chưa có folder nào trong data/enrolled/.")
            return
        self.log.clear()
        self.log.appendPlainText(f"Dựng lại database bằng {self.cb_backbone.currentText()}\n")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        total = 0
        try:
            for name in folders:
                n, rejected, _ = self.engine.commit_folder(name)
                total += n
                self.log.appendPlainText(f"  {name:<20} {n} vector"
                                         + (f"  (loại {rejected} ảnh)" if rejected else ""))
        finally:
            QApplication.restoreOverrideCursor()
        self.log.appendPlainText(f"\n[OK] {len(folders)} người · {total} vector")
        self.refresh()
        if self.on_change:
            self.on_change()

    def _args_eval(self):
        a = ["training.evaluate", "--manifest", "data/manifest_big.json",
             "--backbone", self.engine.backbone, "--tag", self.engine.backbone]
        if self.engine.weights:
            a += ["--weights", self.engine.weights]
            a[-3] = Path(self.engine.weights).stem      # tag theo tên model
        return a

    def apply(self):
        self.engine.threshold = float(self.sp_thr.value())
        self.engine.db_path = self.ed_db.text().strip()
        backend, weights = self.cb_backbone.currentData()
        if backend != "facenet" and not Path(weights).exists():
            QMessageBox.warning(self, "Thiếu model", f"Không thấy {weights}."); return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.engine.set_backbone(backend, weights)
        finally:
            QApplication.restoreOverrideCursor()
        self.ed_weights.setText(weights)

        # Vector trong DB được sinh bởi mô hình CŨ. Đổi mô hình mà không dựng lại
        # DB thì các vector không còn so sánh được với nhau — cảnh báo ngay thay
        # vì để người dùng phát hiện qua việc nhận diện sai một cách khó hiểu.
        if not self.engine.db_matches_model():
            QMessageBox.warning(self, "Cần dựng lại database",
                                "Database đang chứa vector của mô hình khác (khác số chiều).\n"
                                "Bấm 'Dựng lại database' để tạo lại, nếu không nhận diện sẽ sai.")
        elif self.engine.db:
            QMessageBox.information(
                self, "Đã áp dụng",
                f"Mô hình: {self.cb_backbone.currentText()}\n"
                f"Ngưỡng: {self.engine.threshold:.2f}\n\n"
                "Lưu ý: vector trong database do mô hình trước sinh ra. Nên bấm\n"
                "'Dựng lại database' để nhận diện chính xác nhất.")
        else:
            QMessageBox.information(self, "Đã áp dụng",
                                    f"Mô hình: {self.cb_backbone.currentText()}")
        self.refresh()
        if self.on_change:
            self.on_change()

    def run_cmd(self, args, label):
        if self.cmd and self.cmd.isRunning():
            return
        self.log.clear(); self.log.appendPlainText(f"$ python -m {' '.join(args)}\n")
        self.cmd = CmdThread(args)
        self.cmd.line.connect(self.log.appendPlainText)
        self.cmd.done.connect(lambda rc: self._cmd_done(rc, label))
        self.cmd.start()

    def _cmd_done(self, rc, label):
        self.log.appendPlainText(f"\n[{'OK' if rc == 0 else 'LỖI ' + str(rc)}] {label}")
        self.engine.reload_db(); self.refresh()
        if self.on_change:
            self.on_change()

    def refresh(self):
        while self.stats.count():
            it = self.stats.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        def count_tree(root: Path):
            if not root.exists():
                return 0, 0
            people = [d for d in root.iterdir() if d.is_dir()]
            imgs = sum(1 for d in people for p in d.rglob("*") if p.suffix.lower() in IMG_EXT)
            return len(people), imgs

        pa, ia = count_tree(config.ALIGNED_DIR)
        pe, _ = count_tree(config.ENROLLED_DIR)
        for v, k, col in [(pa, "người (đã align)", CY), (ia, "ảnh khuôn mặt", VI),
                          (pe, "folder đã đăng ký", EM), (len(self.engine.db), "người trong DB", AM)]:
            f = QFrame(); f.setObjectName("Stat")
            lay = QVBoxLayout(f); lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(2)
            a = QLabel(str(v)); a.setObjectName("StatV"); a.setStyleSheet(f"color:{col};")
            b = QLabel(k); b.setObjectName("StatK")
            lay.addWidget(a); lay.addWidget(b)
            self.stats.addWidget(f)

        import json
        # Liệt kê CẢ .onnx lẫn .pt. Mã cũ chỉ quét .pt nên bảng chỉ hiện đúng một
        # dòng — mô hình cũ nhất — trong khi năm mô hình ONNX đang dùng thật thì
        # không thấy đâu, khiến người dùng tưởng dự án chỉ có một mô hình.
        rows = []
        for f in sorted(config.MODELS_DIR.glob("*.onnx")) + sorted(config.MODELS_DIR.glob("*.pt")):
            if any(k in f.stem.lower() for k in _NOT_EMBEDDERS):
                continue          # bỏ tệp của bộ phát hiện, không phải mô hình nhận diện
            meta, epochs, loss, ver = {}, "-", "-", "-"

            # Hai định dạng lịch sử tồn tại song song: bản huấn luyện đời đầu ghi
            # thẳng vào <tên>.json, bản hiện tại ghi vào <tên>_history.json.
            js_cu = f.with_suffix(".json")
            js_moi = config.MODELS_DIR / f"{f.stem}_history.json"
            try:
                if js_moi.exists():
                    meta = json.loads(js_moi.read_text(encoding="utf-8"))
                    lich_su = meta.get("history") or []
                    if lich_su:
                        cuoi = lich_su[-1]
                        epochs = str(cuoi.get("epoch", "-"))
                        loss = f"{cuoi.get('loss', 0):.4f}" if "loss" in cuoi else "-"
                        ver = f"{cuoi.get('val_ver', 0):.4f}" if "val_ver" in cuoi else "-"
                elif js_cu.exists():
                    meta = json.loads(js_cu.read_text(encoding="utf-8"))
                    epochs = str(meta.get("epochs_trained", "-"))
                    loss = str(meta.get("loss", "-"))
                    ver = str(meta.get("val_acc", "-"))
            except Exception:  # noqa: BLE001
                pass

            dang = "ONNX (dùng để chạy)" if f.suffix == ".onnx" else "PyTorch (để huấn luyện)"
            rows.append([f.name, dang, loss, ver, epochs, f"{f.stat().st_size / 1e6:.1f}"])
        self.tbl_models.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self.tbl_models.setItem(r, c, QTableWidgetItem(val))

        # Quét theo ĐÚNG tên tệp mà training/evaluate.py sinh ra: "<tag>_eval.png".
        # Mã cũ tìm "*_roc.png" — tên của pipeline đánh giá đời đầu đã bỏ từ lâu —
        # nên danh sách luôn rỗng và khung xem báo cáo không bao giờ hiện gì.
        tags = sorted({p.name[:-len("_eval.png")]
                       for p in config.REPORTS_DIR.glob("*_eval.png")})
        cur = self.cb_tag.currentText()
        self.cb_tag.blockSignals(True)
        self.cb_tag.clear(); self.cb_tag.addItems(tags)
        if cur in tags:
            self.cb_tag.setCurrentText(cur)
        self.cb_tag.blockSignals(False)
        self.show_reports(self.cb_tag.currentText())

    def show_reports(self, tag: str):
        """Ba khung: kết quả của mô hình đang chọn, so sánh các mô hình, ablation.

        Khung đầu đổi theo mục đang chọn trong danh sách; hai khung sau là biểu đồ
        chung của cả dự án nên luôn hiện, không phụ thuộc mục nào được chọn.
        """
        duong_dan = [
            (config.REPORTS_DIR / f"{tag}_eval.png") if tag else None,
            config.REPORTS_DIR / "bc_so_sanh_mo_hinh.png",
            config.REPORTS_DIR / "bc_ablation.png",
        ]
        mo_ta = [f"Đánh giá: {tag}" if tag else "Chưa có kết quả đánh giá",
                 "So sánh các mô hình", "Ablation — đóng góp từng bộ phận"]
        for lbl, fp, ten in zip(self.rep_imgs, duong_dan, mo_ta):
            lbl.dat_anh(fp, ten)


# ---------------------------------------------------------------- main window
class MainWindow(QMainWindow):
    def __init__(self, engine: Engine):
        super().__init__()
        self.engine = engine
        self.setWindowTitle("FaceID Studio — Nhận diện khuôn mặt")
        self.resize(1200, 800)

        root = QWidget(); root.setObjectName("Root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        nav = QFrame(); nav.setObjectName("Nav"); nav.setFixedWidth(218)
        nlay = QVBoxLayout(nav); nlay.setContentsMargins(0, 0, 0, 0); nlay.setSpacing(0)
        brand = QLabel("●  FaceID Studio"); brand.setObjectName("Brand")
        sub = QLabel("COMPUTER VISION"); sub.setObjectName("BrandSub")
        self.nav = QListWidget(); self.nav.setObjectName("NavList")
        self.nav.setIconSize(QSize(19, 19))
        for txt, ic, col in [("Trực tiếp", "live", CY), ("Kiosk điểm danh", "kiosk", EM),
                             ("Nhận diện ảnh", "image", VI), ("Chống giả mạo", "shield", RS),
                             ("Cử chỉ tay", "hand", PK), ("Đăng ký người", "userplus", EM),
                             ("Bảng điều khiển", "dashboard", AM)]:
            self.nav.addItem(QListWidgetItem(make_icon(ic, col, 19), "  " + txt))
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(lambda i: self.stack.setCurrentIndex(i))
        self.status = QLabel(); self.status.setObjectName("StatK")
        self.status.setWordWrap(True); self.status.setContentsMargins(16, 10, 16, 14)
        nlay.addWidget(brand); nlay.addWidget(sub); nlay.addWidget(self.nav, 1); nlay.addWidget(self.status)
        lay.addWidget(nav)

        wrap = QWidget()
        wlay = QVBoxLayout(wrap); wlay.setContentsMargins(18, 16, 18, 16)
        self.stack = QStackedWidget()
        self.live = LivePage(engine)
        self.kiosk = KioskPage(engine)
        self.image = ImagePage(engine)
        self.spoof = SpoofTestPage(engine)
        self.gesture = GesturePage(engine)
        self.enroll = EnrollPage(engine, on_change=self.refresh_status)
        self.dash = DashboardPage(engine, on_change=self.refresh_status)
        for p in (self.live, self.kiosk, self.image, self.spoof,
                  self.gesture, self.enroll, self.dash):
            self.stack.addWidget(p)
        wlay.addWidget(self.stack)
        lay.addWidget(wrap, 1)
        self.refresh_status()

    def refresh_status(self):
        import torch
        dev = "GPU (CUDA)" if torch.cuda.is_available() else "CPU"
        self.status.setText(f"Thiết bị: {dev}\nBackbone: {self.engine.backbone}\n"
                            f"DB: {len(self.engine.db)} người · ngưỡng {self.engine.threshold:.2f}")
        if hasattr(self, "dash"):
            self.dash.refresh()
        if hasattr(self, "enroll"):
            self.enroll.refresh_folders()

    def closeEvent(self, e):
        for p in (self.live, self.kiosk, self.spoof, self.gesture, self.enroll):
            p.closeEvent(e)
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    app.setFont(QFont("Segoe UI", 10))

    dlg = QProgressDialog("Đang nạp mô hình nhận diện...", None, 0, 0)
    dlg.setWindowTitle("FaceID Studio")
    dlg.setCancelButton(None)
    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
    dlg.show()
    app.processEvents()

    engine = Engine()
    try:
        engine.load()
    except Exception as e:  # noqa: BLE001
        dlg.close()
        QMessageBox.critical(None, "Lỗi khởi động", str(e))
        return 1
    dlg.close()

    win = MainWindow(engine)
    win.show()
    if "--selftest" in sys.argv:
        QTimer.singleShot(600, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
