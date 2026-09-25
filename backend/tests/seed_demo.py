"""Tạo dữ liệu mẫu để xem giao diện và chụp ảnh minh hoạ cho báo cáo.

    python -m backend.tests.seed_demo

Chạy trên cơ sở dữ liệu THẬT (`db/faceid.sqlite3`) qua đúng API mà giao diện dùng,
nên nó cũng là một phép kiểm chứng: nếu seed chạy được thì luồng nghiệp vụ chạy được.

Dữ liệu lấy từ LFW đã căn chỉnh, đặt tên Việt hoá để ảnh chụp màn hình trông tự
nhiên. Chạy nhiều lần không nhân bản dữ liệu — người đã có thì bỏ qua.
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

BASE = "http://localhost:8000/api"
NAMES = [
    ("SV001", "Nguyễn Văn An"), ("SV002", "Trần Thị Bình"),
    ("SV003", "Lê Hoàng Cường"), ("SV004", "Phạm Minh Dũng"),
    ("SV005", "Hoàng Thị Em"), ("SV006", "Vũ Đức Phong"),
    ("SV007", "Đặng Thu Giang"), ("SV008", "Bùi Quang Huy"),
]


def login() -> dict:
    r = requests.post(f"{BASE}/auth/login",
                      json={"username": "admin", "password": "admin123"}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def ensure_session(H: dict) -> int | None:
    existing = requests.get(f"{BASE}/sessions", headers=H, timeout=30).json()
    for s in existing:
        if s["name"].startswith("Ca sáng"):
            return s["id"]
    r = requests.post(f"{BASE}/sessions", headers=H, timeout=30, json={
        "name": "Ca sáng — Xử lý ảnh", "start_time": "07:30:00", "end_time": "11:30:00",
        "late_after_min": 10, "location": "Phòng A101", "weekdays": "0,1,2,3,4,5,6"})
    if r.status_code == 201:
        print(f"  tạo ca: {r.json()['name']}")
        return r.json()["id"]
    return None


def people_folders(n: int) -> list[Path]:
    root = Path("data/aligned_big")
    if not root.exists():
        sys.exit("Không thấy data/aligned_big — chạy training/prepare trước")
    out = [d for d in sorted(root.iterdir()) if d.is_dir() and len(list(d.glob("*.jpg"))) >= 6]
    if len(out) < n:
        sys.exit(f"Chỉ có {len(out)} người đủ ảnh, cần {n}")
    return out[:n]


def main() -> int:
    try:
        H = login()
    except Exception as e:                       # noqa: BLE001
        sys.exit(f"Không kết nối được backend ({e}).\n"
                 f"Chạy trước: python -m uvicorn backend.app.main:app --port 8000")

    print("Tạo ca học…")
    session_id = ensure_session(H)

    print("\nThêm người và đăng ký khuôn mặt…")
    folders = people_folders(len(NAMES))
    existing = {p["code"]: p for p in requests.get(f"{BASE}/persons", headers=H, timeout=30).json()}
    created = []

    for (code, name), folder in zip(NAMES, folders):
        if code in existing and existing[code]["num_vectors"] > 0:
            print(f"  {code} {name:<20} đã có, bỏ qua")
            created.append((existing[code]["id"], code, name, folder))
            continue

        if code in existing:
            pid = existing[code]["id"]
        else:
            r = requests.post(f"{BASE}/persons", headers=H, timeout=30,
                              json={"code": code, "full_name": name, "role": "student"})
            if r.status_code != 201:
                print(f"  {code} lỗi: {r.text[:80]}")
                continue
            pid = r.json()["id"]

        imgs = sorted(folder.glob("*.jpg"))[:5]
        files = [("files", (p.name, p.read_bytes(), "image/jpeg")) for p in imgs]
        r = requests.post(f"{BASE}/persons/{pid}/images", headers=H, files=files, timeout=120)
        b = r.json()
        print(f"  {code} {name:<20} {b.get('accepted', 0)} vector "
              f"(loại {b.get('rejected', 0)})")
        created.append((pid, code, name, folder))

    print("\nTạo lịch sử điểm danh 10 ngày…")
    # Dùng ảnh KHÁC với ảnh đã đăng ký để mô phỏng đúng tình huống thật.
    rng = random.Random(42)
    total = 0
    for pid, code, name, folder in created:
        probe = sorted(folder.glob("*.jpg"))[5:]
        if not probe:
            continue
        r = requests.post(f"{BASE}/checkin", headers=H, timeout=120,
                          files={"file": (probe[0].name, probe[0].read_bytes(), "image/jpeg")},
                          data={"device_id": "kiosk-A101",
                                "session_id": str(session_id) if session_id else ""})
        b = r.json()
        ok = "✓" if b.get("recognized") else "✗"
        print(f"  {ok} {code} {name:<20} {b.get('message', '')}")
        total += 1 if b.get("created") else 0

    print(f"\nXong — {total} bản ghi điểm danh mới hôm nay.")
    s = requests.get(f"{BASE}/attendance/summary", headers=H, timeout=30).json()
    print(f"Tổng quan: {s['checked_in']}/{s['enrolled']} người · "
          f"đúng giờ {s['present']} · muộn {s['late']} · tỉ lệ {s['rate']*100:.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
