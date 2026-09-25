"""Kiểm thử client kiosk và hàng đợi ngoại tuyến.

    python -m backend.tests.test_kiosk

Kịch bản đúng như ngoài đời: mạng hỏng giữa buổi, kiosk vẫn phải nhận diện và ghi
nhận; khi có mạng lại thì mọi bản ghi phải tới nơi, không mất và không trùng.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import requests

from desktop_api import QUEUE_DIR, ApiClient

# Đọc cùng biến môi trường mà kiosk thật đọc, để chạy được cả hai kiểu triển khai:
#   uvicorn chạy trực tiếp lúc phát triển  → http://localhost:8000
#   Docker (backend nấp sau nginx)         → http://localhost:8090
# Cắm cứng một cổng thì test sẽ báo "backend chưa chạy" ngay cả khi hệ thống đang
# chạy ngon lành ở cổng kia.
BASE = os.environ.get("FACEID_API_URL", "http://localhost:8000").rstrip("/")
_p, _f = 0, 0


def check(name, cond, detail=""):
    global _p, _f
    if cond:
        _p += 1
        print(f"  [OK]  {name}" + (f"   {detail}" if detail else ""))
    else:
        _f += 1
        print(f"  [LỖI] {name}   {detail}")


def face_bytes() -> bytes:
    """Ảnh của một người ĐÃ đăng ký, nhưng không phải ảnh dùng để đăng ký."""
    for folder in sorted(Path("data/aligned_big").iterdir()):
        imgs = sorted(folder.glob("*.jpg"))
        if len(imgs) >= 7:
            return imgs[6].read_bytes()
    sys.exit("Không đủ ảnh mẫu")


def main() -> int:
    if QUEUE_DIR.exists():
        shutil.rmtree(QUEUE_DIR)
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    print("=== 1. Máy chủ hỏng — phải xếp hàng, không được mất dữ liệu ===")
    offline = ApiClient(base_url="http://localhost:59999", device_id="kiosk-test")
    check("Không kết nối được thì health trả None", offline.health() is None)

    jpeg = face_bytes()
    r = offline.checkin(jpeg)
    check("Vẫn báo thành công cho người dùng", r.ok and r.queued, r.message)
    check("Đã ghi xuống đĩa", offline.queue_size() == 1, f"{offline.queue_size()} bản ghi")

    for _ in range(3):
        offline.checkin(jpeg)
    check("Xếp hàng nhiều bản ghi", offline.queue_size() == 4,
          f"{offline.queue_size()} bản ghi")

    print("\n=== 2. Máy chủ hoạt động trở lại ===")
    online = ApiClient(base_url=BASE, device_id="kiosk-test")
    h = online.health()
    if h is None:
        print("  [BỎ QUA] Backend chưa chạy — bật bằng:")
        print("           python -m uvicorn backend.app.main:app --port 8000")
        return 1
    check("Health trả về ok", h.get("status") == "ok", f"engine={h.get('engine_loaded')}")

    ok, msg = online.login("admin", "sai-mat-khau")
    check("Từ chối mật khẩu sai", not ok, msg)

    ok, msg = online.login("admin", "admin123")
    check("Đăng nhập đúng", ok, msg)

    print("\n=== 3. Đẩy hàng đợi lên máy chủ ===")
    before = requests.get(f"{BASE}/api/attendance",
                          headers={"Authorization": f"Bearer {online.token}"},
                          timeout=30).json()

    res = online.flush_queue()
    check("Đã gửi hết hàng đợi", res["remaining"] == 0,
          f"gửi {res['sent']} · lỗi {res['failed']} · còn {res['remaining']}")

    after = requests.get(f"{BASE}/api/attendance",
                         headers={"Authorization": f"Bearer {online.token}"},
                         timeout=30).json()
    # 4 bản ghi xếp hàng nhưng CÙNG một người trong cùng một ngày → chống trùng
    # phải bảo đảm chỉ có thêm tối đa 1 dòng.
    added = len(after) - len(before)
    check("Chống ghi trùng vẫn hiệu lực sau khi đồng bộ", added <= 1,
          f"4 bản ghi xếp hàng → thêm {added} dòng trong sổ")

    print("\n=== 4. Gửi trực tiếp khi có mạng ===")
    r = online.checkin(jpeg)
    check("Gửi thẳng, không qua hàng đợi", r.ok and not r.queued,
          f"{r.headline} · {r.message}")
    check("Hàng đợi vẫn rỗng", online.queue_size() == 0)

    print(f"\n{'='*54}\n  {_p} đạt · {_f} lỗi\n{'='*54}")
    return 0 if _f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
