"""Nạp và phát hiệu ứng dạng dãy ảnh PNG lên khung hình.

Thiết kế để **thả tệp vào là dùng được**
----------------------------------------
Mỗi hiệu ứng là một thư mục con trong `effects/`, bên trong là dãy ảnh đặt tên
`frame_000.png`, `frame_001.png`… Ứng dụng tự quét lúc khởi động, nên thêm hiệu
ứng mới không phải sửa một dòng mã nào. Nhờ vậy hiệu ứng tự sinh bằng
`tools/sinh_hieu_ung.py` và hiệu ứng tải từ nơi khác dùng chung một đường.

Hai cách trộn, và vì sao cần cả hai
-----------------------------------
* **alpha** — trộn theo kênh trong suốt. Rìa sạch, giữ đúng màu gốc. Hợp với
  khói, vòng sáng, những thứ có hình khối rõ.
* **cong** (cộng sáng) — lấy giá trị sáng cộng thẳng vào nền. Vùng tối của hiệu
  ứng tự biến mất, và vùng sáng thì loé lên. Đây là cách ánh sáng thật hoạt động,
  nên lửa và tia sét trộn kiểu này mới ra chất; trộn alpha sẽ trông như miếng
  dán phẳng.

Hiệu ứng được phát tại **toạ độ ngón tay**, và mỗi lần kích hoạt là một thể hiện
riêng — nên vẫy tay liên tục sẽ thấy nhiều hiệu ứng chồng nhau ở các giai đoạn
khác nhau, thay vì một hiệu ứng bị khởi động lại liên tục.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

THU_MUC = Path("effects")

#: Hiệu ứng nào nên trộn theo kiểu nào. Tên không có trong bảng thì mặc định
#: dùng alpha — an toàn hơn, vì cộng sáng lên một ảnh vốn đã sáng sẽ cháy trắng.
KIEU_TRON = {
    "lua": "cong",
    "tia_set": "cong",
    "tia_lua": "cong",
    "vong_nang_luong": "alpha",
    "khoi": "alpha",
}


class BoHieuUng:
    """Đọc toàn bộ hiệu ứng trong thư mục, giữ sẵn trong bộ nhớ."""

    def __init__(self, thu_muc: Path | str = THU_MUC, co_toi_da: int = 220):
        self.thu_muc = Path(thu_muc)
        self.co_toi_da = co_toi_da
        self.kho: dict[str, list[np.ndarray]] = {}
        self._nap()

    def _nap(self) -> None:
        if not self.thu_muc.exists():
            return
        for d in sorted(p for p in self.thu_muc.iterdir() if p.is_dir()):
            khung = []
            for f in sorted(d.glob("frame_*.png")):
                # IMREAD_UNCHANGED để giữ kênh alpha; thiếu cờ này thì OpenCV
                # bỏ luôn kênh trong suốt và hiệu ứng thành khối vuông đen.
                im = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)
                if im is None:
                    continue
                if im.ndim == 3 and im.shape[2] == 3:       # không có alpha
                    im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
                # Thu nhỏ ngay lúc nạp, không phải mỗi khung hình: trộn ảnh
                # 256px lên video 30 fps là việc làm mỗi 33 ms, còn thu nhỏ là
                # việc làm đúng một lần.
                h, w = im.shape[:2]
                if max(h, w) > self.co_toi_da:
                    ti_le = self.co_toi_da / max(h, w)
                    im = cv2.resize(im, (int(w * ti_le), int(h * ti_le)),
                                    interpolation=cv2.INTER_AREA)
                khung.append(im)
            if khung:
                self.kho[d.name] = khung

    @property
    def ten(self) -> list[str]:
        return sorted(self.kho)

    def __contains__(self, ten: str) -> bool:
        return ten in self.kho

    def so_khung(self, ten: str) -> int:
        return len(self.kho.get(ten, []))


class _TheHien:
    """Một lần phát hiệu ứng tại một vị trí."""

    __slots__ = ("ten", "x", "y", "i", "ti_le")

    def __init__(self, ten: str, x: float, y: float, ti_le: float = 1.0):
        self.ten, self.x, self.y, self.i, self.ti_le = ten, float(x), float(y), 0, ti_le


class MayPhat:
    """Phát và trộn các hiệu ứng đang chạy lên khung hình."""

    def __init__(self, bo: BoHieuUng, toi_da: int = 12):
        self.bo = bo
        self.toi_da = toi_da
        self.dang_chay: list[_TheHien] = []

    def phat(self, ten: str, x: float, y: float, ti_le: float = 1.0) -> bool:
        if ten not in self.bo:
            return False
        # Chặn trần số hiệu ứng cùng lúc. Không chặn thì vẫy tay liên tục sẽ sinh
        # ra hàng trăm thể hiện và tốc độ khung hình tụt thẳng đứng.
        if len(self.dang_chay) >= self.toi_da:
            self.dang_chay.pop(0)
        self.dang_chay.append(_TheHien(ten, x, y, ti_le))
        return True

    def xoa_het(self) -> None:
        self.dang_chay.clear()

    def ve(self, frame: np.ndarray) -> np.ndarray:
        """Trộn mọi hiệu ứng đang chạy vào khung hình, rồi tiến một khung."""
        if not self.dang_chay:
            return frame
        H, W = frame.shape[:2]
        con_song: list[_TheHien] = []
        for th in self.dang_chay:
            khung = self.bo.kho.get(th.ten)
            if not khung or th.i >= len(khung):
                continue
            self._tron(frame, khung[th.i], th, W, H)
            th.i += 1
            if th.i < len(khung):
                con_song.append(th)
        self.dang_chay = con_song
        return frame

    @staticmethod
    def _tron(nen: np.ndarray, sprite: np.ndarray, th: _TheHien, W: int, H: int) -> None:
        if th.ti_le != 1.0:
            sh, sw = sprite.shape[:2]
            sprite = cv2.resize(sprite, (max(2, int(sw * th.ti_le)),
                                         max(2, int(sh * th.ti_le))),
                                interpolation=cv2.INTER_AREA)
        h, w = sprite.shape[:2]
        x0, y0 = int(th.x - w / 2), int(th.y - h / 2)

        # Cắt phần nằm ngoài khung hình. Thiếu bước này thì hiệu ứng ở sát mép
        # sẽ ném lỗi kích thước thay vì bị xén gọn.
        sx0, sy0 = max(0, -x0), max(0, -y0)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(W, x0 + w - sx0), min(H, y0 + h - sy0)
        if x1 <= x0 or y1 <= y0:
            return
        mieng = sprite[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)]
        vung = nen[y0:y1, x0:x1]

        bgr = mieng[..., :3].astype(np.float32)
        a = (mieng[..., 3:4].astype(np.float32) / 255.0)

        if KIEU_TRON.get(th.ten, "alpha") == "cong":
            # Cộng sáng: vùng tối của hiệu ứng tự biến mất, vùng sáng loé lên.
            vung[:] = np.clip(vung.astype(np.float32) + bgr * a, 0, 255).astype(np.uint8)
        else:
            vung[:] = (vung.astype(np.float32) * (1 - a) + bgr * a).astype(np.uint8)
