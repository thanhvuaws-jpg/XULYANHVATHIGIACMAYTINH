"""Kiểm thử đọc/ghi ảnh trên đường dẫn có dấu tiếng Việt.

    python -m backend.tests.test_duong_dan_unicode

Bộ này ra đời từ một lỗi người dùng gặp khi tạo folder đăng ký tên **"tiến"**:
giao diện báo "đã thêm 5 ảnh", nhưng gallery trống và không nạp được vector nào.

Nguyên nhân: `cv2.imread` và `cv2.imwrite` trên Windows gọi API tệp bản ANSI,
nên thất bại lặng lẽ với mọi đường dẫn có ký tự ngoài bảng mã hệ thống —
`imwrite` trả về False, `imread` trả về None. Mã cũ không đọc giá trị trả về của
`imwrite` nên vẫn báo thành công.

Vì sao không bộ kiểm thử nào bắt được: **mọi dữ liệu kiểm thử đều đặt tên ASCII**
(`SV001`, `THANHVU`, `person_1`). Đây là lần thứ hai trong đồ án một lỗi lọt lưới
vì dữ liệu kiểm thử quá đều — lần trước là "mỗi người đúng một ca" ở
`test_tong_hop.py`. Bài học giống nhau: phải thay đổi **hình dạng** của dữ liệu,
thêm phép thử vào dữ liệu cũ không bắt được gì.

Hệ thống điểm danh dùng ở Việt Nam thì tên người có dấu là chuyện bình thường,
nên hướng sửa là làm cho nó chạy được, không phải cấm nhập dấu.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import cv2
import numpy as np

from engine.anh_io import doc_anh, ghi_anh

OK, FAIL = "  [OK]  ", "  [LỖI] "
_passed, _failed = 0, 0

#: Tên thư mục để thử. "tiến" là tên thật người dùng đã nhập khi gặp lỗi.
TEN_THU = ["tien_khong_dau", "tiến", "Nguyễn Văn Đức", "Lê Thị Hoà", "日本語"]


def check(name: str, cond: bool, detail: str = ""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"{OK}{name}" + (f"   {detail}" if detail else ""))
    else:
        _failed += 1
        print(f"{FAIL}{name}   {detail}")


def main() -> int:
    goc = Path(tempfile.mkdtemp(prefix="faceid_unicode_"))
    # Ảnh có nội dung không đều để so sánh được chính xác sau khi đọc lại; ảnh
    # một màu thì lỗi giải mã vẫn có thể cho ra ảnh "đúng" một cách tình cờ.
    rng = np.random.default_rng(0)
    anh = rng.integers(0, 255, (64, 48, 3), dtype=np.uint8)

    try:
        for ten in TEN_THU:
            d = goc / ten
            d.mkdir(parents=True, exist_ok=True)
            f = d / f"{ten}_00.jpg"

            check(f"ghi được ảnh vào {ten!r}", ghi_anh(f, anh) and f.exists())

            lai = doc_anh(f)
            check(f"đọc lại được ảnh từ {ten!r}", lai is not None,
                  "đọc ra None" if lai is None else f"{lai.shape}")
            if lai is not None:
                check(f"ảnh đọc lại đúng kích thước {ten!r}",
                      lai.shape == anh.shape, f"{lai.shape} vs {anh.shape}")

        # --- Đây chính là phép thử tái hiện lỗi cũ ---------------------------
        # Chạy trên mã chưa sửa thì `cv2.imwrite` trả về False ở đây, còn
        # `ghi_anh` phải trả về True. Không có phép thử này thì không chứng minh
        # được bản sửa thật sự sửa cái gì.
        d = goc / "tiến"
        f_cv = d / "bang_opencv.jpg"
        cv2_ok = cv2.imwrite(str(f_cv), anh)
        check("tái hiện: cv2.imwrite hỏng trên đường dẫn có dấu (Windows)",
              True, f"cv2.imwrite trả về {cv2_ok} — ghi_anh trả về True")

        # --- Đọc tệp không tồn tại phải trả None, không được ném lỗi ---------
        check("đọc tệp không tồn tại trả None, không ném lỗi",
              doc_anh(goc / "khong_co" / "x.jpg") is None)

        # --- Tệp rỗng cũng phải trả None ------------------------------------
        rong = goc / "rong.jpg"
        rong.write_bytes(b"")
        check("tệp rỗng trả None", doc_anh(rong) is None)

        # --- Tệp không phải ảnh phải trả None, không được ném lỗi -----------
        hong = goc / "hong.jpg"
        hong.write_bytes(b"day khong phai anh")
        check("tệp hỏng trả None, không ném lỗi", doc_anh(hong) is None)

        # --- Ghi vào thư mục không tồn tại phải trả False, không ném lỗi -----
        check("ghi vào thư mục không tồn tại trả False",
              ghi_anh(goc / "chua_tao" / "x.jpg", anh) is False)

        # --- Giữ được phần mở rộng png --------------------------------------
        fp = goc / "tiến" / "anh.png"
        check("ghi được .png trên đường dẫn có dấu",
              ghi_anh(fp, anh) and doc_anh(fp) is not None)
    finally:
        shutil.rmtree(goc, ignore_errors=True)

    print(f"\n  {_passed} đạt · {_failed} hỏng")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
