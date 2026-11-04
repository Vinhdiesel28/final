# DiaAgents Lab — Final Project

Hệ Single Agent và Multi-Agent hỗ trợ đánh giá nguy cơ, thống kê và hỏi đáp có nguồn về bệnh tiểu đường.

**Sinh viên:** Nguyễn Minh Vinh — B23DCCN934 — D23CTPM01 — Nhóm 08  
**Repository:** https://github.com/Vinhdiesel28/final

## Phiên bản hiện tại

- Dataset dự đoán: 100.000 bản ghi.
- Dataset thống kê: CDC BRFSS 2015, 253.680 bản ghi.
- Ba model: Logistic Regression, Random Forest, MLP.
- Model chọn bằng validation F1; test F1 đọc từ artifact.
- 8 tài liệu WHO/CDC/NIDDK/model card và 16 cạnh Knowledge Graph.
- So sánh đúng hai hệ: Single Agent và Multi-Agent.
- 28 tình huống benchmark ban đầu.
- Dashboard responsive, hiển thị citation và trace từng Agent.

## Chạy lại

```powershell
cd C:\DATA\assignment3\final
C:\DATA\assignment3\.venv\Scripts\activate
pip install -r requirements.txt
python tools\train_models.py
python tools\run_agent_benchmark.py
python tools\build_agent_notebook.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Mở `http://127.0.0.1:8010`.

## Cấu trúc

- `app/`: FastAPI và giao diện demo.
- `src/`: model, knowledge service và Agent.
- `data/`: hai CSV công khai.
- `knowledge/`: corpus và graph có evidence.
- `artifacts/`: checkpoint và model card.
- `results/`: metric và benchmark.
- `notebooks/`: notebook đã chạy.
- `report/`: báo cáo Final và Project 01 (sẽ hoàn thiện ở pha báo cáo).

## Giới hạn an toàn

Risk score không phải chẩn đoán. Hệ thống không kê đơn, không chọn điều trị và không thay thế nhân viên y tế.
