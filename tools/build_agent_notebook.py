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
      nbf.v4.new_markdown_cell("## Cell 6 – Benchmark có kiểm soát\nSingle và Multi dùng cùng 28 tình huống, model và công cụ. Bản đầu chủ yếu kiểm tra route, contract, citation và safety; bộ khó hơn sẽ được bổ sung trước báo cáo cuối."),
      nbf.v4.new_code_cell("summary=json.loads((ROOT/'results/agent_benchmark_summary.json').read_text(encoding='utf-8'))\npd.DataFrame(summary).round(4)"),
      nbf.v4.new_markdown_cell("## Kết luận\nSingle Agent ngắn gọn hơn; Multi-Agent tạo trace chi tiết để khoanh vùng lỗi và kiểm soát nguồn. Không mặc định Multi-Agent chính xác hơn nếu chưa có benchmark khó hơn.")]
    ns={"__name__":"__main__"}
    count=0
    for cell in nb.cells:
        if cell.cell_type!='code': continue
        count+=1; cell.execution_count=count; buf=io.StringIO()
        try:
            with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):
                value=eval(compile(cell.source,f'cell-{count}','eval'),ns) if '\n' not in cell.source else exec(compile(cell.source,f'cell-{count}','exec'),ns)
            out=[]
            if buf.getvalue(): out.append(nbf.v4.new_output('stream',name='stdout',text=buf.getvalue()))
            cell.outputs=out
        except Exception as exc:
            cell.outputs=[nbf.v4.new_output('error',ename=type(exc).__name__,evalue=str(exc),traceback=[repr(exc)])]; raise
    path=ROOT/'notebooks/07_single_vs_multi_agent.ipynb'; nbf.write(nb,path); print(path)


if __name__=='__main__': main()
