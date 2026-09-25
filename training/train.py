"""Huấn luyện MobileFaceNet bằng ArcFace.

    python -m training.train --config training/configs/mobilefacenet.yaml

Sáu điểm khác so với lần train trước (lần đó chỉ đạt 0.52):

  1. **Không đóng băng backbone.** Lần trước đóng băng đặc trưng ImageNet, mà đặc
     trưng ImageNet không phân biệt được khuôn mặt — mạng chỉ học được một phép
     chiếu tuyến tính trên đầu vào sai mục đích. Đây là nguyên nhân số một.
  2. **MobileFaceNet thay ResNet50.** 1,2 triệu tham số thay vì 25 triệu, vừa
     VRAM 4 GB với batch lớn — mà ArcFace thì cần batch lớn mới ổn định.
  3. **Khởi động dần biên độ ArcFace.** m tăng 0 → 0.5 trong vài epoch đầu.
  4. **SGD momentum thay AdamW**, đúng công thức trong bài báo ArcFace.
  5. **Lịch learning rate tự tính** (warmup tuyến tính + cosine). Không dùng
     `CosineAnnealingLR` vì nó tính đệ quy từ `lr` hiện tại, nên bị hỏng nếu ta
     ghi đè `lr` để làm warmup.
  6. **Chia tập theo danh tính** qua manifest — không còn rò rỉ.

AMP mặc định TẮT: đo trên GTX 1650 (không có tensor core) thì fp16 chậm hơn fp32
2 lần và còn gây tràn số trong MobileFaceNet. Chỉ bật lại trên GPU có tensor core.

Kết thúc mỗi epoch, ngoài accuracy phân loại còn đo **verification accuracy trên
tập val** (ghép cặp cùng/khác người). Chỉ số thứ hai mới là thứ dự báo đúng chất
lượng lúc triển khai; accuracy phân loại có thể cao trong khi embedding vẫn tệ.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from engine.embed.mobilefacenet import MobileFaceNet
from training.datasets import FaceDataset
from training.losses.arcface import ArcFaceLoss
from training.split import DEFAULT_MANIFEST, assert_disjoint, load_manifest


# --------------------------------------------------------------------- cấu hình
DEFAULTS = {
    "manifest": str(DEFAULT_MANIFEST),
    #: Nguon RecordIO (CASIA-WebFace). Dat duong dan -> bo qua manifest.
    "recordio_dir": "",
    "num_train_ids": 0,      # 0 = lay het phan con lai
    "num_val_ids": 400,
    "max_per_id": 0,         # 0 = khong gioi han anh moi nguoi
    "out_dir": "models",
    "name": "mobilefacenet_arcface",
    "image_size": 112,
    "embedding_dim": 512,
    "epochs": 50,
    "batch_size": 128,
    "lr": 0.1,
    "weight_decay": 5e-4,
    "momentum": 0.9,
    "scale": 64.0,
    "margin": 0.5,
    "warmup_epochs": 5,
    #: Số bước đầu tiên để nâng dần learning rate từ gần 0 lên `lr`. Thiếu bước
    #: này, SGD với lr lớn làm trọng số phân kỳ ngay epoch đầu và embedding hoá
    #: NaN — chính là lỗi gặp phải ở lần chạy đầu tiên.
    "warmup_iters": 300,
    "label_smoothing": 0.1,
    "workers": 0,
    "amp": True,
    "augment_strength": 1.0,
    "seed": 42,
}


def load_config(path: str | None) -> dict:
    cfg = dict(DEFAULTS)
    if path:
        text = Path(path).read_text(encoding="utf-8")
        try:
            import yaml
            user = yaml.safe_load(text) or {}
        except ImportError:
            user = json.loads(text)
        cfg.update(user)
    return cfg


# ------------------------------------------------------------ đánh giá val
@torch.no_grad()
def verification_accuracy(model, dataset, device, n_pairs=1500, seed=0) -> tuple[float, float]:
    """Ghép cặp trong tập val rồi đo accuracy tốt nhất + AUC thô.

    Đo trực tiếp thứ hệ thống thật sự làm — so hai vector — thay vì đo khả năng
    phân loại vào các lớp đã học.
    """
    model.eval()
    by_class: dict[int, list[int]] = {}
    for idx, (_, label) in enumerate(dataset.samples):
        by_class.setdefault(label, []).append(idx)
    classes = [c for c, v in by_class.items() if len(v) >= 2]
    if len(classes) < 2:
        return 0.0, 0.0

    rng = np.random.default_rng(seed)
    need = sorted({i for c in classes for i in by_class[c]})
    embs: dict[int, np.ndarray] = {}
    batch, keys = [], []
    for i in need:
        img, _ = dataset[i]
        batch.append(img); keys.append(i)
        if len(batch) == 128:
            out = model(torch.stack(batch).to(device)).cpu().numpy()
            embs.update(dict(zip(keys, out))); batch, keys = [], []
    if batch:
        out = model(torch.stack(batch).to(device)).cpu().numpy()
        embs.update(dict(zip(keys, out)))

    scores, labels = [], []
    for _ in range(n_pairs // 2):
        c = classes[rng.integers(len(classes))]
        a, b = rng.choice(by_class[c], size=2, replace=False)
        scores.append(float(embs[a] @ embs[b])); labels.append(1)
    for _ in range(n_pairs // 2):
        ca, cb = rng.choice(len(classes), size=2, replace=False)
        a = by_class[classes[ca]][rng.integers(len(by_class[classes[ca]]))]
        b = by_class[classes[cb]][rng.integers(len(by_class[classes[cb]]))]
        scores.append(float(embs[a] @ embs[b])); labels.append(0)

    scores, labels = np.array(scores), np.array(labels)
    # Trọng số phân kỳ sẽ cho ra embedding NaN. Báo rõ thay vì để sklearn ném lỗi
    # khó hiểu ở tận trong lòng vòng lặp huấn luyện.
    finite = np.isfinite(scores)
    if not finite.all():
        if not finite.any():
            return float("nan"), float("nan")
        scores, labels = scores[finite], labels[finite]

    grid = np.linspace(scores.min(), scores.max(), 400)
    acc = float(max(((scores >= t) == labels).mean() for t in grid))
    from sklearn.metrics import roc_auc_score
    if len(np.unique(labels)) < 2:
        return acc, float("nan")
    return acc, float(roc_auc_score(labels, scores))


# ------------------------------------------------------------------- vòng train
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    for key in ("manifest", "out_dir", "name"):
        ap.add_argument(f"--{key.replace('_', '-')}", default=None)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--batch-size", type=int, default=None)
    ap.add_argument("--lr", type=float, default=None)
    ap.add_argument("--margin", type=float, default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--no-amp", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    for k, v in vars(args).items():
        if k not in ("config", "no_amp") and v is not None:
            cfg[k] = v
    if args.no_amp:
        cfg["amp"] = False

    torch.manual_seed(cfg["seed"]); np.random.seed(cfg["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"Thiết bị: {device}"
          + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""))

    if cfg.get("recordio_dir"):
        # Nguồn RecordIO (CASIA-WebFace...): đọc thẳng từ .rec, không giải nén ra đĩa.
        from training.datasets import RecordIOFaceDataset, split_casia_identities
        rec_dir = cfg["recordio_dir"]
        train_ids, val_ids = split_casia_identities(
            rec_dir, num_train=cfg.get("num_train_ids", 0),
            num_val=cfg.get("num_val_ids", 400), seed=cfg["seed"])
        print(f"Nguồn: {rec_dir}  (chia theo danh tính, train ∩ val = "
              f"{len(train_ids & val_ids)})")
        train_ds = RecordIOFaceDataset(rec_dir, identities=train_ids,
                                       max_per_id=cfg.get("max_per_id", 0),
                                       size=cfg["image_size"], augment=True,
                                       augment_strength=cfg["augment_strength"])
        val_ds = RecordIOFaceDataset(rec_dir, identities=val_ids,
                                     max_per_id=min(8, cfg.get("max_per_id", 8) or 8),
                                     size=cfg["image_size"], augment=False)
        print(f"train: {train_ds.describe()}")
        print(f"val  : {val_ds.describe()}")
    else:
        manifest = load_manifest(cfg["manifest"])
        assert_disjoint(manifest)
        train_ds = FaceDataset(manifest, "train", cfg["image_size"], augment=True,
                               augment_strength=cfg["augment_strength"])
        val_ds = FaceDataset(manifest, "val", cfg["image_size"], augment=False)
        print(train_ds.describe()); print(val_ds.describe())
    if train_ds.num_classes < 20:
        print(f"\n  CẢNH BÁO: chỉ {train_ds.num_classes} danh tính để huấn luyện. ArcFace cần"
              f"\n  hàng trăm đến hàng nghìn danh tính mới học được embedding tổng quát."
              f"\n  Tải dataset lớn hơn: python -m src.download_kaggle --dataset pins\n")

    loader = DataLoader(train_ds, batch_size=cfg["batch_size"], shuffle=True,
                        num_workers=cfg["workers"], drop_last=True,
                        pin_memory=(device.type == "cuda"))

    model = MobileFaceNet(cfg["embedding_dim"], cfg["image_size"]).to(device)
    head = ArcFaceLoss(cfg["embedding_dim"], train_ds.num_classes,
                       scale=cfg["scale"], margin=cfg["margin"],
                       warmup_epochs=cfg["warmup_epochs"],
                       label_smoothing=cfg["label_smoothing"]).to(device)
    print(f"MobileFaceNet: {model.num_parameters()/1e6:.2f}M tham số · "
          f"embedding {cfg['embedding_dim']}-D · {train_ds.num_classes} lớp")

    optimizer = torch.optim.SGD(
        [{"params": model.parameters()}, {"params": head.parameters()}],
        lr=cfg["lr"], momentum=cfg["momentum"], weight_decay=cfg["weight_decay"], nesterov=True)

    total_steps = max(1, len(loader) * cfg["epochs"])
    warmup_iters = int(cfg.get("warmup_iters", 0))

    def lr_at(step: int) -> float:
        """Warmup tuyến tính rồi cosine decay — tính thẳng, không dùng scheduler.

        `CosineAnnealingLR` của PyTorch tính đệ quy từ `lr` hiện tại của
        param_group. Nếu ta ghi đè `lr` mỗi bước để làm warmup thì đệ quy đó bị
        phá, và learning rate tụt xuống thấp hơn dự định cả chục lần — mô hình
        vẫn học được nhưng dừng sớm. Tính thẳng theo `step` thì không có trạng
        thái ẩn nào để hỏng.
        """
        if warmup_iters and step <= warmup_iters:
            return cfg["lr"] * (0.01 + 0.99 * step / warmup_iters)
        progress = (step - warmup_iters) / max(1, total_steps - warmup_iters)
        return cfg["lr"] * 0.5 * (1.0 + math.cos(math.pi * min(1.0, progress)))
    use_amp = bool(cfg["amp"]) and device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    out_dir = Path(cfg["out_dir"]); out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = out_dir / f"{cfg['name']}.pt"
    history, best_val = [], -1.0

    print(f"\n{'ep':>3} {'loss':>8} {'m':>5} {'acc_cls':>8} {'val_ver':>8} {'val_auc':>8} {'lr':>8} {'giây':>6}")
    print("-" * 64)

    step = 0
    skipped_batches = 0

    for epoch in range(1, cfg["epochs"] + 1):
        margin = head.set_epoch(epoch - 1)
        model.train(); head.train()
        t0, total, seen, correct = time.perf_counter(), 0.0, 0, 0

        for images, labels in loader:
            step += 1
            cur_lr = lr_at(step)
            for g in optimizer.param_groups:
                g["lr"] = cur_lr

            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=use_amp):
                emb = model(images)
            # Đầu ArcFace luôn chạy fp32. Nó gồm chuẩn hoá vector, luỹ thừa và
            # căn bậc hai — chuỗi phép toán rất dễ tràn hoặc mất chính xác ở
            # fp16. Backbone vẫn hưởng trọn tốc độ của mixed precision.
            with torch.amp.autocast("cuda", enabled=False):
                loss = head(emb.float(), labels)

            if not torch.isfinite(loss):
                skipped_batches += 1
                if skipped_batches > 20:
                    raise SystemExit(
                        "\nLoss hoá NaN/inf liên tục — quá trình huấn luyện đã phân kỳ.\n"
                        "Thử lần lượt: giảm lr (0.05 rồi 0.01), tăng warmup_iters,\n"
                        "giảm scale ArcFace, hoặc tắt AMP bằng --no-amp.")
                optimizer.zero_grad(set_to_none=True)
                continue

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(list(model.parameters()) + list(head.parameters()), 5.0)
            scaler.step(optimizer); scaler.update()

            bs = labels.size(0)
            total += loss.item() * bs; seen += bs
            with torch.no_grad():
                correct += (head.logits(emb.float()).argmax(1) == labels).sum().item()

        val_acc, val_auc = verification_accuracy(model, val_ds, device)
        row = {"epoch": epoch, "loss": total / max(seen, 1), "margin": margin,
               "acc_cls": correct / max(seen, 1), "val_ver": val_acc, "val_auc": val_auc,
               "lr": cur_lr, "sec": time.perf_counter() - t0}
        history.append(row)
        print(f"{epoch:3d} {row['loss']:8.4f} {margin:5.2f} {row['acc_cls']:8.4f} "
              f"{val_acc:8.4f} {val_auc:8.4f} {row['lr']:8.5f} {row['sec']:6.1f}")

        if val_acc >= best_val:
            best_val = val_acc
            torch.save({"model": model.state_dict(),
                        "meta": {"image_size": cfg["image_size"],
                                 "embedding_dim": cfg["embedding_dim"],
                                 "arch": "mobilefacenet",
                                 "num_train_identities": train_ds.num_classes,
                                 "val_verification_acc": round(best_val, 4),
                                 "val_auc": round(val_auc, 4),
                                 "epoch": epoch,
                                 "manifest": cfg["manifest"]}}, ckpt_path)

    (out_dir / f"{cfg['name']}_history.json").write_text(
        json.dumps({"config": cfg, "history": history}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"\nTốt nhất: val_verification_acc = {best_val:.4f}")
    print(f"-> {ckpt_path}")
    print(f"Bước tiếp: python -m training.export_onnx --checkpoint {ckpt_path}")


if __name__ == "__main__":
    main()
