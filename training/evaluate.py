"""Đánh giá đúng chuẩn — ba giao thức, không rò rỉ danh tính.

Mọi danh tính dùng ở đây đều nằm trong tập `test`/`stranger` của manifest, tức
là chưa từng xuất hiện lúc huấn luyện.

Ba giao thức, đo ba thứ khác nhau
---------------------------------
1. **Xác thực 1:1 (verification)** — giao thức LFW. Ghép cặp ảnh, hỏi "hai ảnh
   này có phải cùng một người không". Cho ra ROC, AUC, EER, và **TAR@FAR** —
   chỉ số mà giới nghiên cứu thực sự báo cáo, vì accuracy đơn thuần không nói
   được hệ thống sai kiểu nào.

2. **Định danh 1:N đóng (closed-set)** — mọi người truy vấn đều đã đăng ký. Cho
   ra rank-1, rank-5 và **đường cong CMC**.

3. **Định danh 1:N mở (open-set)** — có cả người lạ chưa đăng ký trà trộn. Đây
   mới đúng bài toán điểm danh: hệ thống phải nhận ra người quen VÀ từ chối
   người lạ. Cho ra **DIR@FAR**: ở mức chấp nhận x% người lạ bị nhận nhầm thì
   nhận đúng được bao nhiêu % người quen.

Chạy:
    python -m training.evaluate --backbone facenet
    python -m training.evaluate --backbone onnx --weights models/mobilefacenet.onnx
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import auc, roc_curve

from engine.align import align_face
from engine.detect import build_detector
from engine.embed import build_embedder
from engine.settings import DetectSettings, EmbedSettings
from training.split import (DEFAULT_MANIFEST, assert_disjoint, identities,
                            image_paths, load_manifest)

REPORTS = Path("reports")


# --------------------------------------------------------------------- trích đặc trưng
def embed_identity_images(paths, detector, embedder, cache: dict) -> np.ndarray:
    """Trích đặc trưng cho một loạt ảnh, có cache để không tính lại."""
    chips, keys = [], []
    for p in paths:
        key = str(p)
        if key in cache:
            continue
        img = cv2.imread(str(p))
        if img is None:
            continue
        det = detector.detect_largest(img)
        if det is None:
            continue
        chip = align_face(img, det.landmarks, embedder.image_size)
        if chip is None:
            continue
        chips.append(chip)
        keys.append(key)
    if chips:
        for key, vec in zip(keys, embedder.embed(chips)):
            cache[key] = vec
    return np.array([cache[str(p)] for p in paths if str(p) in cache], dtype=np.float32)


# --------------------------------------------------------------- 1. xác thực 1:1
def protocol_verification(manifest, detector, embedder, cache, rng, n_pairs=3000):
    """Ghép cặp genuine/impostor rồi đo ROC, AUC, EER, TAR@FAR."""
    names = identities(manifest, "test") + identities(manifest, "stranger")
    vecs: dict[str, np.ndarray] = {}
    for name in names:
        v = embed_identity_images(image_paths(manifest, name), detector, embedder, cache)
        if len(v) >= 2:
            vecs[name] = v
    usable = sorted(vecs)
    if len(usable) < 4:
        return None

    scores, labels = [], []
    half = n_pairs // 2
    for _ in range(half):                                   # cặp cùng người
        name = rng.choice(usable)
        i, j = rng.choice(len(vecs[name]), size=2, replace=False)
        scores.append(float(vecs[name][i] @ vecs[name][j])); labels.append(1)
    for _ in range(half):                                   # cặp khác người
        a, b = rng.choice(len(usable), size=2, replace=False)
        va, vb = vecs[usable[a]], vecs[usable[b]]
        scores.append(float(va[rng.integers(len(va))] @ vb[rng.integers(len(vb))])); labels.append(0)

    scores, labels = np.array(scores), np.array(labels)
    fpr, tpr, thr = roc_curve(labels, scores)
    roc_auc = float(auc(fpr, tpr))
    fnr = 1 - tpr
    k = int(np.nanargmin(np.abs(fnr - fpr)))
    eer, eer_thr = float((fpr[k] + fnr[k]) / 2), float(thr[k])

    tar = {}
    for far_target in (1e-1, 1e-2, 1e-3):
        idx = np.searchsorted(fpr, far_target, side="right") - 1
        tar[far_target] = float(tpr[max(idx, 0)])

    acc = float(np.max([( (scores >= t) == labels ).mean() for t in thr[::max(1, len(thr)//400)]]))
    return {"auc": roc_auc, "eer": eer, "eer_threshold": eer_thr, "accuracy": acc,
            "tar": tar, "n_pairs": len(scores), "n_identities": len(usable),
            "curve": (fpr, tpr)}


# ------------------------------------------------------ 2 & 3. định danh 1:N
def build_gallery(manifest, detector, embedder, cache):
    """Vector đăng ký cho từng người trong tập test (đóng vai người đã ghi danh)."""
    root = Path(manifest["source"])
    gal_vecs, gal_labels = [], []
    for name, rels in manifest["test_gallery"].items():
        v = embed_identity_images([root / r for r in rels], detector, embedder, cache)
        for vec in v:
            gal_vecs.append(vec); gal_labels.append(name)
    return (np.array(gal_vecs, dtype=np.float32), gal_labels) if gal_vecs else (None, [])


def _best_per_person(sims: np.ndarray, gal_labels: list[str]):
    """Gộp điểm theo người: mỗi người lấy vector giống nhất."""
    best: dict[str, float] = {}
    for s, lab in zip(sims, gal_labels):
        if lab not in best or s > best[lab]:
            best[lab] = float(s)
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
    return ranked


def protocol_identification(manifest, detector, embedder, cache, gal, gal_labels):
    """Closed-set: rank-1, rank-5, CMC."""
    root = Path(manifest["source"])
    people = sorted(set(gal_labels))
    ranks = []
    for name, rels in manifest["test_probe"].items():
        if name not in people:
            continue
        for v in embed_identity_images([root / r for r in rels], detector, embedder, cache):
            ranked = _best_per_person(gal @ v, gal_labels)
            pos = next((i for i, (lab, _) in enumerate(ranked) if lab == name), None)
            if pos is not None:
                ranks.append(pos + 1)
    if not ranks:
        return None
    ranks = np.array(ranks)
    max_rank = min(len(people), 10)
    cmc = [float((ranks <= r).mean()) for r in range(1, max_rank + 1)]
    return {"rank1": cmc[0], "rank5": cmc[min(4, len(cmc) - 1)],
            "n_probe": len(ranks), "n_gallery_people": len(people), "cmc": cmc}


def protocol_openset(manifest, detector, embedder, cache, gal, gal_labels):
    """Open-set: người quen phải nhận đúng, người lạ phải bị từ chối. DIR@FAR."""
    root = Path(manifest["source"])
    people = set(gal_labels)

    genuine = []      # (điểm cao nhất, có đúng người không)
    for name, rels in manifest["test_probe"].items():
        if name not in people:
            continue
        for v in embed_identity_images([root / r for r in rels], detector, embedder, cache):
            ranked = _best_per_person(gal @ v, gal_labels)
            genuine.append((ranked[0][1], ranked[0][0] == name))

    impostor = []     # điểm cao nhất của người LẠ với gallery
    for name in identities(manifest, "stranger"):
        for v in embed_identity_images(image_paths(manifest, name), detector, embedder, cache):
            ranked = _best_per_person(gal @ v, gal_labels)
            impostor.append(ranked[0][1])

    if not genuine or not impostor:
        return None

    g_scores = np.array([s for s, _ in genuine])
    g_correct = np.array([c for _, c in genuine])
    i_scores = np.array(impostor)

    dir_at = {}
    for far_target in (0.10, 0.05, 0.01):
        # Ngưỡng sao cho đúng far_target phần người lạ vượt qua.
        thr = float(np.quantile(i_scores, 1.0 - far_target))
        dir_at[far_target] = float(((g_scores >= thr) & g_correct).mean())

    # Ngưỡng vận hành đề xuất: cân bằng giữa bỏ sót người quen và nhận nhầm người lạ.
    grid = np.linspace(min(i_scores.min(), g_scores.min()), g_scores.max(), 300)
    frr = np.array([1.0 - ((g_scores >= t) & g_correct).mean() for t in grid])
    far = np.array([(i_scores >= t).mean() for t in grid])
    best = int(np.argmin(np.abs(far - frr)))

    return {"dir": dir_at, "n_genuine": len(g_scores), "n_impostor": len(i_scores),
            "n_strangers": len(identities(manifest, "stranger")),
            "operating_threshold": float(grid[best]),
            "far_at_op": float(far[best]), "frr_at_op": float(frr[best]),
            "curve": (grid, far, frr)}


# --------------------------------------------------------------------- vẽ biểu đồ
def plot_all(tag, ver, ident, opn):
    REPORTS.mkdir(parents=True, exist_ok=True)
    n = sum(x is not None for x in (ver, ident, opn))
    fig, axes = plt.subplots(1, max(n, 1), figsize=(5.2 * max(n, 1), 4.4))
    axes = np.atleast_1d(axes)
    i = 0
    if ver:
        fpr, tpr = ver["curve"]
        ax = axes[i]; i += 1
        ax.plot(fpr, tpr, lw=2, label=f"AUC = {ver['auc']:.4f}")
        ax.plot([0, 1], [0, 1], "--", color="gray", lw=1)
        ax.set_xscale("symlog", linthresh=1e-3)
        ax.set_xlabel("FAR (nhận nhầm người lạ)"); ax.set_ylabel("TAR (nhận đúng người quen)")
        ax.set_title(f"Xác thực 1:1 — {tag}")
        ax.legend(loc="lower right"); ax.grid(alpha=.3)
    if ident:
        ax = axes[i]; i += 1
        r = np.arange(1, len(ident["cmc"]) + 1)
        ax.plot(r, ident["cmc"], "o-", lw=2)
        ax.set_ylim(0, 1.02); ax.set_xlabel("Hạng"); ax.set_ylabel("Tỉ lệ nhận đúng")
        ax.set_title(f"CMC closed-set — rank-1 = {ident['rank1']:.3f}")
        ax.grid(alpha=.3)
    if opn:
        grid, far, frr = opn["curve"]
        ax = axes[i]; i += 1
        ax.plot(grid, far, lw=2, label="FAR — nhận nhầm người lạ")
        ax.plot(grid, frr, lw=2, label="FRR — bỏ sót người quen")
        ax.axvline(opn["operating_threshold"], color="crimson", ls="--",
                   label=f"ngưỡng đề xuất = {opn['operating_threshold']:.3f}")
        ax.set_xlabel("Ngưỡng cosine"); ax.set_ylabel("Tỉ lệ lỗi")
        ax.set_title("Open-set — điểm cân bằng")
        ax.legend(fontsize=8); ax.grid(alpha=.3)
    fig.tight_layout()
    out = REPORTS / f"{tag}_eval.png"
    fig.savefig(out, dpi=120); plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--backbone", choices=["facenet", "onnx", "torch"], default="facenet")
    ap.add_argument("--weights", default="")
    ap.add_argument("--detector", default="yunet")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--pairs", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    manifest = load_manifest(args.manifest)
    assert_disjoint(manifest)
    tag = args.tag or args.backbone

    detector = build_detector(DetectSettings(backend=args.detector))
    embedder = build_embedder(EmbedSettings(backend=args.backbone, weights=args.weights))
    cache: dict[str, np.ndarray] = {}
    rng = np.random.default_rng(args.seed)

    print(f"Mô hình: {embedder.name} (dim={embedder.dim}, ảnh vào {embedder.image_size}px)"
          f"  ·  detector: {detector.name}")
    print(f"Danh tính: test={len(identities(manifest,'test'))}  "
          f"stranger={len(identities(manifest,'stranger'))}  "
          f"(train={len(identities(manifest,'train'))} — KHÔNG dùng ở đây)\n")

    ver = protocol_verification(manifest, detector, embedder, cache, rng, args.pairs)
    gal, gal_labels = build_gallery(manifest, detector, embedder, cache)
    ident = protocol_identification(manifest, detector, embedder, cache, gal, gal_labels) if gal is not None else None
    opn = protocol_openset(manifest, detector, embedder, cache, gal, gal_labels) if gal is not None else None

    if ver:
        print("1) XÁC THỰC 1:1")
        print(f"   AUC={ver['auc']:.4f}  EER={ver['eer']*100:.2f}%  acc={ver['accuracy']:.4f}"
              f"  (ngưỡng EER={ver['eer_threshold']:.3f}, {ver['n_pairs']} cặp)")
        for far, t in sorted(ver["tar"].items(), reverse=True):
            print(f"   TAR@FAR={far:<7g} = {t:.4f}")
    if ident:
        print(f"\n2) ĐỊNH DANH ĐÓNG (1:N, N={ident['n_gallery_people']})")
        print(f"   rank-1={ident['rank1']:.4f}  rank-5={ident['rank5']:.4f}"
              f"  ({ident['n_probe']} ảnh truy vấn)")
    if opn:
        print(f"\n3) ĐỊNH DANH MỞ ({opn['n_genuine']} người quen, {opn['n_impostor']} lượt người lạ"
              f" từ {opn['n_strangers']} người)")
        for far, d in sorted(opn["dir"].items(), reverse=True):
            print(f"   DIR@FAR={far:<5g} = {d:.4f}")
        print(f"   ngưỡng vận hành đề xuất = {opn['operating_threshold']:.3f}"
              f"  (FAR={opn['far_at_op']:.3f}, FRR={opn['frr_at_op']:.3f})")

    png = plot_all(tag, ver, ident, opn)
    REPORTS.mkdir(parents=True, exist_ok=True)
    summary = {
        "tag": tag, "backbone": embedder.name, "detector": detector.name,
        "manifest": args.manifest,
        "verification": {k: v for k, v in (ver or {}).items() if k != "curve"},
        "identification": {k: v for k, v in (ident or {}).items() if k != "curve"},
        "openset": {k: v for k, v in (opn or {}).items() if k != "curve"},
    }
    js = REPORTS / f"{tag}_eval.json"
    js.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(f"\n-> {png}\n-> {js}")


if __name__ == "__main__":
    main()
