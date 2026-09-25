"""Client gọi API backend cho máy kiosk, kèm hàng đợi ngoại tuyến.

Vì sao kiosk vẫn chạy engine ở local
------------------------------------
Nhận diện chạy ngay trên máy kiosk chứ không gửi từng khung hình lên server. Ba lý do:

1. **Phản hồi tức thì.** Người dùng thấy tên mình hiện lên trong vài chục mili
   giây thay vì chờ một vòng mạng.
2. **Không phụ thuộc mạng để hoạt động.** Mất mạng thì vẫn nhận diện được; chỉ
   việc ghi sổ bị hoãn lại.
3. **Không tốn băng thông.** Gửi 30 khung hình mỗi giây lên server là không khả thi
   khi có nhiều kiosk.

Server vẫn là bên **xác nhận cuối cùng**: kiosk gửi ảnh chụp lên `/api/checkin`,
server tự nhận diện lại rồi mới ghi. Kiosk chỉ đề xuất, không tự quyết — một máy
kiosk bị chiếm quyền cũng không tạo được bản ghi giả.

Hàng đợi ngoại tuyến
--------------------
Mất mạng giữa buổi là chuyện thường ở phòng học. Khi gọi API thất bại, ảnh và siêu
dữ liệu được ghi xuống đĩa; một luồng nền thử gửi lại theo chu kỳ. Người đứng
trước camera vẫn thấy "đã ghi nhận" vì bản ghi chắc chắn sẽ tới nơi — chỉ là muộn.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

QUEUE_DIR = Path("storage/kiosk_queue")

#: Địa chỉ máy chủ, đọc từ môi trường để một bản kiosk chạy được ở mọi nơi mà
#: không phải sửa mã. Khi triển khai bằng Docker thì trỏ vào cổng của nginx
#: (mặc định 8090) chứ không phải cổng 8000 của backend — backend cố ý không mở
#: ra ngoài. Cả hai đều dùng được vì mọi đường dẫn API đều bắt đầu bằng /api.
#:     FACEID_API_URL=http://192.168.1.50:8090
DEFAULT_URL = os.environ.get("FACEID_API_URL", "http://localhost:8000")


@dataclass
class CheckinResult:
    ok: bool
    recognized: bool = False
    created: bool = False
    name: str = ""
    code: str = ""
    status: str = ""
    late_minutes: int = 0
    confidence: float = 0.0
    message: str = ""
    queued: bool = False          # không gửi được, đã xếp hàng chờ

    @property
    def headline(self) -> str:
        if self.queued:
            return "Đã ghi nhận (chờ đồng bộ)"
        if not self.recognized:
            return "Chưa nhận ra"
        return "Đã điểm danh" if self.created else "Đã điểm danh trước đó"


class ApiClient:
    """Bọc quanh API backend. Mọi lời gọi đều có timeout và không bao giờ ném lỗi ra ngoài."""

    def __init__(self, base_url: str = DEFAULT_URL, device_id: str = "kiosk-01",
                 timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        self.timeout = timeout
        self.token: str | None = None
        self.username: str = ""
        self.role: str = ""
        self._lock = threading.Lock()
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ nội bộ
    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api{path}"

    # ------------------------------------------------------------------ kết nối
    def health(self) -> dict | None:
        try:
            r = requests.get(self._url("/system/health"), timeout=self.timeout)
            return r.json() if r.ok else None
        except requests.RequestException:
            return None

    def login(self, username: str, password: str) -> tuple[bool, str]:
        try:
            r = requests.post(self._url("/auth/login"), timeout=self.timeout,
                              json={"username": username, "password": password})
        except requests.RequestException as e:
            return False, f"Không kết nối được máy chủ: {e.__class__.__name__}"
        if not r.ok:
            return False, (r.json().get("detail") if r.headers.get("content-type", "")
                           .startswith("application/json") else "Đăng nhập thất bại")
        data = r.json()
        self.token, self.username, self.role = data["access_token"], data["username"], data["role"]
        return True, f"Đã đăng nhập: {self.username} ({self.role})"

    @property
    def connected(self) -> bool:
        return bool(self.token)

    # ------------------------------------------------------------- điểm danh
    def checkin(self, jpeg_bytes: bytes, session_id: int | None = None,
                *, allow_queue: bool = True) -> CheckinResult:
        """Gửi ảnh lên server để nhận diện và ghi điểm danh.

        Gửi thất bại mà `allow_queue` bật thì xếp vào hàng đợi trên đĩa và vẫn báo
        thành công cho người dùng — bản ghi sẽ tới nơi khi có mạng lại.
        """
        if not self.token:
            if allow_queue:
                self._enqueue(jpeg_bytes, session_id)
                return CheckinResult(ok=True, queued=True,
                                     message="Chưa đăng nhập máy chủ — đã xếp hàng chờ")
            return CheckinResult(ok=False, message="Chưa đăng nhập máy chủ")

        files = {"file": (f"kiosk_{int(time.time()*1000)}.jpg", jpeg_bytes, "image/jpeg")}
        data = {"device_id": self.device_id}
        if session_id:
            data["session_id"] = str(session_id)
        try:
            r = requests.post(self._url("/checkin"), headers=self._headers,
                              files=files, data=data, timeout=self.timeout)
        except requests.RequestException:
            if allow_queue:
                self._enqueue(jpeg_bytes, session_id)
                return CheckinResult(ok=True, queued=True,
                                     message="Mất kết nối — đã xếp hàng chờ đồng bộ")
            return CheckinResult(ok=False, message="Mất kết nối máy chủ")

        if r.status_code == 401:
            self.token = None
            return CheckinResult(ok=False, message="Phiên đăng nhập hết hạn")
        if not r.ok:
            return CheckinResult(ok=False, message=f"Máy chủ trả lỗi {r.status_code}")

        b = r.json()
        person = b.get("person") or {}
        return CheckinResult(
            ok=True, recognized=bool(b.get("recognized")), created=bool(b.get("created")),
            name=person.get("full_name", ""), code=person.get("code", ""),
            status=b.get("status") or "", late_minutes=b.get("late_minutes") or 0,
            confidence=float(b.get("confidence") or 0.0), message=b.get("message", ""))

    # -------------------------------------------------------- hàng đợi offline
    def _enqueue(self, jpeg_bytes: bytes, session_id: int | None) -> None:
        with self._lock:
            stamp = f"{int(time.time()*1000)}_{len(list(QUEUE_DIR.glob('*.jpg')))}"
            (QUEUE_DIR / f"{stamp}.jpg").write_bytes(jpeg_bytes)
            (QUEUE_DIR / f"{stamp}.json").write_text(json.dumps({
                "device_id": self.device_id, "session_id": session_id,
                "captured_at": time.time()}), encoding="utf-8")

    def queue_size(self) -> int:
        return len(list(QUEUE_DIR.glob("*.jpg")))

    def flush_queue(self, limit: int = 20) -> dict:
        """Thử gửi lại các bản ghi đang xếp hàng. Trả về thống kê."""
        if not self.token:
            return {"sent": 0, "failed": 0, "remaining": self.queue_size(),
                    "note": "chưa đăng nhập"}
        sent = failed = 0
        for jpg in sorted(QUEUE_DIR.glob("*.jpg"))[:limit]:
            meta_path = jpg.with_suffix(".json")
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            except Exception:                       # noqa: BLE001
                meta = {}
            res = self.checkin(jpg.read_bytes(), meta.get("session_id"), allow_queue=False)
            if res.ok:
                jpg.unlink(missing_ok=True)
                meta_path.unlink(missing_ok=True)
                sent += 1
            else:
                failed += 1
                break            # mạng vẫn hỏng thì dừng, để lần sau thử lại
        return {"sent": sent, "failed": failed, "remaining": self.queue_size()}


class QueueSyncer(threading.Thread):
    """Luồng nền định kỳ đẩy hàng đợi lên server."""

    def __init__(self, client: ApiClient, interval: float = 30.0):
        super().__init__(daemon=True)
        self.client = client
        self.interval = interval
        self._stop = threading.Event()
        self.last_result: dict = {}

    def run(self) -> None:
        while not self._stop.wait(self.interval):
            if self.client.queue_size() and self.client.connected:
                try:
                    self.last_result = self.client.flush_queue()
                except Exception:                   # noqa: BLE001
                    pass

    def stop(self) -> None:
        self._stop.set()


# ============================================================ đồng bộ đăng ký
def day_len_may_chu(client: ApiClient, ten_folder: str, duong_dan_anh: list,
                    ho_ten: str = "") -> dict:
    """Đẩy một folder đăng ký ở máy lên cơ sở dữ liệu của máy chủ.

    Vì sao cần hàm này
    ------------------
    Ứng dụng máy tính và máy chủ giữ hai kho dữ liệu riêng, và đó là chủ ý: kiosk
    phải nhận diện được cả khi mất mạng, nên nó cần chỉ mục của chính nó. Nhưng
    hai kho ấy ban đầu **không có đường nối**, dẫn tới một hệ quả không ai muốn:
    đăng ký ở ứng dụng thì máy chủ không biết người đó, đăng ký trên web thì
    kiosk không nhận ra — phải làm hai lần cho cùng một người.

    Tệ hơn, lỗi biểu hiện rất khó hiểu: kiosk hiện đúng tên (nhờ chỉ mục cục bộ)
    rồi báo "chưa nhận ra" (vì máy chủ mới là bên ghi sổ), hoặc ngược lại kiosk
    im lặng không gửi gì cả.

    Hàm này nối hai kho: đăng ký một lần ở ứng dụng, bấm đẩy lên là máy chủ có
    đúng người đó với đúng những tấm ảnh đó.
    """
    if not client.token:
        return {"ok": False, "message": "Chưa đăng nhập máy chủ"}

    ho_ten = ho_ten or ten_folder
    # Mã người dùng chính tên folder viết hoa — folder là nguồn sự thật ở máy,
    # nên lấy nó làm khoá để đẩy lại nhiều lần không sinh ra người trùng.
    ma = ten_folder.upper()[:32]

    try:
        r = requests.get(f"{client.base_url}/api/persons", headers=client._headers,
                         params={"q": ma}, timeout=client.timeout)
        san_co = [p for p in r.json() if p["code"] == ma] if r.ok else []

        if san_co:
            pid = san_co[0]["id"]
        else:
            r = requests.post(f"{client.base_url}/api/persons", headers=client._headers,
                              json={"code": ma, "full_name": ho_ten}, timeout=client.timeout)
            if not r.ok:
                return {"ok": False, "message": f"Không tạo được người: {r.text[:120]}"}
            pid = r.json()["id"]

        files = []
        for i, p in enumerate(duong_dan_anh):
            try:
                files.append(("files", (f"{ten_folder}_{i}.jpg",
                                        open(p, "rb").read(), "image/jpeg")))
            except OSError:
                continue
        if not files:
            return {"ok": False, "message": "Folder không có ảnh đọc được"}

        r = requests.post(f"{client.base_url}/api/persons/{pid}/images",
                          headers=client._headers, files=files, timeout=180)
        if not r.ok:
            return {"ok": False, "message": f"Máy chủ trả lỗi {r.status_code}"}
        b = r.json()
        return {"ok": True, "person_id": pid, "code": ma,
                "accepted": b.get("accepted", 0), "rejected": b.get("rejected", 0),
                "total_vectors": b.get("total_vectors", 0),
                "message": (f"Đã đẩy lên máy chủ: {b.get('accepted', 0)}/{len(files)} ảnh đạt "
                            f"· tổng {b.get('total_vectors', 0)} vector")}
    except requests.RequestException as e:
        return {"ok": False, "message": f"Mất kết nối máy chủ: {e.__class__.__name__}"}
