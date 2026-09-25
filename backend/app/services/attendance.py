"""Nghiệp vụ điểm danh.

Ba quy tắc quyết định chất lượng hệ thống
------------------------------------------
1. **Chống ghi trùng.** Một người đứng trước camera 30 giây tạo ra hàng trăm khung
   hình. Nếu mỗi khung ghi một dòng thì bảng dữ liệu vô dụng. Ràng buộc duy nhất
   `(person_id, session_id, day)` ở tầng cơ sở dữ liệu bảo đảm mỗi người mỗi ca
   mỗi ngày đúng một bản ghi — chốt chặn ở tầng thấp nhất, không phụ thuộc vào
   việc tầng trên có nhớ kiểm tra hay không.

2. **Chọn đúng ca.** Một ngày có nhiều ca. Người đến lúc 7:45 thuộc ca sáng chứ
   không phải ca chiều. Chọn ca có giờ bắt đầu gần nhất trong khoảng hợp lệ.

3. **Ngưỡng tin cậy tách biệt với ngưỡng nhận diện.** Nhận diện có thể trả về một
   cái tên với độ tin cậy 0,56; nhưng để **ghi vào sổ điểm danh** thì nên đòi hỏi
   cao hơn. Nhận nhầm khi hiển thị chỉ gây khó chịu; nhận nhầm khi ghi sổ tạo ra
   dữ liệu sai mà không ai phát hiện.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..core.config import get_settings
from ..db.models import Attendance, AuditLog, Person, Session, UnknownEvent


def pick_session(db: DbSession, when: datetime | None = None) -> Session | None:
    """Tìm ca phù hợp nhất với thời điểm hiện tại.

    Cho phép điểm danh sớm 30 phút trước giờ bắt đầu và muộn tới hết giờ ca.
    Nhiều ca cùng khớp thì lấy ca có giờ bắt đầu gần nhất.
    """
    when = when or datetime.now()
    weekday = str(when.weekday())
    rows = db.execute(select(Session).where(Session.active.is_(True))).scalars().all()

    best, best_gap = None, timedelta.max
    for s in rows:
        if weekday not in [w.strip() for w in s.weekdays.split(",") if w.strip()]:
            continue
        start = datetime.combine(when.date(), s.start_time)
        end = datetime.combine(when.date(), s.end_time)
        if start - timedelta(minutes=30) <= when <= end:
            gap = abs(when - start)
            if gap < best_gap:
                best, best_gap = s, gap
    return best


#: Cho phép điểm danh sớm trước giờ ca bắt đầu.
EARLY_GRACE_MIN = 30


def in_window(sess: Session, when: datetime) -> bool:
    """Thời điểm có nằm trong khung giờ hợp lệ của ca không."""
    start = datetime.combine(when.date(), sess.start_time)
    end = datetime.combine(when.date(), sess.end_time)
    return start - timedelta(minutes=EARLY_GRACE_MIN) <= when <= end


def _status_for(sess: Session | None, when: datetime) -> tuple[str, int]:
    """Xác định trạng thái và số phút đi muộn.

    Điểm danh **sau khi ca đã kết thúc** không phải là đi muộn — ca đó đã xong.
    Nếu không chặn, một lần quét lúc 20:00 với ca sáng 07:30 sẽ bị ghi là
    "muộn 750 phút", một con số vô nghĩa làm hỏng mọi thống kê chuyên cần.
    """
    if sess is None or not in_window(sess, when):
        return "present", 0
    start = datetime.combine(when.date(), sess.start_time)
    late_by = int((when - start).total_seconds() // 60)
    if late_by > sess.late_after_min:
        return "late", late_by
    return "present", max(0, late_by)


def check_in(db: DbSession, person: Person, *, confidence: float,
             liveness: float | None = None, snapshot: str | None = None,
             device_id: str | None = None, when: datetime | None = None,
             session: Session | None = None) -> tuple[Attendance, bool]:
    """Ghi nhận điểm danh. Trả về (bản ghi, có phải bản ghi mới không).

    Gọi lại trong thời gian nguội chỉ trả về bản ghi cũ, không tạo bản ghi mới.
    """
    cfg = get_settings()
    when = when or datetime.now()
    # Ca truyền vào tường minh vẫn phải nằm đúng khung giờ. Không kiểm tra thì
    # một lần quét ngoài giờ sẽ bị gán vào ca đó và tính muộn hàng trăm phút.
    if session is not None and not in_window(session, when):
        session = None
    sess = session or pick_session(db, when)
    day = when.date().isoformat()

    existing = db.execute(
        select(Attendance).where(
            Attendance.person_id == person.id,
            Attendance.day == day,
            Attendance.session_id == (sess.id if sess else None))
    ).scalar_one_or_none()

    if existing:
        # Trong thời gian nguội: coi như cùng một lần đến, không ghi thêm.
        if when - existing.check_in < timedelta(minutes=cfg.checkin_cooldown_minutes):
            return existing, False
        # Ngoài thời gian nguội: coi là lần ra về / quét lại → cập nhật check_out.
        existing.check_out = when
        db.commit()
        return existing, False

    status, late = _status_for(sess, when)
    rec = Attendance(person_id=person.id, session_id=sess.id if sess else None,
                     day=day, check_in=when, status=status, late_minutes=late,
                     confidence=float(confidence), liveness_score=liveness,
                     snapshot_path=snapshot, device_id=device_id)
    db.add(rec)
    db.add(AuditLog(actor=device_id or "kiosk", action="attendance.checkin",
                    entity="person", entity_id=str(person.id),
                    meta={"confidence": round(float(confidence), 4),
                          "status": status, "late_minutes": late,
                          "session": sess.name if sess else None}))
    db.commit()
    db.refresh(rec)
    return rec, True


def log_unknown(db: DbSession, *, best_score: float, best_person_id: int | None = None,
                liveness: float | None = None, snapshot: str | None = None,
                device_id: str | None = None) -> UnknownEvent:
    """Ghi lại một lần người lạ xuất hiện, kèm ảnh để quản trị viên xem lại."""
    ev = UnknownEvent(best_score=float(best_score), best_match_person_id=best_person_id,
                      liveness_score=liveness, snapshot_path=snapshot, device_id=device_id)
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def summary(db: DbSession, day: str | None = None) -> dict:
    """Số liệu tổng hợp cho bảng điều khiển. Mọi con số đếm NGƯỜI, không đếm bản ghi.

    Bản đầu chia thẳng số bản ghi cho số người. Một người dự hai ca trong cùng
    ngày sinh ra hai bản ghi, nên với 3 người đăng ký và 4 bản ghi thì tỉ lệ
    chuyên cần hiện **133 %**. Năm thẻ trên bảng điều khiển đều nói về người —
    "Đã đăng ký", "Đã điểm danh", "vắng" — nên bản ghi là sai đơn vị.

    Dấu hiệu của lỗi đã nằm sẵn trong `max(0, ...)` ở dòng tính số vắng: nó chặn
    kết quả âm thay vì hỏi vì sao một hiệu số người lại có thể âm. Giữ lại
    `max(0, ...)` ở bản này thì thừa, nhưng bỏ đi sẽ mất lưới an toàn nếu sau này
    có người bị gỡ khỏi danh sách hoạt động mà bản ghi trong ngày vẫn còn.

    `trend()` gọi chính hàm này cho từng ngày, nên biểu đồ 14 ngày được sửa theo.
    """
    day = day or date.today().isoformat()
    rows = db.execute(select(Attendance).where(Attendance.day == day)).scalars().all()
    total_people = db.execute(
        select(Person).where(Person.active.is_(True))).scalars().all()

    # Gộp bản ghi theo người. Bản ghi trạng thái "absent" là ghi nhận vắng mặt,
    # không phải một lần có mặt, nên không được vào tập có mặt.
    co_mat = {r.person_id for r in rows if r.status in ("present", "late")}
    # Đi muộn dù chỉ một ca thì tính là đi muộn cả ngày. Báo cáo chuyên cần nên
    # làm lộ việc đi muộn, không nên để một ca đúng giờ khác che đi.
    di_muon = {r.person_id for r in rows if r.status == "late"}
    return {
        "day": day,
        "enrolled": len(total_people),
        "checked_in": len(co_mat),
        "present": len(co_mat - di_muon),
        "late": len(di_muon),
        "absent": max(0, len(total_people) - len(co_mat)),
        "rate": round(len(co_mat) / len(total_people), 4) if total_people else 0.0,
        # Số bản ghi thô vẫn trả về: nó là thông tin thật, chỉ là không dùng để
        # tính tỉ lệ. Một người dự ba ca thì đây là 3 còn checked_in là 1.
        "records": len(rows),
    }
