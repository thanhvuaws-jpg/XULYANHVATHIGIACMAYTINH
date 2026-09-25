"""Điểm vào của backend FaceID Attendance.

    uvicorn backend.app.main:app --reload
    → Swagger UI tại http://localhost:8000/docs

Trình tự khởi động
------------------
1. Tạo bảng nếu chưa có.
2. Tạo tài khoản quản trị đầu tiên nếu cơ sở dữ liệu còn trống.
3. Nạp engine và dựng chỉ mục tra cứu từ cơ sở dữ liệu.

Bước 3 cố ý làm lúc khởi động chứ không để lười tới request đầu tiên: nạp mô hình
mất khoảng một giây, và người dùng đầu tiên trong ngày không nên là người phải
chờ. Đổi lại, tiến trình khởi động lâu hơn một chút — chấp nhận được vì nó chỉ
xảy ra một lần.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from .api.routers import (attendance, auth, events, persons, recognize,
                          sessions, system)
from .core.config import get_settings
from .core.security import hash_password
from .db.base import SessionLocal, init_db
from .db.models import User

log = logging.getLogger("faceid")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s")

DEFAULT_ADMIN = ("admin", "admin123")


def bootstrap() -> None:
    """Tạo tài khoản quản trị đầu tiên nếu chưa có tài khoản nào."""
    with SessionLocal() as db:
        if db.execute(select(User)).first():
            return
        u, p = DEFAULT_ADMIN
        db.add(User(username=u, password_hash=hash_password(p),
                    full_name="Quản trị viên", role="admin"))
        db.commit()
        log.warning("Đã tạo tài khoản quản trị đầu tiên: %s / %s "
                    "— ĐỔI MẬT KHẨU NGAY trước khi triển khai thật", u, p)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()
    init_db()
    bootstrap()
    if not cfg.debug and cfg.secret_key.startswith("doi-khoa-nay"):
        log.warning("SECRET_KEY vẫn là giá trị mặc định — đặt biến môi trường "
                    "FACEID_SECRET_KEY trước khi triển khai thật")
    try:
        from .services import engine as engine_svc
        t0 = time.perf_counter()
        engine_svc.get_pipeline()
        with SessionLocal() as db:
            stats = engine_svc.reload_index(db)
        log.info("Engine sẵn sàng sau %.1fs — %s vector / %s người (mô hình %s)",
                 time.perf_counter() - t0, stats["loaded"], stats["people"],
                 stats["model_tag"])
        if stats["other_model_vectors"]:
            log.warning("%s vector thuộc mô hình khác đang bị bỏ qua — chạy "
                        "POST /api/system/reembed-all để chuyển đổi",
                        stats["other_model_vectors"])
    except Exception as e:                       # noqa: BLE001
        log.error("Không nạp được engine: %s — API vẫn chạy nhưng không nhận diện được", e)
    yield


cfg = get_settings()
app = FastAPI(
    title=cfg.app_name, version=cfg.version, lifespan=lifespan,
    description=(
        "API nhận diện khuôn mặt và điểm danh.\n\n"
        "**Đăng nhập trước:** `POST /api/auth/login` với `admin` / `admin123` "
        "(đổi ngay sau lần đầu), rồi bấm **Authorize** ở góc trên bên phải.\n\n"
        "Phân quyền: `viewer` chỉ đọc · `operator` thêm/sửa và điểm danh · "
        "`admin` toàn quyền."),
)

# Danh sách gốc được phép đọc từ cấu hình, không viết cứng vào mã: khi chạy sau
# nginx thì web và API cùng gốc nên danh sách rỗng mới là đúng, còn lúc phát triển
# Vite ở cổng 5173 lại cần được cho phép. Cùng một image, hai môi trường.
if cors := get_settings().cors_origin_list:
    app.add_middleware(
        CORSMiddleware, allow_origins=cors,
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )


@app.middleware("http")
async def add_timing(request: Request, call_next):
    """Gắn thời gian xử lý vào header — tiện cho việc đo và gỡ lỗi."""
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-ms"] = f"{(time.perf_counter() - t0) * 1000:.1f}"
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Lỗi không bắt được ở %s", request.url.path)
    return JSONResponse(status_code=500,
                        content={"detail": "Lỗi nội bộ máy chủ", "path": request.url.path})


for r in (auth.router, persons.router, recognize.router,
          attendance.router, sessions.router, system.router, events.router):
    app.include_router(r)


@app.get("/", tags=["system"], summary="Thông tin nhanh")
def root():
    return {"name": cfg.app_name, "version": cfg.version,
            "docs": "/docs", "health": "/api/system/health"}
