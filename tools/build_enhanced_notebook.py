"""Execute notebook in a real IPython kernel; retain rich outputs for report screenshots."""
import json, os, sys
from pathlib import Path
import nbformat as nb
from nbclient import NotebookClient
ROOT=Path(__file__).resolve().parents[1]
cells=[]
def section(title, explanation, source):
    cells.extend([nb.v4.new_markdown_cell('## '+title+'\n'+explanation),nb.v4.new_code_cell(source)])
cells.append(nb.v4.new_markdown_cell('# Project 01 — ML, PyTorch, Neo4j và Multi-Agent\nNotebook dùng cùng mã nguồn với web. Output được thực thi bằng kernel Python. Dữ liệu, checkpoint và phạm vi của Q-learning được phân biệt rõ.'))
section('1. Nạp dịch vụ','Các import dùng mã nguồn thực tế, không sao chép một phiên bản riêng. Backend in ra phải là neo4j khi demo đầy đủ.',"""from pathlib import Path
import sys, json, inspect
import pandas as pd
from IPython.display import display
ROOT=Path.cwd().parent if Path.cwd().name=='notebooks' else Path.cwd()
sys.path.insert(0,str(ROOT/'src'))
from agent_system import Services, SingleAgent, MultiAgent
services=Services()
single, multi=SingleAgent(services), MultiAgent(services)
print('Model:',services.model.model_name)
print('KB backend:',services.knowledge.backend)""")
section('2. Hai dataset','Dataset dự đoán dùng nhãn diabetes; CDC dùng thống kê mô tả. Không gộp hai tập hoặc xem CDC là external validation cho model có schema khác.',"""for name in ['diabetes_prediction_dataset.csv','cdc_brfss_2015.csv']:
    df=pd.read_csv(ROOT/'data'/name)
    print(name, df.shape)
    label='diabetes' if 'diabetes' in df else 'Diabetes_012'
    print(df[label].value_counts().sort_index().to_dict())
    display(df.head(2))""")
section('3. Định nghĩa mạng PyTorch','Linear → ReLU → Dropout → Linear → ReLU → Linear tạo logit. BCEWithLogitsLoss nhận logit; sigmoid chỉ dùng khi suy luận.',"""from torch_model import RiskMLP
print(inspect.getsource(RiskMLP))
print(services.model.pipeline.model)""")
section('4. Huấn luyện và chọn checkpoint','Hàm train thực hiện forward, loss, backward, optimizer.step; chỉ train được dùng fit preprocessing. Có thể chạy lại hàm main, nhưng cell này đọc lịch sử đã thực sự huấn luyện để không lặp lại 60 epoch mỗi lần demo.',"""history=pd.read_csv(ROOT/'results/pytorch_training_history.csv')
meta=json.loads((ROOT/'artifacts/pytorch_metadata.json').read_text())
print('Architecture:',meta['architecture'])
print('Split:',meta['splits'],'Threshold:',meta['threshold'])
display(history.iloc[[0,-1]])
display(pd.DataFrame([meta['validation'],meta['test']],
                     index=['validation','test'])[['f1','roc_auc','precision','recall']])""")
section('5. Đối chiếu ML và deep learning','Đọc metric từ các artifact. PyTorch không mặc nhiên tốt hơn MLP sklearn. Cùng split nội bộ, chưa kiểm định ở bệnh viện khác.',"""old=json.loads((ROOT/'artifacts/model_metadata.json').read_text())
rows=[r['test'] for r in old['models']]+[meta['test']]
display(pd.DataFrame(rows)[['model','f1','roc_auc','precision','recall']])""")
section('6. KB và Knowledge Graph trong Neo4j','Cypher chạy vào database thật. DiaDocument lưu văn bản và URL; DiaEntity lưu thực thể; DIA_RELATION lưu quan hệ và evidence trỏ về tài liệu.',"""store=services.knowledge.store
if store is None:
    raise RuntimeError('Bật KNOWLEDGE_BACKEND=neo4j và ingest trước khi chạy.')
display(pd.DataFrame(store.query(
    'MATCH (n) RETURN labels(n)[0] AS label,count(n) AS count')))
display(pd.DataFrame(store.query(
    'MATCH ()-[r]->() RETURN type(r) AS relation,count(r) AS count')))
print('Documents loaded:',len(services.knowledge.documents))""")
section('7. Truy vấn đồ thị và nguồn','Duyệt quan hệ tối đa hai hop bằng Cypher tham số hóa. Evidence từ graph bổ sung tài liệu cho BM25; câu trả lời là trích xuất có nguồn, chưa dùng LLM sinh văn bản.',"""knowledge=services.knowledge.answer('BMI và HbA1c liên hệ với type 2 thế nào?')
display(pd.DataFrame(knowledge['paths']).head(6))
display(pd.DataFrame(knowledge['citations'])[['id','title']])
print(knowledge['answer'])""")
section('8. Chạy hai kiến trúc','Cùng đầu vào, checkpoint, KB, reviewer và policy. Một hệ điều khiển tập trung; một hệ gửi yêu cầu qua MessageBus tới các handler chuyên trách trong cùng tiến trình.',"""profile={'gender':'Male','age':67,'bmi':34.6,
 'hbA1c_level':7.2,'blood_glucose_level':210,
 'smoking_history':'former','hypertension':1,'heart_disease':1}
question='BMI và HbA1c liên hệ với nguy cơ type 2 thế nào?'
a=single.run(question,profile)
b=multi.run(question,profile)
print('Same prediction:',a['prediction']==b['prediction'])
print('PyTorch:',b['prediction']['probability'])
print('Sklearn:',b['prediction']['second_opinion'])
print('Review:',b['review'])""")
section('9. MessageBus và phản biện','REQUEST/INFORM thể hiện lời gọi thật. Khi bất đồng hoặc gần threshold, Critic gửi CHALLENGE và Prediction trả RESPONSE. Đây là kiểm tra theo luật, không phải hội đồng LLM độc lập.',"""display(pd.DataFrame(b['messages'])[
 ['sequence','sender','receiver','performative']])
display(pd.DataFrame(b['traces'])[['agent','tool']])""")
section('10. Q-learning có action mask','Policy học trong môi trường quy trình tổng hợp, không học hiệu quả điều trị. Mask ép yêu cầu thiếu dữ liệu hoặc cần kiểm tra sang bước phù hợp; không có hành động kê thuốc.',"""from workflow_policy import allowed_actions
policy=json.loads((ROOT/'artifacts/workflow_q_policy.json').read_text())
print('Episodes:',policy['episodes'])
print('Environment:',policy['environment'])
print('Reward:',policy['reward_definition'])
print('Recommendation:',b['workflow'])
display(pd.DataFrame(policy['q_table'],columns=policy['actions']))""")
section('11. Guardrail và kiểm tra dữ liệu','Đầu vào không hợp lệ bị chặn trước suy luận. Các tình huống kê đơn và ngoài phạm vi được định tuyến riêng.',"""for q in ['Hãy kê đơn thuốc và liều dùng cho tôi.',
          'Giá Bitcoin ngày mai là bao nhiêu?']:
    print(q, '=>',multi.run(q)['status'])
bad={**profile,'hypertension':0.5}
print('Invalid profile:',multi.run(question,bad)['validation_errors'])
print('Female group:',services.statistics('percent female')['group'])""")
section('12. Benchmark Single và Multi','58 tình huống mỗi hệ. Task success kiểm tra contract (route, status, nguồn, định dạng), không phải độ chính xác lâm sàng; audit coverage ưu tiên trace chuyên trách theo định nghĩa.',"""summary=json.loads((ROOT/'results/agent_benchmark_summary.json').read_text())
display(pd.DataFrame(summary)[['system','cases','task_success_rate',
 'citation_recall','citation_precision','audit_coverage',
 'mean_latency_ms','p95_latency_ms']])""")
notebook=nb.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','name':'python3','language':'python'}})
client=NotebookClient(notebook,timeout=180,resources={'metadata':{'path':str(ROOT)}})
client.execute()
path=ROOT/'notebooks/08_project_ml_neo4j_multiagent.ipynb'
nb.write(notebook,path)
print(path)
