"""YuNet — bộ phát hiện khuôn mặt ONNX có sẵn trong OpenCV.

Model chỉ 340 KB, chạy khoảng 4 ms trên CPU cho ảnh 640px, so với ~40 ms của
MTCNN. Trả về hộp bao + 5 điểm mốc, đúng thứ tự template ArcFace nên dùng thẳng
được cho bước căn chỉnh.

Model được tải tự động lần đầu từ kho opencv_zoo.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import cv2
import numpy as np

from ..settings import ROOT, DetectSettings
from ..types import Detection
from .base import Detector

MODEL_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_detection_yunet/face_detection_yunet_2023mar.onnx")
MODEL_NAME = "face_detection_yunet_2023mar.onnx"


def ensure_model(models_dir: Path | None = None) -> Path:
    models_dir = Path(models_dir) if models_dir else ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    path = models_dir / MODEL_NAME
    if not path.exists():
        urllib.request.urlretrieve(MODEL_URL, path)
    return path


class YuNetDetector(Detector):
    name = "yunet"

    def __init__(self, settings: DetectSettings | None = None,
                 models_dir: Path | None = None):
        self.s = settings or DetectSettings()
        self.model_path = ensure_model(models_dir)
        # Kích thước lúc khởi tạo chỉ là tạm; mỗi lần detect sẽ set lại cho khớp ảnh.
        self._net = cv2.FaceDetectorYN.create(
            model=str(self.model_path),
            config="",
            input_size=(320, 320),
            score_threshold=float(self.s.score_threshold),
            nms_threshold=float(self.s.nms_threshold),
            top_k=int(self.s.top_k),
        )
        # Chiều rộng ảnh đưa vào mạng. Ảnh lớn hơn sẽ được thu nhỏ rồi scale toạ độ ngược lại.
        self._work_width = int(self.s.input_size[0]) if self.s.input_size else 640

    def detect(self, image_bgr: np.ndarray) -> list[Detection]:
        if image_bgr is None or image_bgr.size == 0:
            return []
        h, w = image_bgr.shape[:2]

        scale = 1.0
        work = image_bgr
        if self._work_width and w > self._work_width:
            scale = self._work_width / float(w)
            work = cv2.resize(image_bgr, (self._work_width, max(1, int(round(h * scale)))),
                              interpolation=cv2.INTER_LINEAR)

        wh, ww = work.shape[:2]
        self._net.setInputSize((ww, wh))
        _, faces = self._net.detect(work)
        if faces is None:
            return []

        out: list[Detection] = []
        inv = 1.0 / scale
        for f in faces:
            x, y, bw, bh = f[0:4]
            score = float(f[14])
            if score < self.s.score_threshold:
                continue
            box = np.array([x, y, x + bw, y + bh], dtype=np.float32) * inv
            # f[4:14] = 5 điểm mốc, thứ tự: mắt phải, mắt trái, mũi, khoé miệng phải,
            # khoé miệng trái — tính theo người trong ảnh, tức trùng thứ tự template ArcFace.
            lms = f[4:14].reshape(5, 2).astype(np.float32) * inv
            box[0::2] = np.clip(box[0::2], 0, w - 1)
            box[1::2] = np.clip(box[1::2], 0, h - 1)
            if box[2] - box[0] < 2 or box[3] - box[1] < 2:
                continue
            out.append(Detection(box=box.astype(int), score=score, landmarks=lms))
        return out
