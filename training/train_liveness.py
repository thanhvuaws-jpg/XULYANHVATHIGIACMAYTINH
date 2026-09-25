"""Huấn luyện bộ phát hiện giả mạo thụ động và đánh giá trung thực.

    python -m training.train_liveness --limit 3000

Ba phép thử, tăng dần độ khắt khe
----------------------------------
**Thử 1 — cơ bản.** Ảnh thật (chưa từng thấy) vs đòn tấn công. Cho APCER/BPCER
theo chuẩn ISO/IEC 30107-3. Đây là con số dễ đẹp nhất, và cũng ít ý nghĩa nhất.

**Thử 2 — chéo loại tấn công.** Huấn luyện chỉ trên tấn công in, đo trên tấn công
màn hình (và ngược lại). Nếu vẫn phát hiện được thì mô hình đã học hiện tượng vật
lý chung chứ không thuộc lòng một loại.

**Thử 3 — ảnh thật bị làm nhiễu.** Đây là phép thử quan trọng nhất và là chỗ dễ
thất bại nhất. Webcam phòng học cho ảnh mờ, nén vỡ, thiếu sáng — nếu bộ phát hiện
gán những ảnh đó là "giả mạo" thì sinh viên thật sẽ bị từ chối liên tục và hệ
thống không dùng được. Phép thử này đo đúng điều đó: ảnh thật đã qua augmentation
(mờ, nén JPEG, nhiễu) có bị nhầm không.

Mô hình dùng Gradient Boosting trên 12 đặc trưng có nghĩa vật lý — đủ mạnh cho
lượng dữ liệu này, và quan trọng hơn là **giải thích được**: xuất ra luôn mức độ
đóng góp của từng đặc trưng.
"""
from __future__ import annotations

import argparse
import json
import pickle
import time
from pathlib import Path

import cv2
import numpy as np

from engine.liveness.features import FEATURE_NAMES, extract
from training.spoof_data import print_attack, screen_attack

MODELS = Path("models")
REPORTS = Path("reports")


def degrade_real(img: np.ndarray, rng) -> np.ndarray:
    """Làm nhiễu ảnh THẬT giống điều kiện webcam — KHÔNG thêm dấu vết giả mạo.

    Chỉ dùng những biến dạng mà một camera thật cũng gây ra: mất nét, nhiễu cảm
    biến, nén, thay đổi độ sáng. Tuyệt đối không có lưới nửa tông, lưới điểm ảnh
    hay làm phẳng ánh sáng — vì đó mới là dấu hiệu của giả mạo.
    """
    out = img.copy()
    if rng.random() < 0.8:
        k = int(rng.choice([3, 5]))
        out = cv2.GaussianBlur(out, (k, k), rng.uniform(0.4, 1.3))
    if rng.random() < 0.8:
        out = np.clip(out.astype(np.float32)
                      + rng.normal(0, rng.uniform(2, 7), out.shape), 0, 255).astype(np.uint8)
    if rng.random() < 0.8:
        out = cv2.convertScaleAbs(out, alpha=rng.uniform(0.78, 1.22),
                                  beta=rng.uniform(-25, 25))
    if rng.random() < 0.8:
        q = int(rng.integers(45, 90))
        ok, enc = cv2.imencode(".jpg", out, [int(cv2.IMWRITE_JPEG_QUALITY), q])
        if ok:
            out = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return out


def metrics(y_true: np.ndarray, score: np.ndarray, thr: float) -> dict:
    """APCER / BPCER / ACER theo ISO/IEC 30107-3.  y_true: 1 = thật, 0 = giả."""
    pred_live = score >= thr
    attacks = y_true == 0
    bona = y_true == 1
    apcer = float(pred_live[attacks].mean()) if attacks.any() else 0.0   # tấn công lọt
    bpcer = float((~pred_live[bona]).mean()) if bona.any() else 0.0      # người thật bị chặn
    return {"apcer": apcer, "bpcer": bpcer, "acer": (apcer + bpcer) / 2,
            "threshold": float(thr)}


def best_threshold(y: np.ndarray, s: np.ndarray) -> float:
    """Ngưỡng làm APCER và BPCER cân bằng nhau."""
    grid = np.linspace(s.min(), s.max(), 400)
    best, bt = 1e9, 0.5
    for t in grid:
        m = metrics(y, s, t)
        gap = abs(m["apcer"] - m["bpcer"])
        if gap < best:
            best, bt = gap, t
    return float(bt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/aligned_big")
    ap.add_argument("--limit", type=int, default=3000, help="Số ảnh thật dùng")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="models/liveness_texture.pkl")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    paths = sorted(Path(args.data_dir).rglob("*.jpg"))
    rng.shuffle(paths)
    paths = paths[: args.limit]
    if len(paths) < 200:
        raise SystemExit(f"Chỉ có {len(paths)} ảnh — quá ít.")

    # Chia theo ảnh gốc: một ảnh gốc chỉ nằm ở train HOẶC test, kể cả bản tấn công.
    n_tr = int(len(paths) * 0.7)
    tr_paths, te_paths = paths[:n_tr], paths[n_tr:]
    print(f"Ảnh gốc: {len(tr_paths)} train · {len(te_paths)} test")

    def build(plist, tag, with_hard_negatives: bool = True):
        """Sinh mẫu huấn luyện.

        `with_hard_negatives` đưa **ảnh thật đã bị làm nhiễu** vào với nhãn THẬT.
        Không có chúng, bộ phân loại chỉ học được "ảnh kém chất lượng = giả mạo"
        — đo bằng phép thử 3 thì từ chối oan tới 56 % người thật. Đây chính là
        kỹ thuật *hard negative mining*: ép mô hình phải phân biệt giả mạo với
        ảnh chỉ đơn thuần mờ/nén/thiếu sáng.
        """
        X, y, kind = [], [], []
        t0 = time.perf_counter()
        for i, p in enumerate(plist):
            img = cv2.imread(str(p))
            if img is None:
                continue
            X.append(extract(img)); y.append(1); kind.append("real")
            if with_hard_negatives:
                X.append(extract(degrade_real(img, rng))); y.append(1); kind.append("real_degraded")
            X.append(extract(print_attack(img, rng))); y.append(0); kind.append("print")
            X.append(extract(screen_attack(img, rng))); y.append(0); kind.append("screen")
            if i and i % 500 == 0:
                print(f"  {tag}: {i}/{len(plist)} · {time.perf_counter()-t0:.0f}s", flush=True)
        return np.stack(X), np.array(y), np.array(kind)

    Xtr, ytr, ktr = build(tr_paths, "train")
    Xte, yte, kte = build(te_paths, "test")
    print(f"Mẫu: train {len(ytr)} · test {len(yte)}\n")

    from sklearn.ensemble import HistGradientBoostingClassifier
    clf = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.08,
                                         max_depth=6, random_state=args.seed)
    clf.fit(Xtr, ytr)

    s_te = clf.predict_proba(Xte)[:, 1]
    thr = best_threshold(yte, s_te)

    results = {}

    # ---- Thử 1: cơ bản
    results["basic"] = metrics(yte, s_te, thr)
    print("THỬ 1 — Cơ bản (thật, kể cả ảnh nhiễu, vs mọi tấn công)")
    m = results["basic"]
    print(f"   APCER={m['apcer']*100:6.2f}%   BPCER={m['bpcer']*100:6.2f}%   "
          f"ACER={m['acer']*100:6.2f}%   (ngưỡng {thr:.3f})")
    clean = kte == "real"
    deg = kte == "real_degraded"
    if deg.any():
        print(f"   trong đó: ảnh sạch bị từ chối {(s_te[clean] < thr).mean()*100:5.2f}%  ·  "
              f"ảnh nhiễu bị từ chối {(s_te[deg] < thr).mean()*100:5.2f}%")

    # ---- Thử 2: chéo loại tấn công
    print("\nTHỬ 2 — Chéo loại tấn công (học loại này, đo loại kia)")
    for train_kind, test_kind in (("print", "screen"), ("screen", "print")):
        sel_tr = (ktr == "real") | (ktr == train_kind)
        c2 = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.08,
                                            max_depth=6, random_state=args.seed)
        c2.fit(Xtr[sel_tr], ytr[sel_tr])
        sel_te = (kte == "real") | (kte == test_kind)
        s2 = c2.predict_proba(Xte[sel_te])[:, 1]
        t2 = best_threshold(yte[sel_te], s2)
        m2 = metrics(yte[sel_te], s2, t2)
        results[f"cross_{train_kind}_to_{test_kind}"] = m2
        print(f"   học '{train_kind}' → đo '{test_kind}':  APCER={m2['apcer']*100:6.2f}%   "
              f"BPCER={m2['bpcer']*100:6.2f}%   ACER={m2['acer']*100:6.2f}%")

    # ---- Thử 3: ảnh thật bị làm nhiễu  (phép thử quan trọng nhất)
    print("\nTHỬ 3 — Ảnh THẬT bị làm nhiễu (mờ/nén/nhiễu) có bị nhầm là giả mạo không")
    Xd = []
    for p in te_paths:
        img = cv2.imread(str(p))
        if img is not None:
            Xd.append(extract(degrade_real(img, rng)))
    Xd = np.stack(Xd)
    s_deg = clf.predict_proba(Xd)[:, 1]
    false_reject = float((s_deg < thr).mean())
    attacks_only = s_te[yte == 0]
    results["degraded_real"] = {
        "bpcer_degraded": false_reject,
        "mean_score_degraded_real": float(s_deg.mean()),
        "mean_score_clean_real": float(s_te[yte == 1].mean()),
        "mean_score_attack": float(attacks_only.mean()),
    }
    print(f"   Ảnh thật SẠCH   → điểm sống trung bình {s_te[yte==1].mean():.3f}")
    print(f"   Ảnh thật NHIỄU  → điểm sống trung bình {s_deg.mean():.3f}   "
          f"bị từ chối oan {false_reject*100:.2f}%")
    print(f"   Ảnh tấn công    → điểm sống trung bình {attacks_only.mean():.3f}")

    # ---- Đặc trưng nào đóng góp nhiều nhất
    from sklearn.inspection import permutation_importance
    imp = permutation_importance(clf, Xte, yte, n_repeats=5,
                                 random_state=args.seed, n_jobs=1)
    order = np.argsort(imp.importances_mean)[::-1]
    print("\nĐặc trưng quan trọng nhất:")
    for i in order[:6]:
        print(f"   {FEATURE_NAMES[i]:<18} {imp.importances_mean[i]:.4f}")
    results["importance"] = {FEATURE_NAMES[i]: float(imp.importances_mean[i])
                             for i in order}

    MODELS.mkdir(exist_ok=True)
    with open(args.out, "wb") as f:
        pickle.dump({"model": clf, "threshold": thr,
                     "features": FEATURE_NAMES, "results": results}, f)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "liveness_eval.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {args.out}\n-> reports/liveness_eval.json")


if __name__ == "__main__":
    main()
