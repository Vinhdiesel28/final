Hợp đồng giao tiếp 7 Agent: [AGENT_CONTRACTS.md](docs/AGENT_CONTRACTS.md). Kết quả API có `audit_record`; message schema `2.0`.

## Cấu trúc mã nguồn hiện tại

Mở src/agents để xem đúng bảy tác tử của DiaGuard. src/conversational_agents.py điều phối hai chế độ và các thao tác phản biện của ExplanationAgent.

| Thư mục | Nội dung |
|---|---|
| src/agents | Coordinator, Data, DL, Rule, Knowledge, Explanation, Monitoring |
| src/services | Gọi Groq, mô hình, encoder, Neo4j, Qdrant và truy xuất |
| src/contracts | MessageBus, schema hội thoại và kiểm tra bằng chứng |
| src/knowledge | Thuật ngữ truy xuất và công cụ xử lý quan hệ có nguồn |
| src/legacy | Luồng đa tác tử cũ và RL cho thực nghiệm lịch sử |
| tools | Lệnh train, nạp nguồn, benchmark và tạo tài liệu |
| notebooks | Notebook thực nghiệm với đường import cập nhật |

Lệnh thường dùng từ thư mục final

~~~powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
python tools/kb/add_web_to_kb.py
~~~

Chi tiết các tệp còn phụ thuộc và kết quả rà soát nằm trong docs/SOURCE_LAYOUT.md. Các mục thí nghiệm bên dưới ghi lại quá trình phát triển qua các phiên bản.

# DiaAgents Lab — Final Project

Hệ Single Agent và Multi-Agent hỗ trợ đánh giá nguy cơ, thống kê và hỏi đáp có nguồn về bệnh tiểu đường.

**Sinh viên:** Nguyễn Minh Vinh — B23DCCN934 — D23CTPM01 — Nhóm 08  
**Repository:** https://github.com/Vinhdiesel28/final

## Phiên bản hiện tại

### Hai chế độ và benchmark v3

Giao diện tách **Đánh giá hồ sơ** (`task=assessment`: validation → DL →
rules → evidence → explanation) và **Hỏi kiến thức** (`task=knowledge`:
hiểu câu hỏi → retrieval → explanation → phản biện). Chế độ kiến thức
không gửi profile và không được chạy PredictionAgent.

Trang benchmark chỉ dùng `/api/benchmark/v3`, thay toàn bộ bảng cũ. Bộ đo
mới gồm model trên 14.998 mẫu test, retrieval theo 8 qrels × 3 lượt và
10 tình huống end-to-end × 3 lượt qua MultiAgent hiện tại. Xem số liệu,
điều kiện chấm, lỗi và latency trong `results/benchmark_v3.json`; phương
pháp và giới hạn tại `docs/BENCHMARK_V3.md`. Không dùng số liệu cũ để điền
vào bộ đo mới. Các thống kê benchmark 58 ca bên dưới là lịch sử.

```powershell
python tools/benchmarks/benchmark_conversation_v3.py --phase components --repeats 3
python tools/benchmarks/benchmark_conversation_v3.py --phase live --repeats 3 --resume
```

### Conversation RAG v3 (09/11/2026)

Multi-Agent mặc định dùng Coordinator phân tích câu hỏi và lịch sử, chọn công
cụ, truy xuất nguồn thật, soạn đáp án bằng LLM, rồi Critic chấp nhận hoặc yêu
cầu viết lại/truy xuất lại/hỏi thêm. Challenge thay đổi dữ liệu hoặc bản nháp
thực tế; Verifier kiểm tra kết quả cuối. Xem `docs/CONVERSATION_V3.md`.
Hỏi tiếp trong giao diện giữ ngữ cảnh và chỉ chạy Multi-Agent. Các benchmark
cũ được giữ để tái lập, chưa phải số liệu đánh giá v3.

### Hybrid KB v2 (09/11/2026)

Neo4j hiện có KB hợp nhất gồm 49 Document (3 PDF, 2 web, 44 bản tóm tắt),
515 Chunk, 153 Entity và 158 Fact nhập từ graph cũ. Fact chưa được xác minh
độc lập có trạng thái imported_unreviewed. Vector LSA 128 chiều, fulltext và
graph retrieval cùng chạy trong Neo4j khi KBVersion hiện hành đã được nạp.
Số 862 vector Qdrant bên dưới mô tả phiên bản trước/fallback.

- Tạo/nạp: `python tools/kb/build_hybrid_kb.py --fetch-web --ingest`.
- Schema/demo: `knowledge/DB_diabet.cypher`.
- Seed đầy đủ dữ liệu và vector: `knowledge/hybrid/DB_diabet_seed.cypher`.
- Nguồn: `knowledge/hybrid/source_registry.json`.
- LLM: cấu hình `.env` theo `.env.example` (Ollama hoặc compatible API).
- Xem giới hạn và hướng dẫn tại `docs/HYBRID_KB_V2.md`.

LLM chỉ diễn đạt phần evidence với citation ID và quote kiểm chứng được. Khi
chưa cấu hình provider, app hiện template và không tự nhận đang dùng LLM.
Các benchmark cũ chưa đo phiên bản Hybrid KB/LLM này.

- Dataset dự đoán: 100.000 bản ghi.
- Dataset thống kê: CDC BRFSS 2015, 253.680 bản ghi.
- Ba model sklearn: Logistic Regression, Random Forest, MLP; thêm mạng PyTorch 15–64–32–1 đã huấn luyện.
- Demo dùng PyTorch và đối chiếu checkpoint sklearn; PyTorch không được coi là model thắng validation.
- Neo4j Community lưu KB và Knowledge Graph; MessageBus thực thi handler, Critic kiểm tra bất đồng và Q-learning chọn bước quy trình.
- Model chọn bằng validation F1; test F1 đọc từ artifact.
- 44 tài liệu y khoa đã tuyển chọn, 158 cạnh Knowledge Graph và 862 vector trong Qdrant.
- Pipeline tự động trích 3 PDF nguồn thành 818 chunk theo trang; embedding LSA 128 chiều và hybrid retrieval BM25 + Qdrant.
- So sánh đúng hai hệ: Single Agent và Multi-Agent.
- 58 tình huống benchmark tái lập (116 lượt chạy) trên cùng model, dataset, knowledge base và policy.
- Benchmark Lab trên web: task success, citation, safety, latency và specialist audit coverage.
- Dashboard responsive, hiển thị citation và trace từng Agent.

## Chạy lại

```powershell
cd C:\DATA\assignment3\final
C:\DATA\assignment3\.venv\Scripts\activate
pip install -r requirements.txt
python tools\training\train_models.py
python tools\training\train_torch_model.py
python tools\training\train_workflow_policy.py
python tools\kb\start_neo4j.py
python tools\kb\ingest_neo4j.py
python tools\kb\build_vector_store.py
python tools\benchmarks\run_agent_benchmark.py
python tools\notebooks\build_enhanced_notebook.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Mở `http://127.0.0.1:8010`.

Không cần train lại để demo: checkpoint đã có sẵn. Docker Desktop phải chạy trước `start_neo4j.py`; đợi Neo4j sẵn sàng rồi ingest. Mật khẩu tự sinh nằm trong `.local_config.json` đã gitignore. Neo4j Browser: http://127.0.0.1:7474, truy vấn `MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 100`.

Notebook mới: `notebooks/08_project_ml_neo4j_multiagent.ipynb` có code, giải thích và output thực. Ảnh code trong báo cáo chụp từ bản HTML của notebook này, giữ nguyên khoảng trắng.

Notebook `09_pytorch_training_full.ipynb` chứa toàn bộ code train PyTorch và output đã chạy. Cài `requirements-notebooks.txt` để chạy Jupyter; dùng `tools/notebooks/build_training_notebook.py` để tái tạo notebook train. So sánh mẫu Kiên: giữ dataset của project; đã triển khai Qdrant local, nhưng chưa triển khai hội đồng LLM hoặc RL điều trị.

Render cần Neo4j remote: đặt `KNOWLEDGE_BACKEND=neo4j`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`; chạy `tools/kb/ingest_neo4j.py` với cùng environment. Không commit mật khẩu. Nếu chủ động chọn bản gọn, đặt `KNOWLEDGE_BACKEND=json`; giao diện sẽ ghi JSON, không tự nhận là Neo4j. PyTorch và pandas có thể cần RAM cao hơn gói free; cần đo trên instance thực.

Q-learning học trên mô phỏng quy trình tổng hợp, không học chính sách điều trị. MessageBus đồng bộ trong một tiến trình; phản biện theo luật, chưa là hội đồng LLM. CDC thống kê nhãn `Diabetes_012 > 0`, gộp tiền tiểu đường và tiểu đường, không phải prevalence dân số. RAG dùng hybrid BM25 + Qdrant local, embedding TF-IDF word/character + TruncatedSVD (LSA) 128 chiều, evidence đồ thị và trích câu có kiểm chứng; chưa dùng LLM sinh tự do. Hai PDF CDC chặn tải tự động và được ghi rõ là nguồn còn thiếu trong manifest.

## Cấu trúc

- `app/`: FastAPI và giao diện demo.
- `src/`: model, knowledge service và Agent.
- `data/`: hai CSV công khai.
- `knowledge/`: corpus, graph, PDF nguồn, vector artifacts và Qdrant persistent.
- `artifacts/`: checkpoint và model card.
- `results/`: metric và benchmark.
- `report/`: Tiểu luận Final 7 chương và báo cáo Project 01 ở định dạng DOCX/PDF.

## Hồ sơ nộp bài

Quyển Final đã được viết tiếp từ tiểu luận 3 theo bố cục bảy chương của bài Kiên. Chương 1–5 giữ dataset và kết quả cũ; Chương 6 bổ sung MLP/GCN/GraphSAGE trên 1.600 mẫu CDC của sinh viên; Chương 7 dùng Agent hiện tại, PyTorch và Neo4j. Xem `docs/FINAL_CONTINUATION.md`. Notebook graph mới: `notebooks/10_deep_graph_cdc.ipynb`.

- `report/tieuluan_final_CT_08_934_NguyenMinhVinh.pdf`: quyển tổng hợp ML, CNN, RNN, Knowledge Graph, học sâu trên đồ thị và hệ đa tác tử.
- `report/project01_CT_08_934_NguyenMinhVinh.pdf`: báo cáo riêng của hệ DiaAgents, gồm kiến trúc, dữ liệu, code, notebook, benchmark và demo.
- `notebooks/`: notebook đã chạy.
- `report/`: báo cáo Final và Project 01 (sẽ hoàn thiện ở pha báo cáo).

## Giới hạn an toàn

Risk score không phải chẩn đoán. Hệ thống không kê đơn, không chọn điều trị và không thay thế nhân viên y tế.
