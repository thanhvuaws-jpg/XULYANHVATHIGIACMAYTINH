"""Dependency dùng chung cho các router: phiên CSDL và phân quyền."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.security import decode_token
from ..db.base import get_db
from ..db.models import User

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

#: Thứ bậc quyền. Kiểm tra bằng so sánh số nên thêm vai trò mới không phải sửa
#: rải rác khắp nơi.
ROLE_LEVEL = {"viewer": 1, "operator": 2, "admin": 3}


def current_user(token: str | None = Depends(oauth2),
                 db: Session = Depends(get_db)) -> User:
    err = HTTPException(status.HTTP_401_UNAUTHORIZED, "Chưa đăng nhập hoặc token hết hạn",
                        headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise err
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise err
    user = db.execute(select(User).where(User.username == payload["sub"])).scalar_one_or_none()
    if user is None or not user.active:
        raise err
    return user


def require(min_role: str = "viewer"):
    """Dependency đòi hỏi vai trò tối thiểu.

        @router.post("/", dependencies=[Depends(require("admin"))])
    """
    need = ROLE_LEVEL.get(min_role, 1)

    def _check(user: User = Depends(current_user)) -> User:
        if ROLE_LEVEL.get(user.role, 0) < need:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Cần quyền '{min_role}' trở lên (bạn đang là '{user.role}')")
        return user
    return _check
