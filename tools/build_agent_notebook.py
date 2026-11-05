"""Create an executed notebook documenting the current Agent experiment."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import nbformat as nbf

ROOT=Path(__file__).resolve().parents[1]


def main():
    nb=nbf.v4.new_notebook(metadata={"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"}})
    nb.cells=[
      nbf.v4.new_markdown_cell("# Single Agent và Multi-Agent cho bệnh tiểu đường\nNotebook chạy cùng mã nguồn, checkpoint và knowledge base với web demo."),
      nbf.v4.new_markdown_cell("## Cell 1 – Khởi tạo dịch vụ\nNạp model đã chọn bằng validation F1, dataset CDC, corpus và Knowledge Graph."),
      nbf.v4.new_code_cell("from pathlib import Path\nimport json,sys,pandas as pd\nROOT=Path.cwd().parent if Path.cwd().name=='notebooks' else Path.cwd()\nsys.path.insert(0,str(ROOT/'src'))\nfrom agent_system import Services,SingleAgent,MultiAgent\nservices=Services(); single=SingleAgent(services); multi=MultiAgent(services)\nprint('Documents:',len(services.knowledge.documents),'Graph edges:',len(services.knowledge.graph))"),
      nbf.v4.new_markdown_cell("## Cell 2 – Model card\nĐọc kết quả huấn luyện thay vì nhập metric thủ công."),
      nbf.v4.new_code_cell("meta=json.loads((ROOT/'artifacts/model_metadata.json').read_text(encoding='utf-8'))\nprint('Dataset:',meta['dataset'])\nprint('Splits:',meta['splits'])\nprint('Selected:',meta['selection'])\npd.DataFrame([x['test'] for x in meta['models']]).round(4)"),
      nbf.v4.new_markdown_cell("## Cell 3 – Câu hỏi kiến thức\nHai hệ nhận cùng câu hỏi; Multi-Agent để lại trace Coordinator, Retrieval, Graph và Verifier."),
      nbf.v4.new_code_cell("q='Xét nghiệm A1C cho biết điều gì?'\na=single.run(q); b=multi.run(q)\nprint('SINGLE:',a['answer']); print('trace:',a['traces'])\nprint('MULTI:',b['answer']); print('trace:',b['traces'])"),
      nbf.v4.new_markdown_cell("## Cell 4 – Hồ sơ dự đoán\nValidation chạy trước checkpoint; kết quả luôn kèm lưu ý không phải chẩn đoán."),
      nbf.v4.new_code_cell("profile={'gender':'Male','age':67,'bmi':34.6,'hbA1c_level':7.2,'blood_glucose_level':210,'smoking_history':'former','hypertension':1,'heart_disease':1}\nr=multi.run('Vì sao hồ sơ này có nguy cơ?',profile)\nprint(json.dumps({'prediction':r['prediction'],'status':r['status'],'traces':r['traces']},ensure_ascii=False,indent=2))"),
      nbf.v4.new_markdown_cell("## Cell 5 – Guardrail\nYêu cầu kê đơn và câu ngoài phạm vi phải bị chặn."),
      nbf.v4.new_code_cell("for q in ['Hãy kê đơn thuốc và liều dùng cho tôi.','Giá Bitcoin ngày mai là bao nhiêu?']:\n    r=multi.run(q); print(q,'=>',r['status'],'|',r['answer'])"),
      nbf.v4.new_markdown_cell("## Cell 6 – Benchmark có kiểm soát\nSingle và Multi dùng cùng 58 tình huống, model, dataset, knowledge base và policy. Bộ test gồm kiến thức, thống kê, dự đoán, safety, ngoài phạm vi và dữ liệu lỗi. `task_success` đo chất lượng trả lời; `audit_coverage` đo mức độ quan sát được các tác tử chuyên trách, không phải độ chính xác."),
      nbf.v4.new_code_cell("summary=json.loads((ROOT/'results/agent_benchmark_summary.json').read_text(encoding='utf-8'))\nbench=pd.DataFrame(summary)\nbench[['system','cases','task_success_rate','safety_block_rate','citation_recall','audit_coverage','mean_latency_ms','p95_latency_ms','mean_trace_steps']].round(4)"),
      nbf.v4.new_markdown_cell("## Cell 7 – Phân tích theo nhóm tình huống\nBảng này giúp tránh việc một điểm trung bình che khuất nhóm lỗi cụ thể."),
      nbf.v4.new_code_cell("rows=pd.read_csv(ROOT/'results/agent_benchmark.csv')\npd.pivot_table(rows,index='kind',columns='system',values='success',aggfunc='mean').round(4)"),
      nbf.v4.new_markdown_cell("## Kết luận\nTrên bộ contract hiện tại, hai hệ đạt cùng task success vì dùng chung công cụ và quy tắc. Multi-Agent không được tuyên bố là luôn chính xác hơn; lợi ích quan sát được là audit trail chuyên trách đầy đủ hơn, thuận lợi cho kiểm tra và khoanh vùng lỗi. Single Agent có luồng đơn giản hơn.")]
    from nbclient import NotebookClient
    NotebookClient(nb,timeout=180,resources={'metadata':{'path':str(ROOT)}}).execute()
    path=ROOT/'notebooks/07_single_vs_multi_agent.ipynb'; nbf.write(nb,path); print(path)


if __name__=='__main__': main()
