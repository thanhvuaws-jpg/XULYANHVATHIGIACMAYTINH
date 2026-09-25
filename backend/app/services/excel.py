"""Xuất sổ điểm danh ra tệp Excel có định dạng.

Vì sao không dùng CSV
---------------------
CSV chỉ chứa chữ thô, không mang theo bất kỳ định dạng nào. Mở bằng Excel thì cột
ngày hiện thành `######` vì cột quá hẹp, mọi tiêu đề bị cắt cụt, trạng thái hiện
là `late` thay vì "Đi muộn", và người xem phải tự chỉnh lại độ rộng từng cột trước
khi đọc được. Tệp xuất ra lẽ ra phải dùng được ngay, không phải một việc dở dang
giao lại cho người dùng.

Tệp .xlsx mang được độ rộng cột, kiểu chữ, màu nền, định dạng số, dòng tiêu đề
đóng băng và bộ lọc — nên nó mở ra là đọc được luôn.
"""
from __future__ import annotations

import io
from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# Bảng màu giữ đồng bộ với giao diện web.
XANH_DAM = "0E7C66"
XANH_NHAT = "E8F5F1"
VANG_NHAT = "FFF4E0"
DO_NHAT = "FDECEC"
XAM_VIEN = "D9DEE5"

TIEU_DE = [
    ("Ngày", 12), ("Mã", 12), ("Họ và tên", 26), ("Ca học", 24),
    ("Giờ vào", 10), ("Giờ ra", 10), ("Trạng thái", 13), ("Phút muộn", 11),
    ("Độ tin cậy", 11), ("Điểm sống", 11), ("Thiết bị", 16),
]

TEN_TRANG_THAI = {"present": "Đúng giờ", "late": "Đi muộn", "absent": "Vắng"}


def _vien(mau: str = XAM_VIEN) -> Border:
    net = Side(style="thin", color=mau)
    return Border(left=net, right=net, top=net, bottom=net)


def xuat_diem_danh(rows, day_from: str | None, day_to: str | None) -> bytes:
    """Dựng workbook từ danh sách (Attendance, Person, Session) và trả về bytes."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Điểm danh"

    # ------------------------------------------------------------- dòng tiêu đề
    khoang = (f"{day_from or '…'} đến {day_to or '…'}"
              if (day_from or day_to) else "toàn bộ")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(TIEU_DE))
    o = ws.cell(row=1, column=1, value=f"SỔ ĐIỂM DANH — {khoang}")
    o.font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    o.fill = PatternFill("solid", fgColor=XANH_DAM)
    o.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(TIEU_DE))
    o = ws.cell(row=2, column=1,
                value=f"Xuất lúc {datetime.now():%H:%M %d/%m/%Y} · {len(rows)} bản ghi")
    o.font = Font(size=9, italic=True, color="6B7683")
    o.alignment = Alignment(horizontal="center")

    # -------------------------------------------------------------- tên cột
    HANG_TIEU_DE = 4
    for i, (ten, rong) in enumerate(TIEU_DE, start=1):
        c = ws.cell(row=HANG_TIEU_DE, column=i, value=ten)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=XANH_DAM)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = _vien(XANH_DAM)
        # Đặt độ rộng ngay từ đầu — đây chính là thứ CSV không làm được, và là lý
        # do cột ngày trong tệp CSV hiện ra thành ######.
        ws.column_dimensions[get_column_letter(i)].width = rong
    ws.row_dimensions[HANG_TIEU_DE].height = 22

    # ------------------------------------------------------------------ dữ liệu
    for r, (a, p, s) in enumerate(rows, start=HANG_TIEU_DE + 1):
        muon = a.status == "late"
        nen = PatternFill("solid", fgColor=VANG_NHAT if muon else XANH_NHAT)

        gia_tri = [
            date.fromisoformat(a.day) if isinstance(a.day, str) else a.day,
            p.code, p.full_name, (s.name if s else "—"),
            a.check_in, a.check_out,
            TEN_TRANG_THAI.get(a.status, a.status),
            a.late_minutes or 0,
            a.confidence,
            a.liveness_score,
            a.device_id or "—",
        ]
        for i, v in enumerate(gia_tri, start=1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = _vien()
            c.fill = nen
            c.alignment = Alignment(
                horizontal="left" if i in (3, 4) else "center", vertical="center")

        # Định dạng số và ngày giờ. Không đặt thì Excel hiện ngày thành số
        # nguyên và độ tin cậy thành 0.9228374829…
        ws.cell(row=r, column=1).number_format = "dd/mm/yyyy"
        for cot in (5, 6):
            ws.cell(row=r, column=cot).number_format = "hh:mm:ss"
        ws.cell(row=r, column=9).number_format = "0.000"
        ws.cell(row=r, column=10).number_format = "0.000"

        # Trạng thái là thông tin quan trọng nhất của mỗi dòng — cho nó nổi lên.
        c = ws.cell(row=r, column=7)
        c.font = Font(bold=True, color="B45309" if muon else "0E7C66")
        if muon:
            ws.cell(row=r, column=8).font = Font(bold=True, color="B45309")

    cuoi = HANG_TIEU_DE + len(rows)

    # Đóng băng dòng tiêu đề: cuộn xuống vẫn biết mình đang đọc cột nào. Với sổ
    # điểm danh vài trăm dòng thì đây là khác biệt giữa dùng được và không.
    ws.freeze_panes = ws.cell(row=HANG_TIEU_DE + 1, column=1)
    if rows:
        ws.auto_filter.ref = f"A{HANG_TIEU_DE}:{get_column_letter(len(TIEU_DE))}{cuoi}"

    # ------------------------------------------------------------------ tổng kết
    if rows:
        r = cuoi + 2
        tong = len(rows)
        so_muon = sum(1 for a, _, _ in rows if a.status == "late")
        for i, (nhan, gia) in enumerate([
            ("Tổng lượt điểm danh", tong),
            ("Đúng giờ", tong - so_muon),
            ("Đi muộn", so_muon),
            ("Tỉ lệ đúng giờ", (tong - so_muon) / tong if tong else 0),
        ]):
            ws.cell(row=r + i, column=1, value=nhan).font = Font(bold=True)
            c = ws.cell(row=r + i, column=2, value=gia)
            c.font = Font(bold=True)
            if nhan.startswith("Tỉ lệ"):
                c.number_format = "0.0%"

    # Trang thứ hai: những người bị đánh dấu đi muộn, để giảng viên khỏi phải lọc.
    if any(a.status == "late" for a, _, _ in rows):
        ws2 = wb.create_sheet("Đi muộn")
        for i, (ten, rong) in enumerate(TIEU_DE[:8], start=1):
            c = ws2.cell(row=1, column=i, value=ten)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="B45309")
            c.alignment = Alignment(horizontal="center", wrap_text=True)
            ws2.column_dimensions[get_column_letter(i)].width = rong
        r = 2
        for a, p, s in rows:
            if a.status != "late":
                continue
            for i, v in enumerate([
                date.fromisoformat(a.day) if isinstance(a.day, str) else a.day,
                p.code, p.full_name, (s.name if s else "—"),
                a.check_in, a.check_out, TEN_TRANG_THAI.get(a.status, a.status),
                a.late_minutes or 0,
            ], start=1):
                c = ws2.cell(row=r, column=i, value=v)
                c.border = _vien()
                c.fill = PatternFill("solid", fgColor=DO_NHAT)
                c.alignment = Alignment(horizontal="left" if i in (3, 4) else "center")
            ws2.cell(row=r, column=1).number_format = "dd/mm/yyyy"
            for cot in (5, 6):
                ws2.cell(row=r, column=cot).number_format = "hh:mm:ss"
            r += 1
        ws2.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
