# syntax=docker/dockerfile:1
#
# Image phục vụ giao diện web (React + Vite → tệp tĩnh → nginx).
#
# Build (từ thư mục gốc dự án):
#     docker build -f deploy/web.Dockerfile -t faceid-web .
#
# Vì sao nhiều tầng: Node và toàn bộ node_modules chỉ cần lúc BUILD. Kết quả build
# là mấy tệp .html/.js/.css tĩnh. Tầng chạy thật chỉ là nginx + đống tệp đó:
#
#     node:20-alpine kèm node_modules   ~ 450 MB
#     nginx:alpine + dist/              ~  55 MB
#
# Không có Node trong image chạy thật cũng đồng nghĩa không có runtime JavaScript
# nào để khai thác nếu ai đó tìm được lỗ hổng.

# ============================================================ tầng 1: build
FROM node:20-alpine AS builder

WORKDIR /src

# Chép riêng tệp khai báo phụ thuộc TRƯỚC. Sửa mã nguồn React mà không đổi phụ
# thuộc thì Docker dùng lại tầng `npm ci` từ bộ nhớ đệm — tiết kiệm hàng chục giây
# mỗi lần build.
COPY web/package.json web/package-lock.json* ./

# `npm ci` (không phải `install`): cài đúng theo lock file, dựng lại y hệt mọi lần.
# Không có lock file thì lùi về `install` để build vẫn chạy được.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY web/ ./
RUN npm run build


# ============================================================ tầng 2: phục vụ
FROM nginx:1.27-alpine AS runtime

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /src/dist /usr/share/nginx/html

EXPOSE 80

# Dùng 127.0.0.1 chứ KHÔNG dùng `localhost`.
#
# Trong container, /etc/hosts ánh xạ `localhost` sang cả 127.0.0.1 lẫn ::1, còn
# nginx với `listen 80;` chỉ nghe IPv4. `wget` của busybox thử ::1 trước rồi bỏ
# cuộc ngay — không như curl vốn tự thử nốt địa chỉ còn lại. Hậu quả: container
# phục vụ trang hoàn toàn bình thường nhưng Docker vẫn gắn nhãn `unhealthy`, và
# ở môi trường thật thì nó sẽ bị khởi động lại hoặc bị gỡ khỏi bộ cân bằng tải
# dù chẳng hỏng gì. Đã gặp thật: 94 lần thất bại liên tiếp trong khi web vẫn chạy.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
