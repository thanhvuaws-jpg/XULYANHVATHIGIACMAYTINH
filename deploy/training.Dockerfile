# syntax=docker/dockerfile:1
#
# Image HUẤN LUYỆN — nặng (~7 GB), chỉ dùng khi cần train lại từ đầu.
#
# Nằm sau profile `train` trong compose nên `docker compose up` thường ngày sẽ
# KHÔNG dựng nó. Muốn dùng phải gọi tên rõ ràng:
#
#     docker compose --profile train build training
#     docker compose --profile train run --rm training \
#         python -m training.train --config training/configs/casia.yaml
#
# Cần NVIDIA Container Toolkit trên máy chủ để container thấy được GPU. Không có
# thì vẫn chạy được bằng CPU, chỉ là chậm hơn khoảng hai bậc.
#
# Ghi chú trung thực cho báo cáo: toàn bộ số liệu huấn luyện trong đồ án này được
# đo TRỰC TIẾP trên Windows với GTX 1650, không qua container. Image này tồn tại
# để người khác dựng lại được kết quả trên máy Linux, chứ không phải môi trường đã
# sinh ra các con số đó.

# Image nền đã có sẵn PyTorch biên dịch kèm CUDA và cuDNN — tự cài từ đầu vừa lâu
# vừa dễ lệch phiên bản CUDA với driver.
FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLBACKEND=Agg
    # MPLBACKEND=Agg: matplotlib trong container không có màn hình. Thiếu dòng này
    # thì mọi lệnh vẽ biểu đồ đánh giá sẽ chết vì không tìm thấy trình hiển thị.

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY deploy/requirements-training.txt .
# Tách làm hai lệnh vì facenet-pytorch phải cài với --no-deps (xem ghi chú trong
# tệp requirements). Dùng grep -v để loại nó khỏi lượt cài thường.
RUN grep -v '^facenet-pytorch' requirements-training.txt > /tmp/base.txt \
    && pip install --no-cache-dir -r /tmp/base.txt \
    && pip install --no-cache-dir --no-deps facenet-pytorch==2.6.0

COPY engine/   ./engine/
COPY training/ ./training/

# data/, models/, reports/ đều gắn volume lúc chạy — dữ liệu huấn luyện gần 4 GB,
# nướng vào image là vô nghĩa vì mỗi lần đổi dữ liệu lại phải build lại.
VOLUME ["/app/data", "/app/models", "/app/reports"]

CMD ["python", "-m", "training.train", "--help"]
