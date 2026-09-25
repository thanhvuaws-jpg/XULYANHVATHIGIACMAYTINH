"""Chạy mô hình tự huấn luyện bằng PyTorch — dùng khi chưa xuất ONNX.

Cùng kiến trúc và cùng quy ước tiền xử lý với `onnx_arcface.py`, nên hai đường
chạy phải cho ra vector giống nhau. Có một bài test đối chiếu đúng điểm này trong
`training/export_onnx.py`.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import torch

from ..settings import EmbedSettings, resolve_device
from .base import Embedder, l2_normalize
from .mobilefacenet import MobileFaceNet


class TorchArcFaceEmbedder(Embedder):
    name = "torch"

    def __init__(self, settings: EmbedSettings | None = None, device: str = "auto"):
        self.s = settings or EmbedSettings(backend="torch")
        path = Path(self.s.weights)
        if not path.exists():
            raise FileNotFoundError(f"Không thấy checkpoint: {path}")

        self.device = torch.device(resolve_device(device))
        ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
        state = ckpt.get("model", ckpt) if isinstance(ckpt, dict) else ckpt
        meta = ckpt.get("meta", {}) if isinstance(ckpt, dict) else {}

        self.image_size = int(meta.get("image_size", self.s.image_size))
        self.dim = int(meta.get("embedding_dim", self.s.dim))

        self._net = MobileFaceNet(embedding_dim=self.dim, input_size=self.image_size)
        self._net.load_state_dict(state)
        self._net.eval().to(self.device)
        self.batch_size = self.s.batch_size

    def _to_tensor(self, chip_bgr: np.ndarray) -> torch.Tensor:
        if chip_bgr.shape[0] != self.image_size or chip_bgr.shape[1] != self.image_size:
            chip_bgr = cv2.resize(chip_bgr, (self.image_size, self.image_size),
                                  interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(chip_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
        rgb = (rgb - 127.5) / 127.5
        return torch.from_numpy(np.transpose(rgb, (2, 0, 1)))

    @torch.no_grad()
    def embed(self, chips_bgr: list[np.ndarray]) -> np.ndarray:
        if not chips_bgr:
            return np.zeros((0, self.dim), dtype=np.float32)
        tensors = [self._to_tensor(c) for c in chips_bgr]
        out = []
        for i in range(0, len(tensors), self.batch_size):
            batch = torch.stack(tensors[i:i + self.batch_size]).to(self.device)
            out.append(self._net(batch).cpu().numpy().astype(np.float32))
        return l2_normalize(np.concatenate(out, axis=0))
