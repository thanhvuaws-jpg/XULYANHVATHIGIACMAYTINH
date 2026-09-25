"""ArcFace loss — biên độ góc cộng thêm (Additive Angular Margin).

Tham khảo: Deng et al., *ArcFace: Additive Angular Margin Loss for Deep Face
Recognition*, CVPR 2019.

Ý tưởng
-------
Softmax thường chỉ ép các lớp tách nhau, không quan tâm tách *rộng* bao nhiêu.
ArcFace chuẩn hoá cả embedding lẫn vector trọng số của từng lớp về độ dài 1, nên
tích vô hướng chính là `cos θ` — góc giữa đặc trưng và tâm lớp. Sau đó nó cộng
thêm một biên độ `m` vào góc của **đúng lớp thật**, buộc mạng phải kéo góc đó nhỏ
hơn nữa mới giảm được loss. Kết quả: các lớp bị đẩy ra xa nhau trên mặt cầu, và
khoảng cách cosine trở thành thước đo danh tính dùng được cho cả người chưa từng
thấy lúc train.

Vì sao lần train trước không hội tụ
-----------------------------------
Đặt thẳng `m = 0.5` ngay từ epoch đầu là bài toán quá khó: mạng chưa học được gì
mà đã bị phạt biên độ tối đa, gradient hỗn loạn và loss đi ngang. Lớp
`ArcFaceLoss` ở đây có sẵn cơ chế **khởi động dần biên độ** (`set_epoch`): `m`
tăng tuyến tính từ 0 lên giá trị đích trong vài epoch đầu, nên giai đoạn đầu mạng
học như softmax bình thường rồi mới siết dần.
"""
from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class ArcFaceLoss(nn.Module):
    """Lớp phân loại có biên độ góc + cross-entropy, gộp làm một.

    Args:
        embedding_dim: số chiều vector đặc trưng.
        num_classes:   số danh tính trong tập huấn luyện.
        scale:         `s` — bán kính mặt cầu. Chuẩn là 64 cho tập lớn, 30 cho tập nhỏ.
        margin:        `m` — biên độ góc đích, radian. Chuẩn 0.5 (~28.6°).
        warmup_epochs: số epoch để tăng `m` từ 0 lên `margin`.
        label_smoothing: làm mềm nhãn, chống quá tự tin.
    """

    def __init__(self, embedding_dim: int, num_classes: int, *, scale: float = 64.0,
                 margin: float = 0.5, warmup_epochs: int = 5,
                 label_smoothing: float = 0.1, easy_margin: bool = False):
        super().__init__()
        self.embedding_dim = embedding_dim
        self.num_classes = num_classes
        self.scale = scale
        self.target_margin = margin
        self.warmup_epochs = max(0, warmup_epochs)
        self.easy_margin = easy_margin

        self.weight = nn.Parameter(torch.empty(num_classes, embedding_dim))
        nn.init.xavier_normal_(self.weight)
        self.criterion = nn.CrossEntropyLoss(label_smoothing=label_smoothing)

        self._margin = 0.0 if self.warmup_epochs else margin
        self._refresh()

    # ------------------------------------------------------------ biên độ
    def _refresh(self):
        m = self._margin
        self._cos_m = math.cos(m)
        self._sin_m = math.sin(m)
        self._threshold = math.cos(math.pi - m)      # ngưỡng để θ + m còn < π
        self._mm = math.sin(math.pi - m) * m

    def set_epoch(self, epoch: int) -> float:
        """Cập nhật biên độ theo lịch khởi động. Gọi ở đầu mỗi epoch."""
        if self.warmup_epochs <= 0:
            self._margin = self.target_margin
        else:
            ratio = min(1.0, epoch / float(self.warmup_epochs))
            self._margin = self.target_margin * ratio
        self._refresh()
        return self._margin

    @property
    def margin(self) -> float:
        return self._margin

    # ------------------------------------------------------------ forward
    def logits(self, embeddings: torch.Tensor) -> torch.Tensor:
        """cos θ với mọi tâm lớp — dùng lúc đánh giá, không cộng biên độ.

        `eps=1e-6` thay cho mặc định 1e-12: dưới mixed precision, 1e-12 nằm ngoài
        dải fp16 nên không chặn nổi phép chia cho 0 khi một hàng trọng số có
        chuẩn rất nhỏ, và kết quả hoá NaN.
        """
        return F.linear(F.normalize(embeddings, eps=1e-6),
                        F.normalize(self.weight, eps=1e-6))

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        cosine = self.logits(embeddings).clamp(-1 + 1e-7, 1 - 1e-7)

        if self._margin <= 0:                       # giai đoạn khởi động: softmax thường
            return self.criterion(cosine * self.scale, labels)

        sine = torch.sqrt((1.0 - cosine.pow(2)).clamp_min(1e-9))
        # cos(θ + m) = cos θ·cos m − sin θ·sin m
        phi = cosine * self._cos_m - sine * self._sin_m

        if self.easy_margin:
            phi = torch.where(cosine > 0, phi, cosine)
        else:
            # Khi θ + m vượt quá π, hàm cos không còn đơn điệu; dùng nhánh tuyến tính.
            phi = torch.where(cosine > self._threshold, phi, cosine - self._mm)

        one_hot = torch.zeros_like(cosine)
        one_hot.scatter_(1, labels.view(-1, 1).long(), 1.0)
        output = (one_hot * phi + (1.0 - one_hot) * cosine) * self.scale
        return self.criterion(output, labels)

    @torch.no_grad()
    def accuracy(self, embeddings: torch.Tensor, labels: torch.Tensor) -> float:
        return (self.logits(embeddings).argmax(dim=1) == labels).float().mean().item()
