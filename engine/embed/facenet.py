"""FaceNet (InceptionResnetV1 huấn luyện trên VGGFace2) — mốc tham chiếu.

Đây là mô hình pretrained mạnh, dùng làm baseline để so với mô hình tự huấn
luyện. Yêu cầu ảnh vào 160×160 và chuẩn hoá (x − 127.5) / 128.
"""
from __future__ import annotations

import cv2
import numpy as np
import torch

from ..settings import EmbedSettings, resolve_device
from .base import Embedder, l2_normalize


class FaceNetEmbedder(Embedder):
    name = "facenet"
    image_size = 160
    dim = 512

    def __init__(self, settings: EmbedSettings | None = None, device: str = "auto"):
        from facenet_pytorch import InceptionResnetV1
        self.s = settings or EmbedSettings(backend="facenet", image_size=160)
        self.device = torch.device(resolve_device(device))
        self._net = InceptionResnetV1(pretrained="vggface2").eval().to(self.device)
        self.batch_size = self.s.batch_size

    def _to_tensor(self, chip_bgr: np.ndarray) -> torch.Tensor:
        if chip_bgr.shape[0] != self.image_size or chip_bgr.shape[1] != self.image_size:
            chip_bgr = cv2.resize(chip_bgr, (self.image_size, self.image_size),
                                  interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(chip_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
        t = torch.from_numpy(rgb).permute(2, 0, 1)
        return (t - 127.5) / 128.0

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
