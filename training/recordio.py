"""Đọc dữ liệu đóng gói kiểu MXNet RecordIO (chuẩn InsightFace).

Các bộ khuôn mặt lớn (CASIA-WebFace, MS1M, Glint360K) thường được phát hành dưới
dạng `train.rec` + `train.idx` + `train.lst` thay vì thư mục ảnh, vì hàng trăm
nghìn file nhỏ làm chậm hệ thống tệp một cách khủng khiếp — nhất là trên Windows.

MXNet đã ngừng phát triển và không còn bản cho Python mới, nên module này tự đọc
định dạng, không phụ thuộc thư viện ngoài.

Cấu trúc một bản ghi
--------------------
    magic    : uint32 = 0xced7230a
    lrecord  : uint32  — 3 bit cao là cờ nối, 29 bit thấp là độ dài
    data     : `length` byte, đệm cho tròn bội số 4

Trong `data`:
    header   : struct 'IfQQ' (flag, label, id, id2) = 24 byte
    payload  : ảnh JPEG (khi flag = 0)

`train.idx` là văn bản: `<số thứ tự>\t<vị trí byte trong .rec>`.
`train.lst` là văn bản: `<cờ>\t<đường dẫn gốc>\t<nhãn>\t...` — lấy nhãn từ đây.
"""
from __future__ import annotations

import struct
from pathlib import Path

import cv2
import numpy as np

MAGIC = 0xCED7230A
_IR_HEADER = struct.Struct("IfQQ")      # flag, label, id, id2 -> 24 byte


class RecordIOReader:
    """Truy cập ngẫu nhiên vào một file .rec thông qua .idx."""

    def __init__(self, rec_path: str | Path, idx_path: str | Path | None = None):
        self.rec_path = Path(rec_path)
        idx_path = Path(idx_path) if idx_path else self.rec_path.with_suffix(".idx")
        if not self.rec_path.exists():
            raise FileNotFoundError(self.rec_path)

        # idx: dòng "<số thứ tự>\t<offset>"
        self.offsets: list[int] = []
        with open(idx_path, "r") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    self.offsets.append(int(parts[1]))
        self._fh = open(self.rec_path, "rb")

    def __len__(self) -> int:
        return len(self.offsets)

    def read(self, i: int) -> tuple[int, bytes]:
        """Trả về (nhãn, byte ảnh) của bản ghi thứ i."""
        self._fh.seek(self.offsets[i])
        magic, lrecord = struct.unpack("<II", self._fh.read(8))
        if magic != MAGIC:
            raise ValueError(f"Bản ghi {i} sai magic number: {magic:#x}")
        length = lrecord & 0x1FFFFFFF
        data = self._fh.read(length)

        flag, label, _id, _id2 = _IR_HEADER.unpack_from(data, 0)
        pos = _IR_HEADER.size
        if flag > 0:
            # Nhãn dạng vector: `flag` số thực đứng ngay sau header.
            labels = np.frombuffer(data, dtype=np.float32, count=flag, offset=pos)
            label = float(labels[0])
            pos += flag * 4
        return int(label), data[pos:]

    def image(self, i: int) -> tuple[int, np.ndarray | None]:
        label, blob = self.read(i)
        img = cv2.imdecode(np.frombuffer(blob, np.uint8), cv2.IMREAD_COLOR)
        return label, img

    def close(self):
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def read_property(folder: str | Path) -> tuple[int, int, int]:
    """`property` chứa "<số lớp>,<cao>,<rộng>"."""
    text = (Path(folder) / "property").read_text().strip()
    n, h, w = (int(x) for x in text.split(","))
    return n, h, w


def labels_from_lst(lst_path: str | Path) -> list[int]:
    """Nhãn theo thứ tự bản ghi, đọc từ train.lst (cột thứ 3)."""
    out = []
    with open(lst_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                out.append(int(float(parts[2])))
    return out


# --------------------------------------------------------------------- bin eval
def read_bin_pairs(bin_path: str | Path, image_size: int = 112):
    """Đọc bộ kiểm thử .bin của InsightFace (lfw.bin, agedb_30.bin, cfp_fp.bin...).

    Định dạng: pickle chứa (danh sách byte ảnh JPEG, danh sách nhãn bool).
    Ảnh đi theo cặp: phần tử 2k và 2k+1 tạo thành một cặp, nhãn thứ k cho biết
    cặp đó có cùng người hay không.

    Đây là **giao thức đánh giá chính thức** — dùng nó thì con số của mình so
    sánh trực tiếp được với các bài báo đã công bố.
    """
    import pickle
    with open(bin_path, "rb") as f:
        try:
            bins, issame = pickle.load(f)                    # python 2 pickle
        except UnicodeDecodeError:
            f.seek(0)
            bins, issame = pickle.load(f, encoding="bytes")

    images = []
    for blob in bins:
        arr = np.frombuffer(blob if isinstance(blob, bytes) else bytes(blob), np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is not None and (img.shape[0] != image_size or img.shape[1] != image_size):
            img = cv2.resize(img, (image_size, image_size), interpolation=cv2.INTER_LINEAR)
        images.append(img)
    return images, np.asarray(issame, dtype=bool)
