"""Lược đồ request/response (Pydantic).

Tách khỏi model cơ sở dữ liệu có chủ đích: API không nên phơi bày cấu trúc bảng ra
ngoài. Nhờ tách, đổi lược đồ CSDL không làm vỡ hợp đồng API, và ngược lại.
"""
from __future__ import annotations

from datetime import datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ xác thực
class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    expires_in_minutes: int


# --------------------------------------------------------------------- người
class PersonIn(BaseModel):
    code: str = Field(min_length=1, max_length=64, description="Mã sinh viên / nhân viên")
    full_name: str = Field(min_length=1, max_length=160)
    email: str | None = None
    role: str = "student"
    note: str | None = None


class PersonUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    role: str | None = None
    active: bool | None = None
    note: str | None = None


class PersonOut(ORM):
    id: int
    code: str
    full_name: str
    email: str | None
    role: str
    active: bool
    avatar_path: str | None
    created_at: datetime
    num_vectors: int = 0
    num_images: int = 0


class EnrollResult(BaseModel):
    person_id: int
    code: str
    accepted: int
    rejected: int
    rejected_detail: list[dict] = []
    model_tag: str
    total_vectors: int


# ----------------------------------------------------------------- nhận diện
class FaceOut(BaseModel):
    box: list[int]
    label: str
    person_id: int | None = None
    score: float
    liveness: float | None = None
    quality: float | None = None
    quality_ok: bool | None = None
    quality_hint: str | None = None
    is_known: bool


class RecognizeOut(BaseModel):
    faces: list[FaceOut]
    count: int
    timings_ms: dict[str, float] = {}


class CheckinOut(BaseModel):
    recognized: bool
    created: bool = False
    person: PersonOut | None = None
    attendance_id: int | None = None
    status: str | None = None
    late_minutes: int = 0
    confidence: float = 0.0
    liveness: float | None = None
    message: str


# ---------------------------------------------------------------------- ca
class SessionIn(BaseModel):
    name: str
    start_time: time
    end_time: time
    late_after_min: int = 10
    location: str | None = None
    weekdays: str = "0,1,2,3,4"


class SessionOut(ORM):
    id: int
    name: str
    start_time: time
    end_time: time
    late_after_min: int
    location: str | None
    weekdays: str
    active: bool


# ------------------------------------------------------------------ điểm danh
class AttendanceOut(ORM):
    id: int
    person_id: int
    session_id: int | None
    day: str
    check_in: datetime
    check_out: datetime | None
    status: str
    late_minutes: int
    confidence: float
    liveness_score: float | None
    device_id: str | None
    person_code: str | None = None
    person_name: str | None = None
    session_name: str | None = None


class SummaryOut(BaseModel):
    day: str
    enrolled: int
    checked_in: int
    present: int
    late: int
    absent: int
    rate: float
    records: int = 0     # số bản ghi thô; checked_in là số người


class UnknownOut(ORM):
    id: int
    ts: datetime
    snapshot_path: str | None
    best_score: float
    liveness_score: float | None
    device_id: str | None
    resolved: bool


# ------------------------------------------------------------------ hệ thống
class HealthOut(BaseModel):
    status: str
    version: str
    database: str
    engine_loaded: bool


class SystemInfoOut(BaseModel):
    engine: dict[str, Any]
    index: dict[str, Any]
    settings: dict[str, Any]
