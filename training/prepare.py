"""Chuẩn bị dữ liệu: phát hiện → chấm chất lượng → căn chỉnh → ghi ra thư mục.

Thay cho `src/preprocess.py` cũ. Ba khác biệt:

  • dùng **YuNet** thay MTCNN — nhanh hơn 7 lần, nên xử lý được dataset chục nghìn
    ảnh trong vài phút thay vì cả tiếng;
  • có **cổng chất lượng**, loại ảnh mờ/tối/quay ngang ngay từ đầu thay vì để
    chúng làm nhiễu quá trình huấn luyện;
  • căn chỉnh về **112×112** đúng chuẩn ArcFace.

    python -m training.prepare --src data/kaggle/lfw --dst data/aligned
    python -m training.prepare --src data/enrolled  --dst data/aligned --no-quality
"""
from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

import cv2

from engine import quality as quality_mod
from engine.align import align_face
from engine.detect import build_detector
from engine.settings import DetectSettings, QualitySettings

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Thư mục dạng <tên người>/<ảnh>")
    ap.add_argument("--dst", default="data/aligned")
    ap.add_argument("--size", type=int, default=112)
    ap.add_argument("--detector", default="yunet", choices=["yunet", "mtcnn"])
    ap.add_argument("--no-quality", action="store_true", help="Bỏ qua cổng chất lượng")
    ap.add_argument("--min-quality", type=float, default=None,
                    help="Ngưỡng chất lượng tổng hợp, mặc định lấy từ QualitySettings")
    ap.add_argument("--min-sharpness", type=float, default=None,
                    help="Ngưỡng độ nét. Chuẩn bị dữ liệu TRAIN nên nới (~0.015) vì "
                         "augmentation vốn đã thêm mờ; giữ mức gắt cho lúc đăng ký/nhận diện.")
    ap.add_argument("--limit-per-person", type=int, default=0)
    args = ap.parse_args()

    src, dst = Path(args.src), Path(args.dst)
    if not src.exists():
        raise SystemExit(f"Không thấy thư mục nguồn: {src}")
    dst.mkdir(parents=True, exist_ok=True)

    detector = build_detector(DetectSettings(backend=args.detector))
    qsettings = QualitySettings()
    if args.min_quality is not None:
        qsettings.min_score = args.min_quality
    if args.min_sharpness is not None:
        qsettings.min_sharpness = args.min_sharpness

    people = sorted(p for p in src.iterdir() if p.is_dir())
    if not people:
        raise SystemExit(f"Không có thư mục con nào trong {src} (cần <tên người>/<ảnh>.jpg)")

    stats = Counter()
    t0 = time.perf_counter()
    for n, pdir in enumerate(people, 1):
        out_dir = dst / pdir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = [p for p in sorted(pdir.rglob("*")) if p.suffix.lower() in IMG_EXT]
        if args.limit_per_person:
            paths = paths[: args.limit_per_person]

        for path in paths:
            stats["đọc"] += 1
            img = cv2.imread(str(path))
            if img is None:
                stats["ảnh hỏng"] += 1
                continue
            det = detector.detect_largest(img)
            if det is None:
                stats["không thấy mặt"] += 1
                continue
            if not args.no_quality:
                report = quality_mod.assess(img, det, qsettings)
                if not report.passed:
                    stats["loại: " + (report.reasons[0] if report.reasons else "chất lượng")] += 1
                    continue
            chip = align_face(img, det.landmarks, args.size)
            if chip is None:
                stats["căn chỉnh lỗi"] += 1
                continue
            cv2.imwrite(str(out_dir / f"{path.stem}.jpg"), chip,
                        [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            stats["lưu"] += 1

        if not list(out_dir.iterdir()):
            out_dir.rmdir()
        if n % 100 == 0 or n == len(people):
            el = time.perf_counter() - t0
            print(f"  {n}/{len(people)} người · {stats['lưu']} ảnh · "
                  f"{el:.0f}s ({stats['đọc']/max(el,1e-6):.0f} ảnh/s)")

    kept = len([d for d in dst.iterdir() if d.is_dir() and any(d.iterdir())])
    print(f"\nNguồn: {src}  →  {dst}")
    print(f"{'hạng mục':<26}{'số ảnh':>8}")
    print("-" * 34)
    for key, val in stats.most_common():
        print(f"{key:<26}{val:>8}")
    print(f"\n{kept} người có ảnh dùng được · tỉ lệ giữ lại "
          f"{stats['lưu']/max(stats['đọc'],1)*100:.1f}%")
    print(f"Bước tiếp: python -m training.split --data-dir {dst}")


if __name__ == "__main__":
    main()
