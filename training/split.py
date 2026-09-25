"""Chia tập theo DANH TÍNH và ghi ra manifest — nguồn sự thật duy nhất.

Vì sao phải có file này
-----------------------
Cách chia cũ (`src/evaluate.py`) lấy *ảnh* của cùng một người rồi cắt thành
gallery và query. Hậu quả: mọi danh tính trong tập kiểm thử đều đã xuất hiện lúc
huấn luyện, nên con số báo cáo đo nhầm sang bài toán "nhận lại ảnh đã học" chứ
không phải "nhận ra người chưa từng gặp". Đó là rò rỉ dữ liệu, và nó luôn thổi
phồng kết quả.

Nhận diện khuôn mặt là bài toán **open-set**: mô hình phải trích được đặc trưng
cho những người nó chưa bao giờ nhìn thấy lúc train. Muốn đo đúng điều đó, ranh
giới phải nằm ở mức danh tính, không phải mức ảnh.

Bốn tập, không giao nhau về danh tính
-------------------------------------
  train     — dùng để huấn luyện backbone
  val       — theo dõi trong lúc train, chọn checkpoint
  test      — người ĐƯỢC đăng ký lúc đánh giá (chia tiếp thành gallery / probe)
  stranger  — người KHÔNG được đăng ký, đóng vai người lạ để đo FAR open-set

Manifest ghi ra là file JSON; cả `train.py` lẫn `evaluate.py` đều đọc từ đây nên
không thể lệch nhau.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime
from pathlib import Path

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_MANIFEST = Path("data/manifest.json")


def scan_identities(root: Path, min_images: int) -> dict[str, list[str]]:
    """Quét thư mục dạng <tên người>/<ảnh>, bỏ người có quá ít ảnh."""
    out: dict[str, list[str]] = {}
    if not root.exists():
        raise SystemExit(f"Không thấy thư mục: {root}")
    for pdir in sorted(p for p in root.iterdir() if p.is_dir()):
        imgs = sorted(str(p.relative_to(root)) for p in pdir.rglob("*")
                      if p.suffix.lower() in IMG_EXT)
        if len(imgs) >= min_images:
            out[pdir.name] = imgs
    return out


def build_manifest(root: Path, *, seed: int = 42, min_images: int = 4,
                   ratios: tuple[float, float, float, float] = (0.60, 0.10, 0.20, 0.10),
                   gallery_per_id: int = 3) -> dict:
    """Chia danh tính thành 4 tập rời nhau, kèm chia gallery/probe cho tập test."""
    people = scan_identities(root, min_images)
    if len(people) < 8:
        raise SystemExit(f"Chỉ có {len(people)} người có ≥{min_images} ảnh — quá ít để chia tập.")

    names = sorted(people)
    rng = random.Random(seed)
    rng.shuffle(names)

    n = len(names)
    n_train = int(n * ratios[0])
    n_val = int(n * ratios[1])
    n_test = int(n * ratios[2])
    # Phần dư dồn hết cho stranger để không mất danh tính nào.
    parts = {
        "train": names[:n_train],
        "val": names[n_train:n_train + n_val],
        "test": names[n_train + n_val:n_train + n_val + n_test],
        "stranger": names[n_train + n_val + n_test:],
    }

    # Với tập test, chia tiếp ảnh của mỗi người thành gallery (đăng ký) và probe (truy vấn).
    gallery: dict[str, list[str]] = {}
    probe: dict[str, list[str]] = {}
    for name in parts["test"]:
        imgs = list(people[name])
        rng.shuffle(imgs)
        k = min(gallery_per_id, max(1, len(imgs) - 1))
        gallery[name] = imgs[:k]
        probe[name] = imgs[k:]

    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "source": str(root).replace("\\", "/"),
        "seed": seed,
        "min_images": min_images,
        "gallery_per_id": gallery_per_id,
        "num_identities": n,
        "splits": {
            k: {"identities": v,
                "num_identities": len(v),
                "num_images": sum(len(people[name]) for name in v)}
            for k, v in parts.items()
        },
        "test_gallery": gallery,
        "test_probe": probe,
        "images": {name: people[name] for name in names},
    }
    return manifest


def load_manifest(path: str | Path = DEFAULT_MANIFEST) -> dict:
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"Không thấy manifest: {path}. Chạy `python -m training.split` trước.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def identities(manifest: dict, split: str) -> list[str]:
    return manifest["splits"][split]["identities"]


def image_paths(manifest: dict, name: str) -> list[Path]:
    root = Path(manifest["source"])
    return [root / rel for rel in manifest["images"][name]]


def assert_disjoint(manifest: dict) -> None:
    """Kiểm tra bốn tập thật sự không giao nhau — chốt chặn chống rò rỉ."""
    seen: dict[str, str] = {}
    for split in ("train", "val", "test", "stranger"):
        for name in identities(manifest, split):
            if name in seen:
                raise AssertionError(
                    f"Danh tính {name!r} xuất hiện ở cả {seen[name]!r} và {split!r} — tập bị rò rỉ!")
            seen[name] = split


def main():
    ap = argparse.ArgumentParser(description="Chia tập theo danh tính, ghi ra manifest JSON")
    ap.add_argument("--data-dir", default="data/aligned")
    ap.add_argument("--out", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-images", type=int, default=4)
    ap.add_argument("--gallery-per-id", type=int, default=3,
                    help="Số ảnh đăng ký cho mỗi người trong tập test")
    args = ap.parse_args()

    manifest = build_manifest(Path(args.data_dir), seed=args.seed,
                              min_images=args.min_images,
                              gallery_per_id=args.gallery_per_id)
    assert_disjoint(manifest)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Nguồn: {manifest['source']}  ·  {manifest['num_identities']} danh tính")
    print(f"{'tập':<10}{'người':>8}{'ảnh':>8}")
    print("-" * 26)
    for k in ("train", "val", "test", "stranger"):
        s = manifest["splits"][k]
        print(f"{k:<10}{s['num_identities']:>8}{s['num_images']:>8}")
    ng = sum(len(v) for v in manifest["test_gallery"].values())
    npb = sum(len(v) for v in manifest["test_probe"].values())
    print(f"\ntest chia tiếp: gallery {ng} ảnh · probe {npb} ảnh")
    print(f"Đã kiểm tra: bốn tập KHÔNG giao nhau về danh tính.")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
