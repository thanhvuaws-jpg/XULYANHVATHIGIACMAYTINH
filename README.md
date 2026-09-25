# Chương trình nhận diện khuôn mặt (Face Recognition)

Đồ án Thị giác máy tính — nhận diện khuôn mặt kết hợp **2 nguồn dữ liệu**:

- **Dataset Kaggle** (nhiều người) → dùng để **train CNN** học cách trích đặc trưng khuôn mặt.
- **Dữ liệu tự đăng ký** (webcam) → những người cụ thể bạn muốn hệ thống nhận ra.

Cả hai được quy về **vector embedding** và lưu chung một database. Thêm người mới **không cần train lại CNN** (open-set recognition + incremental enrollment).

---

## 1. Kiến trúc

```
Ảnh/Webcam ─► MTCNN (phát hiện) ─► Alignment 5 điểm (160×160)
           ─► CNN backbone (ResNet50 tự train / FaceNet pretrained) ─► vector 512-D
           ─► so cosine với DB ─► Tên  (hoặc "Unknown" nếu < ngưỡng)
```

| Thành phần | File |
|---|---|
| Tiện ích chung (detect, align, embed, match) | `src/face_utils.py` |
| ArcFace head | `src/arcface.py` |
| Tải dataset Kaggle | `src/download_kaggle.py` |
| Chụp webcam đăng ký | `src/capture_faces.py` |
| Tiền xử lý (detect + align + augment) | `src/preprocess.py` |
| Train CNN (CrossEntropy / ArcFace) | `src/train_cnn.py` |
| Dựng database embedding | `src/build_db.py` |
| Thêm 1 người (không train lại) | `src/enroll_person.py` |
| Nhận diện trên ảnh | `src/recognize_image.py` |
| Nhận diện realtime webcam | `src/recognize_realtime.py` |
| Đánh giá (accuracy, ROC, confusion, FAR/FRR) | `src/evaluate.py` |
| App demo Streamlit | `app.py` |

---

## 2. Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

> Nếu có GPU NVIDIA: cài `torch` bản CUDA theo hướng dẫn ở https://pytorch.org (không thì bản CPU vẫn chạy, chỉ train chậm).
> `numpy` giữ ở bản `<2.0` để tương thích `facenet-pytorch`.

Chạy mọi script **từ thư mục gốc dự án** theo dạng module: `python -m src.<tên>`.

---

## 3. Lấy dữ liệu trên Kaggle — làm thế nào, ở đâu

### Cách A — dùng script có sẵn (khuyên dùng)

**Bước 1.** Cài công cụ:
```bash
pip install kaggle
```

**Bước 2.** Lấy API token: đăng nhập **kaggle.com** → bấm avatar → **Settings** → mục **API** → **Create New Token** → tải về file `kaggle.json`.

**Bước 3.** Đặt file vào đúng chỗ:
```
C:\Users\<tên_windows>\.kaggle\kaggle.json
```
(tạo thư mục `.kaggle` nếu chưa có).

**Bước 4.** Vào trang dataset một lần, bấm nút **“I Understand and Accept”** (Kaggle bắt buộc chấp nhận điều khoản trước khi tải).

**Bước 5.** Tải:
```bash
python -m src.download_kaggle --list                 # xem danh sách
python -m src.download_kaggle --dataset pins         # -> data/kaggle/pins/<tên người>/*.jpg
python -m src.download_kaggle --dataset celeb5       # tập nhỏ để chạy thử nhanh
python -m src.download_kaggle --dataset lfw          # benchmark
```

### Cách C — không có `kaggle.json`? Dùng LFW qua scikit-learn (không cần token)

```bash
python -m src.fetch_lfw --min-faces 20 --max-per-person 40
# -> data/kaggle/lfw/<Tên người>/*.jpg   (ảnh mặt thật, tải trực tiếp, có cache)
```

### Cách B — tải tay

Vào các trang sau, bấm **Download**, giải nén vào `data/kaggle/<tên>/` sao cho cấu trúc là `data/kaggle/<tên>/<tên người>/<ảnh>.jpg`:

| Dataset | Trang Kaggle | Dùng để |
|---|---|---|
| **Pins Face Recognition** (105 người, 17k ảnh) | kaggle.com/datasets/hereisburak/pins-face-recognition | **Train CNN chính** |
| **LFW** | kaggle.com/datasets/jessicali9530/lfw-dataset | Benchmark verification |
| **5 Celebrity Faces** | kaggle.com/datasets/dansbecker/5-celebrity-faces-dataset | Chạy thử pipeline |
| **CelebA** (200k ảnh) | kaggle.com/datasets/jessicali9530/celeba-dataset | Train nâng cao (nặng) |
| **AT&T / ORL** (40 người) | kaggle.com/datasets/kasikrit/att-database-of-faces | Minh họa PCA/Eigenfaces |

> Nếu dataset giải nén ra cấu trúc khác (ví dụ tất cả ảnh nằm một thư mục, hoặc lồng thêm 1 cấp), sắp xếp lại thành `<tên người>/<ảnh>.jpg` rồi mới chạy `preprocess`.

---

## 4. Quy trình chạy đầy đủ

### B1. Tải dataset Kaggle
```bash
python -m src.download_kaggle --dataset pins
```

### B2. Chụp dữ liệu nhóm bạn (mỗi người 1 lần)
```bash
python -m src.capture_faces --name nam --count 40
python -m src.capture_faces --name huy --count 40
python -m src.capture_faces --name lan --count 40
```
Quay đầu trái/phải, ngẩng/cúi, cười, đeo/thao kính, xa/gần.

### B3. Tiền xử lý — detect + align cả 2 nguồn về `data/aligned/`
```bash
python -m src.preprocess --src data/kaggle/pins --dst data/aligned --augment 1
python -m src.preprocess --src data/enrolled    --dst data/aligned --augment 2
```

### B4. Train CNN (bắt buộc có trong báo cáo)
```bash
# Phiên bản 1 — CrossEntropy (dễ, nhanh)
python -m src.train_cnn --data-dir data/aligned --loss ce --epochs 25

# Phiên bản 2 — ArcFace (embedding mạnh hơn, để so sánh)
python -m src.train_cnn --data-dir data/aligned --loss arcface --epochs 30
```
Không có GPU / muốn nhanh: thêm `--freeze-backbone`.
Kết quả: `models/backbone_ce.pt`, `models/backbone_arcface.pt` (+ `.json`).

### B5. Dựng database embedding (gộp người Kaggle + người tự đăng ký)
```bash
python -m src.build_db --backbone resnet50 --weights models/backbone_arcface.pt
# hoặc baseline không cần train:
python -m src.build_db --backbone facenet
```

### B6. Nhận diện
```bash
# Ảnh tĩnh
python -m src.recognize_image --image anh_test.jpg --backbone resnet50 --weights models/backbone_arcface.pt

# Realtime webcam
python -m src.recognize_realtime --backbone resnet50 --weights models/backbone_arcface.pt --every 2
```

### B7. Thêm người mới bất kỳ lúc nào (KHÔNG train lại)
```bash
python -m src.enroll_person --name minh --camera 0 --count 30 --backbone resnet50 --weights models/backbone_arcface.pt
```

### B8. Đánh giá + xuất biểu đồ cho báo cáo
```bash
python -m src.evaluate --backbone resnet50 --weights models/backbone_arcface.pt
python -m src.evaluate --backbone facenet          # chạy lại để so sánh baseline
```
→ `reports/`: `classification_report.txt`, `confusion_matrix.png`, `roc.png`, `far_frr.png`.
Lấy “Ngưỡng đề xuất” in ra cập nhật vào `src/config.py` (`DEFAULT_THRESHOLD`).

### B9a. App desktop (khuyên dùng — chạy mượt, giao diện tối, icon SVG, không lag như web)
```bash
python desktop_app.py
```
Cửa sổ `FaceID Studio`, thanh trái 5 mục: **Trực tiếp · Nhận diện ảnh · Cử chỉ tay · Đăng ký người · Bảng điều khiển**.
Video hiển thị tách khỏi luồng nhận diện nên không giật; chỉnh "mỗi N khung" để cân tốc độ CPU.

**Tab Cử chỉ tay** (MediaPipe HandLandmarker — tự tải `models/hand_landmarker.task` lần đầu):
vẽ trên không bằng ngón trỏ, kèm hiệu ứng hạt. Tích **"Kèm nhận diện mặt"** để chạy song song với nhận diện khuôn mặt.

| Cử chỉ | Tác dụng |
|---|---|
| 1 ngón trỏ | vẽ theo đầu ngón |
| chữ V (2 ngón) | di chuyển, không vẽ |
| nắm tay | xoá hết nét |
| xoè cả bàn tay | đổi màu + bắn hiệu ứng hạt |
| chụm ngón cái + trỏ | chấm 1 điểm |

**Tab Đăng ký người — quản lý data theo folder:**
1. Gõ tên → **Tạo folder** (tạo `data/enrolled/<tên>/`).
2. **Bật camera** → **Chụp vào khay** nhiều lần (hoặc **Thêm ảnh từ máy**). Khay = ảnh tạm chưa lưu.
3. **Thêm khay vào folder** → ghi ảnh xuống `data/enrolled/<tên>/` (quản lý, chưa nhận diện).
4. Lặp bước 2–3 bao nhiêu lần tuỳ ý để gom đủ ảnh.
5. **Nạp folder vào nhận diện** → tạo embedding cho toàn bộ ảnh trong folder và ghi vào DB.
   (**Xoá folder khỏi nhận diện** chỉ gỡ khỏi DB, ảnh vẫn còn trên đĩa.)

### B9b. App web (tuỳ chọn)
```bash
python -m streamlit run app.py
```
(hoặc `streamlit run app.py` nếu Scripts đã có trong PATH)

4 tab:
- **🎥 Nhận diện trực tiếp** — camera chạy liên tục, có người trong khung là nhận diện ngay (dùng `streamlit-webrtc`; nếu chưa cài thì tự chuyển sang chế độ chụp).
- **🖼️ Nhận diện ảnh** — upload ảnh.
- **➕ Đăng ký người** — thêm ảnh bằng upload **hoặc** chụp **nhiều lần**, ảnh gom vào "khay", xem lại / bỏ từng ảnh, rồi **Lưu vào hệ thống** (không train lại CNN).
- **📊 Bảng điều khiển** — thống kê số ảnh theo người, danh sách model, nút *Dựng lại DB* / *Chạy đánh giá*, xem biểu đồ ROC / confusion matrix / FAR-FRR ngay trong app.

Cột trái: thư viện ảnh **theo từng người** (mỗi người một ô, xem được ảnh đã đăng ký), có ô tìm tên và nút xoá người khỏi nhận diện.

---

## 5. Gợi ý nội dung báo cáo

1. **So sánh 3 mô hình**: FaceNet pretrained (baseline) vs CNN-CrossEntropy vs CNN-ArcFace — bảng accuracy / AUC / EER.
2. **ROC + chọn ngưỡng**: giải thích đánh đổi FAR (nhận nhầm người lạ) và FRR (từ chối người thật), điểm EER.
3. **Ablation**: có/không alignment, có/không augmentation.
4. **Thử thách thực tế**: test ảnh thiếu sáng, nghiêng, đeo khẩu trang → mức tụt accuracy.
5. **Hướng mở rộng**: anti-spoofing (liveness), FAISS khi số người lớn.

---

## 6. Xử lý sự cố

| Lỗi | Cách xử lý |
|---|---|
| `Could not open webcam` | Đổi `--camera 1`, đóng app khác đang dùng camera |
| `numpy` xung đột với facenet-pytorch | `pip install "numpy<2.0"` |
| Tải Kaggle báo 403 | Chưa bấm “Accept” trên trang dataset, hoặc `kaggle.json` sai chỗ |
| Train `CUDA out of memory` | Giảm `--batch-size`, thêm `--freeze-backbone` |
| `ImportError: attempted relative import` | Chạy dạng `python -m src.xxx` từ thư mục gốc, không `python src/xxx.py` |
| Nhận diện toàn ra “Unknown” | Hạ `--threshold` (vd 0.35), kiểm tra DB có đúng người, chạy `src.evaluate` lấy ngưỡng |
