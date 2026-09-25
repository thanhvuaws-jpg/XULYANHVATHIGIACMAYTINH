"""Tien xu ly: quet 1 thu muc anh (ImageFolder), phat hien + can chinh khuon mat,
luu ra data/aligned/<ten_nguoi>/*.jpg (160x160).

Dung cho CA HAI nguon:
    python -m src.preprocess --src data/kaggle/pins       --dst data/aligned
    python -m src.preprocess --src data/enrolled          --dst data/aligned

Tuy chon --augment N: tao them N ban sao augment (lat ngang, doi sang) moi anh.
"""
import argparse
import random
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

from . import config
from .face_utils import FaceDetector

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _augment(face: np.ndarray, n: int):
    outs = []
    for _ in range(n):
        f = face.copy()
        if random.random() < 0.5:
            f = cv2.flip(f, 1)
        alpha = random.uniform(0.8, 1.2)   # do tuong phan
        beta = random.uniform(-25, 25)     # do sang
        f = cv2.convertScaleAbs(f, alpha=alpha, beta=beta)
        if random.random() < 0.3:
            k = random.choice([3, 5])
            f = cv2.GaussianBlur(f, (k, k), 0)
        outs.append(f)
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Thu muc ImageFolder: <ten>/<anh>")
    ap.add_argument("--dst", default=str(config.ALIGNED_DIR))
    ap.add_argument("--augment", type=int, default=0, help="So ban augment moi anh")
    ap.add_argument("--min-conf", type=float, default=config.DETECTION_MIN_CONF)
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)
    det = FaceDetector(min_conf=args.min_conf)

    people = sorted([d for d in src.iterdir() if d.is_dir()])
    if not people:
        print(f"[!] Khong thay thu muc con nao trong {src}. Can cau truc <ten_nguoi>/<anh>.jpg")
        return

    n_in = n_out = 0
    for pdir in people:
        out_dir = dst / pdir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        imgs = [p for p in pdir.rglob("*") if p.suffix.lower() in IMG_EXT]
        for img_path in tqdm(imgs, desc=pdir.name, leave=False):
            n_in += 1
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            face = det.largest_face(img)
            if face is None:
                continue
            stem = img_path.stem
            cv2.imwrite(str(out_dir / f"{stem}.jpg"), face)
            n_out += 1
            for i, aug in enumerate(_augment(face, args.augment)):
                cv2.imwrite(str(out_dir / f"{stem}_aug{i}.jpg"), aug)
                n_out += 1

    print(f"\n[OK] {len(people)} nguoi | anh vao: {n_in} | khuon mat luu ra: {n_out}")
    print(f"     -> {dst}")


if __name__ == "__main__":
    main()
