"""Kênh WebSocket đẩy sự kiện thời gian thực xuống trình duyệt."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...core.security import decode_token
from ...services.events import hub

log = logging.getLogger("faceid.ws")
router = APIRouter(prefix="/api", tags=["realtime"])


@router.websocket("/ws")
async def stream(ws: WebSocket) -> None:
    """Luồng sự kiện: điểm danh mới, người lạ, chỉ mục được nạp lại.

    Cách xác thực, và vì sao KHÔNG để token trên URL
    ------------------------------------------------
    Trình duyệt không cho đặt header `Authorization` khi mở WebSocket, nên cách
    phổ biến là nhét token vào chuỗi truy vấn: `/api/ws?token=...`. Ở đây cố ý
    không làm vậy — chuỗi truy vấn bị ghi vào nhật ký máy chủ, nhật ký proxy và
    lịch sử trình duyệt, tức là thẻ đăng nhập bị lưu lại ở ba nơi ngoài tầm kiểm
    soát.

    Thay vào đó: chấp nhận kết nối, rồi **chờ gói tin đầu tiên** chứa token. Sai
    hoặc quá 10 giây không gửi thì đóng. Token đi trong thân gói tin nên không bị
    ghi lại ở đâu cả.
    """
    await hub.connect(ws)
    try:
        try:
            loi_moi = await asyncio.wait_for(ws.receive_json(), timeout=10.0)
        except asyncio.TimeoutError:
            await ws.close(code=4408, reason="Không gửi token trong 10 giây")
            return

        payload = decode_token((loi_moi or {}).get("token", ""))
        if not payload:
            await ws.close(code=4401, reason="Token không hợp lệ")
            return

        await ws.send_json({"type": "ready", "user": payload.get("sub", ""),
                            "clients": hub.count})

        # Giữ kết nối mở. Trình duyệt gửi "ping" theo chu kỳ để giữ đường truyền
        # không bị proxy cắt vì im lặng quá lâu; máy chủ đáp "pong".
        while True:
            tin = await ws.receive_json()
            if (tin or {}).get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:                                # noqa: BLE001
        log.debug("WebSocket kết thúc bất thường", exc_info=True)
    finally:
        await hub.disconnect(ws)
