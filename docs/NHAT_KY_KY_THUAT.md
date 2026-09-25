# Nhật ký kỹ thuật — FaceID Attendance

> Ghi lại **quyết định kỹ thuật, lỗi tìm được và số liệu đo được** ngay lúc chúng xảy ra,
> để sau này ráp vào báo cáo mà không phải nhớ lại. Mỗi mục đều có số đo thật,
> không có con số nào là ước lượng.
>
> Báo cáo cuối dùng **mẫu Word của trường** — file này chỉ là kho nội dung nguồn.

---

## Bối cảnh

Nâng prototype nhận diện khuôn mặt (3.030 dòng, 15 module, dùng MTCNN + FaceNet
pretrained + pickle) thành hệ thống điểm danh client–server ở mức sản phẩm.

Môi trường đo: Windows 11 · Python 3.13 · CPU (chưa rõ model) · **NVIDIA GTX 1650
4 GB (TU117, compute 7.5, KHÔNG có tensor core)**.

---

## Task 1 — Tách lõi AI thành thư viện `engine/`

**Quyết định.** Engine là thư viện Python thuần, không biết gì về web/UI/database.
Backend và các client chỉ gọi qua `engine/pipeline.py`.

**Lý do.** Train, benchmark và viết test cho từng tầng được độc lập; đổi mô hình
không đụng tới API; kiosk chạy được offline.

**Kiến trúc.** `detect → quality → align → liveness → embed → index → track → vote`,
mỗi tầng một giao diện trừu tượng với ít nhất hai implementation để so sánh.

**Kết quả đo.**

| Hạng mục | Kết quả |
|---|---|
| MobileFaceNet | 1,20 M tham số, embedding 512-D chuẩn hoá L2 |
| Nhận diện end-to-end (12 người LFW) | **36/36 đúng** trên ảnh chưa từng thấy |
| Cổng chất lượng | loại 20/72 ảnh đăng ký kém |
| hnsw vs bruteforce | **khớp 100/100**, hnsw nhanh 2,5× ngay ở 600 vector |
| Độ trễ từng tầng | detect 5,0 ms · quality+align 2,3 ms · embed 83,7 ms · tra cứu 0,1 ms |

---

## Task 2 — Thay MTCNN bằng YuNet

**Quyết định.** YuNet (ONNX 232 KB, có sẵn trong OpenCV) làm detector mặc định;
giữ MTCNN làm đối chứng.

**Kết quả đo.**

| Detector | 1 mặt/ảnh (120 ảnh LFW) | Khung 1280×720, 12 người |
|---|---|---|
| **YuNet** | **4,19 ms** · 239 fps | **3,48 ms** · 288 fps |
| MTCNN | 28,48 ms · 35 fps | 200,27 ms · 5 fps |
| Tỉ lệ | **6,8× nhanh hơn** | **57× nhanh hơn** |

Số mặt tìm được: YuNet 72 vs MTCNN 69 trên ảnh LFW thật; nhưng trên khung ghép 12
người thì YuNet 11,0 vs MTCNN 12,0 — YuNet sót khi mặt bị cắt sát mép ảnh.

**Ý nghĩa.** Ở kịch bản lớp học đông người, MTCNN chỉ chạy 5 fps — không dùng được
cho realtime. Đây là nguyên nhân chính khiến bản prototype bị giật.

---

## Task 3 — Cổng chất lượng ảnh

Hai **lỗi phương pháp** tự phát hiện được trong lúc kiểm chứng:

### Lỗi 1: đo độ nét trên chip đã căn chỉnh

Phương sai Laplacian đo trên ảnh 112×112 sau `warpAffine` gần như không phản ứng
với độ mờ, vì phép biến đổi affine lấy mẫu lại ảnh và **tự sinh ra tần số cao do
răng cưa**.

| Cách đo (phương sai Laplacian chuẩn hoá) | gốc | mờ 21px | mờ 31px | Độ nhạy |
|---|---|---|---|---|
| trên chip `warpAffine` 112 | 0,1365 | 0,1004 | 0,0978 | **28 %** ✗ |
| vùng mặt gốc → `INTER_AREA` 128 | 0,0623 | 0,0159 | 0,0104 | **83 %** ✓ |

→ Đo trên **vùng mặt ở độ phân giải gốc**, chuẩn hoá kích thước bằng `INTER_AREA`
(có lọc thông thấp đúng cách), và chuẩn hoá giá trị theo phương sai ảnh xám để
bất biến với độ tương phản.

### Lỗi 2: gộp roll và yaw thành một "độ nghiêng"

`align_face` xoay lại **roll** hoàn toàn, nên roll gần như không hại. Chỉ **yaw**
(quay ngang, che mất một bên mặt) mới làm hỏng embedding. Gộp chung sẽ loại oan
ảnh tốt và cho lọt ảnh xấu.

→ Tách riêng, chỉ chặn theo yaw (30°), nới roll lên 45°.

**Kiểm chứng sau khi sửa.**

| Trường hợp | Kết quả | Đúng? |
|---|---|---|
| ảnh gốc | PASS 0,79 | ✓ |
| mờ Gauss 9px | PASS 0,69 | ✓ (mờ nhẹ vẫn dùng được) |
| mờ Gauss 21px | **LOẠI** "ảnh mờ" | ✓ |
| mờ Gauss 31px | **LOẠI** "ảnh mờ" | ✓ |
| thiếu sáng | **LOẠI** "thiếu sáng" | ✓ |
| roll 30° | PASS 0,92 | ✓ (alignment sửa được) |

Trên 132 ảnh LFW thật: 113 pass / 19 loại (86 %). Hiệu chỉnh yaw trên 120 ảnh
chính diện: trung bình 7,2°, p90 16,8°.

---

## Task 4 — Sửa lỗi đánh giá: rò rỉ danh tính

**Lỗi.** `src/evaluate.py` cũ chia **ảnh** của cùng một người thành gallery và
query, nên mọi danh tính trong tập kiểm thử đều đã xuất hiện lúc huấn luyện. Đó
là rò rỉ dữ liệu và nó luôn thổi phồng kết quả.

**Sửa.** Ranh giới đặt ở mức **danh tính**, không phải ảnh. `training/split.py`
chia 4 tập rời nhau (train / val / test / stranger) và ghi ra manifest JSON làm
nguồn sự thật duy nhất cho cả train lẫn eval, kèm hàm `assert_disjoint()` chốt chặn.

**Ba giao thức đúng chuẩn** thay cho một chỉ số accuracy đơn lẻ:
1. Xác thực 1:1 — ROC, AUC, EER, **TAR@FAR**
2. Định danh đóng 1:N — rank-1, rank-5, **CMC**
3. Định danh mở — **DIR@FAR** (có người lạ trà trộn)

**So sánh trực tiếp trên cùng mô hình FaceNet:**

| Chỉ số | Cách đánh giá cũ (rò rỉ) | Cách đúng (open-set) |
|---|---|---|
| AUC | 0,9998 | **0,9976** |
| EER | 0,34 % | **1,93 %** — xấu hơn 5,7× |
| Ngưỡng đề xuất | 0,571 | **0,504** |
| TAR@FAR=1e-3 | *không đo được* | **0,8233** |

Con số đáng chú ý nhất: ở mức chặt (1/1000 người lạ lọt), hệ thống **bỏ sót 18 %
người quen** — điều mà cách đánh giá cũ hoàn toàn không nhìn thấy.

---

## Task 5 — Pipeline huấn luyện v2

**Chẩn đoán lần train cũ (đạt 0,52).** Nguyên nhân số một: **đóng băng backbone**
ImageNet — đặc trưng ImageNet không phân biệt được khuôn mặt, mạng chỉ học được
một phép chiếu tuyến tính trên đầu vào sai mục đích.

**Thay đổi:** MobileFaceNet thay ResNet50 · không đóng băng · khởi động dần biên
độ ArcFace · SGD momentum thay AdamW · augmentation mô phỏng webcam · chia tập
theo danh tính.

**Kiểm chứng.**

| Kiểm tra | Kết quả |
|---|---|
| Lịch khởi động biên độ | 0,00 → 0,10 → 0,20 → 0,30 → 0,40 → 0,50 ✓ |
| Biên độ có siết bài toán không | loss **7,80** (m=0) → **19,24** (m=0,2) → **35,45** (m=0,5) |
| Overfit test (8 người × 16 ảnh) | acc 0,336 → **1,000 ở epoch 4** |
| Dataset train ∩ val | **0 danh tính chung** ✓ |

Con số thứ hai giải thích vì sao lần trước không hội tụ: đặt `m=0,5` ngay epoch 1
làm loss khởi điểm **cao gấp 4,5 lần**.

---

## Task 6 — Huấn luyện thật + xuất ONNX

**Dữ liệu.** LFW qua scikit-learn (không cần Kaggle token): 901 người → 5.823 ảnh
→ qua YuNet + cổng chất lượng còn **5.552 ảnh (95,3 %)**, tốc độ 119 ảnh/s.
Sau lọc ≥4 ảnh/người: **582 danh tính** — train 349 / val 58 / test 116 / stranger 59.

Ghi chú: cổng chất lượng dùng ngưỡng **nới hơn cho dữ liệu train** (`min_sharpness
0,014` thay vì 0,025) vì augmentation vốn đã thêm mờ; ngưỡng gắt để dành cho lúc
đăng ký và nhận diện. Với ngưỡng gắt, 24 % ảnh LFW bị loại vì mờ.

### Ba lỗi phải sửa mới train được

| Lần | Kết quả | Lỗi | Cách sửa |
|---|---|---|---|
| 1 | NaN ở epoch 1 | Thiếu **LR warmup** | Warmup tuyến tính 200 bước |
| 2 | NaN ở epoch 1 | **AMP fp16 tràn số** trong `block[13]` của MobileFaceNet | Tắt AMP |
| 3 | Chạy được, 0,8240 | Lịch LR sai — `CosineAnnealingLR` tính **đệ quy** từ `lr` hiện tại, việc ghi đè `lr` để warmup phá hỏng đệ quy → lr thấp hơn ~20 lần | Tự tính lịch LR theo `step`, bỏ scheduler |
| 4 | **0,8827** | — | — |

**Phát hiện về AMP trên GTX 1650** (TU117 không có tensor core):

| | ms/batch |
|---|---|
| fp32 | **84,8** |
| AMP (fp16) | 163,2 — **chậm hơn 2×** |

→ AMP là lỗ ròng trên GPU không có tensor core, vừa chậm hơn vừa gây tràn số.
Chỉ bật lại trên RTX 20xx trở lên sau khi đo lại. VRAM đỉnh chỉ 1,22/4,3 GB.

### Kết quả huấn luyện

60 epoch × ~10,5 s = ~11 phút trên GTX 1650.

| | val_ver (người **chưa từng thấy**) | val_auc |
|---|---|---|
| Lần 3 (lr lỗi) | 0,8240 | 0,9038 |
| **Lần 4 (lr đúng)** | **0,8827** | 0,9444 |

`acc_cls` đạt 0,9993 (thuộc lòng 349 người đã học) nhưng `val_ver` chững ở
0,86–0,88 → **overfit rõ rệt** với chỉ 2.743 ảnh. Đây là bằng chứng định lượng
cho thấy cần dataset lớn hơn (Pins 105 người, hoặc CASIA-WebFace ~10k người).

### Xuất ONNX

| | |
|---|---|
| Kích thước | **4,8 MB** (checkpoint torch 5,0 MB · FaceNet 107 MB) |
| Kiểm chứng torch ↔ onnx | sai lệch tối đa **8,20e-08**, cosine **1,000000** → khớp |
| Tốc độ CPU | torch 11,14 ms → **onnx 5,29 ms** (**2,1× nhanh hơn**) |

So với FaceNet (83,7 ms/mặt): MobileFaceNet ONNX **nhanh hơn 15,8 lần**.

Hệ quả triển khai: container chạy thật chỉ cần `onnxruntime` chứ không cần
`torch`. Dung lượng cụ thể của hai bản dựng được **đo thật** ở Task 12 — con số ở
đây trước kia là ước lượng viết trước khi từng dựng image lần nào, đã bỏ.

---

*(còn tiếp — cập nhật sau mỗi task)*

---

## Task 6b — Chưng cất tri thức (Knowledge Distillation)

**Vấn đề.** MobileFaceNet train từ đầu bằng ArcFace chỉ đạt AUC 0,947 vs FaceNet
0,9987. Khoảng cách này là khoảng cách **dữ liệu** (2.743 ảnh vs 3,3 triệu),
không phải khoảng cách siêu tham số — không thể bù bằng tinh chỉnh.

**Cách làm.** FaceNet đóng vai thầy: vector nó sinh ra trở thành đích hồi quy cho
MobileFaceNet. Loss = `1 − cosine(trò, thầy)`.

Ba đặc điểm khiến cách này hợp hoàn cảnh:
1. **Không cần nhãn danh tính** → dùng được cả người chỉ có 1 ảnh. Trong LFW,
   **71 % người (3.870/5.474) chỉ có đúng 1 ảnh** — ArcFace vứt hết số này.
   Kết quả: 9.025 ảnh dùng được thay vì 2.743 (**gấp 3,3 lần**).
2. Đích 512 chiều giàu thông tin hơn nhãn 1-trong-349.
3. **Thầy nhìn ảnh sạch, trò nhìn ảnh đã augment** → trò buộc phải bền vững với
   mờ, thiếu sáng, nén vỡ.

Chống rò rỉ: chỉ chưng cất trên danh tính KHÔNG thuộc val/test/stranger; có
`assert` chốt chặn (đã loại 233 danh tính).

Tối ưu: embedding của thầy được **tính trước và cache** (`data/teacher_embeddings.npz`)
— 9.025 ảnh trong ~45 s trên GPU, sau đó mỗi epoch chỉ còn chi phí của trò.

**Quá trình.** 30 epoch × ~34 s = ~17 phút. `cos_sim` 0,095 → **0,787**.

**Kết quả so sánh (cùng tập test: 116 người quen + 59 người lạ):**

| Chỉ số | ArcFace từ đầu | **Chưng cất** | FaceNet (thầy) |
|---|---|---|---|
| AUC | 0,9473 | **0,9802** | 0,9987 |
| EER | 12,23 % | **7,27 %** | 1,60 % |
| rank-1 | 0,6722 | **0,9030** | 0,9983 |
| rank-5 | 0,8696 | **0,9749** | 1,0000 |
| DIR@FAR=1 % | 0,2274 | 0,2308 | 0,7860 |
| Kích thước | 4,8 MB | **4,8 MB** | 107 MB |
| Tốc độ CPU/mặt | 5,29 ms | **6,63 ms** | 83,7 ms |

**Nhận xét.** Chưng cất cải thiện mạnh khả năng **xếp hạng** (rank-1 +23 điểm,
EER giảm gần một nửa) với cùng kích thước và vẫn nhanh hơn thầy 12,6 lần.

**Nhưng** `DIR@FAR=1 %` gần như không đổi (0,227 → 0,231): model xếp hạng giỏi
nhưng **hiệu chỉnh ngưỡng còn kém** — chưa dứt khoát phân biệt người quen với
người lạ. Không gian embedding của trò bị nén hơn thầy nên hai phân bố chồng lấn
ở đuôi. Ngưỡng vận hành cho FAR 23,8 %, quá cao cho điểm danh thật.

→ Kết luận: sản phẩm hiện dùng FaceNet; hướng khắc phục là **tăng số danh tính**
khi huấn luyện (CASIA-WebFace, 10.575 danh tính).

---
---

# BẢN ĐỒ NỘI DUNG → MẪU BÁO CÁO

Mẫu: `formatbaocao.docx` (tiểu luận môn học, 3 chương). **Giữ nguyên format, chỉ điền nội dung.**
Bảng dưới ánh xạ nội dung đã có ở trên vào từng mục của mẫu.

| Mục trong mẫu | Lấy nội dung từ |
|---|---|
| **MỞ ĐẦU** | Bối cảnh: nâng prototype thành hệ thống điểm danh client–server |
| **1.1 Lý do chọn đề tài** | Điểm danh thủ công tốn thời gian, dễ gian lận; nhận diện khuôn mặt giải quyết cả hai |
| **1.2 Mục tiêu** | Hệ thống điểm danh realtime ≥25 fps, open-set (từ chối người lạ), có chống giả mạo, có app desktop + web |
| **1.3 Phạm vi** | Nhận diện 1:N trong nhóm đã đăng ký; không làm nhận diện đám đông quy mô lớn |
| **1.4 Đối tượng nghiên cứu** | Ảnh/video khuôn mặt; các mô hình CNN trích đặc trưng; giao thức đánh giá open-set |
| **1.5 Phương pháp nghiên cứu** | Thực nghiệm có đối chứng: mỗi thay đổi đều đo trước/sau trên cùng tập test |
| **2.1 Cơ sở lý thuyết A** | Phát hiện khuôn mặt: MTCNN (3 mạng nối tiếp) vs YuNet (ONNX một giai đoạn) → Task 2 |
| **2.2 Cơ sở lý thuyết B** | Trích đặc trưng & ArcFace: chuẩn hoá L2, biên độ góc cộng thêm, vì sao cosine đo được danh tính → Task 5 |
| **2.3 Cơ sở lý thuyết C** | Chưng cất tri thức (thầy–trò); và/hoặc Giao thức đánh giá open-set (TAR@FAR, CMC, DIR@FAR) → Task 4, 6b |
| **3.1 Phân tích hệ thống** | Kiến trúc 7 tầng · sơ đồ client–server · schema CSDL · hợp đồng API → xem artifact bản thiết kế |
| **3.2 Xây dựng giao diện** | Ảnh chụp màn hình app desktop (5 mục) + web React → **chụp sau khi cắm engine** |
| **KẾT LUẬN** | Bảng so sánh 4 mô hình + hạn chế (DIR@FAR còn thấp) + hướng phát triển |
| **PHỤ LỤC** | Cấu hình huấn luyện (`training/configs/*.yaml`), cấu trúc thư mục |

## Danh mục bảng / hình vẽ cần đưa vào

| Số hiệu đề xuất | Nội dung | Nguồn |
|---|---|---|
| Hình 2.1 | Sơ đồ pipeline 7 tầng | vẽ lại từ mục Task 1 |
| Bảng 2.1 | So sánh MTCNN vs YuNet (tốc độ, fps) | Task 2 |
| Bảng 2.2 | Ảnh hưởng biên độ ArcFace lên loss (m=0 / 0,2 / 0,5) | Task 5 |
| Bảng 3.1 | Thống kê bộ dữ liệu (LFW, CASIA — số ảnh, số danh tính) | Task 6 |
| Bảng 3.2 | Chia tập theo danh tính (train/val/test/stranger) | Task 4 |
| Bảng 3.3 | So sánh cách đánh giá cũ (rò rỉ) vs đúng chuẩn | Task 4 |
| Hình 3.1 | `reports/so_sanh_mo_hinh.png` — so sánh 4 mô hình | có sẵn |
| Hình 3.2 | `reports/facenet_eval.png` — ROC · CMC · FAR-FRR | có sẵn |
| Hình 3.3–3.8 | Ảnh chụp màn hình app desktop từng chức năng | **chưa có — chụp sau** |
| Bảng 3.4 | Ngân sách độ trễ từng tầng (trước/sau) | Task 1, 2, 6 |

## Tài liệu tham khảo (thu thập dần)

1. Deng, J., Guo, J., Xue, N., Zafeiriou, S. *ArcFace: Additive Angular Margin Loss for Deep Face Recognition.* CVPR 2019.
2. Chen, S., Liu, Y., Gao, X., Han, Z. *MobileFaceNets: Efficient CNNs for Accurate Real-Time Face Verification on Mobile Devices.* CCBR 2018.
3. Schroff, F., Kalenichenko, D., Philbin, J. *FaceNet: A Unified Embedding for Face Recognition and Clustering.* CVPR 2015.
4. Wu, W., Peng, H., Yu, S. *YuNet: A Tiny Millisecond-level Face Detector.* Machine Intelligence Research, 2023.
5. Zhang, K., Zhang, Z., Li, Z., Qiao, Y. *Joint Face Detection and Alignment using Multi-task Cascaded Convolutional Networks.* IEEE SPL, 2016. (MTCNN)
6. Huang, G.B., Ramesh, M., Berg, T., Learned-Miller, E. *Labeled Faces in the Wild: A Database for Studying Face Recognition in Unconstrained Environments.* Univ. of Massachusetts, Technical Report 07-49, 2007.
7. Yi, D., Lei, Z., Liao, S., Li, S.Z. *Learning Face Representation from Scratch.* arXiv:1411.7923, 2014. (CASIA-WebFace)
8. Hinton, G., Vinyals, O., Dean, J. *Distilling the Knowledge in a Neural Network.* NIPS Deep Learning Workshop, 2015.
9. Malkov, Y.A., Yashunin, D.A. *Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs.* IEEE TPAMI, 2020. (hnswlib)

## Việc còn thiếu trước khi viết báo cáo

- [ ] Ảnh chụp màn hình giao diện (mục 3.2) — sau khi cắm engine vào app
- [x] Kết quả huấn luyện trên CASIA — Task 6c/6d, `reports/so_sanh_mo_hinh.png` (5 mô hình)
- [x] Số liệu chống giả mạo **trong phòng thí nghiệm** (Task 8) — ACER 0,13 %,
      từ chối oan ảnh thật 9,33 % sau khai thác mẫu khó
- [ ] Số liệu chống giả mạo **trên tấn công thật** — phải tự dựng: in ảnh ra giấy
      và giơ ảnh trong điện thoại trước camera, đo bằng tab "Chống giả mạo".
      Số hiện có sinh từ tấn công **mô phỏng**, phải nói rõ điều đó trong báo cáo
- [x] Số liệu ablation: bật/tắt alignment, bật/tắt cổng chất lượng, bật/tắt tracking
      → **Task 12a**, `reports/ablation.png` + `reports/ablation.json`
- [x] Docker chạy được (Task 12) — `deploy/smoke_test.py` 20/20 đạt;
      còn thiếu **ảnh chụp màn hình** `docker compose ps` + trang web ở cổng 8080

---

## Task 6c — Huấn luyện trên CASIA-WebFace

**Dữ liệu.** CASIA-WebFace từ Kaggle, đóng gói **MXNet RecordIO** (`train.rec` 2,7 GB
+ `train.idx` + `train.lst`) — 10.572 danh tính, 501.196 ảnh, **sẵn 112×112**.

MXNet đã ngừng phát triển và không còn bản cho Python 3.13, nên tự viết trình đọc
(`training/recordio.py`). Đọc **thẳng từ file .rec** thay vì giải nén: tiết kiệm
~3 GB đĩa và tránh 501k file nhỏ vốn làm hệ thống tệp Windows chậm thảm hại.

**Cấu hình.** 6.000 danh tính train (chia rời với 400 danh tính val), tối đa 22
ảnh/người → 121.362 ảnh. 18 epoch, batch 64, ArcFace s=64 m=0,5.

**Chi phí.** 18 epoch × 422 s = **2,1 giờ** trên GTX 1650.

**Kết quả (cùng tập test LFW: 116 người quen + 59 người lạ):**

| Chỉ số | ArcFace-LFW (349 id) | ArcFace-CASIA (6.000 id) |
|---|---|---|
| AUC | 0,9473 | **0,9575** |
| EER | 12,23 % | **10,97 %** |
| rank-1 | 0,6722 | **0,7776** |
| DIR@FAR=1 % | 0,2274 | 0,2107 |

**Nhiều danh tính có giúp** — rank-1 tăng 11 điểm. Nhưng mô hình **chưa hội tụ**:
`acc_cls` chỉ 0,03 suốt 15 epoch đầu rồi mới vọt lên 0,30 ở epoch 18 đúng lúc hết
lịch. Phân loại 6.000 lớp cần 40–60 epoch, tức 5–7 giờ.

Triệu chứng rõ nhất của việc chưa hội tụ: **ngưỡng EER = 0,958** (bình thường
~0,4). Cosine của mọi cặp đều dồn sát 1,0 → embedding chưa trải ra trên mặt cầu →
xếp hạng được nhưng không đặt ngưỡng được, đúng như DIR@FAR thấp.

**Bài học định lượng:** số danh tính × số epoch bị chặn bởi năng lực tính toán.
Tăng danh tính mà không tăng epoch tương ứng thì lợi bất cập hại.

---

## Task 7 — Cắm engine mới vào ứng dụng desktop

**Thay đổi.** `desktop_app.py` không còn gọi `src/face_utils.py` (MTCNN + FaceNet)
mà uỷ quyền cho `engine.pipeline.FacePipeline`. Lớp `Engine` trong app giờ chỉ là
lớp dịch giữa thư viện và giao diện — giao diện không đổi một pixel.

Bốn thứ giao diện được hưởng ngay:

1. **YuNet** thay MTCNN ở tầng phát hiện.
2. **Bám vết + bỏ phiếu** trên trang Trực tiếp. Phát hiện chạy mỗi khung (4 ms),
   còn mạng trích đặc trưng giãn ra mỗi N khung *trên từng người*.
3. **Cổng chất lượng** khi đăng ký: báo rõ số ảnh bị loại và lý do, thay vì lặng
   lẽ nạp ảnh mờ vào gallery.
4. **Bộ chọn mô hình** liệt kê mọi ONNX đã train; đổi mô hình có cảnh báo phải
   dựng lại database (vector khác chiều thì không so được với nhau).

**Kết quả đo (cùng máy, cùng ảnh):**

| | Trước (MTCNN + FaceNet) | Sau (YuNet + FaceNet + tracking) |
|---|---|---|
| Thời gian mỗi khung | ~85 ms | **9,2 ms** |
| FPS | 12 | **109** |
| Số lần đổi nhãn / 20 khung (có 2 khung mờ) | nhấp nháy | **0** |
| Thời gian nạp engine | — | 1,0 s |

**Một lỗi tự phát hiện:** danh sách chọn mô hình quét `models/*.onnx` nên liệt kê
cả `face_detection_yunet_2023mar.onnx` — đó là mô hình *phát hiện*, không phải
*trích đặc trưng*; chọn nhầm là hỏng. Đã thêm bộ lọc theo tên.

---

## Task 6d — Chưng cất trên CASIA-WebFace (kết quả tốt nhất)

**Dữ liệu.** Distillation không cần nhãn nên gộp được hai nguồn khác hẳn nhau:
- 9.025 ảnh LFW (đã loại 233 danh tính val/test/stranger)
- 104.454 ảnh CASIA (6.000 danh tính, tối đa 18 ảnh/người)
→ **113.479 ảnh**, sau lọc ảnh hỏng còn **111.967**.

So với ArcFace chỉ dùng được 2.743 ảnh: **gấp 41 lần**.

**Chi phí.** 12 epoch × 380 s = **76 phút** (bằng nửa thời gian của ArcFace-CASIA
mà kết quả tốt hơn hẳn).

**Quá trình.** `cos_sim` với thầy: 0,413 → **0,870**. `val_auc`: 0,946 → **0,996**.

**Kết quả cuối (cùng tập test open-set):**

| Chỉ số | Chưng cất CASIA | FaceNet (thầy) | Chênh lệch |
|---|---|---|---|
| AUC | **0,9962** | 0,9987 | −0,0025 |
| EER | **2,40 %** | 1,60 % | +0,8 điểm |
| rank-1 | **0,9849** | 0,9983 | −1,3 điểm |
| rank-5 | **0,9967** | 1,0000 | −0,3 điểm |
| TAR@FAR=1 % | **0,9213** | 0,9747 | −5,3 điểm |
| DIR@FAR=10 % | **0,9197** | 0,9582 | −3,9 điểm |
| DIR@FAR=1 % | 0,2759 | 0,7860 | −51 điểm |
| **Kích thước** | **4,8 MB** | 107 MB | **nhỏ hơn 22×** |
| **Tốc độ CPU** | **4,73 ms** | 83,7 ms | **nhanh hơn 17,7×** |

---

## Bảng tổng hợp — 5 mô hình, cùng tập test

> ⚠ **Số liệu trong mục này đã lỗi thời.** Nó được đo trên `data/aligned_big`
> — thư mục chứa chip đã căn chỉnh sẵn — nên cột DIR@1% bị bóp méo nghiêm
> trọng. Xem **Task 12b** để biết nguyên nhân và bảng số liệu đúng. Mục này
> giữ lại để đối chiếu, KHÔNG dùng cho báo cáo.

| Mô hình | Dữ liệu huấn luyện | rank-1 | EER | DIR@1% | ms | MB |
|---|---|---|---|---|---|---|
| ArcFace từ đầu | LFW · 349 người · 2.743 ảnh | 0,6722 | 12,23 % | 0,2274 | 5,29 | 4,8 |
| ArcFace từ đầu | CASIA · 6.000 người · 121k ảnh | 0,7776 | 10,97 % | 0,2107 | 4,16 | 4,8 |
| Chưng cất | LFW · 9k ảnh | 0,9030 | 7,27 % | 0,2308 | 6,63 | 4,8 |
| **Chưng cất** | **CASIA+LFW · 112k ảnh** | **0,9849** | **2,40 %** | **0,2759** | **4,73** | **4,8** |
| FaceNet (thầy) | VGGFace2 · 3,3 triệu ảnh | 0,9983 | 1,60 % | 0,7860 | 83,70 | 107,0 |

### Ba kết luận rút ra

1. **Chưng cất vượt xa huấn luyện từ đầu** ở cùng lượng dữ liệu và cùng thời gian.
   Lý do: đích hồi quy 512 chiều mang nhiều thông tin hơn nhãn 1-trong-N, và
   distillation dùng được cả ảnh không có nhãn.

2. **Dữ liệu quan trọng hơn thuật toán** trong bài toán này. Cùng phương pháp
   chưng cất, tăng dữ liệu từ 9k lên 112k ảnh kéo rank-1 từ 0,903 lên 0,985.

3. **Vẫn còn một khoảng cách ở DIR@FAR=1 %** (0,276 vs 0,786). Model trò xếp hạng
   gần bằng thầy nhưng **hiệu chỉnh ngưỡng** còn kém — phân bố điểm của người quen
   và người lạ chồng lấn ở đuôi. Đây là hạn chế cần nêu trong phần Kết luận, và là
   hướng phát triển tiếp (thêm ràng buộc về phân bố khoảng cách khi chưng cất).

**Lựa chọn cho sản phẩm:** dùng **FaceNet** khi ưu tiên độ chính xác (máy có cấu
hình khá), dùng **chưng cất CASIA** khi ưu tiên tốc độ và dung lượng (máy yếu,
thiết bị nhúng). Ứng dụng cho phép đổi mô hình ngay trong Bảng điều khiển.

---

## Task 8 — Chống giả mạo (liveness)

**Vấn đề.** Không có tầng này, toàn bộ độ chính xác 98 % ở các tầng trước trở
thành vô nghĩa: chỉ cần giơ ảnh bạn mình trên điện thoại là điểm danh hộ được.
Thứ hệ thống phải chống ở đây không phải sự nhầm lẫn mà là **gian lận có chủ đích**.

### Không có dữ liệu giả mạo thật — giải pháp và giới hạn

Các bộ dữ liệu chuẩn (CelebA-Spoof, NUAA, CASIA-FASD) đòi hỏi quay lại hàng nghìn
cảnh in ảnh rồi chụp lại. Thay vào đó `training/spoof_data.py` **mô phỏng theo
vật lý**:

| Loại tấn công | Hiện tượng mô phỏng |
|---|---|
| Ảnh in | thu hẹp dải màu CMYK · lưới nửa tông · vân giấy · ánh sáng phẳng |
| Màn hình | **moiré sinh bằng răng cưa thật** (vẽ lưới điểm ảnh ở độ phân giải cao rồi thu nhỏ với tỉ lệ không nguyên) · điểm ảnh phụ RGB · ánh sáng nền · phản xạ mặt kính |
| Cả hai | lệch phối cảnh · mất nét · nhiễu cảm biến · nén JPEG lần hai |

Giới hạn phải nêu trong báo cáo: **mô phỏng không thay thế được dữ liệu thật.**

### Đặc trưng — chọn thủ công thay vì CNN

12 đặc trưng có nghĩa vật lý (moiré, dải màu, phân bố điểm chói, LBP, mật độ cạnh)
thay vì để CNN tự học. Lý do: **giải thích được** khi hệ thống từ chối oan ai đó,
và cần rất ít dữ liệu.

### Thất bại lần đầu và cách chẩn đoán

Ba phép thử, độ khắt khe tăng dần:

| Phép thử | Lần 1 | Sau khi sửa |
|---|---|---|
| 1. Cơ bản (thật vs tấn công) | ACER 0,13 % | ACER 4,73 % |
| 2. Chéo loại tấn công | ACER 0,13–0,53 % | ACER 0,00–0,87 % |
| **3. Ảnh THẬT bị làm nhiễu** | **từ chối oan 56,40 %** ❌ | **9,33 %** ✓ |

Phép thử 1 và 2 cho con số rất đẹp nhưng **vô nghĩa**. Phép thử 3 vạch ra vấn đề:
ảnh thật chỉ bị mờ/nén/nhiễu — đúng thứ webcam phòng học tạo ra — bị gán là giả
mạo hơn một nửa số lần.

**Chẩn đoán từ bảng đóng góp đặc trưng:** `sat_std` chiếm 0,2283, gấp **5 lần**
đặc trưng kế tiếp. Bộ phân loại thực chất chỉ học *"độ bão hoà màu giảm = giả mạo"*.
Mà webcam thật cũng làm giảm bão hoà màu. Nó học **"ảnh kém chất lượng"** chứ
không phải **"ảnh giả mạo"**.

**Cách sửa — hard negative mining:** đưa ảnh thật đã làm nhiễu vào tập huấn luyện
với nhãn THẬT, ép mô hình tìm đặc trưng phân biệt được giả mạo với ảnh chỉ đơn
thuần kém chất lượng.

Sau khi sửa, phân bố đóng góp lành mạnh hơn hẳn:
`sat_std` 0,157 · `lbp_entropy` 0,129 · `edge_density` 0,068 · `lbp_uniformity` 0,029.

### Kết quả cuối (đo qua đúng code path của ứng dụng)

| Loại | Điểm sống trung bình | Bị chặn |
|---|---|---|
| Mặt thật | **0,958** | **0 %** |
| Ảnh in | 0,056 | 92 % |
| Màn hình | 0,045 | 100 % |

Ngưỡng học được từ dữ liệu: **0,396**.

### Hai lớp phòng thủ

**Thụ động** (`texture.py`) — một khung hình, ~2 ms, người dùng không phải làm gì.
Nhược điểm: về bản chất là cuộc chạy đua với chất lượng in.

**Chủ động** (`blink.py`) — thử thách chớp mắt qua EAR (Eye Aspect Ratio) từ 478
điểm mốc MediaPipe. Máy trạng thái bắt đúng chuỗi **mở → nhắm → mở**, chứ không
chỉ bắt "đang nhắm" (ảnh người nhắm mắt cũng cho EAR thấp mãi). Ảnh in **không thể**
chớp mắt — đây là lớp phòng thủ có đáy, không phải cuộc chạy đua.

Chế độ `combo` gộp cả hai: lấy điểm cao nhất trong 4 giây đầu (để người dùng kịp
chớp), sau đó lấy điểm thấp nhất (đòi hỏi qua được cả hai lớp).

### Trang kiểm thử bằng tấn công THẬT

Ứng dụng có thêm mục **Chống giả mạo**: ghi mẫu thật → giơ điện thoại ghi mẫu màn
hình → giơ ảnh in ghi mẫu in → tính APCER/BPCER/ACER theo ISO/IEC 30107-3 và lưu
ra `reports/liveness_thuc_te.json`. **Đây mới là con số nên đưa vào báo cáo**, vì
nó đo trên đòn tấn công thật chứ không phải mô phỏng.

### Bài học phương pháp

Con số đẹp ở phép thử sai còn nguy hiểm hơn con số xấu ở phép thử đúng: ACER
0,13 % ban đầu che giấu một hệ thống từ chối oan quá nửa người dùng. **Chọn đúng
phép đo quan trọng hơn tối ưu con số.**

---

## Task 9 — Backend FastAPI + cơ sở dữ liệu

**Kiến trúc.** `routers → services → engine` với `engine/` là thư viện thuần đã
xây từ Task 1. Backend không chứa logic AI nào; nó chỉ điều phối nghiệp vụ và
lưu trữ.

### Ba quyết định thiết kế đáng nêu

**1. Vector là dữ liệu, chỉ mục là bản dựng lại được.**
Bảng `face_embeddings` là nguồn sự thật duy nhất; chỉ mục hnswlib/bruteforce dựng
lại lúc khởi động. Mất file chỉ mục không mất gì.

**2. Mỗi vector ghi kèm `model_tag`.**
Vector của hai mô hình khác nhau KHÔNG so sánh được. Không có trường này, đổi mô
hình sẽ làm hệ thống nhận diện sai một cách âm thầm — kiểu lỗi rất khó truy. Khi
nạp chỉ mục, chỉ lấy vector đúng mô hình đang dùng và cảnh báo số vector bị bỏ qua.

**3. Giữ lại ảnh gốc trong `enrollment_images`.**
Đổi mô hình chỉ cần chạy `POST /api/system/reembed-all` là khôi phục toàn bộ. Không
giữ ảnh gốc đồng nghĩa mỗi lần nâng cấp mô hình phải gọi từng người đến chụp lại.

### Nghiệp vụ điểm danh — ba quy tắc

1. **Chống ghi trùng** bằng ràng buộc duy nhất `(person_id, session_id, day)` ở
   tầng CSDL, cộng thời gian nguội 5 phút ở tầng nghiệp vụ. Một người đứng trước
   camera 30 giây tạo hàng trăm khung hình; không có quy tắc này thì bảng dữ liệu
   vô dụng.
2. **Chọn đúng ca** theo giờ hiện tại, cho phép sớm 30 phút, nhiều ca cùng khớp
   thì lấy ca gần nhất.
3. **Ngưỡng ghi sổ cao hơn ngưỡng hiển thị.** Nhận nhầm khi hiển thị chỉ gây khó
   chịu; nhận nhầm khi ghi sổ tạo dữ liệu sai mà không ai phát hiện.

### Hai lỗi tìm được khi kiểm thử

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `no such table: users` | `TestClient` chỉ chạy `lifespan` khi dùng làm context manager (`with TestClient(app) as c`) | Bọc lại bằng `with` |
| `password cannot be longer than 72 bytes` với mật khẩu 8 ký tự | `passlib` 1.7.4 đã ngừng bảo trì, không tương thích `bcrypt` ≥ 4.1 | Bỏ passlib, gọi thẳng `bcrypt`, cắt 72 **byte** (không phải ký tự — tiếng Việt có dấu chiếm 2-3 byte) |

### Kết quả kiểm thử tích hợp

`python -m backend.tests.test_flow` — kịch bản đầy đủ đúng thứ tự một trường học
sẽ làm, **25/25 đạt**:

| Nhóm | Nội dung kiểm chứng |
|---|---|
| Xác thực | chặn khi chưa đăng nhập · từ chối mật khẩu sai · JWT hợp lệ |
| Ca học | tạo ca · từ chối giờ kết thúc trước giờ bắt đầu |
| Người | tạo · chặn mã trùng · đăng ký 4 ảnh → 4 vector |
| Nhận diện | ảnh chưa từng dùng đăng ký → đúng, score **0,904** · ảnh trống → rỗng |
| Điểm danh | lần đầu tạo bản ghi · lần hai trong 5 phút **không** tạo thêm · đúng 1 dòng |
| Người lạ | từ chối điểm danh · ghi sự kiện |
| Báo cáo | tổng hợp · xu hướng 7 ngày · CSV có BOM cho Excel |
| Hệ thống | dựng lại chỉ mục · trích đặc trưng lại · nhật ký thao tác |

**23 endpoint**, Swagger UI tự sinh tại `/docs`.

---

## Task 10 — Giao diện web quản trị (React)

**Công nghệ.** React 18 + Vite + Tailwind CSS + Recharts + React Router.
Build ra **590 KB (173 KB sau gzip)**, `node_modules` 74 MB (chỉ dùng lúc phát triển).

**Bảy trang.**

| Trang | Chức năng |
|---|---|
| Tổng quan | Thẻ số liệu · biểu đồ chuyên cần 14 ngày · thống kê hệ thống · điểm danh gần nhất. Tự làm mới mỗi 20 giây |
| Danh sách người | Bảng có tìm kiếm (chờ 300 ms mới gọi API) · thêm/xoá · số vector mỗi người |
| Đăng ký khuôn mặt | Chụp webcam **hoặc** tải ảnh · khay ảnh xem trước · bật/tắt cổng chất lượng · báo rõ ảnh nào bị loại và vì sao |
| Điểm danh | Lọc theo ngày và trạng thái · xuất CSV |
| Ca / buổi học | CRUD ca, chọn thứ trong tuần bằng nút bấm |
| Cảnh báo người lạ | Danh sách sự kiện, đánh dấu riêng trường hợp nghi giả mạo |
| Hệ thống | Cấu hình engine · trạng thái chỉ mục · danh sách mô hình · nhật ký thao tác |

**Ba chi tiết kỹ thuật đáng nêu.**

1. **Gom mọi lời gọi mạng vào `lib/api.js`.** Token đính một chỗ; khi hết hạn thì
   toàn ứng dụng phản ứng giống nhau (xoá token, chuyển về trang đăng nhập) thay
   vì mỗi trang tự xoay xở.
2. **Proxy `/api` trong `vite.config.js`.** Trình duyệt gọi cùng gốc nên không
   dính CORS lúc phát triển; khi triển khai thì nginx làm việc tương tự.
3. **Tắt camera khi rời trang đăng ký.** Không có bước này, đèn webcam vẫn sáng và
   trình duyệt vẫn giữ thiết bị — người dùng tưởng bị theo dõi.

### Lỗi nghiệp vụ phát hiện khi tạo dữ liệu mẫu

Seed chạy lúc 20:12 với ca sáng 07:30–11:30 ghi ra **"đi muộn 763 phút"**.

**Nguyên nhân.** Khi truyền `session_id` tường minh, `check_in` không kiểm tra
thời điểm có nằm trong khung giờ ca không, nên vẫn tính muộn so với 07:30.

**Vì sao đáng sửa.** Điểm danh **sau khi ca đã kết thúc** không phải là đi muộn —
ca đó đã xong. Một con số 763 phút làm hỏng toàn bộ thống kê chuyên cần.

**Sửa.** Thêm hàm `in_window()`; ca truyền tường minh vẫn phải qua kiểm tra khung
giờ, ngoài khung thì bỏ liên kết ca và ghi trạng thái `present`.

| | Trước | Sau |
|---|---|---|
| Quét lúc 20:15, ca 07:30–11:30 | "đi muộn 763 phút" | "đúng giờ" |
| Quét lúc 07:45 | muộn 15 phút | muộn 15 phút *(không đổi)* |
| Quét lúc 08:20 | muộn 50 phút | muộn 50 phút *(không đổi)* |

**Một lỗi phụ về công cụ:** `pkill` trong Git Bash không giết được tiến trình
Windows, nên lần sửa đầu tiên tưởng như vô tác dụng — thực ra server cũ vẫn chạy
code cũ. Phải dùng `Stop-Process` của PowerShell.

### Dữ liệu mẫu

`backend/tests/seed_demo.py` tạo 1 ca, 8 sinh viên (tên Việt hoá, ảnh từ LFW),
mỗi người 5 ảnh đăng ký rồi điểm danh bằng **ảnh khác** với ảnh đã đăng ký.

Kết quả: **36 vector · 8 người · 7/8 điểm danh thành công (88 %)**.

Người thứ 8 (SV007) bị từ chối với thông báo *"Mời lại gần camera"* — **cổng chất
lượng hoạt động đúng**: ảnh truy vấn của người này có khuôn mặt quá nhỏ. Đây là
hành vi mong muốn, không phải lỗi.

---

## Task 11 — Kiosk client và hàng đợi ngoại tuyến

**Kiến trúc lai, không phải client mỏng.** Kiosk chạy engine ở **local** rồi chỉ
gửi *sự kiện điểm danh* lên server. Ba lý do:

1. **Phản hồi tức thì** — người dùng thấy tên mình sau vài chục mili giây thay vì
   chờ một vòng mạng.
2. **Không phụ thuộc mạng để hoạt động** — mất mạng vẫn nhận diện được, chỉ việc
   ghi sổ bị hoãn.
3. **Không tốn băng thông** — gửi 30 khung hình/giây lên server là bất khả thi khi
   có nhiều kiosk.

**Server vẫn là bên xác nhận cuối cùng.** Kiosk gửi *ảnh chụp* lên `/api/checkin`,
server tự nhận diện lại rồi mới ghi. Kiosk chỉ đề xuất, không tự quyết — một máy
kiosk bị chiếm quyền cũng không tạo được bản ghi giả.

### Ba tầng chống ghi trùng

| Tầng | Cơ chế | Chặn được gì |
|---|---|---|
| Bám vết (engine) | mỗi vết phát đúng **một** sự kiện `newly_confirmed` | 30 giây đứng trước camera = 1 sự kiện, không phải 900 |
| Kiosk | nhớ 60 giây gần nhất theo tên | lưu lượng mạng vô ích |
| Cơ sở dữ liệu | ràng buộc duy nhất `(person_id, session_id, day)` | mọi trường hợp còn lại, kể cả sau khi đồng bộ hàng đợi |

Ba tầng độc lập nhau có chủ đích: hai tầng trên là tối ưu, tầng dưới cùng là chốt
chặn đúng nghĩa — nó vẫn giữ được tính đúng đắn ngay cả khi hai tầng trên bị lỗi.

### Hàng đợi ngoại tuyến

Mất mạng giữa buổi là chuyện thường ở phòng học. Gọi API thất bại thì ảnh và siêu
dữ liệu được ghi xuống `storage/kiosk_queue/`; luồng nền `QueueSyncer` thử gửi lại
mỗi 30 giây. Người dùng vẫn thấy "đã ghi nhận" vì bản ghi chắc chắn sẽ tới nơi.

Gọi mạng chạy ở **luồng riêng** (`CheckinWorker`) — gọi thẳng trong luồng giao
diện sẽ làm đứng hình camera mỗi lần mạng chậm.

### Kết quả kiểm thử — 11/11 đạt

| Kịch bản | Kết quả |
|---|---|
| Máy chủ hỏng, gọi checkin | vẫn báo thành công, ghi xuống đĩa |
| Xếp 4 bản ghi | 4 tệp trong hàng đợi |
| Máy chủ trở lại, đăng nhập | từ chối mật khẩu sai, chấp nhận đúng |
| Đẩy hàng đợi | **gửi 4/4, lỗi 0, còn 0** |
| Chống trùng sau đồng bộ | 4 bản ghi cùng người cùng ngày → **thêm 0 dòng** |
| Gửi khi có mạng | đi thẳng, không qua hàng đợi |

### Ứng dụng desktop giờ có 7 mục

Trực tiếp · **Kiosk điểm danh** · Nhận diện ảnh · Chống giả mạo · Cử chỉ tay ·
Đăng ký người · Bảng điều khiển.

Mục Kiosk hiển thị thẻ kết quả cỡ lớn (xanh = đúng giờ, vàng = đi muộn hoặc đang
chờ đồng bộ, đỏ = không nhận ra), nhật ký phiên làm việc, số bản ghi đang chờ, và
nút đồng bộ thủ công.

---

## Task 12a — Ablation: chứng minh từng bộ phận bằng số

Báo cáo nói "hệ thống có căn chỉnh, có cổng chất lượng, có bám vết" thì dễ. Chứng
minh từng thứ đáng tồn tại thì phải **tắt nó đi rồi đo lại** trên cùng tập test,
cùng mô hình. Chênh lệch chính là đóng góp thật.

    python -m training.ablation

### Hai cái bẫy phải tránh trước khi tin bất cứ con số nào

**Bẫy 1 — đo trên ảnh đã căn chỉnh sẵn.** Lần chạy đầu tôi định dùng
`data/aligned_big`. Nhưng thư mục đó chứa chip 112×112 **đã được căn chỉnh từ
trước**. Tắt căn chỉnh trên dữ liệu đã căn chỉnh là đo vào chỗ trống, và con số
thu được sẽ nói dối rằng căn chỉnh vô dụng. Phải dựng manifest mới trên ảnh gốc
LFW 250×250 (`data/manifest_raw.json`, 122 người đăng ký · 61 người lạ).

**Bẫy 2 — mẫu số lệch.** Bật cổng chất lượng ở cả hai phía thì số ảnh truy vấn
tụt từ 632 xuống 452: nhánh có cổng được chấm trên một **tập test đã bị làm dễ
đi**, mọi ảnh khó đều bị loại trước khi chấm. So rank-1 kiểu đó là so lệch. Phải
tách thành nhánh riêng chỉ lọc phía **đăng ký**, giữ nguyên toàn bộ ảnh truy vấn.

Cả hai bẫy đều cho ra con số đẹp hơn sự thật. Đó là lý do phải đi tìm chúng.

### Kết quả

| Cấu hình | rank-1 | DIR@FAR=1% | khoảng cách điểm |
|---|---|---|---|
| Chỉ cắt hộp bao (tắt căn chỉnh) | 0,8829 | 0,5538 | 0,1843 |
| **Căn chỉnh 5 điểm mốc** (mốc so sánh) | **0,9778** | 0,7199 | 0,2546 |
| Căn chỉnh + lọc chất lượng ảnh đăng ký | 0,9668 | **0,7708** | 0,2549 |

**1. Căn chỉnh là bộ phận đóng góp lớn nhất trong toàn hệ thống.**
rank-1 **+9,5 điểm**; open-set DIR@FAR=1% **+16,6 điểm** (0,554 → 0,720, tức tăng
tương đối 30%). Lý do: mạng học đặc trưng với giả định mắt-mũi-miệng luôn nằm
đúng chỗ. Bỏ căn chỉnh thì cùng một người ở hai góc chụp khác nhau cho ra hai
vector cách xa nhau, và khoảng cách điểm giữa người quen với người lạ co lại từ
0,255 xuống 0,184 — ngưỡng nào cũng khó chọn.

**2. Cổng chất lượng: đánh đổi, không phải cải thiện thuần.**
rank-1 **giảm** 1,1 điểm nhưng DIR@FAR=1% **tăng** 5,1 điểm. Không mâu thuẫn:

* rank-1 (closed-set) chỉ hỏi "ai giống nhất trong 122 người" — không có quyền từ
  chối, nên ảnh mẫu mờ vẫn thường xếp đúng hạng nhất.
* DIR@FAR (open-set) hỏi "có dám khẳng định không" — ở đây điểm số phải **đáng
  tin**, và ảnh mẫu mờ tạo ra vector nằm lung tung, kéo điểm của cả người quen
  lẫn người lạ về gần nhau.

Điểm danh là bài toán open-set. Vậy nên cổng chất lượng đáng giữ.

**Giá phải trả, ghi rõ để không tô hồng:** loại **29,5%** ảnh đăng ký (103/108 là
"ảnh mờ"), và **7 trong 122 người** không ghi danh nổi vì hết sạch ảnh đạt chuẩn.
Trên LFW — ảnh báo chí cũ, nhiều ảnh vốn đã nhoè — tỉ lệ này cao hơn thực tế
webcam đáng kể, nhưng nó cho thấy cổng phải kèm **phản hồi hướng dẫn** chứ không
được im lặng từ chối.

**Ablation này xác nhận thiết kế sẵn có là đúng:** trong hệ thống, cổng chất lượng
chặn cứng ở khâu **đăng ký**, còn lúc **nhận diện** chỉ dùng làm gợi ý
(`hint_for` trong `recognize.py` — "mời lại gần camera"), không từ chối. Số liệu
trên giải thích vì sao: chặn cứng lúc nhận diện chỉ làm người dùng bị từ chối
nhiều hơn mà không đổi lấy gì.

### 3. Bám vết + bỏ phiếu đa số

Dựng chuỗi 24 khung giả lập cho mỗi người từ ảnh probe, mỗi khung bị làm xấu đi
như webcam thật (mờ chuyển động, nhiễu, lệch sáng).

| | Độ chính xác | Nhãn nhảy /100 khung |
|---|---|---|
| Tin ngay nhãn từng khung | 0,9467 | **7,0** |
| Bám vết + bỏ phiếu | 0,9672 | **0,9** |

Độ chính xác chỉ nhích 2,1 điểm — nhưng **số lần nhãn nhấp nháy giảm 87%**. Đây
mới là thứ người dùng nhìn thấy: không có bỏ phiếu thì cứ khoảng 14 khung (nửa
giây) tên trên màn hình lại đổi một lần, trông như hệ thống hỏng dù phần lớn thời
gian nó đoán đúng.

**Cái giá:** phải chờ trung bình **5,1 khung** (~0,2 giây ở 25 fps) mới dám chốt
danh tính. Đổi 0,2 giây lấy việc không nhấp nháy là món hời.

**Hình 3.9** — `reports/ablation.png` (3 bảng: căn chỉnh · cổng chất lượng · bám vết)
**Bảng 3.5** — bảng ablation ở trên

---

## Task 12 — Đóng gói và triển khai bằng Docker

Mục tiêu: một lệnh là chạy được cả hệ thống trên máy chưa cài Python, Node hay
OpenCV.

    cd deploy && cp .env.example .env && docker compose up -d --build

### Kiến trúc triển khai

```
trình duyệt ──8080──> web (nginx) ──┬── tệp tĩnh React
                                     └──/api──> backend (uvicorn) ── engine
                                                      └── SQLite / PostgreSQL
```

Chỉ `web` mở cổng ra máy chủ. `backend` khai báo `expose` chứ không `ports`, nên
từ ngoài máy chủ **không gọi thẳng vào API được** — mọi lưu lượng phải đi qua
nginx. Ba cái lợi: cùng một gốc nên không cần CORS, chỉ một cổng phải bảo vệ, và
tệp tĩnh do nginx trả chứ không bắt uvicorn làm việc của máy chủ web.

### Bốn lỗi thật, chỉ lộ ra khi build và chạy

Không lỗi nào trong bốn lỗi này bị bất kỳ bài test mã nguồn nào bắt được. Đó là lý do phải
dựng image thật rồi chạy thật, chứ không chỉ viết Dockerfile rồi tin là xong.

**Lỗi 1 — container chết ngay lúc khởi động vì thiếu torch.**
```
File "/app/engine/embed/__init__.py", line 2, in <module>
    from .mobilefacenet import MobileFaceNet
ModuleNotFoundError: No module named 'torch'
```
Cả thiết kế "backend chạy bằng ONNX, không cần PyTorch" phụ thuộc vào việc mọi
lời `import torch` đều nằm **bên trong hàm**. `build_embedder()` làm đúng điều đó
— nhưng **một dòng trong `__init__.py`** đã vô hiệu hoá toàn bộ, vì import gói là
chạy `__init__.py`.

Nguy hiểm ở chỗ: ở máy phát triển **không ai thấy**, vì máy nào cũng có torch.
Lỗi chỉ nổ đúng lúc triển khai.

*Sửa:* dùng `__getattr__` cấp mô-đun (PEP 562) để nạp lười — tên
`MobileFaceNet` vẫn còn cho mã huấn luyện, nhưng torch chỉ được nạp khi có ai
thật sự hỏi tới nó.

*Chống tái phát:* `backend/tests/test_no_torch.py` — chặn torch ở `sys.meta_path`
rồi nạp toàn bộ backend. Chạy được ngay trên máy **có** torch. 6/6 đạt.

**Lỗi 2 — API chào mời mô hình mà chính nó không chạy nổi.**
`GET /api/system/models` liệt kê cứng "FaceNet (pretrained)" ở đầu danh sách.
Trong container không có torch, chọn nó là hỏng chắc chắn. *Sửa:* chỉ liệt kê khi
`importlib.util.find_spec("torch")` khác `None`.

**Lỗi 3 — image phình 380 MB một cách vô hình.**
Bản đầu dựng bánh xe (wheel) ở tầng builder rồi `COPY /wheels` sang tầng chạy,
cài xong thì `rm -rf /wheels`. Image vẫn **1,5 GB**. Nhìn `docker history` mới rõ:

```
646MB  RUN pip install --no-index --find-links=/wheels …
180MB  COPY /wheels /wheels          ← xoá ở lệnh sau cũng không mất đi
21.2MB RUN … chown -R faceid:faceid /app
```

Các tầng Docker chỉ **cộng dồn**. Xoá tệp ở tầng sau không gỡ được tầng trước —
nó chỉ ghi thêm một tầng đánh dấu "chỗ này trống". Và `chown -R` sờ vào metadata
của mọi tệp, nên nhân đôi cả cây `/app` thành một tầng mới.

*Sửa:* cài vào môi trường ảo `/opt/venv` ở tầng builder rồi chỉ `COPY` đúng thư
mục đó (bánh xe không bao giờ bước vào image cuối), và dùng `COPY --chown=` thay
cho `chown -R`.

**Lỗi 4 — container khoẻ nhưng bị gắn nhãn `unhealthy`.**
`docker compose ps` báo `web` là `unhealthy` với **94 lần thất bại liên tiếp**,
trong khi trang web phục vụ hoàn toàn bình thường và cả 20 phép thử khói đi qua
nó đều đạt. Nguyên nhân:

* nginx với `listen 80;` chỉ nghe **IPv4** (`0.0.0.0:80`);
* `/etc/hosts` trong container ánh xạ `localhost` sang **cả** `127.0.0.1` lẫn `::1`;
* `wget` của busybox thử `::1` trước rồi **bỏ cuộc ngay** — không như `curl` vốn
  tự thử nốt địa chỉ còn lại.

Đây là loại lỗi nguy hiểm hơn vẻ ngoài: ở môi trường thật, một container bị gắn
nhãn `unhealthy` sẽ bị khởi động lại hoặc bị gỡ khỏi bộ cân bằng tải — dù nó
chẳng hỏng gì. Nó cũng chính là thứ khiến `depends_on: condition: service_healthy`
treo vô hạn.

*Sửa:* dùng thẳng `127.0.0.1` trong cả hai HEALTHCHECK thay vì `localhost`.
Backend trước đó "may mà" xanh chỉ nhờ curl tự thử lại — cũng đã sửa cho khỏi phụ
thuộc vào hành vi đó.

### Dung lượng image — số đo, không phải ước lượng

| Bản dựng | Dung lượng |
|---|---|
| Bản đầu (chép bánh xe + `chown -R`) | 1,50 GB |
| Sau khi chép thẳng môi trường ảo | 1,12 GB |
| Sau khi bỏ `__pycache__`, `*/tests`, `pip`, `setuptools` | **941 MB** |
| Giao diện web (nginx + React đã build) | **74,4 MB** |

**Giá của PyTorch — đo bằng một image đối chứng, không phải ước lượng.** Dựng
thêm một image y hệt, chỉ khác ở chỗ cài thêm `torch` (bản CPU):

| Image backend | Dung lượng |
|---|---|
| Có `torch` (bản CPU) | **1,92 GB** |
| **Chỉ `onnxruntime`** | **941 MB** |
| Chênh lệch | **+1,0 GB · to gấp 2,04 lần** |

Con số này thay cho ước lượng "~5 GB xuống ~400 MB" mà tôi từng viết ở Task 6
**trước khi dựng image lần nào** — nó sai cả hai đầu. Ước lượng đã bị gỡ bỏ.

Ghi chú: `torchvision` không có bản dựng sẵn cho Python 3.13 CPU nên đối chứng chỉ
có `torch`. Nếu tính cả `torchvision` và `facenet-pytorch` (bắt buộc nếu muốn dùng
mô hình FaceNet) thì khoảng cách còn rộng hơn.

Gói nặng nhất trong image backend: opencv 153 MB · scipy 140 MB · numpy 71 MB ·
onnxruntime 66 MB · scikit-learn 48 MB. scipy và scikit-learn tồn tại **chỉ** để
bung bộ phân loại chống giả mạo — đây là chỗ còn cắt được nhiều nhất nếu sau này
chuyển bộ phân loại đó sang ONNX.

### Kiểm chứng trên hệ thống đã triển khai

`deploy/smoke_test.py` — **20/20 đạt**. Khác `backend/tests/test_flow.py` ở chỗ
test kia dùng `TestClient`, gọi thẳng vào đối tượng ứng dụng trong cùng tiến
trình; nó kiểm tra mã nguồn đúng nhưng đi vòng qua đúng những thứ mà việc triển
khai phụ thuộc vào. Tệp này gọi qua **HTTP thật, qua nginx**:

| Nhóm | Kiểm chứng |
|---|---|
| Sống | API trả lời qua nginx · CSDL nối được · engine đã nạp · SPA không ra 404 |
| Bảo mật | từ chối mật khẩu sai · **cổng 8000 không gọi được từ máy chủ** |
| Tính đúng | tạo người · nạp 4 ảnh → 4 vector · nhận đúng ảnh chưa từng dùng (0,923) |
| Nghiệp vụ | ghi sổ điểm danh · điểm danh lần hai không tạo dòng thứ hai |
| Bền dữ liệu | khởi động lại toàn bộ → người, ảnh, vector, sổ điểm danh còn nguyên |

Một "lỗi" trong lần chạy đầu hoá ra là **kỳ vọng của test sai, không phải hệ thống
sai**: API trả `label` là *mã người* (`SMOKE01`) chứ không phải họ tên. Đó là
thiết kế đúng — mã là định danh ổn định, sửa tên không phải trích đặc trưng lại.

### Máy kiosk cố ý nằm ngoài Docker

`desktop_app.py` cần camera và cửa sổ đồ hoạ. Đưa hai thứ đó vào container trên
Windows là chuyện khổ sở mà không đem lại lợi ích gì — kiosk vốn đã chạy trên máy
riêng đặt ở cửa lớp. Nó chỉ cần biết địa chỉ máy chủ qua `FACEID_API_URL`.

### Bốn bộ kiểm thử — 62/62 đạt

| Bộ | Số phép | Chạy ở đâu | Bắt lớp lỗi nào |
|---|---|---|---|
| `backend/tests/test_no_torch.py` | 6 | trong tiến trình, chặn torch | import torch lọt vào cấp mô-đun |
| `backend/tests/test_flow.py` | 25 | trong tiến trình (`TestClient`) | logic nghiệp vụ, phân quyền, báo cáo |
| `backend/tests/test_kiosk.py` | 11 | **HTTP thật vào Docker** | hàng đợi ngoại tuyến, đồng bộ, chống trùng |
| `deploy/smoke_test.py` | 20 | **HTTP thật vào Docker** | image, nginx, biến môi trường, volume |

Hai bộ dưới cùng nói chuyện với hệ thống **đã triển khai**, không phải với mã
nguồn — chúng là thứ duy nhất bắt được ba lỗi Docker ở trên.

**Một lỗi test phụ thuộc giờ chạy, tìm được lúc chạy lại cả bộ.**
`test_flow.py` tạo ca học bằng `start = bây giờ − 3 phút`, `end = bây giờ + 2 giờ`.
Chạy lúc 22:54 thì `end` thành 00:54 — mà `start_time`/`end_time` là **giờ trong
ngày**, không phải mốc thời gian, nên API từ chối đúng luật. Test chạy tốt cả
ngày và **chỉ hỏng sau 22 giờ**: đúng kiểu lỗi khiến người ta nghi oan cho mã
nguồn. Đã kẹp cửa sổ ca lại trong ngày.

Ghi nhận một giới hạn thật của hệ thống lộ ra từ đây: ràng buộc
`end_time > start_time` khiến **không tạo được ca qua đêm** (ví dụ ca trực
22:00–02:00). Với điểm danh lớp học thì không sao, nhưng nếu mở rộng sang chấm
công theo ca thì phải xử lý riêng.

---

## Task 12b — Phát hiện: giao thức đánh giá cũ phạt oan chính mô hình của nhóm

Tìm ra trong lúc chuẩn bị số liệu cho báo cáo. Cùng một mô hình
(`mobilefacenet_distill_casia`), chấm trên hai tập test khác nhau:

| Tập test | rank-1 | EER | **DIR@FAR=1%** |
|---|---|---|---|
| `data/aligned_big` — chip 112×112 **đã căn chỉnh sẵn** | 0,9849 | 2,40 % | **0,2759** |
| `data/datasets/lfw_big` — **ảnh gốc** 250×250 | 0,9778 | 2,53 % | **0,7199** |

Xác thực 1:1 và định danh đóng gần như không đổi. Định danh mở **chênh 2,6 lần**.

### Nguyên nhân

`data/aligned_big` chứa chip đã được phát hiện và căn chỉnh từ trước. Khi đánh
giá, `evaluate.py` lại chạy YuNet trên chính chip đó rồi căn chỉnh **lần thứ
hai** — cắt một vùng bên trong ảnh 112×112 vốn đã chật, rồi phóng to lại. Kết quả
là một thứ ảnh **không bao giờ xuất hiện lúc chạy thật**, vì lúc chạy thật camera
đưa vào khung hình gốc và pipeline chỉ căn chỉnh đúng một lần.

Đo trên cả 5 mô hình cho thấy tác hại **không đều**:

| Mô hình | DIR@1% trên chip | DIR@1% trên ảnh gốc | Thay đổi |
|---|---|---|---|
| ArcFace từ đầu · LFW | 0,2274 | **0,6756** | ×2,97 |
| ArcFace từ đầu · CASIA | 0,2107 | 0,2199 | ×1,04 |
| Chưng cất · LFW | 0,2308 | **0,5791** | ×2,51 |
| Chưng cất · CASIA+LFW | 0,2759 | **0,7199** | ×2,61 |
| FaceNet (thầy) | 0,7860 | 0,8513 | ×1,08 |

**Mô hình thầy gần như không bị ảnh hưởng, các mô hình trò thì bị ảnh hưởng
nặng.** Giải thích: FaceNet học trên 3,3 triệu ảnh rất đa dạng nên chịu được biến
dạng lạ; các mô hình trò học trên chip đã căn chỉnh nên gặp ảnh căn chỉnh hai lần
là ra ngoài phân bố dữ liệu chúng từng thấy.

### Kết luận cũ đã sai và được sửa

Bảng tổng hợp 5 mô hình trước đây ghi *"Vẫn còn một khoảng cách ở DIR@FAR=1 %
(0,276 vs 0,786) — model trò xếp hạng gần bằng thầy nhưng hiệu chỉnh ngưỡng còn
kém"*. Kết luận đó **dựa trên phép đo bị bóp méo**. Trên giao thức phản ánh đúng
lúc chạy thật, khoảng cách là **0,720 so với 0,851** — vẫn còn nhưng nhỏ hơn hẳn,
và không còn là điểm yếu nghiêm trọng như đã viết.

### Bảng tổng hợp ĐÚNG — 5 mô hình trên ảnh gốc

| Mô hình | Dữ liệu huấn luyện | rank-1 | EER | DIR@1% | ms | MB |
|---|---|---|---|---|---|---|
| ArcFace từ đầu | LFW · 349 người · 2.743 ảnh | 0,8671 | 9,63 % | 0,6756 | 5,29 | 4,8 |
| ArcFace từ đầu | CASIA · 6.000 người · 121k ảnh | 0,7563 | 9,57 % | 0,2199 | 4,16 | 4,8 |
| Chưng cất | LFW · 9k ảnh | 0,9082 | 5,57 % | 0,5791 | 6,63 | 4,8 |
| **Chưng cất** | **CASIA+LFW · 112k ảnh** | **0,9778** | **2,53 %** | **0,7199** | **4,73** | **4,8** |
| FaceNet (thầy) | VGGFace2 · 3,3 triệu ảnh | 0,9842 | 1,50 % | 0,8513 | 83,70 | 107,0 |

Ngưỡng vận hành đề xuất cho mô hình được chọn: **0,653** (FAR 9,1 % · FRR 9,0 %).

**Hình dùng cho báo cáo:** `reports/so_sanh_mo_hinh_anh_goc.png` (thay cho bản cũ).

### Bài học

Sai lầm ở đây không nằm trong mã nguồn mà nằm ở **chỗ lấy dữ liệu để chấm bài**.
Dùng lại thư mục ảnh đã tiền xử lý cho tiện thì tiết kiệm được vài phút, nhưng nó
lặng lẽ tạo ra một tập test không giống điều kiện vận hành. Nguyên tắc rút ra:
**tập kiểm tra phải đi qua đúng chuỗi xử lý mà hệ thống thật đi qua, không nhiều
hơn cũng không ít hơn một bước nào.**

Cùng một sai lầm này từng xuất hiện ở Task 12a (ablation), khi tôi định đo hiệu
quả của bước căn chỉnh trên dữ liệu vốn đã căn chỉnh sẵn — lần đó bắt được trước
khi chạy, lần này thì đã lỡ báo cáo một kết luận sai suốt nhiều task.

---

## Task 13 — Viết báo cáo vào mẫu Word của trường

**Nguyên tắc: mẫu quy định định dạng, mã nguồn chỉ quy định nội dung.**
`formatbaocao.docx` **không bị sửa** — chương trình đọc nó rồi ghi ra tệp mới.

    python -m report.bieu_do        # vẽ biểu đồ bố cục A4 dọc
    python -m report.build_report   # dựng BAO_CAO_HOAN_CHINH.docx
    python -m report.hoan_thien     # đánh số trang, điền mục lục, xuất PDF

### Cách giữ định dạng

Không tự đặt phông và cỡ chữ, mà **nhân bản một đoạn mẫu có sẵn** trong tệp rồi
thay chữ. Nhờ vậy mọi thuộc tính ở cấp đoạn (`w:pPr`) đều được sao nguyên khối
dưới dạng XML — kể cả những thuộc tính python-docx không phơi ra qua API.

Kết quả kiểm chứng: lề 3–2–2–2 cm, Times New Roman, thân bài 13pt căn đều giãn
dòng 1,5 thụt đầu dòng 1 cm — khớp đúng mẫu.

### Ba lỗi tự gây ra và tự sửa

**Lỗi 1 — xoá theo chỉ số sau khi đã chèn.** `doc.paragraphs` được tính lại mỗi
lần truy cập, nên ngay khi chèn đoạn đầu tiên thì mọi chỉ số ghi từ trước đều
lệch. Bản đầu xoá phần giữ chỗ theo chỉ số gốc **sau** khi đã chèn nội dung, và
nó xoá nhầm chính nội dung vừa viết trong khi giữ nguyên phần giữ chỗ của mẫu.
*Sửa:* giữ tham chiếu tới **đối tượng** đoạn văn, và xoá **trước** khi chèn.

**Lỗi 2 — mục lục tự liệt kê chính nó.** Quét cả tài liệu để thu đề mục thì các
dòng giữ chỗ của mục lục cũ ("KẾT LUẬN", "PHỤ LỤC"…) cũng lọt vào và bị chép lên
đầu mục lục mới. *Sửa:* loại trừ vùng mục lục khỏi phạm vi quét.

**Lỗi 3 — biểu đồ không đọc nổi khi in.** Biểu đồ xem trên màn hình xếp một hàng
ngang, tỉ lệ 3,8 : 1; thu về bề ngang 15,5 cm thì cao chỉ 4 cm và mọi chữ bên
trong biến mất. *Sửa:* `report/bieu_do.py` vẽ lại theo lưới hai cột, tỉ lệ về
1,3 : 1 nên ở cùng bề ngang hình cao gấp ba.

Ngoài ra: chú thích hình bị tách sang trang sau → đặt `keep_with_next` cho đoạn
chứa ảnh; và các dòng mục lục trong mẫu mang style Heading khiến chính chúng bị
Word coi là đề mục → chuyển sang style thân bài, phân cấp bằng độ thụt.

### Kết quả

**38 trang · 11.663 từ · 10 bảng · 2 hình số liệu · 8 chỗ chờ ảnh giao diện.**

| Phần | Nội dung |
|---|---|
| Mở đầu | Bối cảnh và điểm khác biệt của đề tài |
| Chương 1 | 5 mục — lý do, mục tiêu, phạm vi, đối tượng, phương pháp |
| Chương 2 | 3 mục lý thuyết, 10 tiểu mục — phát hiện, ArcFace, chưng cất và đánh giá open-set |
| Chương 3 | 14 tiểu mục phân tích + 8 mục giao diện |
| Kết luận | Đối chiếu mục tiêu · **5 hạn chế nêu rõ** · hướng phát triển theo thứ tự ưu tiên |
| Tài liệu | 11 mục theo chuẩn IEEE |

Mục lục và danh mục bảng/hình được **sinh tự động từ chính thân bài**, kèm số
trang do Word tính, nên không thể lệch với nội dung sau mỗi lần sửa.

### Việc còn lại của nhóm

1. Điền bảng danh sách thành viên ở trang bìa.
2. Thay 8 dòng "[Thay dòng này bằng ảnh chụp màn hình]" ở mục 3.2 bằng ảnh thật.
3. Nếu đo được tấn công giả mạo thật thì cập nhật Bảng 3.7; nếu không, **giữ
   nguyên câu nêu rõ số liệu là tấn công mô phỏng** — không được bỏ câu đó đi.

---

## Task 14 — Hiệu chỉnh lại cổng chất lượng bằng dữ liệu webcam thật

Phát hiện khi người dùng thật ngồi test lần đầu. Đăng ký 12 ảnh webcam, **chỉ 4
ảnh qua cổng**, và nhận diện trực tiếp luôn báo "Chưa nhận ra" với cosine **−1,000**.

### −1,000 không phải điểm số, mà là dấu hiệu chẩn đoán

`engine/pipeline.py` dòng 153:

```python
if report is not None and not report.passed:
    self.tracker.vote(track, Identity(Identity.UNKNOWN, -1.0))
```

Khung hình trượt cổng chất lượng thì hệ thống **không hề trích đặc trưng** — nó
không nhận sai, nó không thèm thử. Một cosine âm hoàn hảo là chuyện gần như không
thể xảy ra với vector thật, nên thấy đúng −1,000 là biết ngay lỗi nằm ở đâu.

### Bằng chứng cổng sai, không phải người dùng sai

Hai ảnh **bị loại vì "ảnh mờ"** (độ nét 0,0133 và 0,0118) vẫn nhận đúng người với
cosine **0,9383** và **0,7751** — thừa xa ngưỡng 0,55. Hai ảnh đó không nằm trong
gallery nên đây không phải kết quả vòng vo.

### Chọn ngưỡng bằng số đo, không bằng cảm tính

Đo rank-1 theo từng khoảng độ nét trên 632 ảnh gốc, 122 người đã đăng ký:

| Khoảng độ nét | Số ảnh | rank-1 |
|---|---|---|
| 0,000–0,010 | 8 | **0,875** ← chỗ duy nhất thật sự sụt |
| 0,010–0,015 | 15 | 1,000 |
| 0,015–0,020 | 64 | 0,953 |
| 0,020–0,025 | 67 | 0,970 |
| 0,025–0,035 | 151 | 0,980 |
| 0,035–0,060 | 212 | 0,981 |
| trên 0,060 | 115 | 0,991 |

Ngưỡng cũ **0,025** loại 146/632 ảnh (23 %) mà những ảnh ấy vẫn nhận đúng ~96 %.
Độ chính xác chỉ sụt thật sự **dưới 0,010**. → `min_sharpness: 0.025 → 0.010`.

Trên 12 ảnh của người dùng: **4/12 → 9/12 đạt**. Ba ảnh còn lại bị loại đúng: hai
ảnh quay ngang 36° và 48°, một ảnh mờ thật (0,0073).

### Hệ quả: ablation phải đo lại, và kết luận cũ phải sửa

| | Ngưỡng 0,025 | Ngưỡng 0,010 |
|---|---|---|
| Ảnh đăng ký bị loại | 29,5 % | **1,9 %** |
| Người không ghi danh nổi | 7/122 | **0/122** |
| rank-1 so với không lọc | −0,0111 | **±0,0000** |
| DIR@FAR=1 % so với không lọc | +0,0508 | **±0,0000** |

Đây là kết luận đáng ghi nhất của cả task: **toàn bộ lợi ích +5,1 điểm DIR mà
cổng chất lượng từng mang lại đều đến từ việc nó loại rất gắt.** Nới ngưỡng đủ để
dùng được ngoài đời thì lợi ích đo được biến mất.

Vậy có nên bỏ cổng chất lượng? **Không**, nhưng phải mô tả đúng vai trò của nó:

* Nó **chặn phần đuôi thật sự hỏng** (dưới 0,010 rank-1 tụt còn 0,875). Phần đuôi
  này hiếm trên LFW nên không hiện ra trong chỉ số tổng hợp, nhưng ảnh mẫu hỏng
  lọt vào gallery sẽ gây nhận nhầm về sau và rất khó truy nguyên.
* Giá trị lớn hơn của nó là **phản hồi hướng dẫn**, không phải lọc bỏ.

Không được tiếp tục khẳng định cổng chất lượng đem lại +5,1 điểm DIR — con số đó
chỉ đúng ở cấu hình đã bị loại bỏ vì không dùng được.

### Lỗi thứ hai: hệ thống biết lý do nhưng vứt đi

Câu nhắc từ `hint_for()` bị bỏ ngay tại chỗ kiểm tra, nên người đứng trước camera
chỉ thấy "Chưa nhận ra" — câu vô dụng nhất có thể hiển thị khi hệ thống biết
chính xác vấn đề. Đã thêm trường `Track.hint` và vẽ câu nhắc ngay dưới khung mặt
("Giu yen may, dung cu dong", "Nhin thang vao camera", "Moi lai gan camera").

`cv2.putText` chỉ vẽ được phông Hershey không có Unicode, nên phải bỏ dấu bằng
`_khong_dau()` — cũng là lý do nhãn trên khung hình xưa nay viết "Chua nhan ra".

### Bài học

Hai lần liên tiếp trong dự án này, một ngưỡng chỉnh trên **dữ liệu chuẩn** tỏ ra
sai khi gặp **dữ liệu thật**: lần trước là giao thức đánh giá (Task 12b), lần này
là cổng chất lượng. Cả hai chỉ lộ ra khi cho hệ thống chạm vào điều kiện vận hành
thật — không phép đo nào trên tập chuẩn phát hiện được.

---

## Task 15 — Chống giả mạo THẤT BẠI trên tấn công thật

Đo bằng tab "Chống giả mạo" với đòn tấn công thật: người dùng ngồi trước camera
ghi 60 khung mặt thật, rồi giơ điện thoại hiện ảnh chân dung ghi 60 khung tấn công.

### Kết quả

| Loại mẫu | Số khung | Điểm sống TB | Nhỏ/Lớn nhất |
|---|---|---|---|
| **Mặt thật** | 60 | **0,426** | 0,01 / 0,94 |
| **Màn hình điện thoại** | 60 | **1,000** | 1,00 / 1,00 |

Điểm sống càng cao nghĩa là càng chắc chắn là người thật. **Mô hình chấm ảnh điện
thoại thật hơn mặt thật.** Không phải kém — **ngược hoàn toàn**.

| Chỉ số | Tại ngưỡng hệ thống (0,396) | Tại ngưỡng "tối ưu" (0,943) |
|---|---|---|
| APCER (tấn công lọt) | **100 %** | **100 %** |
| BPCER (người thật bị chặn oan) | 40 % | 100 % |
| **ACER** | **70 %** | **100 %** |

Không ngưỡng nào cứu được: ở mọi điểm cắt, **mọi** đòn tấn công đều lọt. Đây không
phải lỗi hiệu chỉnh — mô hình sai về bản chất.

### Nguyên nhân

Dữ liệu huấn luyện là tấn công **mô phỏng**: lấy ảnh thật rồi làm xấu đi (thêm vân
moiré, giảm dải màu, giả lập phản xạ giấy). Mô hình học đúng một lối tắt:
**"ảnh xấu = giả, ảnh sạch = thật"**.

Thực tế đảo ngược chính xác lối tắt đó:

* mặt thật trong phòng thiếu sáng → nhiễu, tương phản thấp → mô hình thấy "xấu";
* màn hình điện thoại giơ sát camera → sáng, nét, tương phản cao → thấy "sạch".

Ở Task 8 tôi đã gặp đúng cạm bẫy này (56,40 % ảnh thật bị từ chối oan) và tưởng đã
sửa xong bằng khai thác mẫu khó. Nhưng **mẫu khó cũng do tôi tự sinh ra**, nên nó
chỉ vá được lỗ hổng bên trong thế giới mô phỏng. Con số ACER 0,13 % ở Task 8 vì
vậy không có giá trị dự báo nào về thực tế.

### Kết luận phải sửa trong báo cáo

Báo cáo trước đó liệt "chặn được tấn công bằng ảnh in và ảnh trên màn hình" vào
mục **đã làm được**. Điều đó **đã bị bác bỏ bằng đo đạc**. Phải chuyển sang mục
chưa làm được, kèm số liệu thật.

### Hướng đi

Bộ **chớp mắt** (`blink`) đã cài sẵn và không phụ thuộc kết cấu ảnh chút nào: nó
đo tỉ lệ khép mí mắt qua nhiều khung. Ảnh tĩnh trên điện thoại **không thể chớp
mắt**, nên về nguyên lý không lách được bằng cách chỉnh sáng hay chỉnh nét. Đây là
khác biệt căn bản: kết cấu ảnh là dấu hiệu **tương quan**, còn chuyển động mí mắt
là dấu hiệu **nhân quả**.

Muốn cứu đường kết cấu thì phải thu dữ liệu tấn công **thật** — chụp lại màn hình
và ảnh in ở nhiều thiết bị, nhiều điều kiện sáng — rồi huấn luyện lại. Không có
đường tắt nào từ dữ liệu mô phỏng.

### Bài học

Đây là lần thứ ba trong dự án một phép đo trên dữ liệu tự sinh sụp đổ khi gặp thực
tế (sau giao thức đánh giá ở Task 12b và cổng chất lượng ở Task 14). Lần này nghiêm
trọng nhất, vì nó không chỉ sai số — nó **sai hướng**, và nếu triển khai thật thì
hệ thống sẽ chặn người thật trong khi mở cửa cho kẻ giả mạo.

### Bằng chứng quyết định: "điểm sống" thực chất là điểm chất lượng ảnh

Đo lần thứ hai, cùng người cùng điện thoại, chỉ khác điều kiện ngồi:

| | Mặt thật | Màn hình điện thoại |
|---|---|---|
| Lần 1 — ngồi xa, phòng tối | **0,426** | 1,000 |
| Lần 2 — ngồi gần, sáng hơn | **0,995** | 1,000 |

Điểm của mặt thật **nhảy từ 0,426 lên 0,995** chỉ vì đổi khoảng cách và ánh sáng.
Điểm của đòn tấn công đứng yên ở 1,000 cả hai lần.

Đây là bằng chứng trực tiếp cho chẩn đoán ở trên: đại lượng mà mô hình học được
**không phải sự sống mà là chất lượng ảnh**. Màn hình điện thoại luôn sáng, nét,
tương phản cao nên luôn đạt điểm tối đa. Mặt thật chỉ đạt điểm cao khi được chiếu
sáng tốt — tức là hệ thống thưởng cho **điều kiện chụp**, không phải cho việc
người đó có thật hay không.

Chỉ số ở lần đo thứ hai: APCER 100 %, BPCER 0 %, **ACER 50 %** — đúng bằng đoán
ngẫu nhiên. Ở ngưỡng "tối ưu cho dữ liệu này" thì ACER lên **98,33 %**, nghĩa là
không tồn tại điểm cắt nào có ích.

### Sửa công cụ đo

Trang đo trước đây **ép cứng** phương pháp về `texture`, nên không thể đo phương
pháp chớp mắt — đúng thứ cần đo nhất sau kết quả này. Đã thêm bộ chọn phương pháp.

Kèm theo một chốt chặn: đổi phương pháp thì **bắt buộc xoá mẫu cũ**. Điểm sống của
hai phương pháp nằm trên hai thang khác hẳn nhau (kết cấu bề mặt so với chuyển
động mí mắt); trộn mẫu thật đo bằng cách này với mẫu giả mạo đo bằng cách kia sẽ
ra một bộ APCER/BPCER trông rất chính đáng nhưng vô nghĩa hoàn toàn — và không có
gì trên màn hình gợi ý rằng nó sai. Đây đúng là loại lỗi mà một công cụ đo tử tế
phải tự chặn, thay vì trông chờ người dùng nhớ.

---

## Task 16 — Chớp mắt đạt ACER 0 %, và đưa kết quả đó vào hệ thống thật

### Số đo trên đòn tấn công thật

Cùng người, cùng điện thoại, cùng 60 khung mỗi loại — chỉ đổi phương pháp:

| Phương pháp | Mặt thật | Màn hình điện thoại | APCER | BPCER | **ACER** |
|---|---|---|---|---|---|
| Kết cấu ảnh (`texture`) | 0,426–0,995 | 1,000 | 100 % | 0–40 % | **50–70 %** |
| **Chớp mắt (`blink`)** | **1,000** | **0,000** | **0 %** | **0 %** | **0 %** |

Phân tách tuyệt đối, không chồng lấn một khung nào. Nguyên nhân đơn giản: **ảnh
tĩnh không thể chớp mắt.** Kết cấu ảnh chỉ là dấu hiệu *tương quan* với sự sống —
và tương quan đó đảo chiều ngay khi điều kiện chụp thay đổi. Chuyển động mí mắt là
dấu hiệu *nhân quả*.

### Phát hiện: đo xong nhưng chẳng áp dụng vào đâu

Câu hỏi của người dùng — *"làm vầy rồi áp dụng vào đâu hay chỉ là chức năng test
thôi"* — phơi ra ba lỗ hổng mà bản thân phép đo không thể thấy:

1. **Kiosk không hề kiểm tra liveness trước khi gửi.** `KioskThread` phát sự kiện
   điểm danh cho mọi vết vừa được xác nhận, không đụng tới `track.liveness`. Giơ
   ảnh điện thoại là ghi sổ được.
2. **Máy chủ thì có kiểm tra** (`recognize.py` dòng 94) nhưng được cấu hình bằng
   `texture` — tức đang chạy đúng phương pháp vừa đo là hỏng. Hệ quả: chặn oan
   người thật *đồng thời* cho mọi đòn tấn công lọt. **Tệ hơn là không bật gì**,
   vì nó tạo cảm giác an toàn giả.
3. **Mặc định trong `engine/settings.py` là `minifas`** (bí danh của `texture`),
   nên mọi thành phần chưa cấu hình rõ đều thừa hưởng phương pháp hỏng.

### Hệ quả kiến trúc: liveness KHÔNG thể đặt ở máy chủ

Chớp mắt là tín hiệu **theo thời gian** — phải có chuỗi khung hình. Máy chủ chỉ
nhận **một tấm ảnh** mỗi lần điểm danh, nên về nguyên tắc không thể tự kiểm tra.
Thêm mediapipe vào image backend cũng không cứu được, vì thiếu thứ cần là *chuỗi
khung*, không phải thư viện.

Vậy liveness phải nằm ở **máy kiosk**, nơi có luồng video. Đánh đổi phải nói thẳng:

| Tầng | Ai là bên quyết định | Kiosk bị chiếm quyền thì sao |
|---|---|---|
| Danh tính | **Máy chủ** tự nhận diện lại ảnh gửi lên | Không giả mạo được |
| Chống giả mạo | **Kiosk** | Có thể bỏ qua |

Mô hình tin cậy của tầng chống giả mạo vì vậy **yếu hơn** tầng nhận diện. Muốn
khoá lại thì kiosk phải gửi một chuỗi khung ngắn để máy chủ tự đo — tốn băng thông
hơn nhiều, và nằm ngoài phạm vi đề tài.

### Đã sửa

* `engine/settings.py`: mặc định `minifas` → **`blink`**.
* `desktop_app.py`: `KioskThread` chặn ngay tại chỗ khi điểm sống dưới ngưỡng,
  phát tín hiệu `spoofed`; `KioskPage` hiện thẻ đỏ "Nghi giả mạo — không ghi nhận"
  kèm điểm số và ghi vào nhật ký phiên. **Không gửi gì lên máy chủ.**
* `deploy/compose.yml` và `.env.example`: `texture` → **`none`**, kèm giải thích
  vì sao máy chủ cố ý không làm việc này.
* Trang đo có bộ chọn phương pháp và chốt chặn không cho trộn mẫu hai phương pháp.

Toàn bộ 56 phép thử vẫn đạt sau thay đổi.

### Điều cần nói rõ trong báo cáo

Chớp mắt đạt ACER 0 % trên **một phiên đo, một người, một thiết bị tấn công**. Đó
là bằng chứng đủ để chọn phương pháp, nhưng chưa đủ để tuyên bố hệ thống an toàn.
Cần đo thêm trên nhiều người, nhiều điện thoại, và cả ảnh in. Đặc biệt cần kiểm
tra hai điểm yếu đã biết của phương pháp chớp mắt: **video quay sẵn có người chớp
mắt** (tấn công cao cấp hơn ảnh tĩnh) và **người đeo kính dày** làm mất dấu mí mắt.

---

## Task 17 — WebSocket đẩy sự kiện, và nút gạt hai trạng thái

### Vì sao đẩy chứ không hỏi lại

Giao diện web trước đây chỉ biết có bản ghi mới khi người dùng tự bấm tải lại.
Với màn hình treo ở phòng giáo vụ để theo dõi lớp đang điểm danh thì vô dụng:
thông tin đúng đã nằm trong cơ sở dữ liệu nhưng không ai thấy.

Cách rẻ là để trình duyệt gọi lại API mỗi vài giây. Nó tạo lưu lượng liên tục kể
cả khi cả buổi không ai điểm danh, và vẫn trễ. Cách ở đây là **máy chủ chủ động
đẩy**: không có bản ghi mới thì không có gói tin nào.

### Ba chi tiết quyết định việc nó chạy được lâu dài

**1. Token đi trong THÂN gói tin, không nằm trên URL.** Trình duyệt không cho đặt
header `Authorization` khi mở WebSocket, nên cách phổ biến là `?token=...`. Cố ý
không làm vậy: chuỗi truy vấn bị ghi vào nhật ký máy chủ, nhật ký proxy và lịch sử
trình duyệt — thẻ đăng nhập nằm lại ở ba nơi ngoài tầm kiểm soát. Thay vào đó máy
chủ chấp nhận kết nối rồi **chờ gói tin đầu tiên** chứa token, quá 10 giây thì đóng.

**2. nginx phải được dạy cách nâng cấp.** Thiếu `proxy_set_header Upgrade` và
`Connection` thì nginx coi đó là request HTTP thường và trả 200 thay vì 101.
WebSocket không mở được **mà không có thông báo lỗi nào** để lần ra. Giá trị
`Connection` lấy từ khối `map` chứ không viết cứng "upgrade", vì viết cứng sẽ phá
các request thường đi chung `location /api/`.

**3. Nối lại có giãn cách tăng dần.** Máy chủ khởi động lại thì mọi trình duyệt
đang mở sẽ cùng nối vào một lúc; không giãn cách thì chúng dội liên tục đúng lúc
máy chủ còn đang nạp mô hình. Giãn cách 1s → 2s → 4s… tối đa 15s.

Cộng thêm: nhịp giữ kết nối 25 giây (proxy thường cắt đường truyền im lặng quá 60
giây), và dọn kết nối khi rời trang — thiếu bước dọn thì mỗi lần chuyển trang lại
bỏ lại một kết nối chạy ngầm.

### Quyết định thiết kế ở phía web

Khi nhận sự kiện, trang **gọi lại API** thay vì tự chèn dòng vào bảng. Lý do: bộ
lọc ngày và trạng thái đang bật có thể khiến bản ghi mới *không* thuộc danh sách
đang xem; tự chèn sẽ hiện ra một dòng lẽ ra phải bị lọc đi.

Chấm trạng thái kết nối hiển thị rõ trên đầu trang. Một bảng không tự cập nhật
trông **giống hệt** một bảng không có gì mới — người dùng không phân biệt được, và
sẽ tin nhầm là lớp chưa ai điểm danh.

Sự kiện chỉ phát khi **thực sự tạo bản ghi mới**. Người đứng lại trước camera lần
thứ hai không tạo dòng nào trong sổ, nên cũng không được làm bảng nhấp nháy.

### Kiểm thử — 5 phép, tất cả đạt

`backend/tests/test_websocket.py` chạy **qua nginx** chứ không gọi thẳng backend,
vì phần dễ hỏng nhất nằm đúng ở lớp proxy. Test gọi thẳng backend sẽ xanh trong
khi hệ thống thật hỏng.

Một phép thử đỏ lúc đầu: "đóng kết nối khi token sai". Hoá ra máy chủ hành xử
đúng — `websocket-client` báo đã bị đóng bằng cách trả **chuỗi rỗng**, không ném
lỗi, nên `try/except` luôn đỏ. Lại thêm một lần test sai suýt khiến đi sửa nhầm
phần mã vốn không hỏng.

**Tổng: 67 phép thử trên 5 bộ, tất cả đạt.**

### Nút gạt hai trạng thái ở tab Trực tiếp

Thay danh sách bốn lựa chọn (`none/texture/blink/combo`) bằng một nút gạt:

* **Chống giả mạo: BẬT (chớp mắt)** — nền xanh
* **Nhận tất cả — kể cả ảnh, video** — nền vàng

Bốn lựa chọn kỹ thuật là cách nghĩ của người viết engine, không phải của người
đang đứng trước camera. Nhãn cũng nói **hệ quả** chứ không chỉ tên chế độ: "Chống
giả mạo: Tắt" không cho biết điều gì đang xảy ra, còn "Nhận tất cả — kể cả ảnh,
video" thì nói thẳng. Các tab khác giữ nguyên danh sách đầy đủ.

### Ghi chú về phạm vi

Danh sách kết nối nằm trong bộ nhớ của **một tiến trình**. Hệ thống chạy đúng một
worker nên đủ. Tách thành nhiều tiến trình thì phải thay bằng kênh dùng chung như
Redis pub/sub — nếu không, trình duyệt nối vào worker A sẽ không nhận sự kiện sinh
ra ở worker B, và lỗi đó biểu hiện cực kỳ khó hiểu: cập nhật lúc được lúc không.

---

## Task 18 — Ba lỗi trong chính tầng chống giả mạo vừa tuyên bố là đạt ACER 0 %

Người dùng thử tiếp và phá vỡ kết quả 0 % chỉ trong vài phút. Ba lỗi, lỗi đầu do
chính thay đổi của tôi ở Task 16 gây ra.

### Lỗi 1 — bằng chứng sống bị gắn vào MỘT TOẠ ĐỘ, không gắn vào một người

Ảnh trên điện thoại được chấm **0,92 điểm sống** và điểm danh trót lọt.

`BlinkLiveness._slot_for()` ghép khuôn mặt vào "slot" **chỉ theo khoảng cách tâm**,
và slot sống vĩnh viễn cùng toàn bộ lịch sử chớp mắt:

    người thật chớp mắt   ->  slot ghi "vừa chớp, còn hiệu lực"
    hạ mặt xuống          ->  slot VẪN giữ nguyên tín dụng đó
    giơ ảnh vào đúng chỗ  ->  ghép trúng slot cũ, THỪA HƯỞNG cái chớp

Tệ hơn: ở Task 16 tôi nới cửa sổ hiệu lực từ 6 lên 15 giây, **làm đòn tấn công này
dễ hơn hẳn**. Trong chính ghi chú lúc đó tôi đã nêu rủi ro rồi gạt đi là "khó hơn
hẳn việc chỉ giơ một tấm ảnh lên". Người dùng chứng minh nó mất hai giây.

*Sửa:* slot không thấy mặt quá `SLOT_TIMEOUT` (0,6 giây) thì **xoá hẳn kèm lịch
sử**. Bằng chứng sống buộc phải thuộc về một khuôn mặt được theo dõi liên tục.

*Còn lại điều phải nói rõ:* trượt ảnh vào che mặt **không tạo khoảng trống** thì
vẫn có thể thừa hưởng. Chặn triệt để cần thử thách ngẫu nhiên ("quay đầu sang
trái") để kẻ tấn công không đoán trước được yêu cầu.

### Lỗi 2 — EAR không bất biến theo tỉ lệ như công thức gợi ý

Hiện tượng: **đứng xa thì báo giả mạo, lại gần thì nhận ra**.

Đo trên cùng bộ ảnh, mắt **luôn mở**, chỉ đổi cỡ mặt:

| Cỡ mặt | EAR đo được |
|---|---|
| 60 px | 0,2044 |
| **80 px** | **0,1124** ← thấp hơn cả ngưỡng "đang nhắm" 0,16 |
| 100 px | 0,1371 |
| 130 px | 0,1531 |
| 220 px | 0,2123 ← vẫn chưa chạm ngưỡng "đã mở" 0,22 |

Sai số định vị điểm mốc lấn át tín hiệu thật khi mắt chỉ còn vài chục điểm ảnh.
Hậu quả: mặt xa thì mắt bị coi là **nhắm vĩnh viễn**, máy trạng thái không bao giờ
thấy chuỗi mở → nhắm → mở, không đếm được cái chớp nào, và **người thật bị kết tội
giả mạo**.

Ngưỡng cố định 0,16 / 0,22 lấy từ tài liệu đo trên ảnh độ phân giải cao. Trên
webcam 640×480 chúng sai hoàn toàn.

*Sửa:* ngưỡng **thích nghi theo từng khuôn mặt**. Mỗi mặt tự dựng đường nền EAR
lúc mắt mở (phân vị 80 của 90 khung gần nhất), rồi coi là chớp khi EAR tụt dưới
72 % đường nền và bật lại trên 85 %. Bất biến với cả cỡ mặt lẫn hình dạng mắt.

### Lỗi 3 — nhập nhèm "không đo được" với "đã đo và là giả"

Mặt quá nhỏ thì trả về 0,0 — cùng giá trị với "đã đo và kết luận là giả". Hệ thống
vì thế **kết tội** người chỉ đứng hơi xa.

*Sửa:* trả **−1,0** nghĩa là chưa đo được, khác hẳn 0,0. Ba nơi tiêu thụ đều được
dạy phân biệt: `pipeline.identify` không coi là giả mạo, kiosk **không ghi sổ mà
cũng không kết tội**, giao diện hiện "(chua do duoc)" thay vì "GIA MAO".

Đây là dạng lỗi rất dễ mắc: dùng một giá trị hợp lệ để biểu thị trạng thái "không
có giá trị". Nó không gây lỗi chương trình, chỉ lặng lẽ biến "tôi không biết"
thành "tôi khẳng định là giả".

### Lỗi 4 — khung bao nhấp nháy liên tục

`track_frame` bỏ qua mọi vết có `misses > 0`, nên chỉ cần một khung phát hiện hụt
là khung bao biến mất rồi hiện lại. Bộ bám vết vốn giữ vết sống tới `max_age` khung
**chính là để vượt qua những lần hụt như vậy** — vứt đi ở tầng hiển thị là phá bỏ
đúng thứ nó sinh ra để làm. Đã nới lên `misses > 3`.

### Bài học

Kết quả ACER 0 % ở Task 16 **đúng với quy trình đo đó**: ngồi yên ghi 60 khung
thật, rồi giơ điện thoại ghi 60 khung giả. Nó không sai, nhưng nó **không bao gồm
thao tác chuyển tiếp** giữa hai trạng thái — mà chính khe hở ở chỗ chuyển tiếp mới
là nơi đòn tấn công thật sự sống.

Một phép đo tĩnh trên hai trạng thái tách biệt không thay thế được việc cho người
dùng thật cầm thiết bị và thử phá. Ba trong bốn lỗi trên chỉ lộ ra theo cách đó.

---

## Task 19 — Xuất Excel có định dạng, và "kết tội trước khi xét"

### Lỗi 5 của tầng chống giả mạo: phán quyết khi chưa có bằng chứng

Người dùng mô tả: *"vừa đưa đầu vô là báo giả mạo, phải lách qua rồi đưa vào lại,
chớp mắt 2–3 giây nó mới bỏ phiếu lại mới nhận đúng"*.

Nguyên nhân nằm ở `_FaceState.score()`:

```python
if self.blinks == 0:
    return 0.0        # <- "đã xét và kết luận là giả"
```

Khuôn mặt vừa bước vào khung hình thì đương nhiên chưa quan sát được cái chớp nào.
Trả 0.0 lúc đó là **kết tội trước khi xét**.

Đây đúng là lỗi tôi vừa sửa ở Task 18 (nhập nhèm "không đo được" với "là giả"),
nhưng lần đó chỉ vá trường hợp *mặt quá nhỏ* mà bỏ sót trường hợp *mặt mới xuất
hiện* — cùng một lỗi tư duy, hai chỗ khác nhau.

*Sửa:* thêm khoảng chờ `CHO_CHOP_MAT = 12 giây`. Trong khoảng đó trả **−1.0**
("đang kiểm tra"), hết khoảng chờ mà vẫn không thấy chớp mới trả 0.0 ("là giả").

Trạng thái chờ **vẫn chặn việc ghi điểm danh**, nên nó an toàn: người giơ ảnh cũng
chỉ nhận được "đang kiểm tra" rồi chuyển sang "giả mạo", không lọt qua được.

12 giây chọn theo nhịp chớp mắt của người nhìn chăm chú vào màn hình: 4–6 lần mỗi
phút, tức cách nhau 10–15 giây.

### Ba màu, ba trạng thái

| Màu | Nghĩa |
|---|---|
| 🔴 Đỏ | Đã xét đủ và kết luận **là giả** |
| 🟡 Vàng | **Chưa đủ bằng chứng** — chưa kết luận gì |
| 🟢 Xanh | Người thật, đã nhận ra |

Trạng thái vàng là thứ bản đầu thiếu hoàn toàn. Hệ thống chỉ có hai màu nên buộc
phải chọn một trong hai ngay lập tức, và nó chọn sai.

### Xuất Excel thay cho CSV

CSV chỉ chứa chữ thô. Mở bằng Excel thì cột ngày hiện thành `######`, mọi tiêu đề
bị cắt cụt, trạng thái hiện là `late` thay vì "Đi muộn", và người xem phải tự
chỉnh độ rộng từng cột. Tệp xuất ra lẽ ra phải **dùng được ngay**, không phải một
việc dở dang giao lại cho người dùng.

Điểm cuối mới `/api/attendance/export.xlsx` dựng tệp bằng openpyxl:

* tiêu đề có dấu tiếng Việt, độ rộng cột đặt sẵn theo nội dung;
* định dạng ngày `dd/mm/yyyy`, giờ `hh:mm:ss`, điểm số 3 chữ số thập phân;
* dòng tiêu đề **đóng băng** và có **bộ lọc** — khác biệt giữa dùng được và không
  khi sổ có vài trăm dòng;
* dòng đi muộn tô nền vàng, chữ đậm màu cam; đúng giờ nền xanh nhạt;
* khối tổng kết cuối bảng: tổng lượt, đúng giờ, đi muộn, tỉ lệ;
* **trang thứ hai "Đi muộn"** riêng, để giảng viên khỏi phải tự lọc.

CSV vẫn giữ ở `/api/attendance/export` cho ai cần đưa dữ liệu sang công cụ khác.
Giao diện web có hai nút riêng, nút Excel là nút chính.

**67/67 phép thử vẫn đạt.**

---

## Task 20 — Rút ngắn thời gian kết luận bằng một tín hiệu thứ hai

### Vấn đề

Sau khi thêm khoảng chờ 12 giây (Task 19), hệ thống không còn kết tội oan — nhưng
phải chờ hết 12 giây mới dám kết luận ảnh điện thoại là giả. Người dùng phản ánh
đúng: quá lâu cho một kiosk có người xếp hàng.

Gốc rễ: chỉ có **một** tín hiệu là chớp mắt, nên không phân biệt được "ảnh tĩnh"
với "người thật chưa kịp chớp". Cả hai đều cho `blinks == 0`.

### Tín hiệu thứ hai: mắt người sống không bao giờ đứng yên

Kể cả giữa hai nhịp chớp, EAR vẫn dao động vì rung mắt, đảo mắt, nheo nhẹ theo
ánh sáng. Một tấm ảnh thì EAR gần như hằng số — chỉ còn nhiễu do sai số định vị
điểm mốc.

Đo bằng **hệ số biến thiên** (độ lệch chuẩn chia trung bình) trên 45 khung gần
nhất, không dùng độ lệch chuẩn thô: EAR nền của mỗi người mỗi cỡ mặt một khác,
nên ngưỡng tuyệt đối sẽ lại mắc đúng lỗi tỉ lệ đã gặp ở Task 18.

| Đầu vào | Hệ số biến thiên |
|---|---|
| Ảnh tĩnh (cùng một tệp lặp lại) | **0,00000** |
| Mô phỏng người thật (thêm nhiễu nhẹ) | **0,03894** |

Nhờ đó ảnh tĩnh bị kết luận sau khoảng **hai giây** thay vì mười hai, còn người
thật vẫn được chờ đủ kiên nhẫn. Hai tín hiệu **bổ sung** cho nhau: dao động cho
biết "có sự sống", chớp mắt cho biết "chắc chắn sống".

### Vì sao đặt ngưỡng 0,020 chứ không sát mức đo được

Ngưỡng đầu tôi đặt 0,035 — sát ngay mức 0,03894 của mẫu "người thật". Khoảng cách
đó quá mỏng. **Hai loại sai không ngang giá nhau**: kết tội oan người thật nặng
hơn hẳn việc bắt ảnh giả chậm vài giây, vì người bị từ chối không hiểu tại sao và
không biết phải làm gì, trong khi kẻ giơ ảnh chỉ mất thêm mấy giây rồi vẫn bị
chặn. Hạ xuống **0,020**.

### Điều phải nói rõ về chính con số này

Phép đo trên dùng **cùng một tệp ảnh lặp lại**, nên hệ số biến thiên bằng đúng 0.
Ảnh điện thoại chụp **qua camera** thì vẫn có nhiễu cảm biến, nên số thật sẽ lớn
hơn 0 — và **chưa đo được là bao nhiêu**. Nếu thực tế ảnh điện thoại vẫn phải chờ
hết 12 giây thì ngưỡng còn thấp quá và phải đo lại bằng dữ liệu thật.

Đã phơi `bien_thien_gan_nhat()` ra để giao diện hiển thị con số thật, nhằm hiệu
chỉnh bằng số liệu thay vì đoán — đúng cách đã dùng cho cổng chất lượng ở Task 14.

### Tổng kết năm lỗi của tầng chống giả mạo

| # | Lỗi | Biểu hiện |
|---|---|---|
| 1 | Phân tích kết cấu ảnh học lối tắt "ảnh sạch là thật" | ACER 50–70 %, chấm ảnh điện thoại thật hơn người thật |
| 2 | Bằng chứng sống gắn vào toạ độ, không gắn vào người | Giơ ảnh vào đúng chỗ mặt vừa rời đi là thừa hưởng cái chớp |
| 3 | EAR không bất biến theo tỉ lệ | Đứng xa bị kết tội giả mạo, lại gần thì hết |
| 4 | Nhập nhèm "không đo được" với "là giả" | Kết tội người chỉ đứng hơi xa |
| 5 | Phán quyết khi chưa có bằng chứng | Vừa vào khung hình đã báo giả mạo |

Không lỗi nào trong năm lỗi trên bị phép đo ACER 0 % ở Task 16 phát hiện. Tất cả
đều lộ ra khi người dùng thật cầm thiết bị và thử phá.

---

## Task 21 — Ngưỡng nhận diện 0,55 nhận nhầm một phần tư số người lạ

### Phát hiện

Người dùng giơ điện thoại đang phát video của **một người hoàn toàn khác**. Hệ
thống chấm cosine **0,756** và gán đúng tên người đã đăng ký.

Đây không phải lỗi chống giả mạo — tầng đó làm đúng việc, giữ ở trạng thái "đang
kiểm tra" nên **không có bản ghi nào vào sổ**. Đây là lỗi **nhận diện**: ngưỡng
chấp nhận quá thấp.

### Đo lại trên 632 ảnh người quen và 474 ảnh người lạ

| Ngưỡng | Người lạ lọt (FAR) | Người quen bị từ chối (FRR) |
|---|---|---|
| **0,55 (đang dùng)** | **25,7 %** | 1,9 % |
| 0,60 | 12,0 % | 4,3 % |
| 0,631 (điểm cân bằng lỗi) | 5,5 % | 6,0 % |
| 0,65 | 4,2 % | 7,4 % |
| **0,68** | **2,1 %** | **10,9 %** |
| 0,70 | 1,5 % | 13,8 % |
| 0,75 | 0,2 % | 25,8 % |

Ngưỡng 0,55 cho **một phần tư số người lạ đi qua**. Với một hệ thống điểm danh thì
con số đó phá hỏng chính mục đích tồn tại của nó.

### Vì sao chọn 0,68 chứ không phải điểm cân bằng lỗi 0,631

Điểm cân bằng lỗi (FAR = FRR) là lựa chọn mặc định khi hai loại lỗi ngang giá.
Ở đây **chúng không ngang giá**:

* **Nhận nhầm** → ghi sai vào sổ điểm danh, người vắng thành có mặt, và không ai
  phát hiện ra. Đây đúng là thứ hệ thống sinh ra để ngăn.
* **Từ chối oan** → người dùng đứng lại một lần nữa. Phiền, nhưng tự phục hồi
  được và người dùng biết ngay là có chuyện.

Coi nhận nhầm nặng gấp ba lần từ chối oan thì tổng lỗi nhỏ nhất rơi đúng vào
**0,68**: người lạ lọt giảm từ 25,7 % xuống 2,1 %, đổi lại người quen phải thử lại
nhiều hơn (1,9 % → 10,9 %).

`min_confidence` phía backend cũng nâng theo — để lệch nhau thì engine nhận ra
nhưng backend từ chối ghi, một kiểu hỏng rất khó lần ra nguyên nhân.

### Lỗi thứ hai: nêu tên khi chưa xác minh xong

Khung vàng "đang kiểm tra" vẫn in tên người khớp nhất. Nên khi giơ video người
khác lên, màn hình vẫn hiện tên người đã đăng ký — một kết quả **chưa được xác
nhận** lại được trình bày y như một kết luận, và người xem không có cách nào biết
nó chưa chắc.

Đã bỏ tên khỏi trạng thái vàng. Danh tính chỉ được nêu khi đã qua **cả hai cửa**:
khớp vector và chứng minh là người sống.

### Ghi chú cho báo cáo

Ngưỡng 0,55 là giá trị dùng xuyên suốt mọi phép đo trước đó trong báo cáo, kể cả
bảng so sánh năm mô hình. Các chỉ số rank-1, EER và DIR@FAR **không phụ thuộc
ngưỡng** nên vẫn đúng nguyên. Riêng những chỗ nhắc tới "ngưỡng vận hành 0,55" phải
sửa thành 0,68 kèm bảng đánh đổi ở trên.

---

## Task 22 — Vết bị "đốt" trong lúc chờ xác minh sự sống

### Hiện tượng

Kiosk nhận đúng người (khung xanh, cosine 0,94, điểm sống 1,00) nhưng **nhật ký
không có dòng điểm danh nào**. Nhận diện đúng, chống giả mạo đúng, mà bản ghi
không bao giờ tới máy chủ.

### Nguyên nhân — lỗi do chính tôi tạo ra ở Task 16

`FaceTracker.newly_confirmed()` đánh dấu vết là **đã phát** ngay lúc trả về nó:

```python
def newly_confirmed(self):
    out = [t for t in self.tracks if t.confirmed and not t.announced]
    for t in out:
        t.announced = True      # <- đánh dấu NGAY
    return out
```

Khi thêm chốt chặn chống giả mạo, tôi đặt lệnh kiểm tra **sau** lời gọi đó:

```python
for tr in self.engine.newly_confirmed():   # đã announced = True
    if tr.liveness < 0:
        continue                            # <- vết cháy vĩnh viễn
```

Trình tự thực tế: người bước vào → vết đủ 5 phiếu và được xác nhận sau khoảng
0,2 giây → nhưng đo sự sống cần **vài giây** nên điểm còn là −1,0 → `continue` →
vết mất quyền phát. Sau đó người ấy chớp mắt, điểm lên 1,00, nhưng
`newly_confirmed()` không bao giờ trả vết đó ra nữa.

Hai tầng chạy ở **hai nhịp thời gian khác nhau** — nhận diện chốt sau 0,2 giây,
chống giả mạo cần vài giây — và tôi nối chúng như thể chúng cùng nhịp.

### Sửa

Trả lại quyền phát khi bỏ qua: `tr.announced = False`. Vết chỉ bị tiêu thụ khi
**thực sự gửi được gì đó đi**.

Nhánh giả mạo cũng sửa tương tự: một người thật có thể bị chấm dưới ngưỡng trong
lúc chưa chớp lại, đốt vết ở đó thì họ chớp mắt xong cũng không điểm danh nổi.
Kèm giới hạn báo tối đa 3 giây một lần để khỏi ngập nhật ký.

### Bài học

Đây là loại lỗi **không có thông báo, không có ngoại lệ, không có gì trên màn hình
gợi ý**. Mọi bộ phận đều báo "tôi làm đúng phần của tôi", và chỉ chỗ nối giữa
chúng là hỏng. Không phép thử nào của bốn bộ kiểm thử cũ chạm tới nó, vì chúng
kiểm tra từng tầng riêng.

Đã thêm `backend/tests/test_vet_cho_xac_minh.py` — **6 phép thử**, trong đó có một
phép **tái hiện đúng lỗi cũ** để chứng minh bài test thật sự bắt được nó, chứ
không phải một bài test luôn xanh.

**Tổng: 73 phép thử trên 6 bộ.**

---

## Task 23 — Hệ hiệu ứng cho tính năng cử chỉ tay

### Tự sinh thay vì tải trên mạng

Người dùng đề nghị tôi tìm và tải hiệu ứng về. Máy có mạng, nhưng tôi chọn **tự
sinh bằng mã** vì ba lý do:

1. **Bản quyền.** Hiệu ứng tải về đều có giấy phép ràng buộc; đồ án nộp trường
   dùng tới thì phải giải trình nguồn. Tự sinh thì nhóm sở hữu hoàn toàn.
2. **Khớp bảng màu.** Màu lấy thẳng từ `desktop_app.py`. Hiệu ứng lấy sẵn thường
   lệch tông, nhìn như dán vào.
3. **Nằm trong kho mã.** Đổi màu hay kích thước chỉ là sửa tham số rồi chạy lại,
   không phải đi tìm tệp khác.

`tools/sinh_hieu_ung.py` sinh **5 bộ · 86 khung PNG có alpha · 2,8 MB**: tia lửa,
vòng năng lượng, lửa, khói, tia sét. Kỹ thuật dùng: nhiễu nhiều tầng cuộn theo
thời gian cho lửa, dịch điểm giữa đệ quy cho tia sét, hệ hạt Gauss cho tia lửa.

### Hai lỗi chỉ thấy khi dựng ảnh ra xem

* **Ngọn lửa lộn ngược** — phình ở trên, chúc xuống dưới. Trục `y` chạy từ −1
  (đỉnh ảnh) tới +1 (đáy ảnh), nhưng tôi viết công thức như thể `y` tăng lên
  trên. Đúng loại lỗi mà đọc mã mười lần cũng không thấy.
* **Khói mờ tới mức gần như vô hình** trên nền tối của ứng dụng.

Sau khi trộn thử lên khung hình còn phát hiện lỗi thứ ba: **lửa lộ cạnh hộp
vuông** ở mép, vì nó lan gần hết chiều ngang ảnh. Thêm lớp làm mờ dần ở rìa.

### Hai cách trộn, và vì sao cần cả hai

| Kiểu | Dùng cho | Lý do |
|---|---|---|
| **alpha** | khói, vòng năng lượng | Rìa sạch, giữ đúng màu gốc |
| **cộng sáng** | lửa, tia sét, tia lửa | Vùng tối tự biến mất, vùng sáng loé lên — đúng cách ánh sáng thật hoạt động |

Trộn lửa bằng alpha sẽ ra một miếng dán phẳng; trộn khói bằng cộng sáng thì mất
hết khối.

### Thiết kế "thả tệp vào là dùng được"

`src/effects.py` quét thư mục `effects/`, mỗi thư mục con là một hiệu ứng chứa
dãy `frame_000.png`… Thêm hiệu ứng mới **không phải sửa một dòng mã nào**, nên
hiệu ứng tự sinh và hiệu ứng lấy từ nơi khác dùng chung một đường.

Ba chi tiết quyết định việc nó không làm tụt tốc độ khung hình:

* **Thu nhỏ lúc nạp, không phải mỗi khung.** Trộn ảnh 256 px lên video 30 fps là
  việc làm mỗi 33 ms; thu nhỏ là việc làm đúng một lần.
* **Chặn trần 12 hiệu ứng cùng lúc.** Không chặn thì vẫy tay liên tục sinh ra
  hàng trăm thể hiện.
* **Chỉ bắn khi cử chỉ ĐỔI**, không bắn mỗi khung. Giữ nguyên bàn tay xoè hai
  giây là sáu mươi khung — bắn mỗi khung sẽ chồng sáu mươi hiệu ứng lên nhau.

### Hỏng nhẹ nhàng

Toàn bộ phần nạp hiệu ứng nằm trong `try/except`, và bảng gán bỏ qua tên không
tồn tại. Xoá thư mục `effects/` thì tính năng vẽ vẫn chạy bình thường, chỉ là
không có hiệu ứng. Một phần phụ hỏng không được phép kéo theo phần chính.

### Giao diện

Ba ô chọn trên thanh công cụ tab Cử chỉ tay: **Xoè tay · Chụm ngón · Nắm tay**,
mỗi ô chọn một hiệu ứng hoặc "(không)". Đổi có hiệu lực **ngay lập tức**, không
phải dừng camera rồi bật lại.
