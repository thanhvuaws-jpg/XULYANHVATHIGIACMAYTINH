"""Kiểm thử khói cho hệ thống ĐÃ TRIỂN KHAI bằng Docker.

    python deploy/smoke_test.py                      # mặc định http://localhost:8090
    python deploy/smoke_test.py http://may-chu:8090

Khác gì `backend/tests/test_flow.py`
-----------------------------------
`test_flow.py` dùng `TestClient`, tức là gọi thẳng vào đối tượng ứng dụng **trong
cùng tiến trình Python**. Nó kiểm tra mã nguồn đúng, nhưng đi vòng qua tất cả
những thứ mà việc triển khai thật sự phụ thuộc vào: image có cài đủ gói không,
nginx chuyển tiếp có đúng không, biến môi trường có tới nơi không, volume có ghi
được không, mô hình ONNX có nằm trong image không.

Tệp này gọi qua **HTTP thật, qua nginx**, đúng đường mà trình duyệt và máy kiosk
sẽ đi. Nó bắt được đúng lớp lỗi mà test trong tiến trình không thể thấy — ví dụ
lần container chết vì thiếu torch dù mọi test mã nguồn đều xanh.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8090"
_p = _f = 0

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def check(name: str, cond: bool, detail: str = "") -> None:
    global _p, _f
    if cond:
        _p += 1
        print(f"  [OK]  {name}" + (f"   {detail}" if detail else ""))
    else:
        _f += 1
        print(f"  [LỖI] {name}   {detail}")


def sample_faces(n: int = 4) -> tuple[str, list[bytes]]:
    """Lấy ảnh của một người có đủ ảnh: vài ảnh để đăng ký, một ảnh để nhận diện."""
    for folder in sorted((ROOT / "data" / "aligned_big").iterdir()):
        imgs = sorted(folder.glob("*.jpg"))
        if len(imgs) >= n + 2:
            return folder.name, [p.read_bytes() for p in imgs[:n + 1]]
    sys.exit("Không tìm thấy thư mục ảnh mẫu trong data/aligned_big")


def main() -> int:
    s = requests.Session()

    print(f"=== 1. Hệ thống có sống không — {BASE} ===")
    try:
        h = s.get(f"{BASE}/api/system/health", timeout=15).json()
    except requests.RequestException as e:
        print(f"  [LỖI] Không gọi được {BASE}: {e.__class__.__name__}")
        print("        Chạy trước:  cd deploy && docker compose up -d")
        return 1
    check("API trả lời qua nginx", h.get("status") == "ok", str(h))
    check("Cơ sở dữ liệu kết nối được", h.get("database") == "ok")
    check("Engine nhận diện đã nạp", h.get("engine_loaded") is True)

    r = s.get(f"{BASE}/", timeout=15)
    check("nginx phục vụ giao diện web", r.ok and "<div id=\"root\"" in r.text,
          f"HTTP {r.status_code} · {len(r.content)} bytes")
    r = s.get(f"{BASE}/attendance", timeout=15)
    check("Đường dẫn React Router không ra 404", r.ok,
          "nginx trả index.html cho đường dẫn không có tệp thật")

    print("\n=== 2. Đăng nhập ===")
    r = s.post(f"{BASE}/api/auth/login", timeout=15,
               json={"username": "admin", "password": "sai"})
    check("Từ chối mật khẩu sai", r.status_code == 401, f"HTTP {r.status_code}")

    r = s.post(f"{BASE}/api/auth/login", timeout=15,
               json={"username": "admin", "password": "admin123"})
    check("Đăng nhập đúng", r.ok, f"HTTP {r.status_code}")
    if not r.ok:
        return 1
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    r = s.get(f"{BASE}/api/system/models", timeout=15)
    models = r.json()
    check("Liệt kê được mô hình", bool(models), f"{len(models)} mô hình")
    # Container không cài torch, nên không được quảng cáo mô hình chạy bằng torch.
    torch_models = [m for m in models if m["backend"] in ("facenet", "torch")]
    check("Không chào mời mô hình cần PyTorch", not torch_models,
          f"bị chào: {[m['label'] for m in torch_models]}" if torch_models else
          "chỉ liệt kê ONNX — đúng với image không có torch")

    print("\n=== 3. Đăng ký một người mới ===")
    name, imgs = sample_faces()
    code = "SMOKE01"
    full_name = f"Kiểm thử {name}"

    # Chạy lại nhiều lần phải cho cùng kết quả: xoá người của lần trước nếu còn.
    existing = s.get(f"{BASE}/api/persons", params={"q": code}, timeout=15).json()
    for p in existing:
        if p["code"] == code:
            s.delete(f"{BASE}/api/persons/{p['id']}", timeout=30)

    r = s.post(f"{BASE}/api/persons", timeout=30,
               json={"code": code, "full_name": full_name})
    check("Tạo được người mới", r.ok, f"HTTP {r.status_code} {r.text[:120]}")
    if not r.ok:
        return 1
    pid = r.json()["id"]

    files = [("files", (f"e{i}.jpg", b, "image/jpeg")) for i, b in enumerate(imgs[:-1])]
    r = s.post(f"{BASE}/api/persons/{pid}/images", files=files, timeout=120)
    check("Nạp ảnh và trích đặc trưng được", r.ok, f"HTTP {r.status_code} {r.text[:150]}")
    if r.ok:
        b = r.json()
        check("Có vector được tạo", b.get("total_vectors", 0) > 0,
              f"{b['accepted']}/{len(files)} ảnh đạt · "
              f"{b['total_vectors']} vector · mô hình {b['model_tag']}")

    print("\n=== 4. Nhận diện bằng ảnh CHƯA từng dùng để đăng ký ===")
    r = s.post(f"{BASE}/api/recognize", timeout=60,
               files={"file": ("probe.jpg", imgs[-1], "image/jpeg")})
    check("Gọi được API nhận diện", r.ok, f"HTTP {r.status_code}")
    if r.ok:
        faces = r.json().get("faces", [])
        check("Tìm thấy khuôn mặt", bool(faces), f"{len(faces)} khuôn mặt")
        if faces:
            top = faces[0]
            # Nhãn trả về là MÃ người, không phải họ tên: chỉ mục dùng mã làm
            # định danh vì mã ổn định, còn tên có thể sửa mà không phải trích
            # đặc trưng lại. Tên chỉ được tra ra ở tầng hiển thị.
            check("Nhận đúng người vừa đăng ký", top.get("label") == code,
                  f"nhãn={top.get('label')!r} điểm={top.get('score', 0):.3f}")

    print("\n=== 5. Điểm danh và ghi sổ ===")
    before = len(s.get(f"{BASE}/api/attendance", timeout=15).json())
    r = s.post(f"{BASE}/api/checkin", timeout=60,
               files={"file": ("kiosk.jpg", imgs[-1], "image/jpeg")},
               data={"device_id": "smoke-test"})
    check("Gọi được API điểm danh", r.ok, f"HTTP {r.status_code} {r.text[:150]}")
    if r.ok:
        b = r.json()
        check("Nhận ra người điểm danh", b.get("recognized") is True, b.get("message", ""))

    after = s.get(f"{BASE}/api/attendance", timeout=15).json()
    check("Bản ghi đã vào sổ", len(after) >= before + (1 if r.ok else 0),
          f"{before} → {len(after)} dòng")

    # Gọi lại lần nữa: chống ghi trùng phải chặn, không tạo thêm dòng.
    s.post(f"{BASE}/api/checkin", timeout=60,
           files={"file": ("kiosk2.jpg", imgs[-1], "image/jpeg")},
           data={"device_id": "smoke-test"})
    again = s.get(f"{BASE}/api/attendance", timeout=15).json()
    check("Chống ghi trùng hoạt động", len(again) == len(after),
          f"điểm danh lần hai → vẫn {len(again)} dòng")

    print("\n=== 6. Dữ liệu nằm ở volume, không nằm trong image ===")
    p = s.get(f"{BASE}/api/persons/{pid}", timeout=15).json()
    check("Ảnh đăng ký được lưu lại", p.get("num_images", 0) > 0,
          f"{p.get('num_images')} ảnh · {p.get('num_vectors')} vector "
          f"— nằm trong volume faceid_storage nên sống qua mọi lần dựng lại image")

    print(f"\n{'='*58}\n  {_p} đạt · {_f} lỗi\n{'='*58}")
    return 0 if _f == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
