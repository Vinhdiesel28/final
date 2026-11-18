# Nâng cấp Hybrid KB của DiaGuard

## Luồng hiện tại

Thêm URL bằng python tools/kb/add_web_to_kb.py. Nội dung PDF/web được chia thành Chunk, mã hóa E5, lưu trên Qdrant và Neo4j. Cạnh MENTIONS nối các đoạn với tên hoặc bí danh của thực thể. Bộ dựng mới tạo danh sách facts rỗng. Luồng hỏi đáp lấy bằng chứng từ văn bản gốc.

## Thử embedding đa ngôn ngữ và đo kết quả

```powershell
python -m pip install -r requirements-semantic.txt
$env:HF_HOME = 'D:\DiaGuardModelCache'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
python tools/kb/build_hybrid_kb.py --semantic --output-dir tmp/kb-candidate-e5
python tools/kb/stage_kb_snapshot.py tmp/kb-candidate-e5/kb_bundle.json
python tools/benchmarks/benchmark_kb_retrieval.py --version <version-in-ra-tu-stage> --output results/kb_retrieval_e5.json
```

E5 dùng 768 chiều, khóa revision và dùng cùng một encoder với tiền tố `passage:` khi lập chỉ mục và `query:` khi hỏi. Qdrant tạo collection riêng theo phiên bản. Neo4j giữ vector LSA 128 chiều để tương thích schema hiện có. Staging tạo snapshot riêng và giữ con trỏ `current`. Chạy benchmark không truyền `--version` để đo snapshot đang phục vụ app. Bộ đo gồm 8 câu có qrels và 8 cách diễn đạt lại, báo cáo Hit@5 và MRR@5. Đây là benchmark tầng retrieval.

Sau khi chọn bản đã benchmark, chỉ định lại `--ingest` lúc dựng để đưa phiên bản mới lên `current`. Với E5, môi trường app cần `HYBRID_VECTOR_BACKEND=qdrant`, dependencies trong `requirements-semantic.txt` và đường cache trỏ đến model đã tải, sau đó khởi động lại app. File Cypher seed của bản E5 chỉ tạo snapshot, vì vector E5 cần được nạp bằng pipeline Qdrant.

Để mở app demo trên snapshot đã stage, cấu hình `HYBRID_KB_SNAPSHOT` bằng hash đầy đủ của snapshot và khởi động app. Có thể đặt trong PowerShell cho riêng phiên demo hoặc trong `.env` cho máy cá nhân. Bỏ biến này để quay lại snapshot `current`. Đổi biến chỉ ảnh hưởng app đọc cấu hình đó.

## Kết quả thử nghiệm

Bộ đo truyền câu hỏi tiếng Việt trực tiếp vào tầng retrieval, gồm 8 câu gốc và 8 cách diễn đạt lại. Số liệu khác phép đo v3 dùng truy vấn đã viết lại. Mỗi câu được chạy một lượt, nên latency chỉ mô tả lần chạy này.

| Cấu hình hybrid cloud | Hit@5 | MRR@5 | Latency trung vị |
|---|---:|---:|---:|
| KB cũ, LSA, mọi loại nguồn | 2/16 (12,5%) | 0,047 | 434 ms |
| KG đã duyệt, LSA, chỉ PDF/web | 6/16 (37,5%) | 0,208 | 628 ms |
| KG đã duyệt, E5, chỉ PDF/web | 7/16 (43,75%) | 0,297 | 901 ms |

Thử nghiệm E5 với mọi loại nguồn đạt 0/16 theo qrels của bộ đo. Các bản tóm tắt tiếng Việt thường chiếm các vị trí đầu, trong khi qrels trỏ về đoạn nguồn gốc. Với cùng bộ lọc PDF/web, phép đo vector độc lập đạt 4/16 cho LSA và 6/16 cho E5. Cả ba nhánh truy xuất ở snapshot đã nâng cấp đều dùng PDF/web làm ứng viên bằng chứng. Các bản tóm tắt vẫn có trong bundle để đối chiếu.

Các snapshot benchmark cũ giữ cấu trúc tại thời điểm đo.
