"""Kiểm thử hàm tổng hợp số liệu cho bảng điều khiển.

    python -m backend.tests.test_tong_hop

Bộ này ra đời từ một lỗi người dùng nhìn thấy trước khi bộ kiểm thử nào bắt được:
bảng điều khiển hiện **tỉ lệ chuyên cần 133 %**. Nguyên nhân là `summary()` chia
số *bản ghi* điểm danh cho số *người* đăng ký, trong khi một người dự hai ca
trong cùng ngày sinh ra hai bản ghi.

Không bộ kiểm thử cũ nào bắt được vì tất cả đều dựng dữ liệu **một người một ca**
— trong dữ liệu đó số bản ghi luôn bằng số người, nên hai cách tính cho cùng kết
quả. Lỗi chỉ lộ ra khi có người dự nhiều hơn một ca. Đây là bài học lặp lại của
đồ án: dữ liệu kiểm thử quá đều thì phép tính sai vẫn qua được.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, time
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="faceid_tonghop_"))
os.environ["FACEID_DATABASE_URL"] = f"sqlite:///{(_tmp / 't.sqlite3').as_posix()}"
os.environ["FACEID_STORAGE_DIR"] = str(_tmp / "storage")
os.environ["FACEID_SECRET_KEY"] = "khoa-chi-dung-cho-test"

from backend.app.db.base import engine, SessionLocal                # noqa: E402
from backend.app.db.models import Attendance, Base, Person, Session   # noqa: E402
from backend.app.services import attendance as att_svc             # noqa: E402

OK, FAIL = "  [OK]  ", "  [LỖI] "
_passed, _failed = 0, 0
HOM_NAY = date.today().isoformat()


def check(name: str, cond: bool, detail: str = ""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"{OK}{name}" + (f"   {detail}" if detail else ""))
    else:
        _failed += 1
        print(f"{FAIL}{name}   {detail}")


def dung_du_lieu(db, so_nguoi: int, ban_ghi: list[tuple[int, int, str]]):
    """Xoá sạch rồi dựng lại: `ban_ghi` là các bộ (chỉ số người, chỉ số ca, trạng thái)."""
    db.query(Attendance).delete()
    db.query(Person).delete()
    db.query(Session).delete()
    db.commit()
    # Ca phải tồn tại thật: bảng attendance có khoá ngoại tới sessions, nên gán
    # một mã ca bịa ra sẽ bị SQLite chặn chứ không âm thầm ghi vào.
    ca = []
    for i in range(2):
        c = Session(name=f"Ca {i + 1}", start_time=time(7 + i * 2, 0),
                    end_time=time(9 + i * 2, 0), active=True)
        db.add(c)
        ca.append(c)
    nguoi = []
    for i in range(so_nguoi):
        p = Person(code=f"SV{i:03d}", full_name=f"Sinh vien {i}", active=True)
        db.add(p)
        nguoi.append(p)
    db.commit()
    for i, j, tt in ban_ghi:
        db.add(Attendance(person_id=nguoi[i].id, session_id=ca[j].id, day=HOM_NAY,
                          status=tt, confidence=0.9))
    db.commit()
    return nguoi


def main() -> int:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        # --- Lỗi gốc: 3 người đăng ký, 2 người dự 2 ca -> 4 bản ghi ------------
        # Đây đúng là dữ liệu người dùng gặp khi báo cáo tỉ lệ 133 %.
        dung_du_lieu(db, 3, [(0, 0, "present"), (0, 1, "late"),
                             (1, 0, "present"), (1, 1, "late")])
        s = att_svc.summary(db, HOM_NAY)
        check("tỉ lệ chuyên cần không vượt 100 %", s["rate"] <= 1.0,
              f"rate={s['rate']}")
        check("đếm người có mặt, không đếm bản ghi", s["checked_in"] == 2,
              f"checked_in={s['checked_in']} (4 bản ghi của 2 người)")
        check("số bản ghi thô vẫn trả về", s["records"] == 4, f"records={s['records']}")
        check("vắng = đăng ký − có mặt", s["absent"] == 1, f"absent={s['absent']}")
        check("tỉ lệ = 2/3", abs(s["rate"] - 0.6667) < 0.001, f"rate={s['rate']}")

        # --- Bất biến: các con số phải cộng khớp nhau -------------------------
        check("đúng giờ + đi muộn = đã điểm danh",
              s["present"] + s["late"] == s["checked_in"],
              f"{s['present']}+{s['late']} vs {s['checked_in']}")
        check("đã điểm danh + vắng = đã đăng ký",
              s["checked_in"] + s["absent"] == s["enrolled"],
              f"{s['checked_in']}+{s['absent']} vs {s['enrolled']}")

        # --- Đi muộn một ca thì tính đi muộn cả ngày -------------------------
        check("đi muộn dù chỉ một ca thì không được tính đúng giờ",
              s["late"] == 2 and s["present"] == 0,
              f"late={s['late']} present={s['present']}")

        # --- Trường hợp một người một ca: hai cách tính phải trùng nhau -------
        # Chính vì mọi bộ kiểm thử cũ chỉ dựng dữ liệu kiểu này mà lỗi lọt lưới.
        dung_du_lieu(db, 4, [(0, 0, "present"), (1, 0, "late"), (2, 0, "present")])
        s = att_svc.summary(db, HOM_NAY)
        check("một người một ca: có mặt = số bản ghi",
              s["checked_in"] == 3 and s["records"] == 3, str(s))
        check("một người một ca: tỉ lệ = 3/4", abs(s["rate"] - 0.75) < 0.001,
              f"rate={s['rate']}")

        # --- Bản ghi vắng mặt không được tính là có mặt ----------------------
        dung_du_lieu(db, 2, [(0, 0, "present"), (1, 0, "absent")])
        s = att_svc.summary(db, HOM_NAY)
        check("trạng thái 'absent' không vào tập có mặt",
              s["checked_in"] == 1 and s["absent"] == 1, str(s))

        # --- Không có ai đăng ký thì không được chia cho 0 -------------------
        dung_du_lieu(db, 0, [])
        s = att_svc.summary(db, HOM_NAY)
        check("chưa có người nào thì tỉ lệ = 0, không nổ lỗi chia 0",
              s["rate"] == 0.0 and s["enrolled"] == 0, str(s))
    finally:
        db.close()

    print(f"\n  {_passed} đạt · {_failed} hỏng")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
