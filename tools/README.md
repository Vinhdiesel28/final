# Công cụ của project

Chạy các lệnh từ `C:\DATA\assignment3\final`.

| Thư mục | Chức năng |
| --- | --- |
| `kb/` | Thêm web, dựng KB, nạp Neo4j/Qdrant, chuyển cloud và chọn snapshot |
| `benchmarks/` | Đánh giá Agent, dự đoán, truy xuất và so sánh kết quả; baseline cũ nằm trong `baseline_pre_policy/` |
| `training/` | Huấn luyện ML, PyTorch và thí nghiệm graph; `train_workflow_policy.py` phục vụ thí nghiệm RL cũ |
| `notebooks/` | Tạo notebook và chụp notebook |
| `reports/` | Tạo báo cáo, xuất PDF, chụp demo và kiểm tra bố cục báo cáo |
| `checks/` | Kiểm tra giao diện, trích dẫn, quota và kết nối KB |

## Lệnh thường dùng

```powershell
python tools/kb/add_web_to_kb.py
python tools/kb/build_hybrid_kb.py --help
python tools/training/train_models.py
python tools/training/train_torch_model.py
python tools/benchmarks/benchmark_conversation_v3.py --help
python tools/notebooks/build_training_notebook.py
```

Hai lệnh train và lệnh tạo notebook huấn luyện sẽ chạy huấn luyện khi thực thi. Các script kiểm tra live/cloud có thể gọi dịch vụ bên ngoài; chỉ chạy khi cần. Các snapshot, checkpoint và kết quả đã lưu nằm ở các thư mục dữ liệu riêng của project.

Cập nhật riêng mục 7.1 của notebook DL, giữ output train và checkpoint hiện tại:

```powershell
python tools/notebooks/build_training_notebook.py --integration-only --in-process
```
