# DiaAgents Lab — Final Project

Hệ Single Agent và Multi-Agent hỗ trợ đánh giá nguy cơ, thống kê và hỏi đáp có nguồn về bệnh tiểu đường.

**Sinh viên:** Nguyễn Minh Vinh — B23DCCN934 — D23CTPM01 — Nhóm 08  
**Repository:** https://github.com/Vinhdiesel28/final

## Phiên bản hiện tại

- Dataset dự đoán: 100.000 bản ghi.
- Dataset thống kê: CDC BRFSS 2015, 253.680 bản ghi.
- Ba model sklearn: Logistic Regression, Random Forest, MLP; thêm mạng PyTorch 15–64–32–1 đã huấn luyện.
- Demo dùng PyTorch và đối chiếu checkpoint sklearn; PyTorch không được coi là model thắng validation.
- Neo4j Community lưu KB và Knowledge Graph; MessageBus thực thi handler, Critic kiểm tra bất đồng và Q-learning chọn bước quy trình.
- Model chọn bằng validation F1; test F1 đọc từ artifact.
- 8 tài liệu WHO/CDC/NIDDK/model card và 16 cạnh Knowledge Graph.
- So sánh đúng hai hệ: Single Agent và Multi-Agent.
- 58 tình huống benchmark tái lập (116 lượt chạy) trên cùng model, dataset, knowledge base và policy.
- Benchmark Lab trên web: task success, citation, safety, latency và specialist audit coverage.
- Dashboard responsive, hiển thị citation và trace từng Agent.

## Chạy lại

```powershell
cd C:\DATA\assignment3\final
C:\DATA\assignment3\.venv\Scripts\activate
pip install -r requirements.txt
python tools\train_models.py
python tools\train_torch_model.py
python tools\train_workflow_policy.py
python tools\start_neo4j.py
python tools\ingest_neo4j.py
python tools\run_agent_benchmark.py
python tools\build_enhanced_notebook.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Mở `http://127.0.0.1:8010`.

Không cần train lại để demo: checkpoint đã có sẵn. Docker Desktop phải chạy trước `start_neo4j.py`; đợi Neo4j sẵn sàng rồi ingest. Mật khẩu tự sinh nằm trong `.local_config.json` đã gitignore. Neo4j Browser: http://127.0.0.1:7474, truy vấn `MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 100`.

Notebook mới: `notebooks/08_project_ml_neo4j_multiagent.ipynb` có code, giải thích và output thực. Ảnh code trong báo cáo chụp từ bản HTML của notebook này, giữ nguyên khoảng trắng.

Notebook `09_pytorch_training_full.ipynb` chứa toàn bộ code train PyTorch và output đã chạy. Cài `requirements-notebooks.txt` để chạy Jupyter; dùng `tools/build_training_notebook.py` để tái tạo notebook train. So sánh mẫu Kiên: giữ dataset của project, chưa triển khai Qdrant, hội đồng LLM hoặc RL điều trị; không ghi các tính năng đó là đã có.

Render cần Neo4j remote: đặt `KNOWLEDGE_BACKEND=neo4j`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`; chạy `tools/ingest_neo4j.py` với cùng environment. Không commit mật khẩu. Nếu chủ động chọn bản gọn, đặt `KNOWLEDGE_BACKEND=json`; giao diện sẽ ghi JSON, không tự nhận là Neo4j. PyTorch và pandas có thể cần RAM cao hơn gói free; cần đo trên instance thực.

Q-learning học trên mô phỏng quy trình tổng hợp, không học chính sách điều trị. MessageBus đồng bộ trong một tiến trình; phản biện theo luật, chưa là hội đồng LLM. CDC thống kê nhãn `Diabetes_012 > 0`, gộp tiền tiểu đường và tiểu đường, không phải prevalence dân số. RAG hiện là BM25 kết hợp evidence đồ thị và trích câu; chưa dùng Qdrant hoặc LLM.

## Cấu trúc

- `app/`: FastAPI và giao diện demo.
- `src/`: model, knowledge service và Agent.
- `data/`: hai CSV công khai.
- `knowledge/`: corpus và graph có evidence.
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
