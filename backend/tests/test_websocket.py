"""Kiểm thử kênh WebSocket đẩy sự kiện thời gian thực.

    python -m backend.tests.test_websocket

Chạy qua nginx (cổng WEB_PORT, mặc định 8090) chứ không gọi thẳng backend, vì phần dễ hỏng nhất của
WebSocket nằm đúng ở lớp proxy: thiếu hai header nâng cấp thì nginx trả 200 thay
vì 101, kết nối im lặng không mở được và **không có thông báo lỗi nào** để lần ra
nguyên nhân. Test gọi thẳng backend sẽ xanh trong khi hệ thống thật thì hỏng.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import threading
import time

import requests

BASE = os.environ.get("FACEID_API_URL", "http://localhost:8090").rstrip("/")
WS = BASE.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws"
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


def main() -> int:
    try:
        from websocket import create_connection
    except ImportError:
        print("Thiếu thư viện: python -m pip install websocket-client")
        return 1

    try:
        tok = requests.post(f"{BASE}/api/auth/login", timeout=15,
                            json={"username": "admin", "password": "admin123"}
                            ).json()["access_token"]
    except Exception as e:                           # noqa: BLE001
        print(f"Không đăng nhập được ({e.__class__.__name__}) — máy chủ chưa chạy?")
        print("  cd deploy && docker compose up -d")
        return 1

    print("=== 1. nginx có cho nâng cấp lên WebSocket không ===")
    try:
        ws = create_connection(WS, timeout=15)
        check("Mở được kết nối qua proxy", True, "nhận 101 Switching Protocols")
    except Exception as e:                           # noqa: BLE001
        check("Mở được kết nối qua proxy", False, f"{type(e).__name__}: {e}")
        print("\n  Gợi ý: nginx thiếu 'proxy_set_header Upgrade/Connection'")
        return 1

    print("\n=== 2. Xác thực ===")
    # Token đi trong THÂN gói tin, không nằm trên URL — chuỗi truy vấn bị ghi vào
    # nhật ký máy chủ, nhật ký proxy và lịch sử trình duyệt.
    ws.send(json.dumps({"token": tok}))
    r = json.loads(ws.recv())
    check("Máy chủ báo sẵn sàng", r.get("type") == "ready", f"người dùng {r.get('user')!r}")

    print("\n=== 3. Nhịp giữ kết nối ===")
    ws.send(json.dumps({"type": "ping"}))
    check("Máy chủ đáp pong", json.loads(ws.recv()).get("type") == "pong")

    print("\n=== 4. Token sai phải bị từ chối ===")
    ws2 = create_connection(WS, timeout=15)
    ws2.send(json.dumps({"token": "khong-phai-token-that"}))
    # websocket-client báo "đã bị đóng" bằng cách trả CHUỖI RỖNG, không ném lỗi.
    # Kiểm tra bằng try/except sẽ luôn đỏ dù máy chủ hành xử hoàn toàn đúng —
    # đúng kiểu test sai làm người ta đi sửa nhầm phần mã vốn không hỏng.
    try:
        tra_ve = ws2.recv()
    except Exception:                                # noqa: BLE001
        tra_ve = ""
    check("Đóng kết nối khi token sai", tra_ve == "" and not ws2.connected,
          f"nhận {tra_ve!r}, còn mở = {ws2.connected}")
    try:
        ws2.close()
    except Exception:                                # noqa: BLE001
        pass

    print("\n=== 5. Điểm danh thật có được đẩy xuống không ===")
    anh = sorted(glob.glob("data/enrolled/*/*.jpg"))
    if not anh:
        check("Có ảnh để thử", False, "không thấy data/enrolled/*/*.jpg")
        ws.close()
        return 1

    nhan: list = []

    def doc():
        try:
            ws.settimeout(30)
            nhan.append(json.loads(ws.recv()))
        except Exception as e:                       # noqa: BLE001
            nhan.append({"loi": f"{type(e).__name__}: {e}"})

    th = threading.Thread(target=doc, daemon=True)
    th.start()
    time.sleep(1)

    with open(anh[-1], "rb") as fh:
        res = requests.post(f"{BASE}/api/checkin", timeout=90,
                            headers={"Authorization": f"Bearer {tok}"},
                            files={"file": fh}, data={"device_id": "test-ws"}).json()
    th.join(timeout=31)

    if not res.get("created"):
        # Người này đã điểm danh hôm nay rồi: theo thiết kế thì KHÔNG tạo bản ghi
        # mới, nên cũng không phát sự kiện. Đó là hành vi đúng, không phải lỗi.
        check("Không phát sự kiện khi không tạo bản ghi mới", not nhan,
              f"máy chủ trả: {res.get('message', '')}")
    else:
        e = nhan[0] if nhan else {}
        check("Nhận được sự kiện điểm danh", e.get("type") == "attendance",
              f"{e.get('full_name')} · {e.get('status')}" if "loi" not in e
              else e.get("loi", ""))

    ws.close()
    print(f"\n{'='*54}\n  {_p} đạt · {_f} lỗi\n{'='*54}")
    return 0 if _f == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
