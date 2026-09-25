"""Cau hinh & duong dan dung chung cho toan bo du an."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
KAGGLE_DIR = DATA_DIR / "kaggle"        # dataset tai tu Kaggle (can kaggle.json)
DATASETS_DIR = DATA_DIR / "datasets"   # dataset cong khai khac (LFW qua scikit-learn, khong can token)
ENROLLED_DIR = DATA_DIR / "enrolled"   # anh tu chup bang webcam (ImageFolder)
ALIGNED_DIR = DATA_DIR / "aligned"     # khuon mat da cat + can chinh 160x160 (gop ca 2 nguon)
MODELS_DIR = ROOT / "models"
DB_DIR = ROOT / "db"
REPORTS_DIR = ROOT / "reports"

DB_PATH = DB_DIR / "embeddings.pkl"    # {ten_nguoi: np.ndarray (N, EMBEDDING_DIM)}

# --- Tham so mo hinh ---
ALIGNED_SIZE = 160        # kich thuoc anh khuon mat sau alignment
EMBEDDING_DIM = 512       # so chieu vector dac trung
# 0.68 chon theo so do: o 0.55 co toi 25.7% nguoi la lot qua. Xem giai thich
# day du trong engine/settings.py.
DEFAULT_THRESHOLD = 0.68
                          # (FaceNet tren LFW: EER @ ~0.57; chay src.evaluate de tinh lai cho model cua ban)
DETECTION_MIN_CONF = 0.90 # bo qua khuon mat co xac suat phat hien thap hon nguong nay

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

# Tao san cac thu muc
for _d in (DATA_DIR, KAGGLE_DIR, DATASETS_DIR, ENROLLED_DIR, ALIGNED_DIR, MODELS_DIR, DB_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
