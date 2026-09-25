"""Kiểm thử toàn bộ luồng nghiệp vụ qua API thật.

    python -m backend.tests.test_flow

Không phải unit test rời rạc mà là một kịch bản đầy đủ, đúng thứ tự một trường
học sẽ làm: đăng nhập → tạo ca → thêm sinh viên → đăng ký khuôn mặt → điểm danh →
xem báo cáo → xuất file. Kiểu test này bắt được lỗi tích hợp mà unit test bỏ qua.

Dùng cơ sở dữ liệu tạm nên chạy bao nhiêu lần cũng không đụng dữ liệu thật.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, time, timedelta
from pathlib import Path

# Trỏ vào CSDL tạm TRƯỚC khi import app, vì cấu hình được cache lúc import.
_tmp = Path(tempfile.mkdtemp(prefix="faceid_test_"))
os.environ["FACEID_DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.sqlite3').as_posix()}"
os.environ["FACEID_STORAGE_DIR"] = str(_tmp / "storage")
os.environ["FACEID_SECRET_KEY"] = "khoa-chi-dung-cho-test"

import cv2                                                          # noqa: E402
from fastapi.testclient import TestClient                           # noqa: E402

from backend.app.main import app                                    # noqa: E402

OK, FAIL = "  [OK]  ", "  [LỖI] "
_passed, _failed = 0, 0


def check(name: str, cond: bool, detail: str = ""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"{OK}{name}" + (f"   {detail}" if detail else ""))
    else:
        _failed += 1
        print(f"{FAIL}{name}   {detail}")


def sample_faces(n: int = 4) -> list[Path]:
    """Vài ảnh khuôn mặt thật từ dữ liệu đã align."""
    root = Path("data/aligned_big")
    people = sorted(p for p in root.iterdir() if p.is_dir())
    for pdir in people:
        imgs = sorted(pdir.glob("*.jpg"))
        if len(imgs) >= n + 1:
            return imgs[: n + 1]
    raise SystemExit("Không có đủ ảnh mẫu trong data/aligned_big")


def main() -> int:
    # PHẢI dùng context manager: TestClient chỉ chạy `lifespan` (tạo bảng, tạo
    # tài khoản admin, nạp engine) khi được vào/ra bằng `with`. Thiếu nó thì
    # bảng chưa tồn tại và test đổ ngay ở bước đăng nhập.
    with TestClient(app) as client:
        return run(client)


def run(client: TestClient) -> int:
    imgs = sample_faces(4)
    enroll_imgs, probe_img = imgs[:4], imgs[4]

    print("\n=== 1. Sức khoẻ và đăng nhập ===")
    r = client.get("/api/system/health")
    check("GET /health", r.status_code == 200 and r.json()["status"] == "ok",
          f"engine_loaded={r.json().get('engine_loaded')}")

    r = client.get("/api/persons")
    check("Chặn truy cập khi chưa đăng nhập", r.status_code == 401)

    r = client.post("/api/auth/login", json={"username": "admin", "password": "sai"})
    check("Từ chối mật khẩu sai", r.status_code == 401)

    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    check("Đăng nhập đúng", r.status_code == 200, f"role={r.json().get('role')}")
    token = r.json()["access_token"]
    H = {"Authorization": f"Bearer {token}"}

    print("\n=== 2. Tạo ca học ===")
    # Ca học phải nằm gọn trong một ngày: `start_time`/`end_time` là GIỜ trong
    # ngày, không phải mốc thời gian, nên một ca "22:54 → 00:54" sẽ bị API từ
    # chối đúng luật vì 00:54 nhỏ hơn 22:54.
    #
    # Trước đây test lấy thẳng `now + 2 giờ`, nên nó chạy tốt cả ngày và **chỉ
    # hỏng khi chạy sau 22 giờ** — đúng kiểu lỗi khiến người ta nghi oan cho mã
    # nguồn. Ở đây kẹp lại để cửa sổ luôn nằm trong ngày, vẫn giữ tính chất mà
    # bài test cần: hiện tại đang nằm TRONG ca.
    now = datetime.now()
    start = (now - timedelta(minutes=3)).time().replace(microsecond=0)
    end = min((now + timedelta(hours=2)).time().replace(microsecond=0),
              time(23, 59, 0))
    if end <= start:                       # sát nửa đêm thì lùi ca về sớm hơn
        start, end = time(8, 0), time(10, 0)
    r = client.post("/api/sessions", headers=H, json={
        "name": "Ca sáng - Xử lý ảnh", "start_time": start.isoformat(),
        "end_time": end.isoformat(), "late_after_min": 10,
        "location": "Phòng A101", "weekdays": "0,1,2,3,4,5,6"})
    check("Tạo ca", r.status_code == 201, r.json().get("name", ""))
    session_id = r.json()["id"]

    r = client.post("/api/sessions", headers=H, json={
        "name": "Ca sai giờ", "start_time": "10:00:00", "end_time": "09:00:00"})
    check("Từ chối ca có giờ kết thúc trước giờ bắt đầu", r.status_code == 400)

    print("\n=== 3. Thêm người và đăng ký khuôn mặt ===")
    r = client.post("/api/persons", headers=H,
                    json={"code": "SV001", "full_name": "Nguyen Van A",
                          "email": "a@sv.edu.vn", "role": "student"})
    check("Tạo người", r.status_code == 201, r.json().get("code", ""))
    pid = r.json()["id"]

    r = client.post("/api/persons", headers=H,
                    json={"code": "SV001", "full_name": "Trùng mã"})
    check("Chặn mã trùng", r.status_code == 409)

    files = [("files", (p.name, p.read_bytes(), "image/jpeg")) for p in enroll_imgs]
    r = client.post(f"/api/persons/{pid}/images", headers=H, files=files)
    body = r.json()
    check("Tải ảnh và đăng ký", r.status_code == 200 and body["accepted"] > 0,
          f"nhận {body.get('accepted')} · loại {body.get('rejected')} · "
          f"mô hình {body.get('model_tag')}")

    r = client.get(f"/api/persons/{pid}", headers=H)
    check("Đếm vector sau đăng ký", r.json()["num_vectors"] > 0,
          f"{r.json()['num_vectors']} vector / {r.json()['num_images']} ảnh")

    print("\n=== 4. Nhận diện ===")
    r = client.post("/api/recognize", headers=H,
                    files={"file": (probe_img.name, probe_img.read_bytes(), "image/jpeg")})
    faces = r.json()["faces"]
    check("Nhận diện ảnh chưa từng dùng để đăng ký",
          r.status_code == 200 and faces and faces[0]["label"] == "SV001",
          f"{faces[0]['label']} score={faces[0]['score']:.3f}" if faces else "không thấy mặt")

    blank = _tmp / "blank.jpg"
    cv2.imwrite(str(blank), (cv2.imread(str(probe_img)) * 0))
    r = client.post("/api/recognize", headers=H,
                    files={"file": ("blank.jpg", blank.read_bytes(), "image/jpeg")})
    check("Ảnh không có mặt trả về rỗng", r.status_code == 200 and r.json()["count"] == 0)

    print("\n=== 5. Điểm danh ===")
    r = client.post("/api/checkin", headers=H,
                    files={"file": (probe_img.name, probe_img.read_bytes(), "image/jpeg")},
                    data={"device_id": "kiosk-01", "session_id": str(session_id)})
    b = r.json()
    check("Điểm danh lần đầu tạo bản ghi mới", b["recognized"] and b["created"],
          f"{b.get('status')} · {b.get('message')}")

    r = client.post("/api/checkin", headers=H,
                    files={"file": (probe_img.name, probe_img.read_bytes(), "image/jpeg")},
                    data={"device_id": "kiosk-01", "session_id": str(session_id)})
    b2 = r.json()
    check("Điểm danh lại trong thời gian nguội KHÔNG tạo bản ghi mới",
          b2["recognized"] and not b2["created"], b2.get("message", ""))

    r = client.get("/api/attendance", headers=H)
    rows = r.json()
    check("Chỉ có đúng 1 bản ghi", len(rows) == 1,
          f"{rows[0]['person_code']} {rows[0]['status']}" if rows else "rỗng")

    print("\n=== 6. Người lạ ===")
    other = sorted(Path("data/aligned_big").iterdir())
    stranger = next(p for p in other if p.is_dir() and p.name != enroll_imgs[0].parent.name)
    simg = sorted(stranger.glob("*.jpg"))[0]
    r = client.post("/api/checkin", headers=H,
                    files={"file": (simg.name, simg.read_bytes(), "image/jpeg")},
                    data={"device_id": "kiosk-01"})
    check("Người lạ KHÔNG được điểm danh", not r.json()["recognized"],
          r.json().get("message", ""))
    r = client.get("/api/attendance/unknowns", headers=H)
    check("Đã ghi sự kiện người lạ", len(r.json()) >= 1, f"{len(r.json())} sự kiện")

    print("\n=== 7. Báo cáo ===")
    r = client.get("/api/attendance/summary", headers=H)
    s = r.json()
    check("Số liệu tổng hợp", r.status_code == 200,
          f"đăng ký {s['enrolled']} · điểm danh {s['checked_in']} · "
          f"muộn {s['late']} · tỉ lệ {s['rate']*100:.0f}%")

    r = client.get("/api/attendance/trend?days=7", headers=H)
    check("Xu hướng 7 ngày", r.status_code == 200 and len(r.json()) == 7)

    r = client.get("/api/attendance/export", headers=H)
    lines = r.text.strip().splitlines()
    check("Xuất CSV", r.status_code == 200 and len(lines) >= 2,
          f"{len(lines)} dòng, có BOM={r.text.startswith(chr(0xFEFF))}")

    print("\n=== 8. Hệ thống và phân quyền ===")
    r = client.get("/api/system/info", headers=H)
    info = r.json()
    check("Thông tin engine", r.status_code == 200,
          f"{info['engine']['detector']}+{info['engine']['embedder']} · "
          f"{info['index']['vectors']} vector")

    r = client.post("/api/system/reindex", headers=H)
    check("Dựng lại chỉ mục", r.status_code == 200,
          f"{r.json()['loaded']} vector / {r.json()['people']} người")

    r = client.post(f"/api/persons/{pid}/reembed", headers=H)
    check("Trích đặc trưng lại từ ảnh gốc", r.status_code == 200,
          f"{r.json()['accepted']} vector")

    r = client.get("/api/system/stats", headers=H)
    check("Thống kê", r.status_code == 200, json.dumps(r.json(), ensure_ascii=False))

    r = client.get("/api/system/audit", headers=H)
    check("Nhật ký thao tác được ghi", len(r.json()) >= 4, f"{len(r.json())} dòng")

    print(f"\n{'='*58}\n  {_passed} đạt · {_failed} lỗi\n{'='*58}")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
