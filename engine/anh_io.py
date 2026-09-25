"""Đọc và ghi tệp ảnh chịu được đường dẫn có dấu.

Vì sao cần module này
---------------------
`cv2.imread` và `cv2.imwrite` trên Windows gọi API tệp bản ANSI, nên **thất bại
lặng lẽ** với mọi đường dẫn chứa ký tự ngoài bảng mã hệ thống: `imwrite` trả về
`False` và không ghi gì, `imread` trả về `None`. Không có ngoại lệ nào được ném
ra, nên nơi gọi không đọc giá trị trả về sẽ tưởng mọi thứ bình thường.

Lỗi này được phát hiện khi người dùng tạo folder đăng ký tên **"tiến"**: thư mục
được tạo (Python xử lý Unicode đúng), giao diện báo "đã thêm 5 ảnh", nhưng
gallery trống và không nạp được vector nào. Ba triệu chứng rời rạc, một nguyên
nhân.

Trên Linux thì `cv2` dùng thẳng chuỗi byte UTF-8 nên chạy được — nghĩa là cùng
một đoạn mã chạy đúng trong container và hỏng trên máy Windows của người phát
triển. Đây là loại lỗi chỉ xuất hiện ở một nền tảng, rất dễ đổ oan cho thứ khác.

Cách vòng qua là tự đọc/ghi tệp bằng Python (xử lý Unicode chuẩn trên mọi nền
tảng) và chỉ nhờ OpenCV giải mã/mã hoá phần nội dung trong bộ nhớ.

Một hệ thống điểm danh dùng ở Việt Nam thì tên người có dấu là chuyện bình
thường, nên hướng xử lý là **làm cho nó chạy được**, không phải cấm nhập dấu.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def doc_anh(path: str | Path, co_alpha: bool = False) -> np.ndarray | None:
    """Đọc ảnh, chịu được đường dẫn có dấu. Trả `None` nếu không đọc được.

    `co_alpha=True` giữ kênh trong suốt (tương đương `cv2.IMREAD_UNCHANGED`).
    """
    try:
        buf = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if buf.size == 0:
        return None
    co = cv2.IMREAD_UNCHANGED if co_alpha else cv2.IMREAD_COLOR
    return cv2.imdecode(buf, co)


def ghi_anh(path: str | Path, img: np.ndarray, tham_so: list[int] | None = None) -> bool:
    """Ghi ảnh, chịu được đường dẫn có dấu. Trả về **ghi được hay không**.

    Khác `cv2.imwrite` ở chỗ tên hàm và tài liệu nói rõ giá trị trả về là thứ
    phải kiểm tra — đó chính là bước mà mã cũ bỏ qua, biến một thất bại toàn
    phần thành thông báo "đã thêm 5 ảnh".

    `tham_so` truyền thẳng cho `cv2.imencode`, ví dụ
    `[cv2.IMWRITE_JPEG_QUALITY, 95]`.
    """
    path = Path(path)
    try:
        ok, buf = cv2.imencode(path.suffix or ".jpg", img, tham_so or [])
    except cv2.error:
        return False
    if not ok:
        return False
    try:
        path.write_bytes(buf.tobytes())
    except OSError:
        return False
    return True
