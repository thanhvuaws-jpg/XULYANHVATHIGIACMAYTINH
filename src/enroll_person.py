"""Them 1 nguoi moi vao database MA KHONG train lai CNN.

    # Tu webcam:
    python -m src.enroll_person --name huy --camera 0 --count 30 --backbone facenet

    # Tu thu muc anh co san:
    python -m src.enroll_person --name huy --images data/enrolled/huy --backbone resnet50 \
        --weights models/backbone_arcface.pt

Sau lenh nay, lan nhan dien tiep theo da co "huy" - khong can restart, khong train lai.
"""
import argparse
import time
from pathlib import Path

import cv2
import numpy as np

from . import config
from .face_utils import FaceDetector, embed_faces, load_backbone, load_db, save_db

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def collect_from_dir(path: Path, det: FaceDetector):
    faces = []
    for p in sorted(path.rglob("*")):
        if p.suffix.lower() not in IMG_EXT:
            continue
        img = cv2.imread(str(p))
        if img is None:
            continue
        f = det.largest_face(img)
        if f is not None:
            faces.append(f)
    return faces


def collect_from_webcam(camera: int, count: int, det: FaceDetector):
    cap = cv2.VideoCapture(camera, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise SystemExit(f"Khong mo duoc webcam {camera}")
    faces, last = [], 0.0
    print("[i] Nhin thang / trai / phai / len / xuong. Nhan 'q' de dung.")
    while len(faces) < count:
        ok, frame = cap.read()
        if not ok:
            break
        res = det.detect_and_align(frame)
        disp = frame.copy()
        now = time.time()
        if len(res) == 1 and (now - last) >= 0.35:
            faces.append(res[0]["face"])
            last = now
        for r in res:
            x1, y1, x2, y2 = [int(v) for v in r["box"]]
            cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(disp, f"{len(faces)}/{count}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        cv2.imshow("Enroll - 'q' de thoat", disp)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()
    return faces


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--images", default=None, help="Thu muc anh (neu khong dung webcam)")
    ap.add_argument("--camera", type=int, default=None)
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--backbone", choices=["resnet50", "facenet"], default="facenet")
    ap.add_argument("--weights", default=str(config.MODELS_DIR / "backbone_arcface.pt"))
    ap.add_argument("--db", default=str(config.DB_PATH))
    ap.add_argument("--replace", action="store_true", help="Ghi de neu ten da ton tai")
    args = ap.parse_args()

    det = FaceDetector()
    if args.images:
        faces = collect_from_dir(Path(args.images), det)
    elif args.camera is not None:
        faces = collect_from_webcam(args.camera, args.count, det)
    else:
        raise SystemExit("Can --images <thu_muc> hoac --camera <index>")

    if not faces:
        raise SystemExit("Khong tim thay khuon mat nao.")

    weights = args.weights if args.backbone == "resnet50" else None
    model, kind = load_backbone(args.backbone, weights)
    embs = embed_faces(model, kind, faces).astype(np.float32)

    db = load_db(args.db)
    if args.name in db and not args.replace:
        db[args.name] = np.vstack([db[args.name], embs])
    else:
        db[args.name] = embs
    save_db(db, args.db)

    print(f"[OK] '{args.name}': +{len(embs)} vector (tong {db[args.name].shape[0]}). "
          f"DB co {len(db)} nguoi -> {args.db}")


if __name__ == "__main__":
    main()
