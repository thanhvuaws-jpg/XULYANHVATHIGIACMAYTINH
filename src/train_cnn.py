"""Train CNN (ResNet50) tren dataset khuon mat da align.

    # Phien ban 1 - CrossEntropy (de, co ngay ket qua):
    python -m src.train_cnn --data-dir data/aligned --loss ce --epochs 25

    # Phien ban 2 - ArcFace (embedding manh hon, dung de so sanh trong bao cao):
    python -m src.train_cnn --data-dir data/aligned --loss arcface --epochs 30

Ket qua luu tai:
    models/backbone_<loss>.pt     (state_dict cua FaceEmbedder - dung o build_db / recognize)
    models/backbone_<loss>.json   (metadata: danh sach lop, val_acc, ...)
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms

from . import config
from .arcface import ArcMarginProduct
from .face_utils import FaceEmbedder, get_device


def build_transforms():
    norm = transforms.Normalize(config.IMAGENET_MEAN, config.IMAGENET_STD)
    train_tf = transforms.Compose([
        transforms.Resize((config.ALIGNED_SIZE, config.ALIGNED_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(0.2, 0.2, 0.2, 0.02),
        transforms.RandomRotation(10),
        transforms.ToTensor(),
        norm,
        transforms.RandomErasing(p=0.25),
    ])
    eval_tf = transforms.Compose([
        transforms.Resize((config.ALIGNED_SIZE, config.ALIGNED_SIZE)),
        transforms.ToTensor(),
        norm,
    ])
    return train_tf, eval_tf


@torch.no_grad()
def evaluate(embedder, head, loss_kind, loader, device):
    embedder.eval()
    head.eval()
    correct = total = 0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        emb = embedder(x)
        if loss_kind == "ce":
            logits = head(emb)
        else:
            logits = head.logits_eval(emb)
        correct += (logits.argmax(1) == y).sum().item()
        total += y.numel()
    return correct / max(total, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(config.ALIGNED_DIR))
    ap.add_argument("--loss", choices=["ce", "arcface"], default="ce")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--val-split", type=float, default=0.15)
    ap.add_argument("--workers", type=int, default=0, help="Windows nen de 0")
    ap.add_argument("--freeze-backbone", action="store_true",
                    help="Chi train neck + head (nhanh, it VRAM)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    device = get_device()
    print(f"[i] Device: {device}")

    train_tf, eval_tf = build_transforms()
    full = datasets.ImageFolder(args.data_dir, transform=train_tf)
    classes = full.classes
    n_cls = len(classes)
    if n_cls < 2:
        raise SystemExit(f"Can it nhat 2 nguoi trong {args.data_dir}, dang co {n_cls}.")
    print(f"[i] {n_cls} nguoi | {len(full)} anh")

    n_val = max(1, int(len(full) * args.val_split))
    n_train = len(full) - n_val
    g = torch.Generator().manual_seed(42)
    train_ds, val_ds = random_split(full, [n_train, n_val], generator=g)
    val_ds.dataset = datasets.ImageFolder(args.data_dir, transform=eval_tf)

    train_ld = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                          num_workers=args.workers, drop_last=True)
    val_ld = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                        num_workers=args.workers)

    embedder = FaceEmbedder(embedding_dim=config.EMBEDDING_DIM, pretrained=True).to(device)
    if args.freeze_backbone:
        for p in embedder.backbone.parameters():
            p.requires_grad = False

    if args.loss == "ce":
        head = nn.Linear(config.EMBEDDING_DIM, n_cls).to(device)
    else:
        head = ArcMarginProduct(config.EMBEDDING_DIM, n_cls).to(device)

    params = [p for p in embedder.parameters() if p.requires_grad] + list(head.parameters())
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=5e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    crit = nn.CrossEntropyLoss(label_smoothing=0.1)

    out_path = Path(args.out) if args.out else config.MODELS_DIR / f"backbone_{args.loss}.pt"
    best_acc = 0.0

    for epoch in range(1, args.epochs + 1):
        embedder.train()
        head.train()
        t0 = time.time()
        running = 0.0
        for x, y in train_ld:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            emb = embedder(x)
            logits = head(emb) if args.loss == "ce" else head(emb, y)
            loss = crit(logits, y)
            loss.backward()
            opt.step()
            running += loss.item() * y.size(0)
        sched.step()

        val_acc = evaluate(embedder, head, args.loss, val_ld, device)
        print(f"epoch {epoch:3d}/{args.epochs} | loss {running / n_train:.4f} "
              f"| val_acc {val_acc:.4f} | {time.time() - t0:.1f}s")

        if val_acc >= best_acc:
            best_acc = val_acc
            torch.save(embedder.state_dict(), out_path)
            meta = {
                "kind": "resnet50",
                "loss": args.loss,
                "embedding_dim": config.EMBEDDING_DIM,
                "aligned_size": config.ALIGNED_SIZE,
                "classes": classes,
                "val_acc": round(best_acc, 4),
                "epochs_trained": epoch,
            }
            out_path.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    print(f"\n[OK] Best val_acc = {best_acc:.4f}")
    print(f"     Backbone -> {out_path}")
    print(f"     Metadata -> {out_path.with_suffix('.json')}")


if __name__ == "__main__":
    main()
