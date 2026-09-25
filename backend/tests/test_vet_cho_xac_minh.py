"""Vết đang chờ xác minh sự sống KHÔNG được mất quyền phát sự kiện.

    python -m backend.tests.test_vet_cho_xac_minh

Lỗi mà bài test này canh
------------------------
`FaceTracker.newly_confirmed()` đánh dấu vết là "đã phát" NGAY LÚC trả về nó. Ban
đầu kiosk gọi hàm này rồi mới kiểm tra điểm sống, nên khi điểm sống còn là "đang
đo" thì vòng lặp `continue` — và vết bị đốt vĩnh viễn.

Hậu quả quan sát được ngoài đời: người dùng bước vào, khung chuyển xanh, điểm sống
lên 1,00, nhưng nhật ký không có dòng điểm danh nào và không ai hiểu tại sao. Nhận
diện đúng, chống giả mạo đúng, mà bản ghi vẫn không tới nơi.

Đây là loại lỗi không có thông báo, không có ngoại lệ, và chỉ lộ ra khi ngồi thử
thật — nên phải có test giữ.
"""
from __future__ import annotations

import sys

import numpy as np

from engine.settings import TrackSettings
from engine.track import FaceTracker
from engine.types import Detection, Identity

_p = _f = 0
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def check(ten: str, dieu_kien: bool, chi_tiet: str = "") -> None:
    global _p, _f
    if dieu_kien:
        _p += 1
        print(f"  [OK]  {ten}" + (f"   {chi_tiet}" if chi_tiet else ""))
    else:
        _f += 1
        print(f"  [LỖI] {ten}   {chi_tiet}")


def mot_khuon_mat() -> Detection:
    return Detection(box=np.array([100, 100, 300, 340], dtype=np.float32),
                     score=0.99,
                     landmarks=np.array([[150, 180], [250, 180], [200, 240],
                                         [160, 290], [240, 290]], dtype=np.float32))


def main() -> int:
    s = TrackSettings()
    print(f"Cấu hình bám vết: cần {s.min_votes} phiếu · tỉ lệ ≥ {s.min_ratio}\n")

    print("=== 1. Vết được xác nhận sau đủ số phiếu ===")
    tr = FaceTracker(s)
    det = mot_khuon_mat()
    vet = None
    for _ in range(s.min_votes):
        vet = tr.update([det])[0]
        tr.vote(vet, Identity("THANHVU", 0.92))
    check("Vết đã xác nhận", vet.confirmed, f"{len(vet.votes)} phiếu")

    print("\n=== 2. Mô phỏng ĐÚNG lỗi cũ: bỏ qua mà không trả lại quyền phát ===")
    phat = tr.newly_confirmed()
    check("Lần đầu có phát ra", len(phat) == 1)
    # Kiosk bản cũ: điểm sống đang là -1.0 nên `continue`, KHÔNG trả lại quyền.
    for _ in range(20):
        vet = tr.update([det])[0]
        tr.vote(vet, Identity("THANHVU", 0.92))
    check("Sau đó KHÔNG bao giờ phát lại được", len(tr.newly_confirmed()) == 0,
          "-> đây chính là lỗi: khung xanh, live 1.00, mà không ghi sổ")

    print("\n=== 3. Cách sửa: trả lại quyền phát khi còn đang chờ ===")
    tr2 = FaceTracker(s)
    vet2 = None
    for _ in range(s.min_votes):
        vet2 = tr2.update([det])[0]
        tr2.vote(vet2, Identity("THANHVU", 0.92))

    diem_song = [-1.0, -1.0, -1.0, 1.0]     # ba khung đang đo, rồi đo xong
    da_gui = []
    for ds in diem_song:
        for v in tr2.newly_confirmed():
            if ds < 0:
                v.announced = False          # <- bản sửa
                continue
            da_gui.append((v.identity.label, ds))
        vet2 = tr2.update([det])[0]
        tr2.vote(vet2, Identity("THANHVU", 0.92))

    check("Không gửi gì trong lúc còn đang đo", len(da_gui) <= 1)
    check("Gửi được ĐÚNG MỘT lần khi đo xong", len(da_gui) == 1,
          f"{da_gui}")

    print("\n=== 4. Gửi xong rồi thì không gửi lại (chống ghi trùng) ===")
    them = []
    for _ in range(15):
        for v in tr2.newly_confirmed():
            them.append(v.identity.label)
        vet2 = tr2.update([det])[0]
        tr2.vote(vet2, Identity("THANHVU", 0.92))
    check("Không phát thêm lần nào", not them,
          "một người đứng 30 giây vẫn chỉ tạo một bản ghi")

    print(f"\n{'='*56}\n  {_p} đạt · {_f} lỗi\n{'='*56}")
    return 0 if _f == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
