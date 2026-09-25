"""Ablation study — tắt từng bộ phận để đo xem nó thực sự đóng góp bao nhiêu.

    python -m training.ablation --backbone onnx --weights models/mobilefacenet_distill_casia.onnx

Vì sao cần bài này
------------------
Báo cáo nói "có căn chỉnh khuôn mặt", "có cổng chất lượng", "có bám vết" thì dễ.
Chứng minh từng thứ đáng tồn tại thì phải tắt nó đi rồi đo lại trên **cùng một
tập kiểm tra, cùng một mô hình**. Chênh lệch chính là đóng góp của bộ phận đó.

Không làm bước này thì mọi bộ phận trong hệ thống đều chỉ là niềm tin.

Ba thí nghiệm
-------------
1. **Căn chỉnh** — dùng phép biến đổi tương tự theo 5 điểm mốc, so với chỉ cắt hộp
   bao rồi thu nhỏ. Đo rank-1 và DIR@FAR.
2. **Cổng chất lượng** — bỏ ảnh mờ / thiếu sáng / lệch mặt trước khi đăng ký, so
   với nhận tất. Đo rank-1, DIR@FAR và số ảnh bị loại.
3. **Bám vết + bỏ phiếu** — dựng chuỗi khung hình giả lập từ ảnh của một người,
   so nhãn từng khung độc lập với nhãn sau khi bỏ phiếu đa số. Đo độ chính xác và
   **số lần nhãn nhảy** — thứ người dùng nhìn thấy trực tiếp trên màn hình.

Kết quả ghi ra `reports/ablation.json` và `reports/ablation.png`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from engine import quality as quality_mod
from engine.align import align_face, crop_face
from engine.detect import build_detector
from engine.embed import build_embedder
from engine.settings import DetectSettings, EmbedSettings, QualitySettings, TrackSettings
from engine.track import FaceTracker
from engine.types import Identity
from training.split import (DEFAULT_MANIFEST, identities, image_paths,
                            load_manifest)

REPORTS = Path("reports")

# Cửa sổ lệnh mặc định của Windows dùng bảng mã cp1252, không có chữ Việt có dấu.
# Thiếu dòng này thì script chạy đúng nhưng chết ngay ở lệnh in đầu tiên vì
# UnicodeEncodeError — lỗi vô nghĩa với người dùng, che mất kết quả thật.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ===================================================================== trích đặc trưng
def embed_images(paths, detector, embedder, *, use_align: bool,
                 quality_gate: bool, qs: QualitySettings, stats: dict) -> np.ndarray:
    """Trích đặc trưng cho một loạt ảnh dưới một cấu hình cụ thể.

    `stats` được cộng dồn tại chỗ để biết mỗi cấu hình loại bỏ bao nhiêu ảnh và
    vì lý do gì — con số này quan trọng ngang kết quả nhận diện, vì một cổng chất
    lượng quá gắt sẽ đẹp số nhưng bắt người dùng chụp lại mãi.
    """
    vecs = []
    for p in paths:
        stats["seen"] += 1
        img = cv2.imread(str(p))
        if img is None:
            stats["unreadable"] += 1
            continue
        det = detector.detect_largest(img)
        if det is None:
            stats["no_face"] += 1
            continue

        if quality_gate:
            report = quality_mod.assess(img, det, qs)
            if not report.passed:
                stats["rejected_quality"] += 1
                reasons = stats.setdefault("reasons", {})
                for why in (report.reasons or ["không rõ"]):
                    reasons[why] = reasons.get(why, 0) + 1
                continue

        if use_align:
            chip = align_face(img, det.landmarks, embedder.image_size)
        else:
            # Không căn chỉnh: cắt hộp bao rồi thu nhỏ. Mặt nghiêng hay nghiêng
            # đầu sẽ giữ nguyên độ lệch, mắt mũi mỗi ảnh một chỗ.
            chip = crop_face(img, det, embedder.image_size)
        if chip is None:
            stats["no_chip"] += 1
            continue
        vecs.append(chip)

    if not vecs:
        return np.zeros((0, embedder.dim), dtype=np.float32)
    stats["used"] += len(vecs)
    return embedder.embed(vecs)


# ===================================================================== đo nhận diện
def best_per_person(sims: np.ndarray, labels: list[str]) -> list[tuple[str, float]]:
    best: dict[str, float] = {}
    for s, lab in zip(sims, labels):
        if lab not in best or s > best[lab]:
            best[lab] = float(s)
    return sorted(best.items(), key=lambda kv: kv[1], reverse=True)


def run_config(manifest, detector, embedder, *, use_align: bool,
               quality_gate: bool, qs: QualitySettings,
               gate_probe: bool | None = None) -> dict:
    """Chạy trọn một cấu hình: dựng gallery, đo closed-set và open-set.

    `gate_probe` tách riêng việc lọc chất lượng ở hai phía:

      * `True`  — lọc cả ảnh đăng ký lẫn ảnh truy vấn.
      * `False` — chỉ lọc ảnh ĐĂNG KÝ, giữ nguyên toàn bộ ảnh truy vấn.

    Vì sao phải tách: lọc cả hai phía thì số ảnh probe tụt từ 632 xuống 452, tức
    là nhánh có cổng được chấm trên một tập test ĐÃ BỊ LÀM DỄ ĐI — mọi ảnh khó
    đều bị loại trước khi chấm. So rank-1 kiểu đó là so lệch, và nó sẽ thổi phồng
    hoặc bóp méo đóng góp thật của cổng chất lượng.

    Chỉ lọc phía đăng ký mới trả lời đúng câu hỏi đáng hỏi: *ảnh mẫu sạch hơn có
    làm hệ thống nhận diện tốt hơn không*, trên cùng một tập câu hỏi.
    """
    root = Path(manifest["source"])
    if gate_probe is None:
        gate_probe = quality_gate

    def new_stats():
        return {"seen": 0, "used": 0, "unreadable": 0, "no_face": 0,
                "no_chip": 0, "rejected_quality": 0}

    # Thống kê tách theo TỪNG PHA. Gộp chung một bộ đếm là tự đặt bẫy: cổng chỉ
    # áp lên ảnh đăng ký, nhưng mẫu số lại gồm cả ảnh truy vấn không hề bị lọc,
    # nên tỉ lệ loại in ra sẽ nhỏ hơn thực tế mấy lần.
    s_gal, s_probe = new_stats(), new_stats()
    t0 = time.perf_counter()

    def embed(paths, gate=None, stats=None):
        return embed_images(paths, detector, embedder, use_align=use_align,
                            quality_gate=quality_gate if gate is None else gate,
                            qs=qs, stats=stats if stats is not None else s_probe)

    # --- gallery: những người "đã đăng ký" ---
    gal_vecs, gal_labels = [], []
    for name, rels in manifest["test_gallery"].items():
        for v in embed([root / r for r in rels], stats=s_gal):
            gal_vecs.append(v)
            gal_labels.append(name)
    if not gal_vecs:
        return {"error": "gallery rỗng"}
    gal = np.array(gal_vecs, dtype=np.float32)
    people = set(gal_labels)

    # --- probe: người quen đến điểm danh ---
    ranks, genuine = [], []
    for name, rels in manifest["test_probe"].items():
        if name not in people:
            continue
        for v in embed([root / r for r in rels], gate=gate_probe):
            ranked = best_per_person(gal @ v, gal_labels)
            pos = next((i for i, (lab, _) in enumerate(ranked) if lab == name), None)
            if pos is not None:
                ranks.append(pos + 1)
            genuine.append((ranked[0][1], ranked[0][0] == name))

    # --- người lạ: phải bị từ chối ---
    impostor = []
    for name in identities(manifest, "stranger"):
        for v in embed(image_paths(manifest, name), gate=gate_probe):
            impostor.append(best_per_person(gal @ v, gal_labels)[0][1])

    if not ranks or not impostor:
        return {"error": "không đủ dữ liệu"}

    ranks = np.array(ranks)
    g_scores = np.array([s for s, _ in genuine])
    g_correct = np.array([c for _, c in genuine])
    i_scores = np.array(impostor)

    dir_at = {}
    for far in (0.10, 0.01):
        thr = float(np.quantile(i_scores, 1.0 - far))
        dir_at[str(far)] = float(((g_scores >= thr) & g_correct).mean())

    return {
        "rank1": float((ranks <= 1).mean()),
        "rank5": float((ranks <= 5).mean()),
        "dir": dir_at,
        # Khoảng cách giữa điểm của người quen và người lạ: càng rộng thì việc
        # chọn ngưỡng càng dễ và hệ thống càng ít nhạy cảm với ngưỡng.
        "margin": float(g_scores[g_correct].mean() - i_scores.mean()) if g_correct.any() else 0.0,
        "n_gallery": len(gal_vecs), "n_probe": len(ranks), "n_impostor": len(i_scores),
        "n_enrolled_people": len(people),
        "enroll_images": s_gal, "probe_images": s_probe,
        # Tỉ lệ ảnh ĐĂNG KÝ bị cổng loại — chia đúng cho số ảnh đăng ký, không
        # chia cho tổng số ảnh đã xem.
        "enroll_reject_rate": s_gal["rejected_quality"] / max(s_gal["seen"], 1),
        "seconds": round(time.perf_counter() - t0, 1),
    }


# ===================================================================== bám vết
def degrade(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Làm ảnh xấu đi như một khung hình webcam thật: mờ do chuyển động, nhiễu,
    lệch sáng. Không có bước này thì mọi khung đều đẹp như ảnh chụp studio và
    việc bỏ phiếu chẳng có gì để sửa."""
    out = img
    k = int(rng.choice([1, 3, 5, 7]))
    if k > 1:
        out = cv2.GaussianBlur(out, (k, k), 0)
    gain = float(rng.uniform(0.65, 1.35))
    out = np.clip(out.astype(np.float32) * gain, 0, 255)
    out = np.clip(out + rng.normal(0, rng.uniform(2, 14), out.shape), 0, 255)
    return out.astype(np.uint8)


def run_tracking(manifest, detector, embedder, *, threshold: float,
                 n_frames: int = 40, seed: int = 42) -> dict:
    """So sánh nhãn từng khung độc lập với nhãn sau khi bám vết + bỏ phiếu.

    Dựng chuỗi khung hình giả lập từ ảnh probe của từng người rồi làm xấu đi từng
    khung. Đây không phải video thật, nhưng nó tái hiện đúng thứ mà bỏ phiếu sinh
    ra để chống: một vài khung xấu cho ra nhãn sai giữa một chuỗi khung đúng.
    """
    root = Path(manifest["source"])
    rng = np.random.default_rng(seed)
    qs = QualitySettings()
    stats = {"seen": 0, "used": 0, "unreadable": 0, "no_face": 0,
             "no_chip": 0, "rejected_quality": 0}

    # Gallery dựng ở cấu hình tốt nhất — bài này chỉ đo phần thời gian.
    gal_vecs, gal_labels = [], []
    for name, rels in manifest["test_gallery"].items():
        for v in embed_images([root / r for r in rels], detector, embedder,
                              use_align=True, quality_gate=False, qs=qs, stats=stats):
            gal_vecs.append(v)
            gal_labels.append(name)
    gal = np.array(gal_vecs, dtype=np.float32)
    people = set(gal_labels)

    frame_correct = frame_total = frame_flips = 0
    vote_correct = vote_total = vote_flips = 0
    confirm_delays = []

    for name, rels in manifest["test_probe"].items():
        if name not in people:
            continue
        srcs = [cv2.imread(str(root / r)) for r in rels]
        srcs = [s for s in srcs if s is not None]
        if not srcs:
            continue

        tracker = FaceTracker(TrackSettings())
        prev_frame_label = prev_vote_label = None
        first_confirm = None

        for f in range(n_frames):
            img = degrade(srcs[f % len(srcs)], rng)
            det = detector.detect_largest(img)
            if det is None:
                tracker.update([])
                continue

            chip = align_face(img, det.landmarks, embedder.image_size)
            if chip is None:
                tracker.update([])
                continue
            v = embedder.embed_one(chip)

            ranked = best_per_person(gal @ v, gal_labels)
            lab, score = ranked[0]
            raw_label = lab if score >= threshold else Identity.UNKNOWN

            # --- (a) không bám vết: tin ngay nhãn của khung này ---
            frame_total += 1
            frame_correct += int(raw_label == name)
            if prev_frame_label is not None and raw_label != prev_frame_label:
                frame_flips += 1
            prev_frame_label = raw_label

            # --- (b) có bám vết: bỏ phiếu đa số trong cửa sổ trượt ---
            tracks = tracker.update([det])
            if not tracks:
                continue
            t = tracks[0]
            tracker.vote(t, Identity(label=raw_label, score=float(score)))
            voted = t.identity.label

            vote_total += 1
            vote_correct += int(voted == name)
            if prev_vote_label is not None and voted != prev_vote_label:
                vote_flips += 1
            prev_vote_label = voted

            if t.confirmed and first_confirm is None:
                first_confirm = f + 1

        if first_confirm:
            confirm_delays.append(first_confirm)

    return {
        "threshold": threshold, "frames_per_person": n_frames,
        "no_tracking": {
            "accuracy": frame_correct / max(frame_total, 1),
            "label_flips": frame_flips,
            "flips_per_100_frames": 100 * frame_flips / max(frame_total, 1),
        },
        "with_tracking": {
            "accuracy": vote_correct / max(vote_total, 1),
            "label_flips": vote_flips,
            "flips_per_100_frames": 100 * vote_flips / max(vote_total, 1),
        },
        # Cái giá của bỏ phiếu: phải chờ vài khung mới dám chốt danh tính.
        "confirm_after_frames": (float(np.mean(confirm_delays)) if confirm_delays else None),
        "people_confirmed": len(confirm_delays),
        "frames_evaluated": frame_total,
    }


# ===================================================================== biểu đồ
def draw(results: dict, out: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    fig.suptitle("Ablation — đóng góp thực tế của từng bộ phận", fontsize=13, fontweight="bold")

    # --- 1. căn chỉnh ---
    ax = axes[0]
    keys = ["no_align", "baseline"]
    names = ["Chỉ cắt hộp", "Căn chỉnh\n5 điểm mốc"]
    r1 = [results[k]["rank1"] for k in keys]
    dirs = [results[k]["dir"]["0.01"] for k in keys]
    x = np.arange(2)
    ax.bar(x - 0.19, r1, width=0.36, color="#3b82f6", label="rank-1 (đóng)")
    ax.bar(x + 0.19, dirs, width=0.36, color="#8b5cf6", label="DIR@FAR=1% (mở)")
    ax.set_xticks(x, names)
    ax.set_ylabel("tỉ lệ nhận đúng")
    ax.set_title("1. Căn chỉnh khuôn mặt")
    ax.set_ylim(0, 1.12)
    for i, (a, d) in enumerate(zip(r1, dirs)):
        ax.text(i - 0.19, a + 0.02, f"{a:.3f}", ha="center", fontsize=9, fontweight="bold")
        ax.text(i + 0.19, d + 0.02, f"{d:.3f}", ha="center", fontsize=9, fontweight="bold")
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(axis="y", alpha=0.25)

    # --- 2. cổng chất lượng ---
    # Dùng nhánh `gate_enroll` (chỉ lọc phía đăng ký) vì đó là nhánh duy nhất
    # chấm trên cùng một tập probe với mốc so sánh.
    ax = axes[1]
    keys = ["baseline", "gate_enroll"]
    names = ["Nhận mọi ảnh", "Lọc ảnh\nđăng ký"]
    r1 = [results[k]["rank1"] for k in keys]
    dirs = [results[k]["dir"]["0.01"] for k in keys]
    x = np.arange(2)
    ax.bar(x - 0.19, r1, width=0.36, color="#3b82f6", label="rank-1 (đóng)")
    ax.bar(x + 0.19, dirs, width=0.36, color="#8b5cf6", label="DIR@FAR=1% (mở)")
    ax.set_xticks(x, names)
    ax.set_ylim(0, 1.12)
    ax.set_title("2. Cổng chất lượng ảnh đăng ký")
    for i, (a, d) in enumerate(zip(r1, dirs)):
        ax.text(i - 0.19, a + 0.02, f"{a:.3f}", ha="center", fontsize=9, fontweight="bold")
        ax.text(i + 0.19, d + 0.02, f"{d:.3f}", ha="center", fontsize=9, fontweight="bold")
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(axis="y", alpha=0.25)

    # --- 3. bám vết ---
    ax = axes[2]
    tr = results["tracking"]
    names = ["Từng khung\nđộc lập", "Bám vết +\nbỏ phiếu"]
    acc = [tr["no_tracking"]["accuracy"], tr["with_tracking"]["accuracy"]]
    flips = [tr["no_tracking"]["flips_per_100_frames"],
             tr["with_tracking"]["flips_per_100_frames"]]
    x = np.arange(2)
    ax.bar(x - 0.19, acc, width=0.36, color="#3b82f6", label="độ chính xác")
    ax.set_ylim(0, 1.12)
    ax.set_xticks(x, names)
    ax.set_title("3. Bám vết + bỏ phiếu đa số")
    for i, a in enumerate(acc):
        ax.text(i - 0.19, a + 0.02, f"{a:.3f}", ha="center", fontsize=9, fontweight="bold")
    ax2 = ax.twinx()
    ax2.bar(x + 0.19, flips, width=0.36, color="#ef4444", label="nhãn nhảy /100 khung")
    ax2.set_ylabel("số lần nhãn nhảy / 100 khung", color="#ef4444")
    ax2.tick_params(axis="y", labelcolor="#ef4444")
    # Chừa khoảng trống phía trên: để mặc định thì cột cao nhất chạm trần và nhãn
    # số của nó đè lên tiêu đề.
    ax2.set_ylim(0, max(flips) * 1.25 if max(flips) else 1)
    for i, f in enumerate(flips):
        ax2.text(i + 0.19, f + max(flips) * 0.04, f"{f:.1f}", ha="center",
                 fontsize=9, color="#ef4444", fontweight="bold")
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ===================================================================== main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    # PHẢI dùng manifest trỏ vào ảnh GỐC, không phải data/aligned_big.
    #
    # data/aligned_big chứa các chip 112×112 đã căn chỉnh sẵn từ trước. Đo thí
    # nghiệm "tắt căn chỉnh" trên đó là đo vào chỗ trống: mặt đã được xoay thẳng
    # rồi, tắt hay bật cũng ra gần như nhau, và con số thu được sẽ nói dối rằng
    # căn chỉnh vô dụng. Ảnh gốc LFW (250×250, mặt nghiêng ngả tự nhiên) mới là
    # nơi bước căn chỉnh có việc để làm.
    ap.add_argument("--manifest", default="data/manifest_raw.json",
                    help="manifest trỏ vào ảnh GỐC chưa căn chỉnh")
    ap.add_argument("--backbone", choices=["facenet", "onnx", "torch"], default="onnx")
    ap.add_argument("--weights", default="models/mobilefacenet_distill_casia.onnx")
    ap.add_argument("--detector", choices=["yunet", "mtcnn"], default="yunet")
    ap.add_argument("--threshold", type=float, default=0.55,
                    help="ngưỡng chấp nhận cho thí nghiệm bám vết")
    ap.add_argument("--frames", type=int, default=40)
    ap.add_argument("--tag", default="ablation")
    args = ap.parse_args()

    manifest = load_manifest(args.manifest)
    detector = build_detector(DetectSettings(backend=args.detector))
    embedder = build_embedder(EmbedSettings(backend=args.backbone, weights=args.weights))

    print(f"Mô hình : {args.backbone}  {args.weights}")
    print(f"Detector: {args.detector}")
    print(f"Tập test: {len(manifest['test_gallery'])} người đăng ký · "
          f"{len(identities(manifest, 'stranger'))} người lạ\n")

    qs = QualitySettings()
    results: dict = {}

    configs = [
        ("baseline",     dict(use_align=True,  quality_gate=False),
         "Căn chỉnh, không lọc chất lượng  (mốc so sánh)"),
        ("no_align",     dict(use_align=False, quality_gate=False),
         "TẮT căn chỉnh — chỉ cắt hộp bao"),
        ("gate_enroll",  dict(use_align=True,  quality_gate=True, gate_probe=False),
         "Cổng chất lượng CHỈ ở khâu đăng ký  (so sánh công bằng)"),
        ("quality_gate", dict(use_align=True,  quality_gate=True),
         "Cổng chất lượng ở CẢ hai phía  (tập probe bị làm dễ đi — xem ghi chú)"),
    ]

    for key, kwargs, label in configs:
        print(f"── {label}")
        r = run_config(manifest, detector, embedder, qs=qs, **kwargs)
        results[key] = r
        if "error" in r:
            print(f"   LỖI: {r['error']}\n")
            continue
        g, p = r["enroll_images"], r["probe_images"]
        print(f"   rank-1 {r['rank1']:.4f} · rank-5 {r['rank5']:.4f} · "
              f"DIR@FAR=1% {r['dir']['0.01']:.4f} · khoảng cách điểm {r['margin']:.4f}")
        print(f"   đăng ký: {g['used']}/{g['seen']} ảnh dùng được "
              f"({r['enroll_reject_rate']:.1%} bị cổng loại) → "
              f"{r['n_enrolled_people']} người ghi danh được")
        print(f"   truy vấn: {r['n_probe']} ảnh người quen · "
              f"{r['n_impostor']} ảnh người lạ · {r['seconds']}s\n")

    print("── Bám vết + bỏ phiếu đa số (chuỗi khung giả lập)")
    results["tracking"] = run_tracking(manifest, detector, embedder,
                                       threshold=args.threshold, n_frames=args.frames)
    tr = results["tracking"]
    print(f"   không bám vết: chính xác {tr['no_tracking']['accuracy']:.4f} · "
          f"nhãn nhảy {tr['no_tracking']['flips_per_100_frames']:.1f}/100 khung")
    print(f"   có bám vết   : chính xác {tr['with_tracking']['accuracy']:.4f} · "
          f"nhãn nhảy {tr['with_tracking']['flips_per_100_frames']:.1f}/100 khung")
    if tr["confirm_after_frames"]:
        print(f"   chốt danh tính sau trung bình {tr['confirm_after_frames']:.1f} khung")

    # ---------------------------------------------------------------- kết luận
    print(f"\n{'='*66}\n  TỔNG KẾT — đóng góp của từng bộ phận\n{'='*66}")
    base = results["baseline"]
    if "error" not in base:
        if "error" not in results["no_align"]:
            d = base["rank1"] - results["no_align"]["rank1"]
            print(f"  Căn chỉnh 5 điểm mốc   rank-1 {d:+.4f}  "
                  f"({results['no_align']['rank1']:.4f} → {base['rank1']:.4f})")
        if "error" not in results["gate_enroll"]:
            q = results["gate_enroll"]
            d = q["rank1"] - base["rank1"]
            dd = q["dir"]["0.01"] - base["dir"]["0.01"]
            print(f"  Cổng chất lượng        rank-1 {d:+.4f} · DIR@FAR=1% {dd:+.4f}")
            print(f"     giá phải trả: loại {q['enroll_reject_rate']:.1%} ảnh đăng ký, "
                  f"{base['n_enrolled_people'] - q['n_enrolled_people']} người "
                  f"không ghi danh nổi (hết sạch ảnh đạt)")
    d = tr["with_tracking"]["accuracy"] - tr["no_tracking"]["accuracy"]
    fd = tr["no_tracking"]["flips_per_100_frames"] - tr["with_tracking"]["flips_per_100_frames"]
    print(f"  Bám vết + bỏ phiếu     chính xác {d:+.4f} · "
          f"nhãn nhảy giảm {fd:.1f}/100 khung")

    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"{args.tag}.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    draw(results, REPORTS / f"{args.tag}.png")
    print(f"\nĐã ghi reports/{args.tag}.json và reports/{args.tag}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
