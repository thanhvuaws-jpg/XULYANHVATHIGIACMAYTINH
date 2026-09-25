"""Tien ich dung chung: phat hien, can chinh (alignment), trich xuat embedding, so khop.

Chay cac script bang: python -m src.<ten_script>  (tu thu muc goc du an)
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
from PIL import Image

from . import config

# facenet-pytorch (MTCNN detector + InceptionResnetV1 pretrained lam baseline)
from facenet_pytorch import MTCNN, InceptionResnetV1


# ---------------------------------------------------------------------------
# Thiet bi
# ---------------------------------------------------------------------------
def get_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ---------------------------------------------------------------------------
# Alignment: dua 5 diem landmark ve template chuan (kieu ArcFace)
# ---------------------------------------------------------------------------
_REF_112 = np.array(
    [[38.2946, 51.6963],
     [73.5318, 51.5014],
     [56.0252, 71.7366],
     [41.5493, 92.3655],
     [70.7299, 92.2041]],
    dtype=np.float32,
)
REF_PTS = _REF_112 * (config.ALIGNED_SIZE / 112.0)


def align_face(img_bgr: np.ndarray, landmarks: np.ndarray) -> np.ndarray | None:
    """Can chinh khuon mat bang phep bien doi similarity tu 5 landmark."""
    src = np.asarray(landmarks, dtype=np.float32).reshape(5, 2)
    M, _ = cv2.estimateAffinePartial2D(src, REF_PTS, method=cv2.LMEDS)
    if M is None:
        return None
    return cv2.warpAffine(
        img_bgr, M, (config.ALIGNED_SIZE, config.ALIGNED_SIZE), borderValue=0
    )


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------
class FaceDetector:
    def __init__(self, device: torch.device | None = None,
                 min_conf: float = config.DETECTION_MIN_CONF):
        self.device = device or get_device()
        self.min_conf = min_conf
        self.mtcnn = MTCNN(keep_all=True, device=self.device, post_process=False)

    def detect_boxes(self, img_bgr: np.ndarray):
        """Chi tra ve boxes + probs (nhanh, dung cho vong lap preview webcam)."""
        pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        boxes, probs = self.mtcnn.detect(pil)
        return boxes, probs

    def detect_and_align(self, img_bgr: np.ndarray) -> List[dict]:
        """Tra ve list {box, prob, face(160x160 BGR da align)} cho moi khuon mat."""
        pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        boxes, probs, lms = self.mtcnn.detect(pil, landmarks=True)
        out: List[dict] = []
        if boxes is None:
            return out
        for box, prob, lm in zip(boxes, probs, lms):
            if prob is None or prob < self.min_conf:
                continue
            face = align_face(img_bgr, lm)
            if face is None:
                continue
            out.append({"box": box.astype(int), "prob": float(prob), "face": face})
        return out

    def largest_face(self, img_bgr: np.ndarray) -> np.ndarray | None:
        """Tra ve khuon mat lon nhat (dung khi dang ky / tien xu ly 1 nguoi 1 anh)."""
        faces = self.detect_and_align(img_bgr)
        if not faces:
            return None
        faces.sort(key=lambda d: (d["box"][2] - d["box"][0]) * (d["box"][3] - d["box"][1]))
        return faces[-1]["face"]


# ---------------------------------------------------------------------------
# Mo hinh trich embedding
# ---------------------------------------------------------------------------
class FaceEmbedder(nn.Module):
    """ResNet50 backbone + neck -> vector L2-normalized (dung cho CNN tu train)."""

    def __init__(self, embedding_dim: int = config.EMBEDDING_DIM, pretrained: bool = False):
        super().__init__()
        weights = torchvision.models.ResNet50_Weights.IMAGENET1K_V2 if pretrained else None
        net = torchvision.models.resnet50(weights=weights)
        in_feat = net.fc.in_features
        net.fc = nn.Identity()
        self.backbone = net
        self.neck = nn.Sequential(
            nn.Linear(in_feat, embedding_dim),
            nn.BatchNorm1d(embedding_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.backbone(x)
        x = self.neck(x)
        return F.normalize(x, dim=1)


def face_to_tensor(face_bgr: np.ndarray, kind: str) -> torch.Tensor:
    """Anh khuon mat 160x160 BGR -> tensor CHW da chuan hoa theo loai backbone."""
    rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    t = torch.from_numpy(rgb).permute(2, 0, 1)
    if kind == "facenet":
        t = (t - 127.5) / 128.0
    else:  # resnet50 -> chuan hoa ImageNet
        t = t / 255.0
        mean = torch.tensor(config.IMAGENET_MEAN).view(3, 1, 1)
        std = torch.tensor(config.IMAGENET_STD).view(3, 1, 1)
        t = (t - mean) / std
    return t


def load_backbone(kind: str = "resnet50", weights_path: str | Path | None = None,
                  device: torch.device | None = None):
    """kind='facenet' -> InceptionResnetV1 pretrained (baseline, khong can train).
       kind='resnet50' -> FaceEmbedder, nap weights tu file da train."""
    device = device or get_device()
    if kind == "facenet":
        model = InceptionResnetV1(pretrained="vggface2").eval().to(device)
        return model, "facenet"

    model = FaceEmbedder(pretrained=False)
    if weights_path:
        state = torch.load(str(weights_path), map_location="cpu")
        model.load_state_dict(state)
    model.eval().to(device)
    return model, "resnet50"


@torch.no_grad()
def embed_faces(model, kind: str, faces_bgr: List[np.ndarray],
                device: torch.device | None = None, batch_size: int = 32) -> np.ndarray:
    device = device or get_device()
    if not faces_bgr:
        return np.zeros((0, config.EMBEDDING_DIM), dtype=np.float32)
    tensors = [face_to_tensor(f, kind) for f in faces_bgr]
    embs = []
    for i in range(0, len(tensors), batch_size):
        batch = torch.stack(tensors[i:i + batch_size]).to(device)
        out = model(batch)
        out = F.normalize(out, dim=1)
        embs.append(out.cpu().numpy().astype(np.float32))
    return np.concatenate(embs, axis=0)


# ---------------------------------------------------------------------------
# Database embedding + so khop
# ---------------------------------------------------------------------------
def load_db(path: str | Path = config.DB_PATH) -> Dict[str, np.ndarray]:
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return pickle.load(f)


def save_db(db: Dict[str, np.ndarray], path: str | Path = config.DB_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(db, f)


def match(db: Dict[str, np.ndarray], emb: np.ndarray,
          threshold: float = config.DEFAULT_THRESHOLD):
    """emb: vector (D,) da normalize. Tra ve (ten, cosine_similarity)."""
    best_name, best_sim = "Unknown", -1.0
    for name, mat in db.items():
        sim = float(np.max(mat @ emb))
        if sim > best_sim:
            best_sim, best_name = sim, name
    if best_sim < threshold:
        return "Unknown", best_sim
    return best_name, best_sim


# ---------------------------------------------------------------------------
# Ve ket qua len anh
# ---------------------------------------------------------------------------
def draw_results(img_bgr: np.ndarray, items: List[dict]) -> np.ndarray:
    out = img_bgr.copy()
    for it in items:
        x1, y1, x2, y2 = [int(v) for v in it["box"]]
        label = it.get("label", "?")
        score = it.get("score")
        known = label != "Unknown"
        color = (0, 200, 0) if known else (0, 0, 255)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        txt = label if score is None else f"{label} {score:.2f}"
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(out, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
        cv2.putText(out, txt, (x1 + 2, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return out
