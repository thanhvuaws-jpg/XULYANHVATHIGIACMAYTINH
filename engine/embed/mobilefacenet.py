"""MobileFaceNet — kiến trúc backbone cho bài toán khuôn mặt.

Tham khảo: Chen et al., *MobileFaceNets: Efficient CNNs for Accurate Real-Time
Face Verification on Mobile Devices*, 2018.

Vì sao chọn kiến trúc này thay cho ResNet50:

  • **~1,0 triệu tham số** so với 25 triệu → vừa thoải mái VRAM 4 GB của GTX 1650
    với batch 128, trong khi ResNet50 phải hạ batch xuống rất thấp mà ArcFace lại
    cần batch lớn để ổn định.
  • Thiết kế riêng cho ảnh 112×112, dùng **GDConv** (global depthwise conv) thay
    cho global average pooling ở tầng cuối — GAP coi mọi vị trí không gian như
    nhau, trong khi với khuôn mặt đã căn chỉnh thì vùng giữa (mắt, mũi) quan
    trọng hơn hẳn vùng rìa. Đây chính là đóng góp chính của bài báo.
  • Nhanh hơn ResNet50 khoảng 10 lần khi chạy suy luận.

Module này được dùng chung bởi cả `training/` và `engine/` nên kiến trúc lúc
train và lúc chạy chắc chắn khớp nhau.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class ConvBlock(nn.Module):
    """Conv → BN → PReLU. Đặt `linear=True` để bỏ hàm kích hoạt."""

    def __init__(self, in_c, out_c, kernel=1, stride=1, padding=0, groups=1, linear=False):
        super().__init__()
        self.conv = nn.Conv2d(in_c, out_c, kernel, stride, padding, groups=groups, bias=False)
        self.bn = nn.BatchNorm2d(out_c)
        self.act = None if linear else nn.PReLU(out_c)

    def forward(self, x):
        x = self.bn(self.conv(x))
        return x if self.act is None else self.act(x)


class Bottleneck(nn.Module):
    """Inverted residual kiểu MobileNetV2: nở kênh → depthwise → nén kênh."""

    def __init__(self, in_c, out_c, stride, expansion):
        super().__init__()
        hidden = in_c * expansion
        self.use_residual = (stride == 1 and in_c == out_c)
        self.block = nn.Sequential(
            ConvBlock(in_c, hidden, kernel=1),
            ConvBlock(hidden, hidden, kernel=3, stride=stride, padding=1, groups=hidden),
            ConvBlock(hidden, out_c, kernel=1, linear=True),
        )

    def forward(self, x):
        out = self.block(x)
        return x + out if self.use_residual else out


class MobileFaceNet(nn.Module):
    """Nhận ảnh (N, 3, 112, 112), trả về embedding (N, dim) đã chuẩn hoá L2."""

    # (expansion, out_channels, num_blocks, stride)
    CONFIG = [
        (2, 64, 5, 2),
        (4, 128, 1, 2),
        (2, 128, 6, 1),
        (4, 128, 1, 2),
        (2, 128, 2, 1),
    ]

    def __init__(self, embedding_dim: int = 512, input_size: int = 112):
        super().__init__()
        if input_size % 16 != 0:
            raise ValueError("input_size phải chia hết cho 16")
        self.embedding_dim = embedding_dim
        self.input_size = input_size

        self.stem = ConvBlock(3, 64, kernel=3, stride=2, padding=1)
        self.dw = ConvBlock(64, 64, kernel=3, stride=1, padding=1, groups=64)

        layers, in_c = [], 64
        for expansion, out_c, num, stride in self.CONFIG:
            for i in range(num):
                layers.append(Bottleneck(in_c, out_c, stride if i == 0 else 1, expansion))
                in_c = out_c
        self.blocks = nn.Sequential(*layers)

        self.conv_expand = ConvBlock(in_c, 512, kernel=1)
        # GDConv: depthwise trên toàn bộ bản đồ đặc trưng còn lại (112/16 = 7).
        gd_kernel = input_size // 16
        self.gdconv = ConvBlock(512, 512, kernel=gd_kernel, groups=512, linear=True)
        self.features = nn.Sequential(
            nn.Flatten(),
            nn.Linear(512, embedding_dim, bias=False),
            nn.BatchNorm1d(embedding_dim),
        )
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="leaky_relu")
            elif isinstance(m, (nn.BatchNorm2d, nn.BatchNorm1d)):
                nn.init.constant_(m.weight, 1.0)
                nn.init.constant_(m.bias, 0.0)
            elif isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0, 0.01)

    def forward(self, x: torch.Tensor, normalize: bool = True) -> torch.Tensor:
        x = self.dw(self.stem(x))
        x = self.blocks(x)
        x = self.gdconv(self.conv_expand(x))
        x = self.features(x)
        # eps=1e-6 chứ không dùng mặc định 1e-12: dưới chế độ mixed precision,
        # 1e-12 nằm ngoài dải biểu diễn của fp16 nên không chặn được phép chia
        # cho 0, và embedding sẽ hoá NaN.
        return F.normalize(x, dim=1, eps=1e-6) if normalize else x

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())
