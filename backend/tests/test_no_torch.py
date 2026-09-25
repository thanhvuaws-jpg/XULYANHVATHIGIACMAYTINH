"""Kiểm tra: backend phải nạp được KHI KHÔNG CÓ PyTorch.

    python -m backend.tests.test_no_torch

Vì sao cần bài test này
-----------------------
Container triển khai cố tình không cài torch — mô hình đã xuất sang ONNX nên lúc
chạy chỉ cần onnxruntime, và image tụt từ khoảng 3 GB xuống dưới 700 MB.

Nhưng "không cần torch" là một tính chất **rất dễ vỡ**. Nó phụ thuộc vào việc mọi
lời import torch đều nằm bên trong hàm, không ở cấp mô-đun. Chỉ cần một dòng
`from .mobilefacenet import MobileFaceNet` trong một tệp `__init__.py` là toàn bộ
tính chất đó biến mất — và ở máy phát triển sẽ **không ai phát hiện ra**, vì máy
phát triển có torch. Lỗi chỉ nổ khi container khởi động, tức là lúc triển khai.

Chuyện này đã xảy ra thật: `engine/embed/__init__.py` nạp sẵn `MobileFaceNet`,
container chết ngay lúc khởi động với `ModuleNotFoundError: No module named
'torch'` dù đường chạy thật không hề đụng tới PyTorch.

Bài test giả lập việc torch vắng mặt bằng cách chặn nó ở `sys.modules`, nên nó
chạy được ngay trên máy phát triển CÓ torch.
"""
from __future__ import annotations

import importlib
import sys

BLOCKED = ("torch", "torchvision", "facenet_pytorch")
_p = _f = 0


class BlockTorch:
    """Trình tìm mô-đun đứng đầu `sys.meta_path`, từ chối mọi lời import torch."""

    def find_module(self, name, path=None):        # API cũ, một số nơi vẫn gọi
        return self.find_spec(name, path)

    def find_spec(self, name, path=None, target=None):
        root = name.split(".")[0]
        if root in BLOCKED:
            raise ModuleNotFoundError(f"No module named {root!r}")
        return None


def check(name: str, cond: bool = True, detail: str = "") -> None:
    global _p, _f
    if cond:
        _p += 1
        print(f"  [OK]  {name}" + (f"   {detail}" if detail else ""))
    else:
        _f += 1
        print(f"  [LỖI] {name}   {detail}")


def purge() -> None:
    """Xoá mọi mô-đun đã nạp của dự án và của torch, để lần import sau chạy lại thật."""
    for mod in list(sys.modules):
        root = mod.split(".")[0]
        if root in BLOCKED or root in ("engine", "backend"):
            del sys.modules[mod]


def main() -> int:
    print("=== Giả lập môi trường KHÔNG có PyTorch ===")
    purge()
    blocker = BlockTorch()
    sys.meta_path.insert(0, blocker)
    try:
        try:
            import torch                                    # noqa: F401
            check("Chặn torch thành công", False, "vẫn import được torch")
            return 1
        except ModuleNotFoundError:
            check("Chặn torch thành công")

        # --- 1. Gói engine ---
        try:
            import engine
            import engine.embed
            import engine.detect
            import engine.pipeline
            check("Nạp được engine.pipeline", True, f"phiên bản {engine.__version__}")
        except ModuleNotFoundError as e:
            check("Nạp được engine.pipeline", False, str(e))
            return 1

        # --- 2. Dựng embedder ONNX ---
        try:
            from engine.embed import build_embedder
            from engine.settings import EmbedSettings
            emb = build_embedder(EmbedSettings(
                backend="onnx", weights="models/mobilefacenet_distill_casia.onnx"))
            check("Dựng được embedder ONNX", True,
                  f"{emb.image_size}×{emb.image_size} → {emb.dim} chiều")
        except Exception as e:                              # noqa: BLE001
            check("Dựng được embedder ONNX", False, f"{type(e).__name__}: {e}")

        # --- 3. Toàn bộ ứng dụng backend ---
        try:
            from backend.app.main import app
            check("Nạp được backend.app.main", True,
                  f"{len(app.routes)} tuyến đường")
        except ModuleNotFoundError as e:
            check("Nạp được backend.app.main", False, str(e))

        # --- 4. Tên MobileFaceNet vẫn còn, chỉ là nạp lười ---
        # Hỏi tới nó thì PHẢI hỏng — đúng như trong container thật. Điều quan
        # trọng là nó chỉ hỏng khi bị hỏi, không hỏng lúc nạp gói.
        try:
            from engine.embed import MobileFaceNet          # noqa: F401
            check("MobileFaceNet nạp lười đúng cách", False,
                  "lấy được cả khi không có torch — đáng ngờ")
        except ModuleNotFoundError:
            check("MobileFaceNet nạp lười đúng cách",
                  True, "chỉ hỏng khi bị gọi tên, không hỏng lúc nạp gói")

        # --- 5. Không mô-đun nào của dự án kéo torch vào ---
        leaked = [m for m in sys.modules if m.split(".")[0] in BLOCKED]
        check("Không mô-đun nào kéo torch vào", not leaked,
              f"bị kéo vào: {leaked}" if leaked else "")
    finally:
        sys.meta_path.remove(blocker)
        purge()

    print(f"\n{'='*54}\n  {_p} đạt · {_f} lỗi\n{'='*54}")
    if _f:
        print("\nGợi ý: tìm dòng `import torch` ở CẤP MÔ-ĐUN trong engine/ hoặc")
        print("backend/. Mọi lời import torch phải nằm bên trong hàm.")
    return 0 if _f == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
