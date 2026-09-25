"""Tai LFW (Labeled Faces in the Wild) truc tiep qua scikit-learn - KHONG can Kaggle.

Dung khi ban chua co kaggle.json de test toan bo pipeline voi mat that.

    python -m src.fetch_lfw --min-faces 20 --max-per-person 40

Ket qua: data/datasets/lfw/<Ten_Nguoi>/<i>.jpg  ->  sau do chay preprocess nhu binh thuong:
    python -m src.preprocess --src data/kaggle/lfw --dst data/aligned --augment 1
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from . import config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-faces", type=int, default=20,
                    help="Chi lay nguoi co it nhat bao nhieu anh")
    ap.add_argument("--max-per-person", type=int, default=40)
    ap.add_argument("--upscale", type=int, default=250, help="Phong to canh (px) truoc khi luu")
    ap.add_argument("--out", default=str(config.DATASETS_DIR / "lfw"))
    args = ap.parse_args()

    from sklearn.datasets import fetch_lfw_people  # import cham -> de trong ham

    print(f"[i] Tai LFW (min_faces_per_person={args.min_faces}, color)... "
          f"lan dau se tai ~200MB va cache lai.")
    data = fetch_lfw_people(min_faces_per_person=args.min_faces, color=True,
                            resize=1.0, funneled=True)
    images = (data.images * 255).astype(np.uint8)   # (N, H, W, 3)
    targets = data.target
    names = data.target_names
    print(f"[i] {len(images)} anh | {len(names)} nguoi")

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    per_person = {}
    saved = 0
    for img, t in zip(images, targets):
        name = names[t].replace(" ", "_")
        per_person.setdefault(name, 0)
        if per_person[name] >= args.max_per_person:
            continue
        pdir = out_root / name
        pdir.mkdir(exist_ok=True)
        im = Image.fromarray(img)
        if args.upscale and im.width < args.upscale:
            r = args.upscale / im.width
            im = im.resize((args.upscale, int(im.height * r)), Image.LANCZOS)
        im.save(pdir / f"{per_person[name]:03d}.jpg", quality=95)
        per_person[name] += 1
        saved += 1

    print(f"[OK] Luu {saved} anh / {len(per_person)} nguoi -> {out_root}")
    print(f"     Buoc tiep: python -m src.preprocess --src {out_root} --dst data/aligned --augment 1")


if __name__ == "__main__":
    main()
