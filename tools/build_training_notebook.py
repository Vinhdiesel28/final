"""Expose and run the complete PyTorch training implementation in a notebook."""
from pathlib import Path
import nbformat as nb
from nbclient import NotebookClient
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tools/train_torch_model.py').read_text(encoding='utf-8')
source=source.replace('ROOT = Path(__file__).resolve().parents[1]',"ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\nsys.path.insert(0, str(ROOT/'tools'))")
source=source.replace("if __name__ == '__main__': main()",'main()')
notebook=nb.v4.new_notebook(cells=[
 nb.v4.new_markdown_cell('# Huấn luyện PyTorch từ CSV đến checkpoint\nCell dưới chứa toàn bộ implementation dùng trong script, đã chạy thật. Không cần chạy lại khi chỉ demo notebook 08. Preprocessing fit train; checkpoint chọn validation loss, threshold chọn validation F1; test chỉ dùng đánh giá.'),
 nb.v4.new_code_cell(source),
 nb.v4.new_markdown_cell('## Giải thích vòng lặp\n`train()` bật dropout; `randperm` xáo batch. `zero_grad` xóa gradient, `backward` lan truyền ngược, `step` cập nhật trọng số. `eval()` tắt dropout khi đo validation; `inference_mode()` không xây đồ thị gradient. `deepcopy(state_dict)` giữ checkpoint tốt nhất. Adam dùng 0,001; tối đa 60 epoch và patience 8. Test không được dùng chọn checkpoint hoặc threshold.')
],metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
NotebookClient(notebook,timeout=600,resources={'metadata':{'path':str(ROOT)}}).execute()
path=ROOT/'notebooks/09_pytorch_training_full.ipynb';nb.write(notebook,path);print(path)
