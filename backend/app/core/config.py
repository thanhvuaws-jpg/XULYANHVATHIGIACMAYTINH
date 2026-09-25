"""Cấu hình backend, nạp từ biến môi trường hoặc file `.env`.

Không hardcode bất cứ thứ gì vào mã: khoá bí mật, đường dẫn cơ sở dữ liệu, mô hình
đang dùng đều đọc từ môi trường. Nhờ vậy cùng một image Docker chạy được ở cả máy
phát triển lẫn máy triển khai mà không phải sửa code.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FACEID_", env_file=".env",
                                      env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FaceID Attendance API"
    version: str = "1.0.0"
    debug: bool = False

    # --- cơ sở dữ liệu ---
    #: SQLite khi phát triển; đổi sang postgresql+psycopg://... khi triển khai.
    database_url: str = f"sqlite:///{(ROOT / 'db' / 'faceid.sqlite3').as_posix()}"

    # --- bảo mật ---
    #: BẮT BUỘC đổi khi triển khai thật. Backend từ chối khởi động nếu để nguyên
    #: giá trị mặc định mà `debug=False`.
    secret_key: str = "doi-khoa-nay-truoc-khi-trien-khai"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 12 * 60

    #: Các gốc (origin) được phép gọi API từ trình duyệt, cách nhau bằng dấu phẩy.
    #: Khi triển khai qua nginx thì web và API cùng một gốc nên để trống là đúng —
    #: không có yêu cầu chéo gốc thì không cần nới CORS. Chỉ điền khi giao diện
    #: hoặc máy kiosk nằm ở tên miền khác.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # --- engine nhận diện ---
    embed_backend: str = "facenet"          # facenet | onnx | torch
    embed_weights: str = ""
    detect_backend: str = "yunet"
    #: Ngưỡng cosine tối thiểu để không trả về Unknown.
    #:
    #: 0,68 chọn theo SỐ ĐO, không theo cảm tính. Đo trên 632 ảnh người quen và
    #: 474 ảnh người lạ (ảnh gốc, 122 người đã đăng ký):
    #:
    #:     ngưỡng   người lạ lọt (FAR)   người quen bị từ chối (FRR)
    #:      0,55         25,7 %                    1,9 %
    #:      0,60         12,0 %                    4,3 %
    #:      0,65          4,2 %                    7,4 %
    #:      0,68          2,1 %                   10,9 %
    #:      0,70          1,5 %                   13,8 %
    #:      0,75          0,2 %                   25,8 %
    #:
    #: Ngưỡng cũ 0,55 nhận nhầm **một phần tư số người lạ** — quan sát được ngay
    #: khi chạy thử: mặt một người hoàn toàn khác trên màn hình điện thoại được
    #: chấm 0,756 và gán đúng tên người đã đăng ký.
    #:
    #: Với điểm danh, hai loại lỗi KHÔNG ngang giá: nhận nhầm thì ghi sai sổ và
    #: phá hỏng chính mục đích của hệ thống, còn từ chối oan thì người dùng chỉ
    #: cần đứng lại một lần nữa. Coi nhận nhầm nặng gấp ba lần từ chối oan thì
    #: tổng lỗi nhỏ nhất rơi đúng vào 0,68.
    match_threshold: float = 0.68
    liveness_backend: str = "none"          # none | texture | blink | combo
    index_backend: str = "bruteforce"       # bruteforce | hnsw

    # --- nghiệp vụ điểm danh ---
    #: Cùng một người trong khoảng này chỉ ghi một bản ghi — chống việc đứng
    #: trước camera vài giây tạo ra hàng chục dòng điểm danh.
    checkin_cooldown_minutes: int = 5
    #: Ngưỡng tin cậy tối thiểu để chấp nhận một lần điểm danh tự động.
    #: Phải đi cùng match_threshold ở trên — để lệch nhau thì engine nhận ra
    #: nhưng backend lại từ chối ghi, một kiểu hỏng rất khó lần ra.
    min_confidence: float = 0.68

    # --- lưu trữ tệp ---
    storage_dir: Path = ROOT / "storage"
    models_dir: Path = ROOT / "models"

    @property
    def enrolled_dir(self) -> Path:
        return self.storage_dir / "enrolled"

    @property
    def snapshot_dir(self) -> Path:
        return self.storage_dir / "snapshots"

    def ensure_dirs(self) -> None:
        for d in (self.storage_dir, self.enrolled_dir, self.snapshot_dir):
            d.mkdir(parents=True, exist_ok=True)
        Path(self.database_url.replace("sqlite:///", "")).parent.mkdir(
            parents=True, exist_ok=True) if self.database_url.startswith("sqlite") else None


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
