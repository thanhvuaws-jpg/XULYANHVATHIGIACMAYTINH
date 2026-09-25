"""Kênh phát sự kiện thời gian thực tới các trình duyệt đang mở.

Vì sao cần
----------
Trước đây giao diện web chỉ biết có bản ghi mới khi người dùng tự bấm tải lại
trang. Với một màn hình treo ở phòng giáo vụ để theo dõi lớp đang điểm danh thì
điều đó vô dụng: thông tin đúng đã nằm trong cơ sở dữ liệu nhưng không ai thấy.

Hai cách giải quyết, và vì sao chọn cách này
-------------------------------------------
Cách đơn giản là để trình duyệt gọi lại API mỗi vài giây. Nó chạy được, nhưng tạo
lưu lượng liên tục kể cả khi cả buổi không ai điểm danh, và vẫn trễ vài giây.

Cách ở đây là **máy chủ chủ động đẩy**: trình duyệt mở một kết nối WebSocket và
giữ nguyên; mỗi khi có bản ghi mới, máy chủ gửi thẳng xuống. Không có bản ghi thì
không có gói tin nào. Độ trễ tính bằng mili giây.

Ghi chú về phạm vi
------------------
Danh sách kết nối nằm trong bộ nhớ của **một tiến trình**. Hệ thống chạy đúng một
worker (xem ghi chú trong deploy/backend.Dockerfile) nên như vậy là đủ. Nếu sau
này tách thành nhiều tiến trình thì phải thay bằng một kênh dùng chung như Redis
pub/sub, nếu không trình duyệt nối vào worker A sẽ không nhận được sự kiện sinh ra
ở worker B — và lỗi đó biểu hiện cực kỳ khó hiểu: cập nhật lúc được lúc không.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("faceid.events")


class EventHub:
    """Giữ danh sách kết nối đang mở và phát sự kiện tới tất cả."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        #: Vòng lặp sự kiện của tiến trình, ghi lại lúc có kết nối đầu tiên.
        #: Cần nó để phát sự kiện từ mã ĐỒNG BỘ (các hàm xử lý request thường)
        #: sang thế giới bất đồng bộ của WebSocket.
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._loop = asyncio.get_running_loop()
        async with self._lock:
            self._clients.add(ws)
        log.info("WebSocket nối vào — hiện có %d kết nối", len(self._clients))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
        log.info("WebSocket ngắt — còn %d kết nối", len(self._clients))

    @property
    def count(self) -> int:
        return len(self._clients)

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        if not self._clients:
            return
        # Chép ra danh sách riêng trước khi gửi: gửi lỗi sẽ làm thay đổi tập hợp,
        # mà sửa tập hợp trong lúc đang duyệt nó là lỗi.
        hong: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(payload)
            except Exception:                        # noqa: BLE001
                hong.append(ws)
        for ws in hong:
            await self.disconnect(ws)

    def publish(self, loai: str, **du_lieu: Any) -> None:
        """Phát một sự kiện từ mã đồng bộ.

        Các hàm xử lý request của FastAPI ở đây là hàm thường (đồng bộ) vì chúng
        gọi vào engine và cơ sở dữ liệu theo lối chặn. Muốn gửi được gói tin
        WebSocket từ đó thì phải nhờ vòng lặp sự kiện chạy hộ, bằng
        `run_coroutine_threadsafe`.

        Hàm này **không bao giờ ném lỗi ra ngoài**: phát sự kiện là việc phụ, nó
        hỏng thì cũng không được phép làm hỏng việc ghi điểm danh.
        """
        if not self._clients or self._loop is None:
            return
        goi = {"type": loai, "at": datetime.now().isoformat(timespec="seconds"), **du_lieu}
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(goi), self._loop)
        except Exception:                            # noqa: BLE001
            log.debug("Không phát được sự kiện %s", loai, exc_info=True)


hub = EventHub()
