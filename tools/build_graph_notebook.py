"""Run the graph experiment and preserve its real stdout in a runnable notebook."""
import contextlib,io
from pathlib import Path
import nbformat as nb
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tools/train_graph_chapter.py').read_text()
source=source.replace('ROOT=Path(__file__).resolve().parents[1]',"ROOT=Path.cwd().parent if Path.cwd().name=='notebooks' else Path.cwd()")
source=source.replace("if __name__=='__main__':main()",'main()')
cell=nb.v4.new_code_cell(source)
output=io.StringIO()
with contextlib.redirect_stdout(output):exec(compile(source,'chapter6','exec'),{'__name__':'__main__'})
cell.execution_count=1;cell.outputs=[nb.v4.new_output('stream',name='stdout',text=output.getvalue())]
notebook=nb.v4.new_notebook(cells=[
 nb.v4.new_markdown_cell('# Chương 6 — Học sâu trên đồ thị CDC của bài\nThí nghiệm được thực thi bằng Python; output dưới đây được ghi từ lần chạy thật. Đây là đồ thị tương đồng giữa 1.600 bản ghi được chọn phân tầng từ CSV CDC của sinh viên. Không phải Pubmed hay dữ liệu của bài Kiên. Đồ thị này khác Knowledge Graph Neo4j.\n\nScaler chỉ fit train. kNN dùng đặc trưng không có nhãn. Giao thức transductive cho phép nhìn đặc trưng test và cấu trúc graph khi train, nhưng loss chỉ dùng nhãn train. Không trình bày kết quả như khả năng tổng quát hóa inductive.'),cell,
 nb.v4.new_markdown_cell('## Giải thích và giới hạn\nMLP là đối chứng chỉ dùng thuộc tính. GCN tổng hợp bằng ma trận đối xứng chuẩn hóa có self-loop. GraphSAGE mean ghép thuộc tính riêng với trung bình hàng xóm; đây là cài đặt full-neighbor minh họa, không dùng neighbor sampling. Cả ba chọn checkpoint bằng validation loss và threshold bằng validation F1. Chỉ 1.600 mẫu, một seed; chưa đủ kết luận kiến trúc nào luôn tốt hơn. Không đưa GNN này vào dự đoán web hiện tại.')
],metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}})
nb.write(notebook,ROOT/'notebooks/10_deep_graph_cdc.ipynb');print(output.getvalue())
