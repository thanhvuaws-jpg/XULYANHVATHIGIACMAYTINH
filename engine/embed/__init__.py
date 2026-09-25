"""Các bộ trích đặc trưng khuôn mặt.

Vì sao KHÔNG `from .mobilefacenet import MobileFaceNet` ở đây
-------------------------------------------------------------
`mobilefacenet.py` import torch ở cấp mô-đun. Nếu gói này nạp sẵn nó thì mọi lời
gọi `import engine.embed` đều kéo theo torch — kể cả khi chương trình chỉ định
dùng ONNX Runtime.

Đó không phải chuyện lý thuyết: container backend cố tình không cài torch, và
chính dòng import sẵn ở đây từng làm nó **chết ngay lúc khởi động** với
`ModuleNotFoundError: No module named 'torch'` — dù đường chạy thật không hề đụng
tới PyTorch. Thiết kế nạp lười ở `base.build_embedder()` bị vô hiệu hoá chỉ bởi
một dòng trong `__init__.py`, và ở máy phát triển thì không ai thấy vì máy nào
cũng có torch.

`backend/tests/test_no_torch.py` canh đúng chuyện này.

`__getattr__` cấp mô-đun (PEP 562) giữ được `from engine.embed import
MobileFaceNet` cho mã huấn luyện, nhưng chỉ thực sự nạp torch vào đúng lúc ai đó
hỏi tới cái tên ấy.
"""
from .base import Embedder, build_embedder, l2_normalize

__all__ = ["Embedder", "build_embedder", "l2_normalize", "MobileFaceNet"]


def __getattr__(name: str):
    if name == "MobileFaceNet":
        from .mobilefacenet import MobileFaceNet
        return MobileFaceNet
    raise AttributeError(f"module {__name__!r} không có thuộc tính {name!r}")
