# Triển khai bằng Docker

Toàn bộ hệ thống — API, engine nhận diện, giao diện web — gói trong hai image và
chạy bằng một lệnh. Không cần cài Python, Node hay OpenCV trên máy đích.

## Chạy nhanh

```bash
cd deploy
cp .env.example .env
# mở .env, đổi FACEID_SECRET_KEY (lệnh sinh khoá có ghi sẵn trong tệp)
docker compose up -d --build
```

| Địa chỉ | Nội dung |
|---|---|
| <http://localhost:8090> | Giao diện web |
| <http://localhost:8090/docs> | Tài liệu API (Swagger) |

Đăng nhập lần đầu: `admin` / `admin123` — **đổi ngay sau khi vào được**.

Dừng: `docker compose down` · Dừng và xoá sạch dữ liệu: `docker compose down -v`

Kiểm chứng hệ thống đã triển khai chạy đúng (20 phép thử qua HTTP thật):

```bash
python deploy/smoke_test.py
```

## Sơ đồ

```
                    ┌─────────────────── cổng 8090 (duy nhất mở ra ngoài)
                    │
trình duyệt ────────┤
                    │
              ┌─────▼──────┐   tệp tĩnh React (nginx tự trả)
              │    web     │
              │  (nginx)   │   /api/*  ──┐
              └────────────┘             │
                                  ┌──────▼──────┐
                                  │   backend   │  uvicorn + FastAPI
                                  │             │  engine: YuNet → căn chỉnh
                                  │             │  → chống giả mạo → ONNX
                                  └──────┬──────┘  → chỉ mục → bám vết
                                         │
                                  ┌──────▼──────┐
                                  │ SQLite hoặc │
                                  │  Postgres   │
                                  └─────────────┘
```

`backend` **không** mở cổng ra máy chủ. Chỉ nginx gọi được nó, qua mạng nội bộ của
Docker. Muốn gọi thẳng API lúc gỡ lỗi thì dùng lớp phủ dev bên dưới.

## Vì sao image backend không có PyTorch

Mô hình đã huấn luyện được xuất sang ONNX bằng `training/export_onnx.py`, nên lúc
chạy chỉ cần ONNX Runtime. Số đo thật của hai image dựng bằng cùng một Dockerfile,
chỉ khác ở chỗ có thêm `torch` + `torchvision` (bản CPU):

| Image backend | Dung lượng đo được | Một lần trích đặc trưng |
|---|---|---|
| Có `torch` (bản CPU) | 1,92 GB | 9,1 ms |
| **Chỉ `onnxruntime`** | **941 MB** | **4,7 ms** |
| | **nhẹ hơn 1,0 GB** | **nhanh gần 2×** |

Bước xuất ONNX vì vậy không phải việc làm cho đẹp mà là một phần của kiến trúc
triển khai: nó quyết định image nhỏ đi bao nhiêu và mỗi khuôn mặt chạy nhanh hơn
bao nhiêu.

Tính chất "không cần torch" rất dễ vỡ: chỉ một dòng `import torch` ở cấp mô-đun
trong `engine/` là hỏng, và ở máy phát triển **sẽ không ai thấy** vì máy nào cũng
có torch — lỗi chỉ nổ lúc container khởi động. Bài test
`backend/tests/test_no_torch.py` canh đúng chuyện đó:

```bash
python -m backend.tests.test_no_torch
```

## Các chế độ chạy

### Thường (mặc định) — SQLite

```bash
docker compose up -d --build
```

Chạy được ngay, không cần dịch vụ nào khác. Đủ dùng thật: hệ thống này ghi rất
thưa (vài chục dòng mỗi buổi) và chỉ có một tiến trình backend ghi vào.

### PostgreSQL

Đổi trong `.env`:

```
FACEID_DATABASE_URL=postgresql+psycopg://faceid:<mật-khẩu>@db:5432/faceid
POSTGRES_PASSWORD=<mật-khẩu>
```

```bash
docker compose --profile pg up -d --build
```

Đáng chuyển khi có nhiều máy chủ cùng ghi, hoặc cần sao lưu nóng.

### Phát triển — sửa code thấy ngay

```bash
docker compose -f compose.yml -f compose.dev.yml up
```

Giao diện chuyển sang <http://localhost:5173> (Vite, có thay nóng), API mở thẳng
ở <http://localhost:8000>. Mã nguồn gắn từ máy chủ nên sửa `.py` hay `.jsx` là
container nhận ngay, không phải build lại.

### Huấn luyện lại

```bash
docker compose --profile train build training
docker compose --profile train run --rm training \
    python -m training.train --config training/configs/casia.yaml
```

Image này nặng ~7 GB và cần NVIDIA Container Toolkit để thấy GPU. Nó nằm sau
profile riêng nên `docker compose up` thường ngày không đụng tới.

> Ghi chú trung thực: mọi số liệu huấn luyện trong đồ án được đo trực tiếp trên
> Windows với GTX 1650, không qua container. Image này để người khác dựng lại
> được kết quả trên máy Linux.

## Máy kiosk không nằm trong Docker

Ứng dụng kiosk (`desktop_app.py`) cần camera và cửa sổ đồ hoạ. Đưa hai thứ đó vào
container trên Windows là chuyện khổ sở và không đem lại lợi ích gì — kiosk vốn
đã chạy trên máy riêng đặt ở cửa lớp. Nó chỉ cần biết địa chỉ máy chủ:

```
FACEID_API_URL=http://<địa-chỉ-máy-chủ>:8090
```

Kiosk có hàng đợi ngoại tuyến nên mất mạng vẫn điểm danh được; bản ghi tự đồng bộ
khi mạng trở lại.

## Xử lý sự cố

| Hiện tượng | Nguyên nhân và cách xử lý |
|---|---|
| `required variable FACEID_SECRET_KEY is missing` | Chưa tạo `.env`. Chạy `cp .env.example .env`. |
| Web báo 502 trong khoảng một phút đầu | Backend đang nạp mô hình. `depends_on` chờ health nên thường không thấy; nếu kéo dài, xem `docker compose logs backend`. |
| `engine_loaded: false` ở trang Hệ thống | Không thấy tệp ONNX. Kiểm tra `FACEID_EMBED_WEIGHTS` và `docker compose exec backend ls models/`. |
| Nhận diện đúng nhưng không ghi điểm danh | Đang ngoài khung giờ của buổi học, hoặc đã điểm danh rồi trong hôm nay. |
| Sửa code mà container không đổi | Bản thường chạy code đã nướng vào image — build lại, hoặc dùng lớp phủ dev. |
| Cổng đã bị chiếm | Đổi `WEB_PORT` trong `deploy/.env` — hai tệp .bat và các bộ kiểm thử đọc lại từ đó. |

Xem log: `docker compose logs -f backend`
