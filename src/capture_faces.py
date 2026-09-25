"""Chup anh khuon mat cua 1 nguoi qua webcam -> data/enrolled/<ten>/*.jpg

    python -m src.capture_faces --name nam --count 40

Meo: vua chup vua quay dau trai/phai, ngang/cui, cuoi, deo/thao kinh,
di chuyen xa/gan de dataset da dang.
Sau khi chup xong -> chay: python -m src.preprocess --src data/enrolled --dst data/aligned
"""
import argparse
import time
from pathlib import Path

import cv2

from . import config
from .face_utils import FaceDetector


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="Ten nguoi (khong dau, khong khoang trang)")
    ap.add_argument("--count", type=int, default=40, help="So anh can chup")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--interval", type=float, default=0.4, help="Giay giua 2 lan luu")
    ap.add_argument("--dst", default=str(config.ENROLLED_DIR))
    args = ap.parse_args()

    out_dir = Path(args.dst) / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = len(list(out_dir.glob("*.jpg")))

    det = FaceDetector()
    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)  # CAP_DSHOW: mo webcam nhanh tren Windows
    if not cap.isOpened():
        print(f"[!] Khong mo duoc webcam index {args.camera}. Thu --camera 1")
        return

    saved = 0
    last = 0.0
    print("[i] Nhan 'q' de dung som. Bat dau chup...")
    while saved < args.count:
        ok, frame = cap.read()
        if not ok:
            break
        boxes, probs = det.detect_boxes(frame)
        disp = frame.copy()
        one_good = boxes is not None and len(boxes) == 1 and probs[0] is not None and probs[0] >= 0.95

        if boxes is not None:
            for b in boxes:
                x1, y1, x2, y2 = [int(v) for v in b]
                cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 0) if one_good else (0, 165, 255), 2)

        now = time.time()
        if one_good and (now - last) >= args.interval:
            fname = out_dir / f"{args.name}_{int(now * 1000)}.jpg"
            cv2.imwrite(str(fname), frame)
            saved += 1
            last = now

        cv2.putText(disp, f"{args.name}: {saved}/{args.count}  (tong file: {existing + saved})",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        if not one_good:
            cv2.putText(disp, "Can dung 1 khuon mat ro net trong khung",
                        (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv2.imshow("Capture faces - nhan 'q' de thoat", disp)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"[OK] Da luu {saved} anh vao {out_dir}")


if __name__ == "__main__":
    main()
