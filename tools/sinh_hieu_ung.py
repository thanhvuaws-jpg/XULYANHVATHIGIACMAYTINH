"""Sinh các bộ hiệu ứng dạng dãy ảnh PNG có nền trong suốt.

    python -m tools.sinh_hieu_ung

Vì sao tự sinh thay vì tải trên mạng
------------------------------------
1. **Bản quyền.** Hiệu ứng tải về phần lớn có giấy phép ràng buộc; đồ án nộp
   trường dùng tới thì phải giải trình nguồn. Tự sinh thì thuộc sở hữu của nhóm.
2. **Khớp bảng màu.** Hiệu ứng lấy sẵn thường lệch tông so với giao diện, nhìn
   như dán vào. Ở đây màu lấy thẳng từ bảng màu của ứng dụng.
3. **Nằm trong kho mã.** Đổi màu hay đổi kích thước chỉ là sửa tham số rồi chạy
   lại, không phải đi tìm lại tệp khác.

Mỗi hiệu ứng ghi ra `effects/<tên>/frame_000.png …` với kênh alpha thật, nên bộ
nạp trộn được rìa mềm thay vì dán một khối vuông lên khung hình.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RA = Path("effects")
CO = 256                      # cạnh ảnh, đủ nét mà không nặng khi trộn mỗi khung

# Bảng màu lấy từ desktop_app.py — hiệu ứng phải cùng tông với giao diện.
XANH_NGOC = (34, 211, 238)
TIM = (167, 139, 250)
XANH_LA = (52, 211, 153)
VANG = (251, 191, 36)
CAM = (251, 146, 60)


def _luoi(n: int = CO):
    """Lưới toạ độ chuẩn hoá về [-1, 1] kèm bán kính tới tâm."""
    t = np.linspace(-1.0, 1.0, n, dtype=np.float32)
    x, y = np.meshgrid(t, t)
    return x, y, np.hypot(x, y)


def _mo_ria(cd: np.ndarray, bien: float = 0.12) -> np.ndarray:
    """Ép cường độ về 0 ở sát mép ảnh.

    Hiệu ứng chạm tới biên ảnh sẽ lộ **cạnh hộp vuông** khi trộn lên khung hình —
    nhìn thấy rõ ở ngọn lửa, vì nó lan gần hết chiều ngang. Nhân thêm một lớp
    giảm dần ở rìa để hiệu ứng tan vào nền thay vì bị cắt phẳng.
    """
    n = cd.shape[0]
    t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    giam = np.clip(np.minimum(t, 1.0 - t) / bien, 0.0, 1.0)
    return cd * giam[None, :] * giam[:, None]


def _to_rgba(mau, cuong_do: np.ndarray) -> np.ndarray:
    """Ghép màu với bản đồ cường độ thành ảnh RGBA.

    Alpha lấy chính cường độ, còn RGB được đẩy dần về trắng ở vùng mạnh — đúng
    cách nguồn sáng thật hoạt động: lõi luôn trắng hơn rìa. Thiếu chi tiết này
    thì hiệu ứng trông như miếng giấy màu chứ không như ánh sáng.
    """
    c = np.clip(cuong_do, 0.0, 1.0)
    loi = c ** 3
    rgb = np.stack([np.clip(mau[i] * c + 255.0 * loi, 0, 255) for i in range(3)], axis=-1)
    return np.dstack([rgb, c * 255.0]).astype(np.uint8)


def _ghi(ten: str, khung: list[np.ndarray]) -> None:
    d = RA / ten
    d.mkdir(parents=True, exist_ok=True)
    for cu in d.glob("frame_*.png"):
        cu.unlink()
    for i, k in enumerate(khung):
        # OpenCV ghi PNG theo thứ tự BGRA, mảng của ta là RGBA -> đảo hai kênh.
        cv2.imwrite(str(d / f"frame_{i:03d}.png"),
                    cv2.cvtColor(k, cv2.COLOR_RGBA2BGRA))
    print(f"  {ten:<18s} {len(khung):3d} khung · {CO}x{CO}")


# ------------------------------------------------------------------ hiệu ứng
def tia_lua(so_khung: int = 18, so_hat: int = 80) -> list[np.ndarray]:
    """Chùm tia bắn ra từ tâm rồi tắt dần — hợp với cử chỉ xoè bàn tay."""
    rng = np.random.default_rng(7)
    goc = rng.uniform(0, 2 * np.pi, so_hat)
    toc = rng.uniform(0.25, 0.95, so_hat)
    co_hat = rng.uniform(0.015, 0.040, so_hat)
    x, y, _ = _luoi()
    ra = []
    for f in range(so_khung):
        t = f / (so_khung - 1)
        cd = np.zeros((CO, CO), np.float32)
        for g, v, s in zip(goc, toc, co_hat):
            cx, cy = np.cos(g) * v * t, np.sin(g) * v * t
            cd += np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (s * s))
        ra.append(_to_rgba(XANH_NGOC, cd * (1.0 - t) ** 1.5))
    return ra


def vong_nang_luong(so_khung: int = 16) -> list[np.ndarray]:
    """Vòng tròn lan rộng rồi mờ dần — hợp với cử chỉ chụm ngón."""
    _, _, r = _luoi()
    ra = []
    for f in range(so_khung):
        t = f / (so_khung - 1)
        bk = 0.12 + t * 0.82
        day = 0.10 * (1.0 - t) + 0.012
        cd = np.exp(-((r - bk) ** 2) / (day * day)) * (1.0 - t) ** 1.2
        ra.append(_to_rgba(XANH_LA, cd))
    return ra


def lua(so_khung: int = 20) -> list[np.ndarray]:
    """Ngọn lửa bốc lên. Nhiễu nhiều tầng cho hình dạng tự nhiên."""
    rng = np.random.default_rng(3)
    # Ba tầng nhiễu: tầng thô tạo dáng chung, tầng mịn tạo mép lưỡi lửa.
    tang = [rng.random((8, 8)).astype(np.float32),
            rng.random((16, 16)).astype(np.float32),
            rng.random((32, 32)).astype(np.float32)]
    x, y, _ = _luoi()
    ra = []
    for f in range(so_khung):
        t = f / so_khung
        n = np.zeros((CO, CO), np.float32)
        for i, lop in enumerate(tang):
            k = lop.shape[0]
            dich = int(t * k * (i + 1)) % k          # cuộn để lửa "chảy" lên
            lan = np.roll(lop, -dich, axis=0)
            phong = cv2.resize(lan, (CO, CO), interpolation=cv2.INTER_CUBIC)
            n += phong / (i + 1)
        n = (n - n.min()) / (n.max() - n.min() + 1e-6)

        # Dáng ngọn lửa: SÁNG VÀ RỘNG Ở ĐÁY, nhọn dần lên đỉnh.
        #
        # Lưu ý về hệ trục: y chạy từ -1 (đỉnh ảnh) tới +1 (đáy ảnh). Bản đầu
        # tôi viết công thức như thể y tăng dần lên trên, nên ngọn lửa ra lộn
        # ngược — phình ở trên, chúc xuống dưới. Nhìn ảnh dựng thử mới thấy.
        duoi = np.clip((y + 1.0) / 2.0, 0, 1)          # 0 ở đỉnh, 1 ở đáy
        cao = duoi ** 1.2                              # sáng dần xuống đáy
        hep = np.exp(-(x ** 2) / (0.05 + 0.30 * duoi))  # hẹp trên, rộng dưới
        cd = _mo_ria(np.clip(cao * hep * (0.45 + 0.70 * n) * 1.15, 0, 1))

        rgba = _to_rgba(CAM, cd)
        loi = _to_rgba(VANG, np.clip((cd - 0.45) * 2.2, 0, 1))
        m = loi[..., 3:4].astype(np.float32) / 255.0
        rgba[..., :3] = (rgba[..., :3] * (1 - m) + loi[..., :3] * m).astype(np.uint8)
        ra.append(rgba)
    return ra


def khoi(so_khung: int = 22) -> list[np.ndarray]:
    """Cuộn khói lan ra rồi tan — hợp với cử chỉ nắm tay (xoá nét)."""
    rng = np.random.default_rng(11)
    tam = rng.uniform(-0.35, 0.35, (14, 2)).astype(np.float32)
    huong = rng.uniform(-1, 1, (14, 2)).astype(np.float32) * 0.55
    x, y, _ = _luoi()
    ra = []
    for f in range(so_khung):
        t = f / (so_khung - 1)
        cd = np.zeros((CO, CO), np.float32)
        for (cx, cy), (dx, dy) in zip(tam, huong):
            px, py = cx + dx * t, cy + dy * t - t * 0.30    # khói bốc lên
            s = 0.10 + t * 0.32
            cd += np.exp(-((x - px) ** 2 + (y - py) ** 2) / (s * s))
        # Chia 2.2 chứ không chia 5: bản đầu khói mờ tới mức gần như
        # không nhìn thấy trên nền tối của ứng dụng.
        ra.append(_to_rgba(TIM, _mo_ria(np.clip(cd / 2.2, 0, 1)) * (1.0 - t) ** 1.1))
    return ra


def tia_set(so_khung: int = 10) -> list[np.ndarray]:
    """Tia sét phân nhánh. Mỗi khung một hình khác nên nhấp nháy tự nhiên."""
    ra = []
    for f in range(so_khung):
        rng = np.random.default_rng(100 + f)
        cd = np.zeros((CO, CO), np.float32)

        def ve(x0, y0, x1, y1, lech, sau):
            """Dịch điểm giữa đệ quy — cách dựng đường gãy khúc kiểu tia sét."""
            if sau == 0 or abs(y1 - y0) < 3:
                cv2.line(cd, (int(x0), int(y0)), (int(x1), int(y1)), 1.0, 1)
                return
            mx = (x0 + x1) / 2 + rng.normal(0, lech)
            my = (y0 + y1) / 2
            ve(x0, y0, mx, my, lech / 2, sau - 1)
            ve(mx, my, x1, y1, lech / 2, sau - 1)
            if sau > 2 and rng.random() < 0.45:              # nhánh phụ
                ve(mx, my, mx + rng.normal(0, 40),
                   my + abs(y1 - y0) * 0.35, lech / 2, sau - 2)

        ve(CO // 2 + rng.normal(0, 12), 6, CO // 2 + rng.normal(0, 30), CO - 6, 34, 6)
        # Quầng sáng rộng cộng với lõi sắc — tia sét không bao giờ là một nét đơn.
        quang = cv2.GaussianBlur(cd, (0, 0), 6.0) * 3.0
        sac = cv2.GaussianBlur(cd, (0, 0), 1.0) * 1.5
        ra.append(_to_rgba(XANH_NGOC, np.clip(sac + quang, 0, 1)))
    return ra


def main() -> int:
    print("Sinh hiệu ứng vào thư mục effects/\n")
    _ghi("tia_lua", tia_lua())
    _ghi("vong_nang_luong", vong_nang_luong())
    _ghi("lua", lua())
    _ghi("khoi", khoi())
    _ghi("tia_set", tia_set())
    so = len(list(RA.rglob("frame_*.png")))
    dung = sum(p.stat().st_size for p in RA.rglob("*.png")) / 1e6
    print(f"\nTổng {so} ảnh · {dung:.1f} MB · {RA.resolve()}")
    print("\nThả thêm hiệu ứng của riêng bạn: tạo effects/<tên>/ rồi bỏ vào dãy")
    print("ảnh PNG đặt tên frame_000.png, frame_001.png… App tự quét lúc khởi động.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
