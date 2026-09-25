"""Danh gia mo hinh: accuracy, precision/recall, confusion matrix, ROC/AUC, FAR-FRR, EER.

Tu dong chia data/aligned theo nguoi thanh gallery / query (seed co dinh).

    python -m src.evaluate --backbone facenet
    python -m src.evaluate --backbone resnet50 --weights models/backbone_arcface.pt

Ket qua -> reports/: classification_report.txt, confusion_matrix.png, roc.png, far_frr.png
"""
import argparse
import random
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import (ConfusionMatrixDisplay, auc, classification_report,
                             confusion_matrix, roc_curve)

from . import config
from .face_utils import embed_faces, load_backbone

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_split(root: Path, test_split: float, seed: int):
    rng = random.Random(seed)
    gallery, query = {}, {}
    for pdir in sorted(d for d in root.iterdir() if d.is_dir()):
        paths = [p for p in pdir.rglob("*") if p.suffix.lower() in IMG_EXT]
        rng.shuffle(paths)
        if len(paths) < 2:
            continue
        k = max(1, int(len(paths) * (1 - test_split)))
        gallery[pdir.name] = paths[:k]
        query[pdir.name] = paths[k:]
    return gallery, query


def embed_paths(model, kind, paths):
    faces = [cv2.imread(str(p)) for p in paths]
    faces = [f for f in faces if f is not None]
    return embed_faces(model, kind, faces)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aligned-root", default=str(config.ALIGNED_DIR))
    ap.add_argument("--backbone", choices=["resnet50", "facenet"], default="facenet")
    ap.add_argument("--weights", default=str(config.MODELS_DIR / "backbone_arcface.pt"))
    ap.add_argument("--test-split", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tag", default=None, help="Nhan cho ten file bao cao (mac dinh = backbone)")
    args = ap.parse_args()

    weights = args.weights if args.backbone == "resnet50" else None
    model, kind = load_backbone(args.backbone, weights)
    root = Path(args.aligned_root)
    gallery_p, query_p = load_split(root, args.test_split, args.seed)
    names = sorted(gallery_p)
    if len(names) < 2:
        raise SystemExit("Can it nhat 2 nguoi co >=2 anh.")

    # Gallery: vector trung binh moi nguoi
    gal_mat = np.stack([embed_paths(model, kind, gallery_p[n]).mean(0) for n in names])
    gal_mat /= np.linalg.norm(gal_mat, axis=1, keepdims=True)

    y_true, y_pred, gen_scores, imp_scores = [], [], [], []
    for gi, n in enumerate(names):
        q = embed_paths(model, kind, query_p[n])
        if len(q) == 0:
            continue
        sims = q @ gal_mat.T                     # (Nq, Nnguoi)
        pred = sims.argmax(1)
        for row, pi in zip(sims, pred):
            y_true.append(gi)
            y_pred.append(int(pi))
            gen_scores.append(float(row[gi]))
            imp_scores.extend(float(row[j]) for j in range(len(names)) if j != gi)

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    acc = (y_true == y_pred).mean()
    print(f"\n=== Closed-set identification ===")
    print(f"Accuracy: {acc:.4f}  ({len(y_true)} anh query, {len(names)} nguoi)")

    # prefix ten file theo backbone de giu lai nhieu lan chay de so sanh
    tag = args.tag or args.backbone

    rep = classification_report(y_true, y_pred, target_names=names, zero_division=0)
    print(rep)
    (config.REPORTS_DIR / f"{tag}_classification_report.txt").write_text(
        f"Backbone: {args.backbone} (tag={tag})\nAccuracy: {acc:.4f}\n\n{rep}", encoding="utf-8")

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(names))))
    fig, ax = plt.subplots(figsize=(max(6, len(names) * 0.6),) * 2)
    ConfusionMatrixDisplay(cm, display_labels=names).plot(ax=ax, xticks_rotation=90, colorbar=False)
    ax.set_title(f"Confusion matrix ({tag})")
    fig.tight_layout()
    fig.savefig(config.REPORTS_DIR / f"{tag}_confusion_matrix.png", dpi=120)
    plt.close(fig)

    # ROC verification (genuine vs impostor)
    scores = np.array(gen_scores + imp_scores)
    labels = np.array([1] * len(gen_scores) + [0] * len(imp_scores))
    fpr, tpr, thr = roc_curve(labels, scores)
    roc_auc = auc(fpr, tpr)
    fnr = 1 - tpr
    eer_idx = np.nanargmin(np.abs(fnr - fpr))
    eer = (fpr[eer_idx] + fnr[eer_idx]) / 2
    eer_thr = thr[eer_idx]

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(fpr, tpr, label=f"AUC = {roc_auc:.4f}")
    ax.plot([0, 1], [0, 1], "--", color="gray")
    ax.scatter([fpr[eer_idx]], [tpr[eer_idx]], color="red",
               label=f"EER = {eer:.3f} @ thr={eer_thr:.3f}")
    ax.set_xlabel("False Accept Rate (FAR)")
    ax.set_ylabel("True Accept Rate")
    ax.set_title(f"ROC verification ({tag})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(config.REPORTS_DIR / f"{tag}_roc.png", dpi=120)
    plt.close(fig)

    # FAR / FRR theo nguong
    ts = np.linspace(scores.min(), scores.max(), 200)
    far = [(np.array(imp_scores) >= t).mean() for t in ts]
    frr = [(np.array(gen_scores) < t).mean() for t in ts]
    best_t = ts[int(np.argmin(np.abs(np.array(far) - np.array(frr))))]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(ts, far, label="FAR (nhan nham nguoi la)")
    ax.plot(ts, frr, label="FRR (tu choi nguoi that)")
    ax.axvline(best_t, color="red", ls="--", label=f"Nguong de xuat = {best_t:.3f}")
    ax.set_xlabel("Nguong cosine similarity")
    ax.set_ylabel("Ty le loi")
    ax.set_title(f"FAR - FRR ({tag})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(config.REPORTS_DIR / f"{tag}_far_frr.png", dpi=120)
    plt.close(fig)

    print(f"AUC = {roc_auc:.4f} | EER = {eer:.4f} @ threshold {eer_thr:.3f}")
    print(f"Nguong de xuat (FAR=FRR): {best_t:.3f}  -> cap nhat config.DEFAULT_THRESHOLD")
    print(f"[OK] Bao cao & bieu do -> {config.REPORTS_DIR}")


if __name__ == "__main__":
    main()
