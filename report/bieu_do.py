"""Vẽ lại biểu đồ theo bố cục dành riêng cho trang A4 dọc.

    python -m report.bieu_do

Vì sao cần bản riêng
--------------------
Biểu đồ dùng để xem trên màn hình được xếp một hàng ngang cho dễ so sánh, tỉ lệ
khoảng 3,8 : 1. Đưa nguyên hình đó vào báo cáo với bề ngang 15,5 cm thì chiều cao
chỉ còn hơn 4 cm, và mọi chữ trong hình nhỏ tới mức không đọc nổi khi in.

Bản này xếp lại thành lưới hai cột, đưa tỉ lệ về khoảng 1,3 : 1 nên ở cùng bề
ngang hình cao gấp ba lần. Số liệu không đổi — chỉ đổi cách bày.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"

TEN = {
    "lfw_raw": "ArcFace\nLFW · 349 người",
    "casia_raw": "ArcFace\nCASIA · 6.000 người",
    "distill_raw": "Chưng cất\nLFW · 9k ảnh",
    "distill_casia_raw": "Chưng cất\nCASIA · 112k ảnh",
    "facenet_raw": "FaceNet\n(thầy)",
}
MAU = ["#f59e0b", "#d97706", "#5eb89f", "#0e7c66", "#4f46e5"]
CHI_PHI = {"lfw_raw": (5.29, 4.8), "casia_raw": (4.16, 4.8), "distill_raw": (6.63, 4.8),
           "distill_casia_raw": (4.73, 4.8), "facenet_raw": (83.70, 107.0)}


def _cot(ax, x, vals, mau, tieu_de, ylabel, fmt="{:.3f}", ylim=None, ten=None):
    b = ax.bar(x, vals, color=mau, width=0.62)
    ax.set_title(tieu_de, fontsize=11, fontweight="bold", pad=8)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_xticks(x)
    # Nhãn hai dòng ở bốn ô nhỏ vẫn chạm nhau; nghiêng nhẹ là đủ tách ra mà
    # không phải rút gọn tên mô hình.
    ax.set_xticklabels(ten, fontsize=7.5, rotation=16, ha="right")
    if ylim:
        ax.set_ylim(*ylim)
    ax.grid(axis="y", alpha=.25)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelsize=8)
    for r, v in zip(b, vals):
        ax.annotate(fmt.format(v), (r.get_x() + r.get_width() / 2, v),
                    ha="center", va="bottom", fontsize=9, fontweight="bold")


def ve_so_sanh_mo_hinh(out: Path) -> None:
    tags = list(TEN)
    data = {}
    for t in tags:
        p = REPORTS / f"{t}_eval.json"
        if not p.exists():
            print(f"  thiếu {p.name} — bỏ qua biểu đồ so sánh")
            return
        data[t] = json.loads(p.read_text(encoding="utf-8"))

    ten = [TEN[t] for t in tags]
    x = np.arange(len(tags))
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.6))

    _cot(axes[0][0], x, [data[t]["identification"]["rank1"] for t in tags], MAU,
         "Định danh 1:N — rank-1", "tỉ lệ đúng", ylim=(0, 1.14), ten=ten)
    _cot(axes[0][1], x, [data[t]["verification"]["eer"] * 100 for t in tags], MAU,
         "Xác thực 1:1 — EER (thấp hơn = tốt hơn)", "%", fmt="{:.2f}%", ten=ten)
    _cot(axes[1][0], x, [data[t]["openset"]["dir"]["0.01"] for t in tags], MAU,
         "Open-set — DIR@FAR=1%", "tỉ lệ nhận đúng người quen", ylim=(0, 1.0), ten=ten)

    ax = axes[1][1]
    ms = [CHI_PHI[t][0] for t in tags]
    b = ax.bar(x, ms, color=MAU, width=0.62)
    ax.set_title("Chi phí — thời gian CPU mỗi khuôn mặt", fontsize=11, fontweight="bold", pad=8)
    ax.set_ylabel("ms", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(ten, fontsize=7.5, rotation=16, ha="right")
    ax.grid(axis="y", alpha=.25)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_ylim(0, max(ms) * 1.28)
    for r, t, v in zip(b, tags, ms):
        ax.annotate(f"{v:.1f} ms\n{CHI_PHI[t][1]:.1f} MB",
                    (r.get_x() + r.get_width() / 2, v),
                    ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    d0 = data[tags[0]]
    fig.suptitle(f"Cùng tập test open-set: {d0['identification']['n_gallery_people']} người "
                 f"đã đăng ký + {d0['openset']['n_strangers']} người lạ · ảnh gốc chưa căn chỉnh",
                 fontsize=10.5, y=0.985)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {out.name}")


def ve_ablation(out: Path) -> None:
    p = REPORTS / "ablation.json"
    if not p.exists():
        print("  thiếu ablation.json — bỏ qua")
        return
    d = json.loads(p.read_text(encoding="utf-8"))

    # Hai cột ở hàng trên, panel thứ ba trải ngang hàng dưới — ba panel không chia
    # đều cho lưới 2×2, để panel cuối rộng gấp đôi vừa lấp chỗ trống vừa hợp lý
    # vì nó có hai trục tung.
    fig = plt.figure(figsize=(11, 8.2))
    gs = fig.add_gridspec(2, 2, hspace=0.42, wspace=0.28)
    fig.suptitle("Ablation — đóng góp thực tế của từng bộ phận",
                 fontsize=12.5, fontweight="bold", y=0.98)

    # --- 1. căn chỉnh ---
    ax = fig.add_subplot(gs[0, 0])
    keys, ten = ["no_align", "baseline"], ["Chỉ cắt hộp", "Căn chỉnh\n5 điểm mốc"]
    r1 = [d[k]["rank1"] for k in keys]
    dr = [d[k]["dir"]["0.01"] for k in keys]
    x = np.arange(2)
    ax.bar(x - 0.19, r1, width=0.36, color="#3b82f6", label="rank-1 (đóng)")
    ax.bar(x + 0.19, dr, width=0.36, color="#8b5cf6", label="DIR@FAR=1% (mở)")
    ax.set_xticks(x, ten, fontsize=9)
    ax.set_ylabel("tỉ lệ nhận đúng", fontsize=9)
    ax.set_title("1. Căn chỉnh khuôn mặt", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 1.16)
    for i, (a, c) in enumerate(zip(r1, dr)):
        ax.text(i - 0.19, a + 0.025, f"{a:.3f}", ha="center", fontsize=9, fontweight="bold")
        ax.text(i + 0.19, c + 0.025, f"{c:.3f}", ha="center", fontsize=9, fontweight="bold")
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(axis="y", alpha=.25)
    ax.set_axisbelow(True)

    # --- 2. cổng chất lượng ---
    ax = fig.add_subplot(gs[0, 1])
    keys, ten = ["baseline", "gate_enroll"], ["Nhận mọi ảnh", "Lọc ảnh\nđăng ký"]
    r1 = [d[k]["rank1"] for k in keys]
    dr = [d[k]["dir"]["0.01"] for k in keys]
    ax.bar(x - 0.19, r1, width=0.36, color="#3b82f6", label="rank-1 (đóng)")
    ax.bar(x + 0.19, dr, width=0.36, color="#8b5cf6", label="DIR@FAR=1% (mở)")
    ax.set_xticks(x, ten, fontsize=9)
    ax.set_title("2. Cổng chất lượng ảnh đăng ký", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 1.16)
    for i, (a, c) in enumerate(zip(r1, dr)):
        ax.text(i - 0.19, a + 0.025, f"{a:.3f}", ha="center", fontsize=9, fontweight="bold")
        ax.text(i + 0.19, c + 0.025, f"{c:.3f}", ha="center", fontsize=9, fontweight="bold")
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(axis="y", alpha=.25)
    ax.set_axisbelow(True)

    # --- 3. bám vết (trải ngang hàng dưới) ---
    ax = fig.add_subplot(gs[1, :])
    tr = d["tracking"]
    ten = ["Từng khung độc lập", "Bám vết + bỏ phiếu"]
    acc = [tr["no_tracking"]["accuracy"], tr["with_tracking"]["accuracy"]]
    flips = [tr["no_tracking"]["flips_per_100_frames"],
             tr["with_tracking"]["flips_per_100_frames"]]
    ax.bar(x - 0.16, acc, width=0.30, color="#3b82f6", label="độ chính xác")
    ax.set_xticks(x, ten, fontsize=10)
    ax.set_ylabel("độ chính xác", fontsize=9)
    ax.set_ylim(0, 1.18)
    ax.set_title("3. Bám vết + bỏ phiếu đa số — đổi 0,2 giây chờ lấy màn hình hết nhấp nháy",
                 fontsize=11, fontweight="bold")
    for i, a in enumerate(acc):
        ax.text(i - 0.16, a + 0.03, f"{a:.3f}", ha="center", fontsize=10, fontweight="bold")
    ax.grid(axis="y", alpha=.25)
    ax.set_axisbelow(True)
    ax2 = ax.twinx()
    ax2.bar(x + 0.16, flips, width=0.30, color="#ef4444",
            label="số lần nhãn nhảy / 100 khung")
    ax2.set_ylabel("số lần nhãn nhảy / 100 khung", color="#ef4444", fontsize=9)
    ax2.tick_params(axis="y", labelcolor="#ef4444", labelsize=8)
    ax2.set_ylim(0, max(flips) * 1.3)
    for i, f in enumerate(flips):
        ax2.text(i + 0.16, f + max(flips) * 0.05, f"{f:.1f}", ha="center",
                 fontsize=10, color="#ef4444", fontweight="bold")
    # Hai trục tung nên chú giải phải gộp thủ công, nếu không mỗi trục vẽ một
    # khung chú giải riêng đè lên nhau.
    cot, nhan = ax.get_legend_handles_labels()
    cot2, nhan2 = ax2.get_legend_handles_labels()
    ax.legend(cot + cot2, nhan + nhan2, fontsize=9, loc="center",
              framealpha=0.95, ncol=1)

    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {out.name}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("Vẽ biểu đồ bố cục A4 dọc cho báo cáo:")
    ve_so_sanh_mo_hinh(REPORTS / "bc_so_sanh_mo_hinh.png")
    ve_ablation(REPORTS / "bc_ablation.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
