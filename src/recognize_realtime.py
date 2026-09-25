"""Nhan dien khuon mat realtime qua webcam.

    python -m src.recognize_realtime --backbone facenet
    python -m src.recognize_realtime --backbone resnet50 --weights models/backbone_arcface.pt \
        --threshold 0.5 --every 2

--every N: chi trich embedding moi N frame (tang FPS khi chay CPU), giua cac frame
           chi ve lai ket qua cu.
Nhan 'q' de thoat.
"""
import argparse
import time

import cv2

from . import config
from .face_utils import (FaceDetector, draw_results, embed_faces, load_backbone,
                         load_db, match)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--backbone", choices=["resnet50", "facenet"], default="facenet")
    ap.add_argument("--weights", default=str(config.MODELS_DIR / "backbone_arcface.pt"))
    ap.add_argument("--db", default=str(config.DB_PATH))
    ap.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD)
    ap.add_argument("--every", type=int, default=2)
    args = ap.parse_args()

    db = load_db(args.db)
    if not db:
        raise SystemExit(f"DB rong: {args.db}. Chay src.build_db truoc.")

    weights = args.weights if args.backbone == "resnet50" else None
    model, kind = load_backbone(args.backbone, weights)
    det = FaceDetector()

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise SystemExit(f"Khong mo duoc webcam {args.camera}")

    items = []
    frame_id = 0
    fps, t_prev = 0.0, time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_id += 1

        if frame_id % args.every == 0:
            faces = det.detect_and_align(frame)
            if faces:
                embs = embed_faces(model, kind, [f["face"] for f in faces])
                items = []
                for f, emb in zip(faces, embs):
                    name, sim = match(db, emb, args.threshold)
                    items.append({"box": f["box"], "label": name, "score": sim})
            else:
                items = []

        disp = draw_results(frame, items)
        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - t_prev, 1e-6))
        t_prev = now
        cv2.putText(disp, f"FPS: {fps:4.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        cv2.imshow("Nhan dien khuon mat - 'q' de thoat", disp)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
