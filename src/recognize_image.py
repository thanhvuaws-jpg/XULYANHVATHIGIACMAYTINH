"""Nhan dien khuon mat tren 1 anh tinh.

    python -m src.recognize_image --image test.jpg --backbone facenet
    python -m src.recognize_image --image test.jpg --backbone resnet50 \
        --weights models/backbone_arcface.pt --threshold 0.5
"""
import argparse
from pathlib import Path

import cv2

from . import config
from .face_utils import (FaceDetector, draw_results, embed_faces, load_backbone,
                         load_db, match)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--backbone", choices=["resnet50", "facenet"], default="facenet")
    ap.add_argument("--weights", default=str(config.MODELS_DIR / "backbone_arcface.pt"))
    ap.add_argument("--db", default=str(config.DB_PATH))
    ap.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        raise SystemExit(f"Khong doc duoc anh: {args.image}")

    db = load_db(args.db)
    if not db:
        raise SystemExit(f"DB rong: {args.db}. Chay src.build_db truoc.")

    weights = args.weights if args.backbone == "resnet50" else None
    model, kind = load_backbone(args.backbone, weights)
    det = FaceDetector()

    faces = det.detect_and_align(img)
    if not faces:
        print("[i] Khong phat hien khuon mat nao.")
        return

    embs = embed_faces(model, kind, [f["face"] for f in faces])
    items = []
    for f, emb in zip(faces, embs):
        name, sim = match(db, emb, args.threshold)
        items.append({"box": f["box"], "label": name, "score": sim})
        print(f"  - {name:<20s} cosine={sim:.3f}")

    out = draw_results(img, items)
    out_path = args.out or str(Path(args.image).with_name(Path(args.image).stem + "_out.jpg"))
    cv2.imwrite(out_path, out)
    print(f"[OK] Anh ket qua -> {out_path}")


if __name__ == "__main__":
    main()
