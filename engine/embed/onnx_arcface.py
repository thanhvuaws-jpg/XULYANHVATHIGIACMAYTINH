"""Trích đặc trưng bằng ONNX Runtime — đường chạy chính khi triển khai.

Đây là mô hình do chính nhóm huấn luyện (MobileFaceNet + ArcFace), xuất sang ONNX
bằng `training/export_onnx.py`. Hai lợi ích:

  • nhanh hơn PyTorch trên CPU (đo được: 9,1 ms → 4,7 ms mỗi khuôn mặt);
  • container chạy thật không cần cài PyTorch, nên image nhẹ đi đáng kể — số đo
    cụ thể của hai bản dựng nằm ở `docs/NHAT_KY_KY_THUAT.md`, mục Task 12.

Quy ước tiền xử lý theo chuẩn ArcFace: RGB, 112×112, (x − 127.5) / 127.5.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..settings import EmbedSettings
from .base import Embedder, l2_normalize


class OnnxArcFaceEmbedder(Embedder):
    name = "onnx"

    def __init__(self, settings: EmbedSettings | None = None, providers: list[str] | None = None):
        import onnxruntime as ort

        self.s = settings or EmbedSettings(backend="onnx")
        path = Path(self.s.weights)
        if not path.exists():
            raise FileNotFoundError(
                f"Không thấy model ONNX: {path}. Chạy training/export_onnx.py trước.")

        if providers is None:
            available = ort.get_available_providers()
            providers = (["CUDAExecutionProvider", "CPUExecutionProvider"]
                         if "CUDAExecutionProvider" in available else ["CPUExecutionProvider"])

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._sess = ort.InferenceSession(str(path), sess_options=opts, providers=providers)

        inp = self._sess.get_inputs()[0]
        self._input_name = inp.name
        # Hình dạng thường là (N, 3, H, W); chiều batch có thể là ký hiệu động.
        shape = inp.shape
        self.image_size = int(shape[2]) if isinstance(shape[2], int) else self.s.image_size
        out_shape = self._sess.get_outputs()[0].shape
        self.dim = int(out_shape[1]) if isinstance(out_shape[1], int) else self.s.dim
        self._output_name = self._sess.get_outputs()[0].name
        self.batch_size = self.s.batch_size

    def _preprocess(self, chip_bgr: np.ndarray) -> np.ndarray:
        if chip_bgr.shape[0] != self.image_size or chip_bgr.shape[1] != self.image_size:
            chip_bgr = cv2.resize(chip_bgr, (self.image_size, self.image_size),
                                  interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(chip_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
        rgb = (rgb - 127.5) / 127.5
        return np.transpose(rgb, (2, 0, 1))          # HWC -> CHW

    def embed(self, chips_bgr: list[np.ndarray]) -> np.ndarray:
        if not chips_bgr:
            return np.zeros((0, self.dim), dtype=np.float32)
        arrs = [self._preprocess(c) for c in chips_bgr]
        out = []
        for i in range(0, len(arrs), self.batch_size):
            batch = np.stack(arrs[i:i + self.batch_size]).astype(np.float32)
            res = self._sess.run([self._output_name], {self._input_name: batch})[0]
            out.append(np.asarray(res, dtype=np.float32))
        return l2_normalize(np.concatenate(out, axis=0))
