"""Chưng cất tri thức: dạy MobileFaceNet bắt chước FaceNet.

    python -m training.distill --config training/configs/distill.yaml

Vấn đề cần giải
---------------
Huấn luyện MobileFaceNet từ đầu bằng ArcFace trên 2.743 ảnh chỉ đạt AUC 0,947 —
kém xa FaceNet pretrained (0,9987) vốn học từ 3,3 triệu ảnh. Không có cách nào bù
khoảng cách đó bằng tinh chỉnh siêu tham số: nó là khoảng cách về dữ liệu.

Nhưng FaceNet nặng 107 MB và chạy 83,7 ms mỗi khuôn mặt, trong khi MobileFaceNet
chỉ 4,8 MB và 5,29 ms. Ta muốn cả hai.

Cách giải
---------
Cho FaceNet đóng vai **thầy**: với mỗi ảnh, vector nó sinh ra trở thành đích để
MobileFaceNet (**trò**) học theo. Trò không học "ảnh này là ai" mà học "hãy mô tả
khuôn mặt giống hệt cách thầy mô tả" — nhờ vậy nó thừa hưởng gián tiếp tri thức
mà thầy chắt lọc từ 3,3 triệu ảnh, dù bản thân chỉ nhìn thấy vài nghìn ảnh.

Ba điểm khiến cách này đặc biệt hợp hoàn cảnh:

1. **Không cần nhãn danh tính.** ArcFace bắt buộc mỗi người phải có ít nhất 2 ảnh
   để tạo lớp; distillation thì mọi ảnh đều dùng được, kể cả người chỉ có đúng 1
   ảnh. Riêng với LFW, điều đó mở thêm hàng nghìn ảnh vốn bị vứt đi.

2. **Đích hồi quy giàu thông tin hơn nhãn phân loại.** Mỗi ảnh cho 512 số làm
   đích, thay vì một nhãn 1-trong-349.

3. **Học tính bền vững.** Thầy nhìn ảnh **sạch**, trò nhìn ảnh **đã augment**.
   Trò buộc phải cho ra cùng một vector dù ảnh bị mờ, thiếu sáng hay nén vỡ —
   đúng thứ webcam phòng học tạo ra.

Chống rò rỉ
-----------
Chỉ chưng cất trên những danh tính KHÔNG nằm trong val/test/stranger của manifest.
Dù không dùng nhãn, việc cho trò nhìn ảnh của người trong tập kiểm thử vẫn là rò
rỉ. Danh sách ảnh được lọc qua `assert` trước khi train.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from engine.embed.facenet import FaceNetEmbedder
from engine.embed.mobilefacenet import MobileFaceNet
from engine.settings import EmbedSettings
from training.datasets import FaceAugment, to_tensor
from training.split import identities, load_manifest
from training.train import verification_accuracy

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

DEFAULTS = {
    "manifest": "data/manifest_big.json",
    "extra_dirs": [],          # thư mục ảnh đã align thêm, dùng cho distillation
    #: Nguồn RecordIO (CASIA-WebFace). Gộp thêm vào cùng với extra_dirs.
    "recordio_dir": "",
    "recordio_num_ids": 6000,
    "recordio_max_per_id": 20,
    "out_dir": "models",
    "name": "mobilefacenet_distill",
    "cache": "data/teacher_embeddings.npz",
    "image_size": 112,
    "embedding_dim": 512,
    "epochs": 40,
    "batch_size": 128,
    "lr": 0.05,
    "weight_decay": 5e-4,
    "momentum": 0.9,
    "warmup_iters": 200,
    "augment_strength": 1.0,
    "workers": 0,
    "seed": 42,
}


def load_config(path: str | None) -> dict:
    cfg = dict(DEFAULTS)
    if path:
        import yaml
        cfg.update(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})
    return cfg


# ------------------------------------------------------ chọn ảnh, tránh rò rỉ
def collect_images(manifest: dict, extra_dirs: list[str]) -> tuple[list[Path], set[str]]:
    """Mọi ảnh dùng được cho distillation, đã loại danh tính của val/test/stranger."""
    forbidden = set()
    for split in ("val", "test", "stranger"):
        forbidden.update(identities(manifest, split))

    paths: list[Path] = []
    root = Path(manifest["source"])
    for name in identities(manifest, "train"):
        paths.extend(root / rel for rel in manifest["images"][name])

    for d in extra_dirs:
        d = Path(d)
        if not d.exists():
            continue
        for pdir in sorted(p for p in d.iterdir() if p.is_dir()):
            if pdir.name in forbidden:
                continue                       # chốt chặn rò rỉ
            paths.extend(p for p in sorted(pdir.rglob("*")) if p.suffix.lower() in IMG_EXT)

    # Bỏ trùng theo (tên người, tên file) để hai nguồn không đếm hai lần.
    seen, unique = set(), []
    for p in paths:
        key = (p.parent.name, p.name)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique, forbidden


# ---------------------------------------------- tính trước embedding của thầy
@torch.no_grad()
def build_teacher_cache(source: "ImageSource", cache_path: Path, batch_size: int = 64) -> np.ndarray:
    """Chạy FaceNet một lần trên toàn bộ ảnh sạch rồi lưu lại.

    Thầy không đổi trong suốt quá trình, nên chạy lại mỗi epoch là lãng phí. Tính
    trước rồi cache giúp mỗi epoch chỉ còn chi phí của trò.
    """
    cache_path = Path(cache_path)
    keys = source.keys()
    n = len(keys)
    if cache_path.exists():
        data = np.load(cache_path, allow_pickle=True)
        if len(data["paths"]) == n and list(data["paths"]) == keys:
            print(f"Dùng lại cache thầy: {cache_path} ({n} ảnh)")
            return data["emb"].astype(np.float32)
        print("Cache cũ không khớp danh sách ảnh — tính lại.")

    teacher = FaceNetEmbedder(EmbedSettings(backend="facenet", batch_size=batch_size))
    out = np.zeros((n, teacher.dim), dtype=np.float32)
    t0 = time.perf_counter()
    for i in range(0, n, batch_size):
        idxs = range(i, min(i + batch_size, n))
        imgs = [(j, source.read(j)) for j in idxs]
        ok = [(j, im) for j, im in imgs if im is not None]
        if ok:
            vecs = teacher.embed([im for _, im in ok])
            for (j, _), v in zip(ok, vecs):
                out[j] = v
        if (i // batch_size) % 100 == 0:
            el = time.perf_counter() - t0
            done = min(i + batch_size, n)
            eta = el / max(done, 1) * (n - done)
            print(f"  thầy: {done}/{n} ảnh · {el:.0f}s · còn ~{eta/60:.1f} phút", flush=True)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache_path, paths=np.array(keys), emb=out)
    print(f"Đã lưu cache thầy: {cache_path} ({time.perf_counter()-t0:.0f}s)")
    return out


# --------------------------------------------------------------------- dataset
class ImageSource:
    """Nguồn ảnh thống nhất: file trên đĩa và/hoặc bản ghi trong RecordIO.

    Distillation không cần nhãn, nên gộp được nhiều nguồn khác nhau vào một danh
    sách phẳng — miễn là mỗi phần tử trả về được một ảnh và một khoá định danh
    ổn định để cache embedding của thầy.
    """

    def __init__(self, paths: list[Path] | None = None,
                 rec_dir: str | Path | None = None,
                 rec_indices: list[int] | None = None):
        self.paths = list(paths or [])
        self.rec_dir = Path(rec_dir) if rec_dir else None
        self.rec_indices = list(rec_indices or [])
        self._reader = None

    def __len__(self) -> int:
        return len(self.paths) + len(self.rec_indices)

    def _reader_lazy(self):
        if self._reader is None:
            from training.recordio import RecordIOReader
            self._reader = RecordIOReader(self.rec_dir / "train.rec",
                                          self.rec_dir / "train.idx")
        return self._reader

    def read(self, i: int) -> np.ndarray | None:
        if i < len(self.paths):
            return cv2.imread(str(self.paths[i]))
        try:
            _, img = self._reader_lazy().image(self.rec_indices[i - len(self.paths)])
            return img
        except Exception:                       # noqa: BLE001
            return None

    def key(self, i: int) -> str:
        if i < len(self.paths):
            return str(self.paths[i])
        return f"rec:{self.rec_dir.name}:{self.rec_indices[i - len(self.paths)]}"

    def keys(self) -> list[str]:
        return [self.key(i) for i in range(len(self))]

    def subset(self, mask: np.ndarray) -> "ImageSource":
        np_paths = len(self.paths)
        keep_paths = [p for p, k in zip(self.paths, mask[:np_paths]) if k]
        keep_recs = [r for r, k in zip(self.rec_indices, mask[np_paths:]) if k]
        return ImageSource(keep_paths, self.rec_dir, keep_recs)

    def describe(self) -> str:
        return f"{len(self.paths)} ảnh từ đĩa + {len(self.rec_indices)} bản ghi RecordIO"


class DistillDataset(Dataset):
    """Trả về (ảnh đã augment cho trò, vector đích của thầy tính trên ảnh sạch)."""

    def __init__(self, source: ImageSource, targets: np.ndarray, size: int = 112,
                 augment_strength: float = 1.0):
        self.source = source
        self.targets = targets
        self.size = size
        self.aug = FaceAugment(size, augment_strength)

    def __len__(self) -> int:
        return len(self.source)

    def __getitem__(self, i: int):
        img = self.source.read(i)
        if img is None:
            img = np.zeros((self.size, self.size, 3), np.uint8)
        return to_tensor(self.aug(img), self.size), torch.from_numpy(self.targets[i])


# ----------------------------------------------------------------------- train
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--batch-size", type=int, default=None)
    ap.add_argument("--lr", type=float, default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    for k, v in vars(args).items():
        if k != "config" and v is not None:
            cfg[k] = v

    torch.manual_seed(cfg["seed"]); np.random.seed(cfg["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    manifest = load_manifest(cfg["manifest"])

    print(f"Thiết bị: {device}"
          + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""))

    paths, forbidden = collect_images(manifest, cfg["extra_dirs"])
    leaked = [p for p in paths if p.parent.name in forbidden]
    assert not leaked, f"Rò rỉ! {len(leaked)} ảnh thuộc danh tính val/test/stranger"
    n_people = len({p.parent.name for p in paths})
    print(f"Từ đĩa   : {len(paths)} ảnh · {n_people} người "
          f"(đã loại {len(forbidden)} danh tính val/test/stranger)")

    rec_indices: list[int] = []
    rec_dir = cfg.get("recordio_dir") or None
    if rec_dir:
        # CASIA là bộ độc lập với LFW nên không dùng chung danh tính; vẫn giới hạn
        # số ảnh mỗi người để không một người nào lấn át quá trình chưng cất.
        from training.recordio import labels_from_lst
        from training.datasets import split_casia_identities
        train_ids, _ = split_casia_identities(rec_dir,
                                              num_train=cfg["recordio_num_ids"],
                                              num_val=0, seed=cfg["seed"])
        per_id: dict[int, int] = {}
        cap = cfg["recordio_max_per_id"]
        for i, lab in enumerate(labels_from_lst(Path(rec_dir) / "train.lst")):
            if lab not in train_ids:
                continue
            c = per_id.get(lab, 0)
            if cap and c >= cap:
                continue
            per_id[lab] = c + 1
            rec_indices.append(i)
        print(f"Từ RecordIO: {len(rec_indices)} ảnh · {len(per_id)} người ({rec_dir})")

    source = ImageSource(paths, rec_dir, rec_indices)
    print(f"Tổng cộng: {len(source)} ảnh — {source.describe()}")

    targets = build_teacher_cache(source, Path(cfg["cache"]), cfg["batch_size"])
    keep = np.linalg.norm(targets, axis=1) > 0.5          # bỏ ảnh thầy không đọc được
    source = source.subset(keep)
    targets = targets[keep]
    print(f"Sau khi lọc ảnh hỏng: {len(source)} ảnh")

    ds = DistillDataset(source, targets, cfg["image_size"], cfg["augment_strength"])
    loader = DataLoader(ds, batch_size=cfg["batch_size"], shuffle=True,
                        num_workers=cfg["workers"], drop_last=True,
                        pin_memory=(device.type == "cuda"))

    from training.datasets import FaceDataset
    val_ds = FaceDataset(manifest, "val", cfg["image_size"], augment=False)

    student = MobileFaceNet(cfg["embedding_dim"], cfg["image_size"]).to(device)
    print(f"Trò: MobileFaceNet {student.num_parameters()/1e6:.2f}M tham số · "
          f"thầy: FaceNet 512-D")

    optimizer = torch.optim.SGD(student.parameters(), lr=cfg["lr"],
                                momentum=cfg["momentum"],
                                weight_decay=cfg["weight_decay"], nesterov=True)
    total_steps = max(1, len(loader) * cfg["epochs"])
    warmup = int(cfg["warmup_iters"])

    def lr_at(step: int) -> float:
        if warmup and step <= warmup:
            return cfg["lr"] * (0.01 + 0.99 * step / warmup)
        p = (step - warmup) / max(1, total_steps - warmup)
        return cfg["lr"] * 0.5 * (1.0 + math.cos(math.pi * min(1.0, p)))

    out_dir = Path(cfg["out_dir"]); out_dir.mkdir(parents=True, exist_ok=True)
    ckpt = out_dir / f"{cfg['name']}.pt"
    best, history, step = -1.0, [], 0

    print(f"\n{'ep':>3} {'cos_loss':>9} {'cos_sim':>8} {'val_ver':>8} {'val_auc':>8} {'lr':>8} {'giây':>6}")
    print("-" * 56)

    for epoch in range(1, cfg["epochs"] + 1):
        student.train()
        t0, tot, seen, sim_sum = time.perf_counter(), 0.0, 0, 0.0
        for images, tgt in loader:
            step += 1
            for g in optimizer.param_groups:
                g["lr"] = lr_at(step)
            images = images.to(device, non_blocking=True)
            tgt = tgt.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)
            emb = student(images)
            # Cả hai vector đã chuẩn hoá L2 nên cosine chính là tích vô hướng.
            # Loss = 1 − cosine: bằng 0 khi trò khớp thầy hoàn toàn.
            cos = (emb * F.normalize(tgt, eps=1e-6)).sum(dim=1)
            loss = (1.0 - cos).mean()
            loss.backward()
            nn.utils.clip_grad_norm_(student.parameters(), 5.0)
            optimizer.step()

            bs = images.size(0)
            tot += loss.item() * bs; sim_sum += cos.sum().item(); seen += bs

        val_acc, val_auc = verification_accuracy(student, val_ds, device)
        row = {"epoch": epoch, "loss": tot / seen, "cos": sim_sum / seen,
               "val_ver": val_acc, "val_auc": val_auc, "lr": lr_at(step),
               "sec": time.perf_counter() - t0}
        history.append(row)
        print(f"{epoch:3d} {row['loss']:9.5f} {row['cos']:8.4f} {val_acc:8.4f} "
              f"{val_auc:8.4f} {row['lr']:8.5f} {row['sec']:6.1f}")

        if val_acc >= best:
            best = val_acc
            torch.save({"model": student.state_dict(),
                        "meta": {"image_size": cfg["image_size"],
                                 "embedding_dim": cfg["embedding_dim"],
                                 "arch": "mobilefacenet",
                                 "trained_by": "distillation from facenet",
                                 "num_distill_images": len(source),
                                 "val_verification_acc": round(best, 4),
                                 "val_auc": round(val_auc, 4),
                                 "epoch": epoch}}, ckpt)

    (out_dir / f"{cfg['name']}_history.json").write_text(
        json.dumps({"config": cfg, "history": history}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"\nTốt nhất: val_verification_acc = {best:.4f}")
    print(f"-> {ckpt}")
    print(f"Bước tiếp: python -m training.export_onnx --checkpoint {ckpt}")


if __name__ == "__main__":
    main()
