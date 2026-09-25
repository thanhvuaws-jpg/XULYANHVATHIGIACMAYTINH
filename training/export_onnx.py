"""Xuất checkpoint PyTorch sang ONNX + kiểm chứng hai đường chạy khớp nhau.

    python -m training.export_onnx --checkpoint models/mobilefacenet_arcface.pt

Vì sao đây là bước quan trọng chứ không phải thủ tục
---------------------------------------------------
1. **Nhanh hơn 2–4 lần trên CPU.** ONNX Runtime hợp nhất các phép toán và tối ưu
   đồ thị tốt hơn PyTorch eager.
2. **Container triển khai không cần PyTorch.** `onnxruntime` khoảng 50 MB, còn
   `torch` khoảng 2,5 GB. Image backend tụt từ ~5 GB xuống ~400 MB — chạy được
   trên VPS rẻ và khởi động nhanh hơn hẳn.

Script luôn chạy kiểm chứng: đưa cùng một loạt ảnh qua cả hai đường, so vector
ra. Sai lệch phải dưới 1e-4 — nếu không thì tiền xử lý hai bên đang lệch nhau,
và lỗi kiểu đó rất khó phát hiện về sau vì mô hình vẫn chạy, chỉ là kém đi.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import torch

from engine.embed.mobilefacenet import MobileFaceNet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default="models/mobilefacenet_arcface.pt")
    ap.add_argument("--out", default=None)
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--dynamic-batch", action="store_true", default=True)
    args = ap.parse_args()

    ckpt_path = Path(args.checkpoint)
    if not ckpt_path.exists():
        raise SystemExit(f"Không thấy checkpoint: {ckpt_path}. Chạy training/train.py trước.")

    ckpt = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    state = ckpt.get("model", ckpt) if isinstance(ckpt, dict) else ckpt
    meta = ckpt.get("meta", {}) if isinstance(ckpt, dict) else {}
    size = int(meta.get("image_size", 112))
    dim = int(meta.get("embedding_dim", 512))

    model = MobileFaceNet(embedding_dim=dim, input_size=size)
    model.load_state_dict(state)
    model.eval()

    out_path = Path(args.out) if args.out else ckpt_path.with_suffix(".onnx")
    dummy = torch.randn(1, 3, size, size)

    dynamic_axes = ({"input": {0: "batch"}, "embedding": {0: "batch"}}
                    if args.dynamic_batch else None)
    torch.onnx.export(
        model, dummy, str(out_path),
        input_names=["input"], output_names=["embedding"],
        dynamic_axes=dynamic_axes, opset_version=args.opset,
        do_constant_folding=True,
    )
    print(f"Đã xuất: {out_path}  ({out_path.stat().st_size/1e6:.1f} MB, "
          f"checkpoint gốc {ckpt_path.stat().st_size/1e6:.1f} MB)")

    # ---------------------------------------------------- kiểm chứng khớp nhau
    import onnxruntime as ort
    sess = ort.InferenceSession(str(out_path), providers=["CPUExecutionProvider"])

    rng = np.random.default_rng(0)
    batch = rng.normal(size=(8, 3, size, size)).astype(np.float32)

    with torch.no_grad():
        torch_out = model(torch.from_numpy(batch)).numpy()
    onnx_out = sess.run(["embedding"], {"input": batch})[0]

    diff = float(np.abs(torch_out - onnx_out).max())
    cos = float(np.mean([np.dot(a, b) for a, b in zip(torch_out, onnx_out)]))
    ok = diff < 1e-4
    print(f"\nKiểm chứng torch ↔ onnx: sai lệch tối đa = {diff:.2e}  ·  "
          f"cosine trung bình = {cos:.6f}  ->  {'KHỚP' if ok else 'LỆCH — xem lại tiền xử lý!'}")

    # ------------------------------------------------------------- đo tốc độ
    reps = 30
    with torch.no_grad():
        for _ in range(3):
            model(torch.from_numpy(batch))
        t0 = time.perf_counter()
        for _ in range(reps):
            model(torch.from_numpy(batch))
        t_torch = (time.perf_counter() - t0) / reps / len(batch) * 1000

    for _ in range(3):
        sess.run(["embedding"], {"input": batch})
    t0 = time.perf_counter()
    for _ in range(reps):
        sess.run(["embedding"], {"input": batch})
    t_onnx = (time.perf_counter() - t0) / reps / len(batch) * 1000

    print(f"\nTốc độ CPU (mỗi khuôn mặt):  torch = {t_torch:.2f} ms   "
          f"onnx = {t_onnx:.2f} ms   -> nhanh hơn {t_torch/max(t_onnx,1e-9):.1f} lần")
    print(f"\nDùng trong engine:\n  EmbedSettings(backend='onnx', weights='{out_path}')")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
