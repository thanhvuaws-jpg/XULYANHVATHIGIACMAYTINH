"""Hoàn thiện báo cáo: đánh số trang và điền số trang vào mục lục.

    python -m report.hoan_thien

Vì sao phải nhờ tới Word thay vì làm hết bằng python-docx
--------------------------------------------------------
python-docx thao tác trên XML của tài liệu, mà XML **không chứa thông tin phân
trang**. Việc một đề mục rơi vào trang nào chỉ được quyết định lúc dàn trang, tuỳ
theo phông chữ, cỡ ảnh và độ dài từng đoạn. Muốn biết số trang thật thì phải để
một trình dàn trang thực sự tính hộ.

Script này điều khiển Microsoft Word (đã có sẵn trên máy) để:
  1. chèn trường số trang vào chân trang;
  2. hỏi Word xem mỗi đề mục nằm ở trang nào;
  3. ghi số trang đó vào đúng dòng mục lục, kèm dấu chấm dẫn;
  4. xuất PDF để xem lại.

Nếu máy không có Word, bỏ qua bước này — tài liệu vẫn hoàn chỉnh, chỉ thiếu số
trang trong mục lục.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCX = ROOT / "BAO_CAO_HOAN_CHINH.docx"
PDF = ROOT / "BAO_CAO_HOAN_CHINH.pdf"

# Hằng số của Word (thư viện COM không phơi tên hằng khi dùng liên kết muộn).
WD_PAGE_NUMBER = 3            # wdActiveEndPageNumber
WD_ALIGN_CENTER = 1
WD_ALIGN_RIGHT = 2
WD_TAB_LEADER_DOTS = 1
WD_FIELD_PAGE = 33            # wdFieldPage
WD_FORMAT_PDF = 17
WD_STORY_MAIN = 1

DE_MUC = re.compile(r"^(MỞ ĐẦU$|CHƯƠNG \d+\.|KẾT LUẬN$|DANH MỤC TÀI LIỆU|PHỤ LỤC|"
                    r"\d+\.\d+\.\s|\d+\.\d+\.\d+\.\s)")


def la_de_muc(t: str) -> bool:
    return bool(t) and bool(DE_MUC.match(t))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not DOCX.exists():
        print(f"Chưa có {DOCX.name} — chạy `python -m report.build_report` trước.")
        return 1

    try:
        import win32com.client as com
    except ImportError:
        print("Không có pywin32 — bỏ qua bước đánh số trang.")
        return 0

    word = com.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = False
    try:
        doc = word.Documents.Open(str(DOCX))

        # ------------------------------------------------ 1. số trang ở chân trang
        for sec in doc.Sections:
            footer = sec.Footers(1)          # wdHeaderFooterPrimary
            footer.LinkToPrevious = False
            rng = footer.Range
            rng.Text = ""
            rng.ParagraphFormat.Alignment = WD_ALIGN_CENTER
            rng.Font.Name = "Times New Roman"
            rng.Font.Size = 12
            doc.Fields.Add(rng, WD_FIELD_PAGE)
        print("  đã chèn số trang vào chân trang")

        doc.Repaginate()

        # -------------------------------- 2. tìm mục lục và các đề mục trong thân bài
        paras = doc.Paragraphs
        n = paras.Count

        i_muc_luc = i_het_muc_luc = None
        for i in range(1, n + 1):
            t = paras(i).Range.Text.strip().rstrip("\r")
            if t == "MỤC LỤC" and i_muc_luc is None:
                i_muc_luc = i
            elif i_muc_luc and t.startswith("DANH MỤC CÁC BẢNG"):
                i_het_muc_luc = i
                break
        if not (i_muc_luc and i_het_muc_luc):
            print("  không tìm thấy vùng mục lục — bỏ qua")
            doc.Close(False)
            return 1

        dong_muc_luc = list(range(i_muc_luc + 1, i_het_muc_luc))

        # Đề mục trong THÂN BÀI: nằm sau vùng mục lục và sau danh mục bảng/hình.
        trang_cua: dict[str, int] = {}
        thu_tu: list[str] = []
        for i in range(i_het_muc_luc, n + 1):
            t = paras(i).Range.Text.strip().rstrip("\r")
            if la_de_muc(t) and t not in trang_cua:
                trang_cua[t] = int(paras(i).Range.Information(WD_PAGE_NUMBER))
                thu_tu.append(t)
        print(f"  đã xác định trang cho {len(trang_cua)} đề mục")

        # ----------------------------------------- 3. ghi số trang vào mục lục
        # Điểm dừng tab căn phải ở mép lề phải, dẫn bằng dấu chấm — cách trình bày
        # mục lục quy ước.
        rong = doc.PageSetup.PageWidth - doc.PageSetup.LeftMargin - doc.PageSetup.RightMargin
        da_ghi = 0
        for i in dong_muc_luc:
            p = paras(i)
            t = p.Range.Text.strip().rstrip("\r")
            # Bỏ phần "<tab><số trang>" nếu tệp đã được xử lý một lần trước đó.
            # Thiếu bước này thì chạy lại lần hai sẽ không khớp được dòng nào
            # (vì chữ giờ là "MỞ ĐẦU\t8" chứ không còn là "MỞ ĐẦU"), và tệp im
            # lặng giữ nguyên mục lục cũ — một kiểu hỏng rất khó nhận ra.
            if "\t" in t:
                t = t.rsplit("\t", 1)[0].strip()
                r = p.Range
                r.SetRange(r.Start, r.End - 1)
                r.Text = t
            if t not in trang_cua:
                continue
            p.TabStops.ClearAll()
            p.TabStops.Add(Position=rong, Alignment=WD_ALIGN_RIGHT,
                           Leader=WD_TAB_LEADER_DOTS)
            # Chèn vào cuối đoạn, TRƯỚC ký tự xuống dòng.
            r = p.Range
            r.SetRange(r.End - 1, r.End - 1)
            r.InsertAfter(f"\t{trang_cua[t]}")
            da_ghi += 1
        print(f"  đã điền số trang cho {da_ghi} dòng mục lục")

        # Thêm chữ "Trang" ở đầu mục lục cho khớp mẫu.
        tieu_de = paras(i_muc_luc)
        r = tieu_de.Range
        r.SetRange(r.End - 1, r.End - 1)

        doc.Repaginate()
        doc.Save()
        doc.SaveAs(str(PDF), FileFormat=WD_FORMAT_PDF)
        tong_trang = doc.ComputeStatistics(2)
        tong_tu = doc.ComputeStatistics(0)
        doc.Close(False)
        print(f"\n  {tong_trang} trang · {tong_tu} từ")
        print(f"  Đã ghi: {DOCX.name} và {PDF.name}")
    finally:
        # Word đôi khi đã tự thoát trước khi tới đây; gọi Quit() lúc đó ném
        # AttributeError và che mất kết quả thật của cả lần chạy.
        try:
            word.Quit()
        except Exception:                        # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
