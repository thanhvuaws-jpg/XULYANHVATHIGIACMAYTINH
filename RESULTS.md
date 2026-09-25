# Kết quả chạy thử pipeline (2026-09-09)

Chạy end-to-end trên máy này để kiểm chứng toàn bộ code. **CPU** (chưa dùng GPU), dữ liệu = **LFW subset**.

## Dữ liệu
- Nguồn: `scikit-learn fetch_lfw_people` (không cần Kaggle token) — `src/fetch_lfw.py`
- 42 người × ~22 ảnh = 924 ảnh → sau MTCNN detect + align 160×160: **914 khuôn mặt** trong `data/aligned/`
- Chia đánh giá: 70% gallery / 30% query (seed 42) → 292 ảnh query

## Mô hình đã train (`src/train_cnn.py`, ResNet50, backbone đóng băng, CPU)
| Model | Loss | Epochs | val_acc (head) | File |
|---|---|---|---|---|
| ResNet50 | CrossEntropy | 15 | 0.29 | `models/backbone_ce.pt` |
| ResNet50 | ArcFace | 12 | 0.37 | `models/backbone_arcface.pt` |

## Đánh giá nhận diện (cosine matching, `src/evaluate.py`)
| Backbone | Accuracy (1:N) | AUC | EER | Ngưỡng đề xuất |
|---|---|---|---|---|
| **FaceNet (pretrained vggface2)** | **1.000** | **0.9998** | **0.34%** | 0.571 |
| ResNet50 + ArcFace (tự train) | 0.521 | 0.862 | 22.9% | 0.342 |
| ResNet50 + CrossEntropy (tự train) | 0.469 | 0.916 | 16.5% | 0.282 |

Biểu đồ: `reports/<tag>_confusion_matrix.png`, `_roc.png`, `_far_frr.png`, `_classification_report.txt`.

## Demo nhận diện ảnh
`demo_input.jpg` (ghép 4 người) → `demo_output.jpg`: **4/4 đúng**, cosine 0.85–0.95.
```
Serena_Williams    0.912
Vladimir_Putin     0.851
Junichiro_Koizumi  0.941
Tony_Blair         0.951
```

## Đọc kết quả này thế nào

- **Pipeline hoạt động đầy đủ**: detect → align → train CNN → embedding → matching → đánh giá → demo.
- **FaceNet baseline ~100%** vì nó đã được huấn luyện sẵn trên 3.3M ảnh khuôn mặt.
- **CNN tự train mới đạt 47–52%** vì đang bị giới hạn nặng: chạy CPU, backbone **đóng băng**, chỉ 12–15 epoch, tập LFW 42 người (~15 ảnh/người để train). Đây là mức kỳ vọng của cấu hình rút gọn — **không phải giới hạn của phương pháp**.

## Để CNN tự train đạt >95% (làm trên máy GPU của nhóm)
1. Dữ liệu lớn hơn: `src/download_kaggle.py --dataset pins` (105 người, 17k ảnh) hoặc VGGFace2.
2. **Bỏ `--freeze-backbone`** để fine-tune toàn mạng.
3. Tăng epoch: 40–80, thêm `--augment 2` khi preprocess.
4. Train trên GPU: `python -m src.train_cnn --data-dir data/aligned --loss arcface --epochs 60 --batch-size 64`
5. Chạy lại `src.evaluate` để lấy ngưỡng tối ưu, cập nhật `src/config.py`.
