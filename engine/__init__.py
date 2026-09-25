"""FaceID engine — thư viện nhận diện khuôn mặt thuần Python.

Không phụ thuộc web, UI hay database: nhận ảnh vào, trả kết quả ra. Nhờ vậy có
thể train, benchmark và viết test cho từng tầng một cách độc lập; backend và các
client chỉ là những thứ gọi vào đây.

Pipeline:  detect → quality → align → liveness → embed → index → track → vote
"""
from .settings import (DetectSettings, EmbedSettings, EngineSettings, IndexSettings,
                       LivenessSettings, QualitySettings, TrackSettings)
from .types import Detection, Face, Identity, QualityReport, TrackedFace

__version__ = "2.0.0"

__all__ = [
    "EngineSettings", "DetectSettings", "QualitySettings", "EmbedSettings",
    "IndexSettings", "TrackSettings", "LivenessSettings",
    "Detection", "Face", "Identity", "QualityReport", "TrackedFace",
]
