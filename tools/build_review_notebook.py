"""Create an explanatory notebook with saved output from the paired run."""
from pathlib import Path
import json
import nbformat as nb
ROOT=Path(__file__).resolve().parents[1]
result=json.loads((ROOT/'results/paired_agent_evaluation.json').read_text(encoding='utf-8'))
summary=json.dumps(result['summary'],ensure_ascii=False,indent=2)
faults=json.dumps(result['faults'],ensure_ascii=False,indent=2)
n=nb.v4.new_notebook(cells=[
 nb.v4.new_markdown_cell('# So sánh Single và Multi-Agent có kiểm tra lại\nBộ dữ liệu được chia giống huấn luyện; lấy ngẫu nhiên 100 dòng test có nhãn. Hai hệ chạy trực tiếp trên cùng hồ sơ, đảo thứ tự. Trường hợp cần người xem xét không được tính là đã được sửa đúng.'),
 nb.v4.new_code_cell("from pathlib import Path\nimport json\nROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\nresults = json.loads((ROOT/'results/paired_agent_evaluation.json').read_text(encoding='utf-8'))\nprint(json.dumps(results['summary'], ensure_ascii=False, indent=2))",execution_count=1,outputs=[nb.v4.new_output('stream',name='stdout',text=summary+'\n')]),
 nb.v4.new_markdown_cell('## Kết quả theo nhãn thật\nConfusion matrix theo thứ tự âm/dương. Coverage là tỷ lệ không chuyển người xem xét. Selective accuracy chỉ tính các ca được nhận, vì vậy không so trực tiếp mà bỏ qua coverage.'),
 nb.v4.new_code_cell("print(json.dumps(results['faults'], ensure_ascii=False, indent=2))",execution_count=2,outputs=[nb.v4.new_output('stream',name='stdout',text=faults+'\n')]),
 nb.v4.new_markdown_cell('## Lỗi truy xuất tạm thời\nMỗi hệ gặp một lần truy xuất rỗng giả lập; lặp năm lần. Citation xuất hiện trở lại không chứng minh nội dung nguồn hỗ trợ câu trả lời. Thời gian là một lần đo trên mỗi hồ sơ; chưa đánh giá tải đồng thời. Chạy lại benchmark bằng `python tools/benchmark_review_agents.py`.')],metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
nb.write(n,ROOT/'notebooks/11_agent_review_benchmark.ipynb')
