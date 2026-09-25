"""ArcFace head (ArcMarginProduct) - dung khi train CNN voi --loss arcface.

Tham khao: Deng et al., "ArcFace: Additive Angular Margin Loss for Deep Face
Recognition", CVPR 2019.
"""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class ArcMarginProduct(nn.Module):
    def __init__(self, in_features: int, out_features: int,
                 s: float = 30.0, m: float = 0.50, easy_margin: bool = False):
        super().__init__()
        self.s = s
        self.m = m
        self.easy_margin = easy_margin
        self.weight = nn.Parameter(torch.FloatTensor(out_features, in_features))
        nn.init.xavier_uniform_(self.weight)

        self.cos_m = math.cos(m)
        self.sin_m = math.sin(m)
        self.th = math.cos(math.pi - m)
        self.mm = math.sin(math.pi - m) * m

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        cosine = F.linear(F.normalize(embeddings), F.normalize(self.weight))
        cosine = cosine.clamp(-1 + 1e-7, 1 - 1e-7)
        sine = torch.sqrt(1.0 - cosine ** 2)
        phi = cosine * self.cos_m - sine * self.sin_m
        if self.easy_margin:
            phi = torch.where(cosine > 0, phi, cosine)
        else:
            phi = torch.where(cosine > self.th, phi, cosine - self.mm)

        one_hot = torch.zeros_like(cosine)
        one_hot.scatter_(1, labels.view(-1, 1).long(), 1.0)
        output = one_hot * phi + (1.0 - one_hot) * cosine
        return output * self.s

    @torch.no_grad()
    def logits_eval(self, embeddings: torch.Tensor) -> torch.Tensor:
        """Dung khi danh gia: cosine voi tung class weight (khong them margin)."""
        return F.linear(F.normalize(embeddings), F.normalize(self.weight))
