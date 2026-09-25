"""Băm mật khẩu và phát hành JWT.

Dùng thẳng thư viện `bcrypt` chứ không qua `passlib`: passlib 1.7.4 đã ngừng bảo
trì và không tương thích với bcrypt từ 4.1 trở lên — nó ném lỗi
"password cannot be longer than 72 bytes" ngay cả với mật khẩu 8 ký tự. Gọi trực
tiếp vừa bớt một lớp trung gian, vừa hết lỗi.

Giới hạn 72 byte là của chính thuật toán bcrypt, không phải của thư viện. Ở đây
cắt tường minh trước khi băm để hành vi rõ ràng thay vì phụ thuộc vào việc phiên
bản nào tự cắt, phiên bản nào ném lỗi.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from .config import get_settings

settings = get_settings()

#: Giới hạn cứng của thuật toán bcrypt.
BCRYPT_MAX_BYTES = 72


def _prepare(raw: str) -> bytes:
    """Mã hoá UTF-8 rồi cắt về 72 byte — cắt theo BYTE, không theo ký tự.

    Cắt theo ký tự sẽ sai với tiếng Việt có dấu, vì một ký tự chiếm 2-3 byte.
    """
    return raw.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(_prepare(raw), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(raw), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, role: str,
                        expires_minutes: int | None = None) -> str:
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": exp}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
