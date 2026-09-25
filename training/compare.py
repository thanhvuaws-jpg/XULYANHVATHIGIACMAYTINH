"""Gộp kết quả của nhiều mô hình thành một biểu đồ so sánh cho báo cáo.

    python -m training.compare --tags facenet distill mobilefacenet

Đọc các file `reports/<tag>_eval.json` do `training/evaluate.py` sinh ra, nên chỉ
chạy được sau khi đã đánh giá từng mô hình. Không tính lại gì — chỉ trình bày.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPORTS = Path("reports")

#: Tên hiển thị và màu cho từng mô hình. Thứ tự cũng là thứ tự vẽ.
STYLE = {
    "mobilefacenet": ("ArcFace\nLFW · 349 người", "#f59e0b"),
    "casia": ("ArcFace\nCASIA · 6.000 người", "#d97706"),
    "distill": ("Chưng cất\nLFW · 9k ảnh", "#5eb89f"),
    "distill_casia": ("Chưng cất\nCASIA · 112k ảnh", "#0e7c66"),
    "facenet": ("FaceNet\n(thầy, pretrained)", "#4f46e5"),
}
# Bản đánh giá trên ẢNH GỐC (manifest_raw) — đây mới là giao thức phản ánh đúng
# lúc chạy thật, vì camera đưa vào khung hình gốc chứ không đưa vào chip đã căn
# chỉnh sẵn. Xem ghi chú ở Task 12b trong nhật ký kỹ thuật.
STYLE.update({f"{k}_raw": v for k, v in STYLE.items()})
STYLE["lfw_raw"] = STYLE["mobilefacenet"]

#: Kích thước và tốc độ đo được, không nằm trong file eval.
FACTS = {
    "mobilefacenet": {"mb": 4.8, "ms": 5.29},
    "casia": {"mb": 4.8, "ms": 4.16},
    "distill": {"mb": 4.8, "ms": 6.63},
    "distill_casia": {"mb": 4.8, "ms": 4.73},
    "facenet": {"mb": 107.0, "ms": 83.7},
}
FACTS.update({f"{k}_raw": v for k, v in FACTS.items()})
FACTS["lfw_raw"] = FACTS["mobilefacenet"]


def load(tag: str) -> dict | None:
    p = REPORTS / f"{tag}_eval.json"
    if not p.exists():
        print(f"  bỏ qua {tag}: chưa có {p}")
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="+", default=["mobilefacenet", "casia", "distill", "distill_casia", "facenet"])
    ap.add_argument("--out", default="reports/so_sanh_mo_hinh.png")
    args = ap.parse_args()

    data = {t: d for t in args.tags if (d := load(t)) is not None}
    if not data:
        raise SystemExit("Không có kết quả nào để so sánh.")

    tags = list(data)
    names = [STYLE.get(t, (t, "#888"))[0] for t in tags]
    colors = [STYLE.get(t, (t, "#888"))[1] for t in tags]
    x = np.arange(len(tags))

    fig, axes = plt.subplots(1, 4, figsize=(19, 4.8))

    def bars(ax, values, title, ylabel, fmt="{:.3f}", ylim=None, log=False):
        b = ax.bar(x, values, color=colors, width=0.62)
        # Nhãn hai dòng ở khổ này bị chồng lên nhau; nghiêng 18° và thu nhỏ vừa
        # đủ để đọc được mà không phải cắt bớt chữ.
        ax.set_xticks(x)
        ax.set_xticklabels(names, fontsize=7.2, rotation=18, ha="right")
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_ylabel(ylabel, fontsize=9)
        if log:
            ax.set_yscale("log")
        elif ylim:
            ax.set_ylim(*ylim)
        ax.grid(axis="y", alpha=.25)
        ax.set_axisbelow(True)
        for rect, v in zip(b, values):
            ax.annotate(fmt.format(v), (rect.get_x() + rect.get_width() / 2, v),
                        ha="center", va="bottom", fontsize=9, fontweight="bold")

    # 1. Độ chính xác xếp hạng
    bars(axes[0], [data[t]["identification"]["rank1"] for t in tags],
         "Định danh 1:N — rank-1", "tỉ lệ đúng", ylim=(0, 1.12))

    # 2. Chất lượng phân biệt
    bars(axes[1], [data[t]["verification"]["eer"] * 100 for t in tags],
         "Xác thực 1:1 — EER (thấp hơn = tốt hơn)", "%", fmt="{:.2f}%")

    # 3. Chỉ số thật của điểm danh
    bars(axes[2], [data[t]["openset"]["dir"]["0.01"] for t in tags],
         "Open-set — DIR@FAR=1%", "tỉ lệ nhận đúng người quen", ylim=(0, 1.0))

    # 4. Chi phí: tốc độ và kích thước
    ax = axes[3]
    ms = [FACTS.get(t, {}).get("ms", 0) for t in tags]
    b = ax.bar(x, ms, color=colors, width=0.62)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=7.2, rotation=18, ha="right")
    ax.set_title("Chi phí — thời gian CPU mỗi khuôn mặt", fontsize=11, fontweight="bold")
    ax.set_ylabel("ms", fontsize=9)
    ax.grid(axis="y", alpha=.25); ax.set_axisbelow(True)
    for rect, t, v in zip(b, tags, ms):
        mb = FACTS.get(t, {}).get("mb", 0)
        ax.annotate(f"{v:.1f} ms\n{mb:.1f} MB",
                    (rect.get_x() + rect.get_width() / 2, v),
                    ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_ylim(0, max(ms) * 1.25)

    # Đọc quy mô tập test từ chính kết quả đánh giá thay vì viết cứng — trước đây
    # con số 116/59 bị viết cứng và giữ nguyên cả khi đổi sang tập khác, khiến
    # biểu đồ chú thích sai tập dữ liệu mà nó đang vẽ.
    any_d = next(iter(data.values()))
    n_reg = any_d["identification"]["n_gallery_people"]
    n_str = any_d["openset"]["n_strangers"]
    src = any_d.get("manifest", "")
    ghi_chu = " · ảnh gốc chưa căn chỉnh" if "raw" in src else ""
    fig.suptitle(f"So sánh mô hình trích đặc trưng — cùng tập test open-set "
                 f"({n_reg} người đã đăng ký + {n_str} người lạ, "
                 f"không ai xuất hiện lúc huấn luyện{ghi_chu})",
                 fontsize=11.5, y=1.02)
    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)

    print(f"\n{'mô hình':<34}{'rank-1':>9}{'EER':>9}{'DIR@1%':>9}{'ms':>8}{'MB':>8}")
    print("-" * 77)
    for t in tags:
        d = data[t]
        f = FACTS.get(t, {})
        label = STYLE.get(t, (t, ""))[0].replace("\n", " ")
        print(f"{label:<34}{d['identification']['rank1']:>9.4f}"
              f"{d['verification']['eer']*100:>8.2f}%{d['openset']['dir']['0.01']:>9.4f}"
              f"{f.get('ms', 0):>8.2f}{f.get('mb', 0):>8.1f}")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
