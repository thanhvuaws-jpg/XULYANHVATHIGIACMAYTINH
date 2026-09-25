"""Đo hệ số biến thiên EAR thật trên camera của bạn, để chọn ngưỡng bằng số liệu.

    python do_nguong_song.py

Hai lần trước tôi đặt ngưỡng "mắt đứng im" bằng cách suy luận trên ảnh tĩnh lấy từ
đĩa — nơi nhiễu bằng đúng 0. Ảnh điện thoại đi QUA CAMERA thì có nhiễu cảm biến,
nên con số thật khác hẳn. Script này lấy đúng con số đó.

Cách dùng: chạy, rồi làm theo hướng dẫn trên màn hình. Mỗi pha 10 giây.
"""
from __future__ import annotations
import sys, time
import cv2, numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from engine.detect import build_detector
from engine.settings import DetectSettings
from engine.liveness.blink import (LEFT_EYE, RIGHT_EYE, ensure_model,
                                   eye_aspect_ratio, SO_KHUNG_XET_DUNG_IM)
import mediapipe as mp
from mediapipe.tasks import python as mp_py
from mediapipe.tasks.python import vision


def do_mot_pha(cap, det, lm, ten: str, giay: float = 10.0) -> list[float]:
    print(f"\n=== {ten} ===")
    for i in (3, 2, 1):
        print(f"  bắt đầu sau {i}…"); time.sleep(1)
    print("  ĐANG ĐO — giữ nguyên…")
    ears, t0 = [], time.time()
    while time.time() - t0 < giay:
        ok, frame = cap.read()
        if not ok:
            break
        dets = det.detect(frame)
        if not dets:
            continue
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        r = lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                                int((time.time() - t0) * 1000) + 1)
        if not r.face_landmarks:
            continue
        pts = np.array([[p.x * w, p.y * h] for p in r.face_landmarks[0]], dtype=np.float32)
        ears.append((eye_aspect_ratio(pts, LEFT_EYE) + eye_aspect_ratio(pts, RIGHT_EYE)) / 2)
    return ears


def he_so(ears: list[float]) -> float:
    if len(ears) < 10:
        return float("nan")
    a = np.array(ears[-SO_KHUNG_XET_DUNG_IM:] if len(ears) > SO_KHUNG_XET_DUNG_IM
                 else ears, dtype=np.float32)
    return float(a.std() / a.mean()) if a.mean() > 0 else float("nan")


def main() -> int:
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("Không mở được camera."); return 1
    det = build_detector(DetectSettings(backend="yunet"))
    lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=mp_py.BaseOptions(model_asset_path=str(ensure_model())),
        running_mode=vision.RunningMode.VIDEO, num_faces=1))

    print("Đo hệ số biến thiên EAR — dùng để chọn ngưỡng phát hiện ảnh tĩnh.")
    print("Sẽ đo hai pha, mỗi pha 10 giây.")

    input("\n[1] Ngồi trước camera bằng MẶT THẬT, nhìn thẳng. Enter để bắt đầu…")
    that = do_mot_pha(cap, det, lm, "MẶT THẬT")

    input("\n[2] Giơ ĐIỆN THOẠI hiển thị ảnh chân dung, giữ yên. Enter để bắt đầu…")
    gia = do_mot_pha(cap, det, lm, "ẢNH TRÊN ĐIỆN THOẠI")
    cap.release()

    ht, hg = he_so(that), he_so(gia)
    print(f"\n{'='*54}")
    print(f"  Mặt thật          : {len(that):3d} khung · hệ số biến thiên {ht:.5f}")
    print(f"  Ảnh điện thoại    : {len(gia):3d} khung · hệ số biến thiên {hg:.5f}")
    print(f"{'='*54}")
    if not (np.isnan(ht) or np.isnan(hg)):
        if hg >= ht:
            print("\n  ⚠ Ảnh điện thoại dao động NHIỀU HƠN mặt thật.")
            print("    Dấu hiệu này KHÔNG phân biệt được ở camera của bạn.")
        else:
            goi_y = (ht + hg) / 2
            print(f"\n  Ngưỡng nên đặt: {goi_y:.4f}  (nằm giữa hai giá trị)")
            print(f"  Hiện đang đặt : 0.0200")
    print("\nGửi toàn bộ kết quả này cho tôi để chỉnh ngưỡng bằng số thật.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
