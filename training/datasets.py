"""Dataset và augmentation cho huấn luyện.

Dataset đọc danh sách danh tính từ **manifest**, không tự quét thư mục — nhờ vậy
tập train tuyệt đối không chạm vào danh tính của tập test/stranger.

Về augmentation
---------------
Mục tiêu không phải "làm méo ảnh cho nhiều", mà là **mô phỏng đúng thứ webcam
phòng học tạo ra**: nén JPEG, nhoè do chuyển động, thiếu sáng, ảnh hơi lệch khung.
Augmentation không giống điều kiện triển khai chỉ làm chậm hội tụ chứ không giúp
mô hình bền hơn.

Quy ước tiền xử lý theo chuẩn ArcFace: RGB, 112×112, (x − 127.5) / 127.5 — khớp
với `engine/embed/onnx_arcface.py` và `torch_arcface.py`.
"""
from __future__ import annotations

import random
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset

from training.split import identities, load_manifest


# ------------------------------------------------------------------ augmentation
class FaceAugment:
    """Augmentation viết tay bằng OpenCV — nhanh hơn torchvision trên ảnh nhỏ."""

    def __init__(self, size: int = 112, strength: float = 1.0):
        self.size = size
        self.p = strength

    def __call__(self, img_bgr: np.ndarray) -> np.ndarray:
        img = img_bgr
        r = random.random

        if r() < 0.5 * self.p:                                   # lật ngang
            img = cv2.flip(img, 1)

        if r() < 0.5 * self.p:                                   # cắt lệch nhẹ + phóng lại
            h, w = img.shape[:2]
            s = random.uniform(0.86, 1.0)
            nh, nw = int(h * s), int(w * s)
            y0 = random.randint(0, h - nh)
            x0 = random.randint(0, w - nw)
            img = cv2.resize(img[y0:y0 + nh, x0:x0 + nw], (w, h), interpolation=cv2.INTER_LINEAR)

        if r() < 0.6 * self.p:                                   # sáng / tương phản
            alpha = random.uniform(0.75, 1.25)
            beta = random.uniform(-28, 28)
            img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

        if r() < 0.25 * self.p:                                  # ám màu
            img = img.astype(np.float32)
            img *= np.array([random.uniform(0.9, 1.1) for _ in range(3)], np.float32)
            img = np.clip(img, 0, 255).astype(np.uint8)

        if r() < 0.12 * self.p:                                  # ảnh xám (camera hồng ngoại)
            img = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)

        if r() < 0.25 * self.p:                                  # nhoè chuyển động
            k = random.choice([3, 5])
            kernel = np.zeros((k, k), np.float32)
            if random.random() < 0.5:
                kernel[k // 2, :] = 1.0 / k
            else:
                kernel[:, k // 2] = 1.0 / k
            img = cv2.filter2D(img, -1, kernel)

        if r() < 0.3 * self.p:                                   # nén JPEG
            q = random.randint(35, 85)
            ok, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
            if ok:
                img = cv2.imdecode(enc, cv2.IMREAD_COLOR)

        if r() < 0.2 * self.p:                                   # nhiễu hạt
            noise = np.random.normal(0, random.uniform(3, 11), img.shape)
            img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        if img.shape[0] != self.size or img.shape[1] != self.size:
            img = cv2.resize(img, (self.size, self.size), interpolation=cv2.INTER_LINEAR)

        if r() < 0.25 * self.p:                                  # che ngẫu nhiên (khẩu trang, tay)
            h, w = img.shape[:2]
            eh, ew = random.randint(h // 8, h // 3), random.randint(w // 8, w // 3)
            y0, x0 = random.randint(0, h - eh), random.randint(0, w - ew)
            img[y0:y0 + eh, x0:x0 + ew] = random.randint(0, 255)

        return img


def to_tensor(img_bgr: np.ndarray, size: int = 112) -> torch.Tensor:
    """BGR uint8 → tensor CHW float đã chuẩn hoá theo quy ước ArcFace."""
    if img_bgr.shape[0] != size or img_bgr.shape[1] != size:
        img_bgr = cv2.resize(img_bgr, (size, size), interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    rgb = (rgb - 127.5) / 127.5
    return torch.from_numpy(np.transpose(rgb, (2, 0, 1)).copy())


# ---------------------------------------------------------------------- dataset
class FaceDataset(Dataset):
    """Ảnh khuôn mặt đã căn chỉnh, lấy đúng các danh tính của một split."""

    def __init__(self, manifest: dict | str | Path, split: str = "train",
                 size: int = 112, augment: bool = True, augment_strength: float = 1.0):
        self.manifest = load_manifest(manifest) if not isinstance(manifest, dict) else manifest
        self.split = split
        self.size = size
        self.root = Path(self.manifest["source"])

        names = identities(self.manifest, split)
        self.classes = sorted(names)
        self.class_to_idx = {n: i for i, n in enumerate(self.classes)}

        self.samples: list[tuple[Path, int]] = []
        for name in self.classes:
            idx = self.class_to_idx[name]
            for rel in self.manifest["images"][name]:
                self.samples.append((self.root / rel, idx))

        self.aug = FaceAugment(size, augment_strength) if augment else None

    def __len__(self) -> int:
        return len(self.samples)

    @property
    def num_classes(self) -> int:
        return len(self.classes)

    def __getitem__(self, i: int):
        path, label = self.samples[i]
        img = cv2.imread(str(path))
        if img is None:                       # ảnh hỏng: trả về ảnh đen thay vì làm sập train
            img = np.zeros((self.size, self.size, 3), np.uint8)
        if self.aug is not None:
            img = self.aug(img)
        return to_tensor(img, self.size), label

    def describe(self) -> str:
        return (f"{self.split}: {self.num_classes} danh tính · {len(self.samples)} ảnh"
                f" · {len(self.samples)/max(1,self.num_classes):.1f} ảnh/người")


# ------------------------------------------------------- dataset đọc RecordIO
class RecordIOFaceDataset(Dataset):
    """Đọc thẳng từ `train.rec` của InsightFace, không giải nén ra đĩa.

    CASIA-WebFace có 501.196 ảnh. Giải nén ra thành 501k file nhỏ vừa tốn thêm
    ~3 GB vừa làm hệ thống tệp Windows chậm thảm hại. Đọc trực tiếp bằng cách
    nhảy tới đúng vị trí byte trong file .rec nhanh hơn hẳn và không tốn đĩa.

    Nhãn lấy từ `train.lst` (nhanh, dạng văn bản) chứ không quét toàn bộ .rec.
    """

    def __init__(self, rec_dir: str | Path, *, identities: set[int] | None = None,
                 max_per_id: int = 0, size: int = 112, augment: bool = True,
                 augment_strength: float = 1.0):
        from training.recordio import RecordIOReader, labels_from_lst

        rec_dir = Path(rec_dir)
        self.rec_dir = rec_dir
        self.size = size
        self._reader = None                      # mở lười, để pickle được cho worker

        all_labels = labels_from_lst(rec_dir / "train.lst")

        by_id: dict[int, list[int]] = {}
        for rec_idx, lab in enumerate(all_labels):
            if identities is not None and lab not in identities:
                continue
            bucket = by_id.setdefault(lab, [])
            if max_per_id and len(bucket) >= max_per_id:
                continue
            bucket.append(rec_idx)

        # Bỏ người chỉ có 1 ảnh: ArcFace không học được gì từ lớp một phần tử.
        by_id = {k: v for k, v in by_id.items() if len(v) >= 2}

        self.classes = sorted(by_id)
        self.class_to_idx = {c: i for i, c in enumerate(self.classes)}
        self.samples: list[tuple[int, int]] = [
            (rec_idx, self.class_to_idx[lab])
            for lab in self.classes for rec_idx in by_id[lab]
        ]
        self.aug = FaceAugment(size, augment_strength) if augment else None

    def _get_reader(self):
        if self._reader is None:
            from training.recordio import RecordIOReader
            self._reader = RecordIOReader(self.rec_dir / "train.rec",
                                          self.rec_dir / "train.idx")
        return self._reader

    def __len__(self) -> int:
        return len(self.samples)

    @property
    def num_classes(self) -> int:
        return len(self.classes)

    def __getitem__(self, i: int):
        rec_idx, label = self.samples[i]
        try:
            _, img = self._get_reader().image(rec_idx)
        except Exception:                        # noqa: BLE001
            img = None
        if img is None:
            img = np.zeros((self.size, self.size, 3), np.uint8)
        if self.aug is not None:
            img = self.aug(img)
        return to_tensor(img, self.size), label

    def describe(self) -> str:
        return (f"{self.num_classes} danh tính · {len(self.samples)} ảnh · "
                f"{len(self.samples)/max(1,self.num_classes):.1f} ảnh/người")


def split_casia_identities(rec_dir: str | Path, *, num_train: int = 0,
                           num_val: int = 400, seed: int = 42
                           ) -> tuple[set[int], set[int]]:
    """Chia danh tính CASIA thành train / val, KHÔNG giao nhau.

    `num_train=0` nghĩa là lấy hết phần còn lại sau khi trích val.
    """
    import random
    from training.recordio import read_property

    n_classes, _, _ = read_property(rec_dir)
    ids = list(range(n_classes))
    random.Random(seed).shuffle(ids)
    val = set(ids[:num_val])
    rest = ids[num_val:]
    train = set(rest if num_train <= 0 else rest[:num_train])
    assert not (train & val), "Danh tính train và val bị chồng lấn!"
    return train, val
