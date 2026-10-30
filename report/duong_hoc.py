"""Vẽ đường học của bốn mô hình do nhóm huấn luyện.

    python -m report.duong_hoc

Vì sao cần hình này
-------------------
Bảng cấu hình huấn luyện cho biết mỗi mô hình chạy bao nhiêu vòng và đạt kết quả
nào ở vòng cuối, nhưng **không cho thấy nó đi tới đó bằng đường nào**. Mà chính
hình dạng đường đi mới giải thích được con số khó hiểu nhất của đề tài: mô hình
ArcFace trên CASIA chạy lâu nhất (128,8 phút) lại cho kết quả thấp nhất (0,7563).

Nhìn đường học thì thấy ngay: nó bị **cắt ngang giữa chừng** lúc còn đang đi lên,
chứ không phải đi ngang rồi dừng. Đó là bằng chứng trực quan cho kết luận "chưa
hội tụ vì không đủ số vòng", thay vì phải suy luận gián tiếp từ ngưỡng vận hành.

Một lưu ý về trục tung bên trái
-------------------------------
Hai nhóm mô hình dùng **hàm mất mát khác nhau về bản chất**: ArcFace cho giá trị
hàng chục (phân loại trên hàng nghìn lớp), còn chưng cất cho giá trị dưới 1 (hồi
quy cosine). Vẽ chung một trục thì đường chưng cất bị ép sát đáy thành một vạch
thẳng. Nên mỗi mô hình được vẽ ở một ô riêng với thang đo riêng — so sánh **hình
dạng** đường đi, không so sánh độ cao giữa hai ô.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"

#: (tên tệp lịch sử, nhãn hiển thị, cách huấn luyện)
MO_HINH = [
    ("mobilefacenet_lfw", "ArcFace · LFW", "từ đầu"),
    ("mobilefacenet_casia", "ArcFace · CASIA", "từ đầu"),
    ("mobilefacenet_distill", "Chưng cất · LFW", "chưng cất"),
    ("mobilefacenet_distill_casia", "Chưng cất · CASIA+LFW", "chưng cất"),
]

MAU_MAT_MAT = "#c2410c"      # cam đất — hàm mất mát khi huấn luyện
MAU_KIEM_DINH = "#1d4ed8"    # xanh — tỉ lệ đúng trên tập kiểm định


def doc(ten: str):
    f = MODELS / f"{ten}_history.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    h = d.get("history") or []
    if not h:
        return None
    return {
        "epoch": [e["epoch"] for e in h],
        "loss": [e.get("loss") for e in h],
        "val": [e.get("val_ver") for e in h],
        "cfg": d.get("config", {}),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    du_lieu = [(ten, nhan, cach, doc(ten)) for ten, nhan, cach in MO_HINH]
    du_lieu = [x for x in du_lieu if x[3]]
    if not du_lieu:
        print("Không đọc được lịch sử huấn luyện nào trong models/")
        return 1

    fig, axes = plt.subplots(2, 2, figsize=(9.4, 7.0))
    fig.suptitle("Đường học của bốn mô hình do nhóm huấn luyện",
                 fontsize=13, fontweight="bold", y=0.975)

    for ax, (ten, nhan, cach, d) in zip(axes.ravel(), du_lieu):
        ep = d["epoch"]
        ax.plot(ep, d["loss"], color=MAU_MAT_MAT, linewidth=2,
                marker="o", markersize=2.6, label="Hàm mất mát (huấn luyện)")
        ax.set_xlabel("Vòng lặp (epoch)", fontsize=9)
        ax.set_ylabel("Hàm mất mát", fontsize=9, color=MAU_MAT_MAT)
        ax.tick_params(axis="y", labelcolor=MAU_MAT_MAT, labelsize=8)
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(alpha=0.25, linewidth=0.6)

        # Trục phải: tỉ lệ xác thực đúng trên tập kiểm định — những người mô hình
        # CHƯA từng thấy lúc học. Đây mới là thứ nói lên mô hình có dùng được không.
        ax2 = ax.twinx()
        ax2.plot(ep, d["val"], color=MAU_KIEM_DINH, linewidth=2,
                 marker="s", markersize=2.6, label="Đúng trên tập kiểm định")
        ax2.set_ylabel("val_ver", fontsize=9, color=MAU_KIEM_DINH)
        ax2.tick_params(axis="y", labelcolor=MAU_KIEM_DINH, labelsize=8)
        ax2.set_ylim(0, 1.0)

        cuoi = d["val"][-1]
        ax.set_title(f"{nhan}  ·  {cach}\n{len(ep)} vòng  →  val_ver {cuoi:.4f}",
                     fontsize=10, pad=7)

        # Đánh dấu mô hình bị cắt ngang lúc còn đang lên.
        if ten == "mobilefacenet_casia":
            ax2.annotate("còn đang lên thì hết vòng",
                         xy=(ep[-1], d["val"][-1]), xytext=(-6, -34),
                         textcoords="offset points", fontsize=8,
                         color=MAU_KIEM_DINH, ha="right",
                         arrowprops=dict(arrowstyle="->", color=MAU_KIEM_DINH,
                                         linewidth=1.1))

    duong, nhan_duong = [], []
    for ax in [axes[0][0], axes[0][0].get_shared_x_axes()]:
        break
    fig.legend(handles=[plt.Line2D([], [], color=MAU_MAT_MAT, marker="o",
                                   markersize=4, linewidth=2),
                        plt.Line2D([], [], color=MAU_KIEM_DINH, marker="s",
                                   markersize=4, linewidth=2)],
               labels=["Hàm mất mát khi huấn luyện (trục trái)",
                       "Tỉ lệ xác thực đúng trên tập kiểm định (trục phải)"],
               loc="lower center", ncol=2, fontsize=9, frameon=False,
               bbox_to_anchor=(0.5, -0.005))

    fig.tight_layout(rect=[0, 0.045, 1, 0.955])
    REPORTS.mkdir(parents=True, exist_ok=True)
    ra = REPORTS / "bc_duong_hoc.png"
    fig.savefig(ra, dpi=170)
    plt.close(fig)
    print(f"Đã ghi: {ra}")
    for ten, nhan, cach, d in du_lieu:
        print(f"  {nhan:<24} {len(d['epoch']):>2} vòng · "
              f"mất mát {d['loss'][0]:.4f} -> {d['loss'][-1]:.4f} · "
              f"val_ver {d['val'][0]:.4f} -> {d['val'][-1]:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
