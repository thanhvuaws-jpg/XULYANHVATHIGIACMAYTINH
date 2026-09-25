"""Cấu hình engine.

Khác với `src/config.py` cũ (biến toàn cục + tạo thư mục lúc import), ở đây cấu
hình là một dataclass truyền vào pipeline — nên test được, và backend có thể nạp
từ biến môi trường mà không đụng tới file.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class DetectSettings:
    backend: str = "yunet"           # yunet | mtcnn
    score_threshold: float = 0.75    # ngưỡng tin cậy của detector
    nms_threshold: float = 0.30
    top_k: int = 50
    input_size: tuple[int, int] = (320, 320)   # YuNet chạy trên ảnh thu nhỏ


@dataclass
class QualitySettings:
    enabled: bool = True
    #: Độ nét CHUẨN HOÁ (lap_var / gray_var), đo trên vùng mặt gốc thu về 128px
    #: bằng INTER_AREA. Thang đo trên LFW: nét ~0.062, mờ nhẹ ~0.037,
    #: mờ Gauss 21×21 ~0.016, mờ 31×31 ~0.010.
    #:
    #: Ngưỡng 0.010 chọn theo SỐ ĐO, không theo cảm tính. Đo rank-1 theo từng
    #: khoảng độ nét trên 632 ảnh gốc (122 người đã đăng ký):
    #:
    #:     0.000–0.010   8 ảnh   rank-1 0.875   <- chỗ duy nhất thật sự sụt
    #:     0.010–0.015  15 ảnh   rank-1 1.000
    #:     0.015–0.020  64 ảnh   rank-1 0.953
    #:     0.020–0.025  67 ảnh   rank-1 0.970
    #:     0.025–0.035 151 ảnh   rank-1 0.980
    #:     trên 0.060  115 ảnh   rank-1 0.991
    #:
    #: Ngưỡng cũ 0.025 loại 146/632 ảnh (23%) mà những ảnh ấy vẫn nhận đúng tới
    #: ~96%. Trên webcam thật còn tệ hơn: một lần đăng ký 12 ảnh chỉ qua được 4,
    #: trong khi hai ảnh bị loại vì "mờ" vẫn nhận đúng người với cosine 0.94 và
    #: 0.78. Cổng chất lượng khi đó không bảo vệ ai cả — nó chỉ chặn người dùng.
    #:
    #: Dưới 0.010 thì từ chối là đúng: độ chính xác sụt xuống 0.875 và ảnh mẫu
    #: kém sẽ làm hỏng cả gallery về sau.
    min_sharpness: float = 0.010
    min_brightness: float = 45.0
    max_brightness: float = 215.0
    min_face_size: int = 70          # pixel, cạnh nhỏ nhất của hộp bao
    max_pose_angle: float = 30.0     # yaw tối đa — alignment không sửa được
    max_roll_angle: float = 45.0     # roll tối đa — alignment sửa được nên nới rộng
    min_score: float = 0.45          # ngưỡng tổng hợp để coi là "đạt"


@dataclass
class EmbedSettings:
    backend: str = "facenet"         # facenet | onnx | torch
    weights: str = ""                # đường dẫn .onnx hoặc .pt
    image_size: int = 112            # chuẩn ArcFace; facenet dùng 160
    dim: int = 512
    batch_size: int = 32


@dataclass
class IndexSettings:
    backend: str = "bruteforce"      # bruteforce | hnsw
    space: str = "cosine"
    ef_construction: int = 200
    ef_search: int = 64
    m: int = 16
    max_elements: int = 100_000


@dataclass
class TrackSettings:
    enabled: bool = True
    iou_threshold: float = 0.30      # ngưỡng ghép hộp giữa 2 khung
    max_age: int = 15                # số khung được phép mất dấu trước khi xoá
    vote_window: int = 12            # kích thước hàng đợi bỏ phiếu
    min_votes: int = 5               # số phiếu tối thiểu để xác nhận
    min_ratio: float = 0.70          # tỷ lệ phiếu tối thiểu để xác nhận
    embed_every: int = 5             # trích đặc trưng lại mỗi N khung / mỗi vết


@dataclass
class LivenessSettings:
    enabled: bool = False
    #: Mặc định là `blink`, KHÔNG phải phân tích kết cấu ảnh.
    #:
    #: Đo bằng đòn tấn công thật (điện thoại hiển thị ảnh chân dung, 60 khung mỗi
    #: loại) cho kết quả cách biệt hoàn toàn:
    #:
    #:     texture  mặt thật 0,426–0,995 · màn hình 1,000  -> ACER 50–70 %
    #:     blink    mặt thật 1,000       · màn hình 0,000  -> ACER 0 %
    #:
    #: `texture` không chỉ kém mà còn NGƯỢC: nó chấm ảnh điện thoại thật hơn mặt
    #: thật, vì được huấn luyện trên tấn công mô phỏng nên chỉ học được lối tắt
    #: "ảnh sạch là thật" — mà màn hình điện thoại thì luôn sáng và nét.
    #:
    #: `blink` đo chuyển động mí mắt qua nhiều khung. Ảnh tĩnh không thể chớp mắt,
    #: nên đây là dấu hiệu NHÂN QUẢ của sự sống chứ không phải dấu hiệu tương quan.
    #:
    #: Hệ quả kiến trúc: blink cần CHUỖI khung hình, nên chỉ chạy được ở nơi có
    #: luồng video (máy kiosk). Máy chủ chỉ nhận một tấm ảnh mỗi lần điểm danh nên
    #: về nguyên tắc không thể tự kiểm tra liveness — xem ghi chú ở deploy/compose.yml.
    backend: str = "blink"           # blink | texture | combo | none
    weights: str = ""
    threshold: float = 0.55          # dưới ngưỡng coi là giả mạo


@dataclass
class EngineSettings:
    detect: DetectSettings = field(default_factory=DetectSettings)
    quality: QualitySettings = field(default_factory=QualitySettings)
    embed: EmbedSettings = field(default_factory=EmbedSettings)
    index: IndexSettings = field(default_factory=IndexSettings)
    track: TrackSettings = field(default_factory=TrackSettings)
    liveness: LivenessSettings = field(default_factory=LivenessSettings)

    #: Ngưỡng cosine tối thiểu để không trả về Unknown.
    #:
    #: 0,68 chọn theo SỐ ĐO, không theo cảm tính. Đo trên 632 ảnh người quen và
    #: 474 ảnh người lạ (ảnh gốc, 122 người đã đăng ký):
    #:
    #:     ngưỡng   người lạ lọt (FAR)   người quen bị từ chối (FRR)
    #:      0,55         25,7 %                    1,9 %
    #:      0,60         12,0 %                    4,3 %
    #:      0,65          4,2 %                    7,4 %
    #:      0,68          2,1 %                   10,9 %
    #:      0,70          1,5 %                   13,8 %
    #:      0,75          0,2 %                   25,8 %
    #:
    #: Ngưỡng cũ 0,55 nhận nhầm **một phần tư số người lạ** — quan sát được ngay
    #: khi chạy thử: mặt một người hoàn toàn khác trên màn hình điện thoại được
    #: chấm 0,756 và gán đúng tên người đã đăng ký.
    #:
    #: Với điểm danh, hai loại lỗi KHÔNG ngang giá: nhận nhầm thì ghi sai sổ và
    #: phá hỏng chính mục đích của hệ thống, còn từ chối oan thì người dùng chỉ
    #: cần đứng lại một lần nữa. Coi nhận nhầm nặng gấp ba lần từ chối oan thì
    #: tổng lỗi nhỏ nhất rơi đúng vào 0,68.
    match_threshold: float = 0.68
    models_dir: Path = ROOT / "models"
    device: str = "auto"             # auto | cpu | cuda

    @classmethod
    def from_env(cls) -> "EngineSettings":
        """Nạp override từ biến môi trường — backend trong Docker dùng cái này."""
        s = cls()
        if v := os.getenv("FACEID_DETECT_BACKEND"):
            s.detect.backend = v
        if v := os.getenv("FACEID_EMBED_BACKEND"):
            s.embed.backend = v
        if v := os.getenv("FACEID_EMBED_WEIGHTS"):
            s.embed.weights = v
        if v := os.getenv("FACEID_INDEX_BACKEND"):
            s.index.backend = v
        if v := os.getenv("FACEID_MATCH_THRESHOLD"):
            s.match_threshold = float(v)
        if v := os.getenv("FACEID_DEVICE"):
            s.device = v
        if v := os.getenv("FACEID_MODELS_DIR"):
            s.models_dir = Path(v)
        if os.getenv("FACEID_LIVENESS") in ("1", "true", "True"):
            s.liveness.enabled = True
        return s


def resolve_device(device: str = "auto") -> str:
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001
        return "cpu"
