"""Lược đồ cơ sở dữ liệu.

Nguyên tắc thiết kế
-------------------
**Vector là dữ liệu, chỉ mục là bản dựng lại được.** Bảng `face_embeddings` là
nguồn sự thật duy nhất; chỉ mục tra cứu (hnswlib) dựng lại từ nó lúc khởi động.
Mất file chỉ mục không mất gì; đổi mô hình chỉ cần trích đặc trưng lại từ ảnh gốc
trong `enrollment_images`.

**Mọi bản ghi điểm danh đều truy vết được.** Lưu kèm `confidence`, `liveness_score`
và ảnh chụp lúc đó — khi có khiếu nại "em có đi mà hệ thống không ghi nhận" thì
tra ra được ngay chuyện gì đã xảy ra. Đây là yêu cầu bắt buộc của một hệ thống
chấm công, không phải tính năng thêm.
"""
from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer,
                        LargeBinary, String, Text, Time, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now()


class Person(Base):
    """Một người được hệ thống nhận diện — sinh viên, nhân viên."""
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # mã SV/NV
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="student")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    avatar_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    embeddings: Mapped[list["FaceEmbedding"]] = relationship(
        back_populates="person", cascade="all, delete-orphan")
    images: Mapped[list["EnrollmentImage"]] = relationship(
        back_populates="person", cascade="all, delete-orphan")
    attendance: Mapped[list["Attendance"]] = relationship(
        back_populates="person", cascade="all, delete-orphan")


class FaceEmbedding(Base):
    """Một vector đặc trưng khuôn mặt.

    `model_tag` ghi lại mô hình đã sinh ra vector này. Vector của hai mô hình khác
    nhau KHÔNG so sánh được với nhau, nên khi đổi mô hình phải lọc theo trường này
    rồi trích đặc trưng lại — không có nó thì hệ thống sẽ nhận diện sai một cách
    rất khó truy nguyên.
    """
    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"),
                                           index=True)
    vector: Mapped[bytes] = mapped_column(LargeBinary)      # float32 đóng gói
    dim: Mapped[int] = mapped_column(Integer)
    model_tag: Mapped[str] = mapped_column(String(80), index=True)
    quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_image_id: Mapped[int | None] = mapped_column(
        ForeignKey("enrollment_images.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    person: Mapped[Person] = relationship(back_populates="embeddings")


class EnrollmentImage(Base):
    """Ảnh gốc dùng để đăng ký. Giữ lại để trích đặc trưng lại khi đổi mô hình."""
    __tablename__ = "enrollment_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"),
                                           index=True)
    path: Mapped[str] = mapped_column(String(300))
    quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=True)
    reject_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    person: Mapped[Person] = relationship(back_populates="images")


class Session(Base):
    """Một ca làm việc hoặc buổi học — khung thời gian để tính đúng giờ / đi muộn."""
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    late_after_min: Mapped[int] = mapped_column(Integer, default=10)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    #: Các thứ trong tuần áp dụng, "0,1,2" = thứ Hai, Ba, Tư (0 = thứ Hai).
    weekdays: Mapped[str] = mapped_column(String(20), default="0,1,2,3,4")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    attendance: Mapped[list["Attendance"]] = relationship(back_populates="session")


class Attendance(Base):
    """Một bản ghi điểm danh."""
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("person_id", "session_id", "day",
                                       name="uq_attendance_per_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"),
                                           index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    #: Ngày dạng YYYY-MM-DD, tách riêng để ràng buộc "mỗi người một bản ghi/ngày".
    day: Mapped[str] = mapped_column(String(10), index=True)
    check_in: Mapped[datetime] = mapped_column(DateTime, default=_now)
    check_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="present")  # present|late|absent
    late_minutes: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    snapshot_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    person: Mapped[Person] = relationship(back_populates="attendance")
    session: Mapped[Session | None] = relationship(back_populates="attendance")


class UnknownEvent(Base):
    """Người lạ xuất hiện trước camera — lưu ảnh để quản trị viên xem lại."""
    __tablename__ = "unknown_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    snapshot_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    best_match_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    best_score: Mapped[float] = mapped_column(Float, default=0.0)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class User(Base):
    """Tài khoản đăng nhập hệ thống quản trị (khác với `Person` được nhận diện)."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="operator")  # admin|operator|viewer
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Device(Base):
    """Một máy kiosk đặt tại cửa lớp."""
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLog(Base):
    """Nhật ký thao tác — ai làm gì, lúc nào. Bắt buộc với hệ thống chấm công."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
