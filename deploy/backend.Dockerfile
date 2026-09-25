# syntax=docker/dockerfile:1
#
# Image chạy API nhận diện + điểm danh.
#
# Build (từ THƯ MỤC GỐC dự án, không phải từ deploy/):
#     docker build -f deploy/backend.Dockerfile -t faceid-backend .
#
# Ba quyết định đáng ghi vào báo cáo
# ----------------------------------
# 1. **Không cài PyTorch.** Mô hình đã xuất sang ONNX nên lúc chạy chỉ cần
#    onnxruntime (66 MB đo trong image) thay cho torch + torchvision.
#    Tính chất này rất dễ vỡ — chỉ một dòng `import torch` ở cấp mô-đun trong
#    engine/ là hỏng, mà ở máy phát triển sẽ không ai thấy vì máy nào cũng có
#    torch. `backend/tests/test_no_torch.py` canh đúng chuyện đó.
# 2. **Nhiều tầng, và chỉ chép MÔI TRƯỜNG ẢO sang.** Xem ghi chú dài bên dưới —
#    đây là chỗ dễ mất vài trăm MB mà không nhận ra.
# 3. **Chạy bằng người dùng thường.** Container mặc định chạy quyền root; một lỗ
#    hổng trong API sẽ thành quyền root trong container.

# ============================================================ tầng 1: cài đặt
FROM python:3.13-slim AS builder

# hnswlib không có wheel dựng sẵn cho mọi nền → cần trình biên dịch C++.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Cài vào một môi trường ảo riêng thay vì vào Python hệ thống. Nhờ vậy tầng sau
# chỉ cần chép đúng MỘT thư mục là có trọn bộ phụ thuộc.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY deploy/requirements-backend.txt .
RUN pip install --no-cache-dir -r requirements-backend.txt \
    # Dọn những thứ chỉ có ích lúc cài, không có ích lúc chạy:
    #   __pycache__  — sinh lại được, mà container chạy PYTHONDONTWRITEBYTECODE
    #   */tests      — bộ test của scipy/sklearn, vài chục MB không bao giờ chạy
    #   pip, setuptools — image chạy thật không cài thêm gói nào nữa
    # Đo được: bớt khoảng 130 MB. Bộ kiểm thử khói (deploy/smoke_test.py) là chốt
    # chặn — nếu xoá nhầm thứ gì cần thiết thì nó sẽ đỏ ngay.
    && find /opt/venv -name '__pycache__' -type d -prune -exec rm -rf {} + \
    && find /opt/venv -path '*/site-packages/*/tests' -type d -prune -exec rm -rf {} + \
    && rm -rf /opt/venv/lib/python3.13/site-packages/pip \
              /opt/venv/lib/python3.13/site-packages/setuptools \
              /opt/venv/lib/python3.13/site-packages/pkg_resources


# ============================================================ tầng 2: chạy thật
FROM python:3.13-slim AS runtime

# PYTHONUNBUFFERED: log ra ngay, không kẹt trong bộ đệm khi `docker logs`.
# PYTHONDONTWRITEBYTECODE: không sinh .pyc trong container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=2 \
    PATH="/opt/venv/bin:$PATH"

# libgomp1: onnxruntime và scikit-learn liên kết động tới OpenMP.
# curl: dùng cho HEALTHCHECK ở cuối tệp.
# Không cần libGL — đó chính là lý do chọn opencv-python-headless.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Chỉ chép môi trường ảo đã cài xong.
#
# VÌ SAO KHÔNG chép các bánh xe (wheel) rồi cài ở đây: cách đó từng làm image
# phình thêm 180 MB một cách vô hình. Mỗi lệnh trong Dockerfile tạo ra một tầng,
# và các tầng chỉ CỘNG DỒN — `COPY /wheels /wheels` rồi `RUN pip install … &&
# rm -rf /wheels` ở lệnh sau KHÔNG hề làm image nhỏ lại: bánh xe đã bị đóng băng
# trong tầng COPY, lệnh xoá chỉ thêm một tầng ghi đè lên chỗ trống đó. Chép thẳng
# môi trường ảo thì bánh xe không bao giờ bước chân vào image cuối.
COPY --from=builder /opt/venv /opt/venv

# Tạo người dùng TRƯỚC khi chép mã nguồn.
#
# VÌ SAO KHÔNG `chown -R /app` sau khi chép: `chown -R` sờ vào metadata của mọi
# tệp, mà tầng nào cũng ghi lại nguyên vẹn tệp bị đổi — nên nó nhân đôi toàn bộ
# cây /app thành một tầng mới (đo được 21 MB). `COPY --chown=` đặt quyền ngay lúc
# ghi, không tốn thêm tầng nào.
RUN useradd --create-home --shell /usr/sbin/nologin faceid \
    && mkdir -p /app/storage /app/db \
    && chown faceid:faceid /app /app/storage /app/db

WORKDIR /app

# Chép mã nguồn SAU khi cài phụ thuộc. Sửa một dòng code thì Docker chỉ dựng lại
# từ đây trở xuống; tầng cài đặt (chậm nhất) vẫn được dùng lại từ bộ nhớ đệm.
COPY --chown=faceid:faceid engine/  ./engine/
COPY --chown=faceid:faceid backend/ ./backend/

# Chỉ nướng mô hình ONNX + bộ phân loại chống giả mạo (~20 MB).
# .dockerignore đã loại các checkpoint .pt (~230 MB) vì bản chạy không cần.
COPY --chown=faceid:faceid models/*.onnx         ./models/
COPY --chown=faceid:faceid models/liveness_*.pkl ./models/

USER faceid

EXPOSE 8000

# Nếu engine không nạp được, /api/system/health vẫn trả 200 nhưng engine_loaded=false.
# Ở đây coi container là "hỏng" khi cổng không trả lời; engine hỏng đã có log riêng
# và trang Hệ thống trên web báo riêng.
# 127.0.0.1 chứ không phải `localhost`: trong container `localhost` phân giải ra
# cả ::1, mà uvicorn ở đây chỉ nghe IPv4. curl tự thử nốt địa chỉ còn lại nên vẫn
# qua, nhưng viết thẳng địa chỉ IPv4 thì không phụ thuộc vào hành vi đó nữa.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/system/health || exit 1

# 1 worker là cố ý: engine giữ mô hình và chỉ mục vector trong RAM của tiến trình.
# Nhiều worker sẽ nhân bản mô hình và mỗi bản có chỉ mục riêng — đăng ký người mới
# ở worker này thì worker kia không thấy. Muốn mở rộng thì tách engine thành dịch
# vụ riêng có chỉ mục dùng chung, không phải tăng số worker.
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
