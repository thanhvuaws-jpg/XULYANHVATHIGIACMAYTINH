"""Xay dung database embedding tu anh da align -> db/embeddings.pkl

Gop CA HAI nguon (nguoi tu Kaggle + nguoi tu dang ky) vi ca hai deu nam trong
data/aligned/<ten_nguoi>/ sau buoc preprocess.

    # Dung CNN tu train:
    python -m src.build_db --backbone resnet50 --weights models/backbone_arcface.pt

    # Hoac dung baseline pretrained (khong can train gi):
    python -m src.build_db --backbone facenet
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

from . import config
from .face_utils import embed_faces, load_backbone, save_db

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aligned-root", default=str(config.ALIGNED_DIR))
    ap.add_argument("--backbone", choices=["resnet50", "facenet"], default="resnet50")
    ap.add_argument("--weights", default=str(config.MODELS_DIR / "backbone_arcface.pt"))
    ap.add_argument("--per-person-limit", type=int, default=0, help="0 = khong gioi han")
    ap.add_argument("--out", default=str(config.DB_PATH))
    args = ap.parse_args()

    weights = args.weights if args.backbone == "resnet50" else None
    if weights and not Path(weights).exists():
        raise SystemExit(f"Khong thay file weights: {weights}. Train truoc bang src.train_cnn "
                         f"hoac dung --backbone facenet.")
    model, kind = load_backbone(args.backbone, weights)

    root = Path(args.aligned_root)
    people = sorted([d for d in root.iterdir() if d.is_dir()])
    if not people:
        raise SystemExit(f"Khong co du lieu trong {root}. Chay src.preprocess truoc.")

    db = {}
    total = 0
    for pdir in tqdm(people, desc="build_db"):
        paths = [p for p in pdir.rglob("*") if p.suffix.lower() in IMG_EXT]
        if args.per_person_limit > 0:
            paths = paths[: args.per_person_limit]
        faces = [cv2.imread(str(p)) for p in paths]
        faces = [f for f in faces if f is not None]
        if not faces:
            continue
        embs = embed_faces(model, kind, faces)
        db[pdir.name] = embs.astype(np.float32)
        total += len(embs)

    save_db(db, args.out)
    print(f"\n[OK] {len(db)} nguoi | {total} vector | -> {args.out}")
    for name, mat in db.items():
        print(f"   - {name:<20s} {mat.shape[0]} vector")


if __name__ == "__main__":
    main()
