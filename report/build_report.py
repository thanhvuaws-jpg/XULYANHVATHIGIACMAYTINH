"""Dựng báo cáo hoàn chỉnh vào mẫu Word của trường.

    python -m report.build_report

Đọc `formatbaocao.docx` (mẫu gốc, KHÔNG bị sửa) và ghi ra `BAO_CAO_HOAN_CHINH.docx`.

Nguyên tắc: mẫu gốc quy định định dạng, tệp này chỉ quy định nội dung. Mọi đoạn
văn tạo ra đều là bản sao của một đoạn mẫu có sẵn trong tệp, nên thừa hưởng trọn
vẹn lề, phông, cỡ chữ, giãn dòng và thụt đầu dòng mà trường yêu cầu.
"""
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from report.docx_tools import (_strip_runs, add_page_break, build_table,
                               clone_paragraph, insert_after, insert_image,
                               set_text, style_cell)
from report.noidung_c1_c2 import CHUONG_1, CHUONG_2, MO_DAU
from report.noidung_c3 import (CHUONG_3, GIAO_DIEN, KET_LUAN, MO_DAU_32,
                               PHU_LUC)
from report.noidung_c3b import NGUOI_DUNG_THAT

ROOT = Path(__file__).resolve().parent.parent
MAU = ROOT / "formatbaocao.docx"
RA = ROOT / "BAO_CAO_HOAN_CHINH.docx"
ANH_APP = ROOT / "report" / "anh_app"   # ảnh chụp màn hình sản phẩm

# Chỉ số các đoạn trong mẫu, tra được bằng cách in ra cấu trúc tệp.
I_CHUONG = 31        # "CHƯƠNG 1. GIỚI THIỆU"  — 16pt đậm căn giữa
I_MUC = 33           # "1.1. Lý do chọn đề tài" — 14pt đậm
I_TIEUMUC = 63       # "3.1.1 ...."             — 13pt đậm
I_THAN = 34          # đoạn thân bài            — 13pt, căn đều, giãn 1,5, thụt 1cm

VIET_TAT = [
    ["Ký hiệu, chữ viết tắt", "Chữ viết đầy đủ"],
    ["ACER", "Average Classification Error Rate — tỉ lệ lỗi phân loại trung bình"],
    ["APCER", "Attack Presentation Classification Error Rate — tỉ lệ tấn công lọt qua"],
    ["API", "Application Programming Interface — giao diện lập trình ứng dụng"],
    ["ArcFace", "Additive Angular Margin Loss — hàm mất mát biên độ góc cộng thêm"],
    ["BPCER", "Bona fide Presentation Classification Error Rate — tỉ lệ từ chối oan người thật"],
    ["CMC", "Cumulative Match Characteristic — đường cong tỉ lệ khớp tích luỹ"],
    ["CNN", "Convolutional Neural Network — mạng nơ-ron tích chập"],
    ["CSDL", "Cơ sở dữ liệu"],
    ["DIR", "Detection and Identification Rate — tỉ lệ phát hiện và định danh đúng"],
    ["EER", "Equal Error Rate — tỉ lệ lỗi cân bằng"],
    ["FAR", "False Acceptance Rate — tỉ lệ chấp nhận sai"],
    ["FRR", "False Rejection Rate — tỉ lệ từ chối sai"],
    ["JWT", "JSON Web Token — thẻ xác thực phiên đăng nhập"],
    ["LFW", "Labeled Faces in the Wild — bộ dữ liệu khuôn mặt gán nhãn"],
    ["MTCNN", "Multi-task Cascaded Convolutional Networks — mạng tích chập nối tiếp đa nhiệm"],
    ["ONNX", "Open Neural Network Exchange — định dạng trao đổi mô hình mạng nơ-ron"],
    ["ROC", "Receiver Operating Characteristic — đường cong đặc trưng hoạt động"],
    ["TAR", "True Acceptance Rate — tỉ lệ chấp nhận đúng"],
]

TAI_LIEU = [
    "[1] J. Deng, J. Guo, N. Xue and S. Zafeiriou (2019) ArcFace: Additive Angular Margin "
    "Loss for Deep Face Recognition. IEEE/CVF Conference on Computer Vision and Pattern "
    "Recognition (CVPR), pp. 4690–4699.",
    "[2] S. Chen, Y. Liu, X. Gao and Z. Han (2018) MobileFaceNets: Efficient CNNs for "
    "Accurate Real-Time Face Verification on Mobile Devices. Chinese Conference on "
    "Biometric Recognition (CCBR), pp. 428–438.",
    "[3] F. Schroff, D. Kalenichenko and J. Philbin (2015) FaceNet: A Unified Embedding "
    "for Face Recognition and Clustering. IEEE Conference on Computer Vision and Pattern "
    "Recognition (CVPR), pp. 815–823.",
    "[4] W. Wu, H. Peng and S. Yu (2023) YuNet: A Tiny Millisecond-level Face Detector. "
    "Machine Intelligence Research, vol. 20, pp. 656–665.",
    "[5] K. Zhang, Z. Zhang, Z. Li and Y. Qiao (2016) Joint Face Detection and Alignment "
    "Using Multitask Cascaded Convolutional Networks. IEEE Signal Processing Letters, "
    "vol. 23, no. 10, pp. 1499–1503.",
    "[6] G. B. Huang, M. Ramesh, T. Berg and E. Learned-Miller (2007) Labeled Faces in "
    "the Wild: A Database for Studying Face Recognition in Unconstrained Environments. "
    "University of Massachusetts Amherst, Technical Report 07-49.",
    "[7] D. Yi, Z. Lei, S. Liao and S. Z. Li (2014) Learning Face Representation from "
    "Scratch. arXiv preprint arXiv:1411.7923.",
    "[8] G. Hinton, O. Vinyals and J. Dean (2015) Distilling the Knowledge in a Neural "
    "Network. NIPS Deep Learning and Representation Learning Workshop.",
    "[9] Y. A. Malkov and D. A. Yashunin (2020) Efficient and Robust Approximate Nearest "
    "Neighbor Search Using Hierarchical Navigable Small World Graphs. IEEE Transactions "
    "on Pattern Analysis and Machine Intelligence, vol. 42, no. 4, pp. 824–836.",
    "[10] ISO/IEC 30107-3:2023 Information technology — Biometric presentation attack "
    "detection — Part 3: Testing and reporting. International Organization for "
    "Standardization.",
    "[11] Q. Cao, L. Shen, W. Xie, O. M. Parkhi and A. Zisserman (2018) VGGFace2: A "
    "Dataset for Recognising Faces across Pose and Age. IEEE International Conference on "
    "Automatic Face and Gesture Recognition (FG), pp. 67–74.",
]


class Builder:
    """Ghi nội dung nối tiếp nhau, luôn chèn sau đoạn vừa tạo."""

    def __init__(self, doc: Document, cursor):
        self.doc = doc
        self.cur = cursor
        #: Ghi lại chú thích bảng/hình theo đúng thứ tự xuất hiện, để sinh
        #: "Danh mục các bảng, hình vẽ" mà không phải liệt kê tay — liệt kê tay
        #: là thứ chắc chắn sẽ lệch với thân bài sau vài lần sửa nội dung.
        self.chu_thich_da_ghi: list[str] = []
        self.refs = {
            "chuong": doc.paragraphs[I_CHUONG],
            "muc": doc.paragraphs[I_MUC],
            "tieumuc": doc.paragraphs[I_TIEUMUC],
            "than": doc.paragraphs[I_THAN],
        }

    def _put(self, p):
        insert_after(self.cur, p)
        self.cur = p
        return p

    def chuong(self, text):
        p = clone_paragraph(self.refs["chuong"])
        set_text(p, text, bold=True, size=16)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return self._put(p)

    def muc(self, text):
        p = clone_paragraph(self.refs["muc"])
        set_text(p, text, bold=True, size=14)
        pf = p.paragraph_format
        pf.space_before, pf.space_after = Pt(10), Pt(4)
        # Đề mục không được đứng một mình ở cuối trang, tách khỏi nội dung của nó.
        pf.keep_with_next = True
        return self._put(p)

    def tieumuc(self, text):
        p = clone_paragraph(self.refs["tieumuc"])
        set_text(p, text, bold=True, size=13)
        pf = p.paragraph_format
        pf.space_before, pf.space_after = Pt(8), Pt(3)
        pf.keep_with_next = True
        return self._put(p)

    def than(self, text):
        p = clone_paragraph(self.refs["than"])
        set_text(p, text, size=13)
        return self._put(p)

    def gach_dau_dong(self, text):
        p = clone_paragraph(self.refs["than"])
        pf = p.paragraph_format
        pf.first_line_indent = Cm(0)
        pf.left_indent = Cm(1.0)
        pf.space_after = Pt(3)
        set_text(p, "− " + text, size=13)
        return self._put(p)

    def chu_thich(self, text):
        self.chu_thich_da_ghi.append(text)
        p = clone_paragraph(self.refs["than"])
        pf = p.paragraph_format
        pf.first_line_indent = Cm(0)
        pf.line_spacing = 1.0
        pf.space_before, pf.space_after = Pt(4), Pt(10)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_text(p, text, italic=True, size=12)
        return self._put(p)

    def dong_lenh(self, text):
        """Một dòng lệnh gõ vào terminal.

        Dùng phông đơn cách để phân biệt rõ với văn xuôi — trong câu lệnh thì
        dấu gạch, dấu chấm và khoảng trắng đều mang nghĩa, nên không được để
        phông chữ có chân làm người đọc gõ nhầm.
        """
        p = clone_paragraph(self.refs["than"])
        pf = p.paragraph_format
        pf.first_line_indent = Cm(0)
        pf.left_indent = Cm(1.0)
        pf.line_spacing = 1.0
        pf.space_before, pf.space_after = Pt(3), Pt(6)
        set_text(p, text, size=12, font="Consolas")
        return self._put(p)

    def trong(self, pts=6):
        p = clone_paragraph(self.refs["than"])
        p.paragraph_format.space_after = Pt(pts)
        p.paragraph_format.line_spacing = 1.0
        return self._put(p)

    def anh(self, path, width=15.5):
        p = insert_image(self.doc, self.cur, self.refs["than"], ROOT / path, width)
        self.cur = p
        return p

    def bang(self, data, size=11.5):
        """Dựng bảng ở cuối tài liệu rồi di chuyển tới vị trí con trỏ."""
        t = build_table(self.doc, self.doc.tables[3], data, size=size)
        self.cur._p.addnext(t._tbl)
        # Sau một bảng phải có đoạn văn, nếu không Word sẽ dính bảng vào phần sau.
        p = clone_paragraph(self.refs["than"])
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.0
        t._tbl.addnext(p._p)
        # Hai ràng buộc, và CHỈ hai — đặt nhiều hơn là Word treo.
        #
        #   1. `cantSplit` trên mọi hàng: không cho một hàng tự vỡ đôi giữa hai
        #      trang. Rẻ và an toàn.
        #   2. `keep_with_next` trên HÀNG CUỐI và đoạn đệm: để chú thích luôn
        #      đi theo bảng, không trôi sang trang sau đứng trơ một mình.
        #
        # Bản trước đặt `keep_with_next` lên MỌI hàng với ý giữ cả bảng trong
        # một trang. Hậu quả: khi bảng cao hơn một trang — bảng bộ kiểm thử sau
        # khi thêm một dòng là vừa đúng trường hợp đó — Word không thoả mãn nổi
        # ràng buộc và **treo vô hạn** lúc mở tệp. Không báo lỗi, chỉ đứng im;
        # phải tự tay tắt tiến trình. Bảng bị cắt ngang trang thì xấu, nhưng tệp
        # không mở được thì hỏng hẳn.
        for hang in t.rows:
            trPr = hang._tr.get_or_add_trPr()
            if trPr.find(qn("w:cantSplit")) is None:
                trPr.append(trPr.makeelement(qn("w:cantSplit"), {}))
        for o in t.rows[-1].cells:
            for doan in o.paragraphs:
                doan.paragraph_format.keep_with_next = True
        p.paragraph_format.keep_with_next = True
        self.cur = p
        return t

    def ngat_trang(self):
        add_page_break(self.cur)

    def render(self, items):
        for kind, val in items:
            if kind == "p":
                self.than(val)
            elif kind == "li":
                self.gach_dau_dong(val)
            elif kind == "h2":
                self.muc(val)
            elif kind == "h3":
                self.tieumuc(val)
            elif kind == "cap":
                self.chu_thich(val)
            elif kind == "img":
                self.anh(val)
            elif kind == "tbl":
                self.bang(val)
            elif kind == "cmd":
                self.dong_lenh(val)
            elif kind == "br":
                self.ngat_trang()
            else:
                raise ValueError(f"Loại nội dung lạ: {kind}")


def xoa(paragraphs) -> int:
    """Xoá các đoạn đã cho **theo đối tượng**, không theo chỉ số.

    Chỉ số là cái bẫy ở đây: `doc.paragraphs` được tính lại mỗi lần truy cập, nên
    ngay khi chèn đoạn đầu tiên thì mọi chỉ số ghi lại từ trước đều lệch. Bản đầu
    của tệp này xoá theo chỉ số gốc sau khi đã chèn nội dung, và kết quả là nó
    xoá nhầm chính nội dung vừa viết trong khi giữ nguyên phần giữ chỗ của mẫu.
    """
    n = 0
    for p in paragraphs:
        parent = p._p.getparent()
        if parent is not None:
            parent.remove(p._p)
            n += 1
    return n


import re

_DE_MUC = re.compile(r"^(MỞ ĐẦU$|CHƯƠNG \d+\.|KẾT LUẬN$|DANH MỤC TÀI LIỆU|PHỤ LỤC|"
                     r"\d+\.\d+\.\s|\d+\.\d+\.\d+\.\s)")


def _la_de_muc(t: str) -> bool:
    return bool(t) and bool(_DE_MUC.match(t))


def viet_muc_luc(doc, anchor, o_muc_luc, de_muc: list[str], khuon) -> None:
    """Ghi mục lục vào các đoạn giữ chỗ có sẵn của mẫu.

    Mẫu dựng sẵn một số dòng mục lục mang style Heading; ở đây dùng lại đúng
    những dòng đó cho các mục đầu, rồi nhân bản thêm cho phần còn lại. Nhờ vậy
    mục lục vẫn nằm trong khung định dạng mà mẫu quy định.
    """
    for p in o_muc_luc:
        p._p.getparent().remove(p._p)

    cur = None
    for t in de_muc:
        cap1 = bool(re.match(r"^(MỞ ĐẦU|CHƯƠNG|KẾT LUẬN|DANH MỤC|PHỤ LỤC)", t))
        # Dùng đoạn thân bài làm khuôn, KHÔNG dùng style Heading như mẫu gốc.
        # Mẫu gán style Heading cho các dòng mục lục, nhưng làm vậy thì chính các
        # dòng mục lục lại bị Word coi là đề mục: chúng hiện trong khung điều
        # hướng, và nếu sau này chèn mục lục tự động thì mục lục ấy sẽ liệt kê
        # lại chính nó. Cấp mục ở đây thể hiện bằng độ thụt và chữ đậm.
        p = clone_paragraph(khuon)
        pf = p.paragraph_format
        pf.line_spacing = 1.3
        pf.space_before = Pt(6 if cap1 else 0)
        pf.space_after = Pt(0)
        # Thụt vào theo cấp: 1.1 thụt một bậc, 1.1.1 thụt hai bậc.
        bac = 0 if cap1 else (2 if re.match(r"^\d+\.\d+\.\d+\.", t) else 1)
        pf.left_indent = Cm(0.8 * bac)
        pf.first_line_indent = Cm(0)
        set_text(p, t, bold=cap1, size=13)
        (anchor if cur is None else cur)._p.addnext(p._p)
        cur = p


def viet_danh_muc_hinh(doc, anchor, b: "Builder") -> None:
    """Ghi danh mục bảng và hình vẽ, tách hai nhóm, theo đúng thứ tự thân bài."""
    bang = [t for t in b.chu_thich_da_ghi if t.startswith("Bảng")]
    hinh = [t for t in b.chu_thich_da_ghi if t.startswith("Hình")]

    cur = anchor
    def them(text, bold=False, truoc=0):
        nonlocal cur
        p = clone_paragraph(b.refs["than"])
        pf = p.paragraph_format
        pf.first_line_indent = Cm(0)
        pf.left_indent = Cm(0)
        pf.line_spacing = 1.3
        pf.space_before, pf.space_after = Pt(truoc), Pt(0)
        set_text(p, text, bold=bold, size=13)
        cur._p.addnext(p._p)
        cur = p

    them("DANH MỤC CÁC BẢNG, HÌNH VẼ, ĐỒ THỊ", bold=True)
    them("Danh mục bảng", bold=True, truoc=10)
    for t in bang:
        them(t)
    them("Danh mục hình vẽ", bold=True, truoc=10)
    for t in hinh:
        them(t)
    add_page_break(cur)


# --------------------------------------------------------------------- bìa
#: Thông tin hành chính của bài nộp. Gom vào một chỗ để sửa một lần là xong,
#: thay vì rải rác trong mã dựng.
BIA = {
    "hoc_phan": "XỬ LÝ ẢNH VÀ THỊ GIÁC MÁY TÍNH",
    "de_tai": "XÂY DỰNG HỆ THỐNG ĐIỂM DANH SINH VIÊN BẰNG NHẬN DIỆN KHUÔN MẶT",
    "gvhd": "Hồ Văn Quí",
    "nhom": "10",
    "ma_lop": "010100086904",
    "thang_nam": "10/2026",
}

#: (họ tên, MSSV, lớp, ghi chú)
THANH_VIEN = [
    ("Đàm Thanh Vũ", "2431540219", "24ĐHTT04", "Nhóm trưởng"),
    ("Hoàng Thuỷ Tiên", "2431540237", "24ĐHTT04", ""),
    ("Trương Ngọc Tiến", "2431540017", "24ĐHTT01", ""),
]


def dung_bia(doc) -> None:
    """Điền trang bìa và bảng danh sách nhóm của mẫu.

    Mẫu của trường có **hai trang bìa** nằm trong hai hàng của cùng một bảng:
    một bản ghi "TP.Hồ Chí Minh", một bản ghi "Thành phố Hồ Chí Minh". Đó là hai
    phương án để người làm chọn một, không phải hai trang phải nộp cả. Hàm này
    xoá hàng thứ hai, giữ lại bản đầu.

    Các ô còn tô vàng trong mẫu là chỗ giữ chỗ. Ghi đè bằng cách xoá run cũ rồi
    ghi run mới nên vệt vàng mất theo, không phải xoá tay từng chỗ.
    """
    bang_bia = doc.tables[0]
    if len(bang_bia.rows) > 1:
        bang_bia._tbl.remove(bang_bia.rows[-1]._tr)

    o = bang_bia.rows[0].cells[0]
    dien = {
        8: (BIA["hoc_phan"], 20.0),
        9: (BIA["de_tai"], 18.0),
        12: (f"Giảng viên hướng dẫn: {BIA['gvhd']}", 14.0),
        13: (f"Sinh viên/ Nhóm sinh viên thực hiện: Nhóm {BIA['nhom']}", 14.0),
        14: ("Mã số sinh viên: " + ", ".join(t[1] for t in THANH_VIEN), 14.0),
        15: (f"Lớp: {BIA['ma_lop']}", 14.0),
        22: (f"TP. Hồ Chí Minh, tháng {BIA['thang_nam']}", 14.0),
    }
    for i, (chu, co) in dien.items():
        doan = o.paragraphs[i]
        canh = doan.alignment
        _strip_runs(doan._p)
        set_text(doan, chu, bold=True, size=co)
        doan.alignment = canh

    # Tên đề tài dài hơn chỗ giữ chỗ "TÊN ĐỀ TÀI" nên xuống hai dòng, đẩy dòng
    # địa danh tràn sang trang thứ hai và để lại một trang gần như trống chỉ có
    # khung viền. Bỏ bớt ba dòng trắng ở cuối ô để bìa gọn lại trong một trang.
    trong = [d for d in o.paragraphs[16:22] if not d.text.strip()]
    for d in trong[:3]:
        d._p.getparent().remove(d._p)

    # Bảng danh sách nhóm: mẫu có sẵn 5 hàng mẫu, nhóm chỉ có 3 người.
    bang = doc.tables[1]
    while len(bang.rows) > 1:
        bang._tbl.remove(bang.rows[-1]._tr)
    for i, (ten, mssv, lop, ghi_chu) in enumerate(THANH_VIEN, start=1):
        hang = bang.add_row()
        style_cell(hang.cells[0], str(i), size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
        style_cell(hang.cells[1], ten, size=12)
        style_cell(hang.cells[2], mssv, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
        style_cell(hang.cells[3], lop, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
        style_cell(hang.cells[4], ghi_chu, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    print(f"  bìa: nhóm {BIA['nhom']}, {len(THANH_VIEN)} thành viên, đã bỏ trang bìa trùng")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    doc = Document(str(MAU))
    dung_bia(doc)
    ps = doc.paragraphs

    # ------------------------------------------------ bảng chữ viết tắt (bảng 3)
    tb = doc.tables[3]
    while len(tb.rows) > 1:
        tb._tbl.remove(tb.rows[-1]._tr)
    style_cell(tb.cell(0, 0), VIET_TAT[0][0], bold=True, size=12,
               align=WD_ALIGN_PARAGRAPH.CENTER)
    style_cell(tb.cell(0, 1), VIET_TAT[0][1], bold=True, size=12,
               align=WD_ALIGN_PARAGRAPH.CENTER)
    for kh, day in VIET_TAT[1:]:
        row = tb.add_row()
        style_cell(row.cells[0], kh, bold=True, size=12)
        style_cell(row.cells[1], day, size=12)
    for row in tb.rows:
        row.cells[0].width = Cm(3.0)
        row.cells[1].width = Cm(12.5)
    print(f"  bảng chữ viết tắt: {len(VIET_TAT) - 1} mục")

    # ------------------------------------- giữ MỐC và GIỮ CHỖ theo đối tượng
    # Bắt buộc lấy tham chiếu tới đối tượng ngay bây giờ, khi chỉ số còn đúng.
    moc = {
        # Danh mục bảng/hình đặt SAU mục lục, ngay trước MỞ ĐẦU — đúng thứ tự mà
        # mục lục của mẫu liệt kê (ký hiệu → bảng hình vẽ → mở đầu).
        "danh_muc": ps[27],     # đoạn rỗng mang ngắt trang, trước "MỞ ĐẦU"
        "muc_luc": ps[7],       # tiêu đề "MỤC LỤC"
        "mo_dau": ps[28],       # tiêu đề "MỞ ĐẦU"
        "c1": ps[31],           # "CHƯƠNG 1. GIỚI THIỆU"
        "c2": ps[49],           # "CHƯƠNG 2. CƠ SỞ LÝ THUYẾT"  (mang ngắt trang)
        "c3": ps[59],           # "CHƯƠNG 3. PHÂN TÍCH HỆ THỐNG…"
        "kl": ps[81],           # "KẾT LUẬN"                    (mang ngắt trang)
        "tl": ps[89],           # "DANH MỤC TÀI LIỆU THAM KHẢO"
        "pl": ps[97],           # "PHỤ LỤC (nếu có)"
    }
    # Các đoạn hướng dẫn/giữ chỗ của mẫu. KHÔNG đụng tới các đoạn rỗng mang ngắt
    # trang (30, 58, 88, 96) vì chúng giữ bố cục phân trang của mẫu.
    giu_cho = ([ps[29]] + [ps[32]] + ps[33:49] + ps[50:58]
               + ps[60:81] + ps[82:88] + ps[90:96])
    # Các dòng mục lục giữ chỗ của mẫu — giữ lại tham chiếu để lấy style, và chỉ
    # ghi đè ở bước cuối, sau khi thân bài đã dựng xong.
    o_muc_luc = ps[8:27]
    b = Builder(doc, moc["mo_dau"])

    # Xoá giữ chỗ TRƯỚC khi chèn: sau khi chèn thì mọi chỉ số đều lệch, còn các
    # đối tượng mốc ở trên vẫn hợp lệ vì chúng không bị xoá.
    print(f"  đã bỏ {xoa(giu_cho)} đoạn hướng dẫn của mẫu")

    # ------------------------------------------------------------------- MỞ ĐẦU
    b.cur = moc["mo_dau"]
    b.render(MO_DAU)
    print(f"  MỞ ĐẦU: {len(MO_DAU)} đoạn")

    # ----------------------------------------------------------------- CHƯƠNG 1
    b.cur = moc["c1"]
    b.render(CHUONG_1)
    print(f"  CHƯƠNG 1: {len(CHUONG_1)} khối")

    # ----------------------------------------------------------------- CHƯƠNG 2
    b.cur = moc["c2"]
    b.render(CHUONG_2)
    print(f"  CHƯƠNG 2: {len(CHUONG_2)} khối")

    # ----------------------------------------------------------------- CHƯƠNG 3
    b.cur = moc["c3"]
    b.render(CHUONG_3)
    # Thứ tự bắt buộc: 3.1.16 và 3.1.17 nằm TRƯỚC tiêu đề 3.2. Bản dựng trước gộp
    # phần mở đầu 3.2 vào cuối CHUONG_3 nên hai mục này rơi xuống giữa mục giao
    # diện — đúng chỗ người đọc không tìm tới.
    b.render(NGUOI_DUNG_THAT)
    b.render(MO_DAU_32)

    thieu = []
    for i, (ten, mota, ten_anh) in enumerate(GIAO_DIEN, 1):
        b.tieumuc(ten)
        b.than(mota)
        chu = f"Hình 3.{i + 2}. {ten.split('. ', 1)[1]}"
        anh = ANH_APP / f"{ten_anh}.png"
        if anh.exists():
            # Dùng b.anh chứ không gọi thẳng insert_image: b.anh còn dời con trỏ
            # của bộ dựng tới đoạn chứa ảnh. Gọi thẳng thì con trỏ đứng yên ở đoạn
            # mô tả, chú thích chèn đè lên trước ảnh và cả bảy ảnh bị đẩy về cuối
            # tài liệu — đúng lỗi đã gặp ở bản dựng trước.
            #
            # Ảnh chụp toàn cửa sổ rộng 1920 px. Ở 15,5 cm — cỡ tối đa mà lề của
            # mẫu trường cho phép — ảnh cao khoảng 8,3 cm.
            b.anh(anh, 15.5)
        else:
            thieu.append(ten_anh)
            cho_dan = b.than("[Thay dòng này bằng ảnh chụp màn hình]")
            cho_dan.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cho_dan.paragraph_format.first_line_indent = Cm(0)
            cho_dan.paragraph_format.keep_with_next = True
        b.chu_thich(chu)
    if thieu:
        print(f"  !! chua co anh: {', '.join(thieu)}")
    print(f"  CHƯƠNG 3: {len(CHUONG_3)} khối + {len(GIAO_DIEN)} mục giao diện")

    # ---------------------------------------------------------------- KẾT LUẬN
    b.cur = moc["kl"]
    b.render(KET_LUAN)
    print(f"  KẾT LUẬN: {len(KET_LUAN)} đoạn")

    # ---------------------------------------------------------------- PHỤ LỤC
    # Mẫu ghi "PHỤ LỤC (nếu có)" — đó là hướng dẫn cho người làm, không phải tên
    # đề mục. Có nội dung rồi thì phải bỏ phần trong ngoặc, nếu không mục lục
    # cũng in nguyên chữ "(nếu có)".
    _strip_runs(moc["pl"]._p)
    set_text(moc["pl"], "PHỤ LỤC", bold=True, size=14)
    moc["pl"].alignment = WD_ALIGN_PARAGRAPH.CENTER
    b.cur = moc["pl"]
    b.render(PHU_LUC)
    print(f"  PHỤ LỤC: {len(PHU_LUC)} khối")

    # ------------------------------------------------------- TÀI LIỆU THAM KHẢO
    b.cur = moc["tl"]
    for t in TAI_LIEU:
        p = clone_paragraph(b.refs["than"])
        pf = p.paragraph_format
        pf.first_line_indent = Cm(0)
        pf.left_indent = Cm(0.8)
        pf.line_spacing = 1.15
        pf.space_after = Pt(6)
        set_text(p, t, size=13)
        b._put(p)
    print(f"  TÀI LIỆU THAM KHẢO: {len(TAI_LIEU)} mục")

    # ------------------------------------------- MỤC LỤC và DANH MỤC BẢNG/HÌNH
    # Sinh từ chính tài liệu vừa dựng, nên không bao giờ lệch với thân bài.
    # Chỉ quét THÂN BÀI. Nếu quét cả tài liệu thì chính các dòng giữ chỗ của mục
    # lục cũ ("KẾT LUẬN", "PHỤ LỤC"…) cũng lọt vào danh sách và bị chép lại lên
    # đầu mục lục mới.
    bo_qua = {id(p._p) for p in o_muc_luc}
    de_muc = [t for p in doc.paragraphs
              if id(p._p) not in bo_qua and _la_de_muc(t := p.text.strip())]
    viet_muc_luc(doc, moc["muc_luc"], o_muc_luc, de_muc, b.refs["than"])
    print(f"  MỤC LỤC: {len(de_muc)} đề mục")

    viet_danh_muc_hinh(doc, moc["danh_muc"], b)
    print(f"  DANH MỤC BẢNG, HÌNH VẼ: {len(b.chu_thich_da_ghi)} mục")

    doc.save(str(RA))
    print(f"\nĐã ghi: {RA.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
