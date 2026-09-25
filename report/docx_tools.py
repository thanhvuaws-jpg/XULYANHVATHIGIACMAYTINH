"""Công cụ ghi nội dung vào mẫu Word của trường mà KHÔNG phá format.

Vì sao không tự tạo tài liệu mới
--------------------------------
Mẫu `formatbaocao.docx` mang sẵn quy định của trường: lề 3–2–2–2 cm, Times New
Roman, chương 16pt đậm căn giữa, mục 14pt, thân bài 13pt căn đều giãn dòng 1,5 và
thụt đầu dòng 1 cm, các ngắt trang giữa phần. Dựng lại tài liệu từ đầu là chắc
chắn lệch một chỗ nào đó.

Cách làm ở đây: **nhân bản một đoạn mẫu** đã có sẵn trong tệp, xoá phần chữ của
nó rồi ghi chữ mới vào. Nhờ vậy mọi thuộc tính định dạng ở cấp đoạn (`w:pPr`) —
kể cả những thuộc tính python-docx không phơi ra qua API — đều được giữ nguyên,
vì chúng được sao chép nguyên khối ở dạng XML.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph

FONT = "Times New Roman"


# ------------------------------------------------------------------ đoạn văn
def _strip_runs(p_el) -> None:
    """Xoá mọi run (chữ, ngắt trang, ảnh) nhưng giữ nguyên khối định dạng w:pPr."""
    for child in list(p_el):
        if child.tag != qn("w:pPr"):
            p_el.remove(child)


def clone_paragraph(ref: Paragraph) -> Paragraph:
    """Nhân bản một đoạn (giữ trọn định dạng) rồi trả về bản trống chữ."""
    new_el = copy.deepcopy(ref._p)
    _strip_runs(new_el)
    return Paragraph(new_el, ref._parent)


def set_text(p: Paragraph, text: str, *, bold=False, italic=False,
             size: float | None = None, font: str = FONT) -> Paragraph:
    """Ghi chữ vào đoạn, hỗ trợ đánh dấu **đậm** bằng cặp dấu sao.

    Viết `**...**` trong nội dung sẽ thành chữ đậm — tiện để nhấn số liệu ngay
    trong câu mà không phải tách thành nhiều lời gọi.
    """
    for part in re.split(r"(\*\*[^*]+\*\*)", text):
        if not part:
            continue
        strong = part.startswith("**") and part.endswith("**")
        run = p.add_run(part[2:-2] if strong else part)
        run.font.name = font
        # Chữ Việt dùng bảng mã Đông Âu/complex script; phải đặt cả w:eastAsia và
        # w:cs, nếu không Word sẽ tự thay bằng phông mặc định cho các ký tự có dấu.
        rpr = run._element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = rpr.makeelement(qn("w:rFonts"), {})
            rpr.insert(0, rfonts)
        for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rfonts.set(qn(attr), font)
        if size:
            run.font.size = Pt(size)
        run.font.bold = True if strong else bold
        run.font.italic = italic
    return p


def insert_after(anchor: Paragraph, p: Paragraph) -> Paragraph:
    anchor._p.addnext(p._p)
    return p


def add_page_break(p: Paragraph) -> Paragraph:
    run = p.add_run()
    br = run._element.makeelement(qn("w:br"), {qn("w:type"): "page"})
    run._element.append(br)
    return p


# --------------------------------------------------------------------- bảng
def clone_table(ref_table, rows: int, cols: int):
    """Nhân bản một bảng mẫu để giữ nguyên đường kẻ và style, rồi nắn kích thước."""
    new_el = copy.deepcopy(ref_table._tbl)
    from docx.table import Table
    t = Table(new_el, ref_table._parent)
    # Xoá hết hàng cũ, chỉ giữ lại khung.
    for r in list(t.rows):
        new_el.remove(r._tr)
    return t


def style_cell(cell, text: str, *, bold=False, size=12.0, align=None,
               font: str = FONT) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.line_spacing = 1.0
    pf.space_before = Pt(2)
    pf.space_after = Pt(2)
    pf.first_line_indent = Cm(0)
    set_text(p, text, bold=bold, size=size, font=font)


def build_table(doc, ref_table, data: list[list[str]], *, widths=None,
                size=12.0, header=True):
    """Dựng bảng mới ở CUỐI tài liệu; nơi gọi tự di chuyển nó tới đúng chỗ."""
    rows, cols = len(data), len(data[0])
    t = doc.add_table(rows=rows, cols=cols)
    t.style = ref_table.style
    t.autofit = True
    for i, row in enumerate(data):
        for j, val in enumerate(row):
            style_cell(t.cell(i, j), str(val),
                       bold=(header and i == 0),
                       size=size,
                       align=WD_ALIGN_PARAGRAPH.CENTER if (header and i == 0) or j > 0
                       else WD_ALIGN_PARAGRAPH.LEFT)
    if widths:
        for j, w in enumerate(widths):
            for row in t.rows:
                row.cells[j].width = Cm(w)
    return t


# --------------------------------------------------------------------- ảnh
def insert_image(doc, anchor: Paragraph, ref_body: Paragraph, path: str | Path,
                 width_cm: float = 15.5) -> Paragraph:
    """Chèn ảnh căn giữa ngay sau `anchor`, trả về đoạn chứa ảnh."""
    p = clone_paragraph(ref_body)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.first_line_indent = Cm(0)
    pf.line_spacing = 1.0
    # Giữ ảnh dính với đoạn ngay sau nó — đoạn đó luôn là chú thích. Thiếu dòng
    # này thì khi ảnh rơi vào cuối trang, chú thích bị đẩy sang trang kế và đứng
    # trơ trọi ở đầu trang, tách khỏi hình mà nó đang chú thích.
    pf.keep_with_next = True
    insert_after(anchor, p)
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    return p
