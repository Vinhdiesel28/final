"""Build and execute the PyTorch training notebook."""
from pathlib import Path

import nbformat as nb
from nbclient import NotebookClient
from dl_integration_cells import integration_cells, TAG

ROOT = Path(__file__).resolve().parents[2]


def benchmark_cells():
    return [
        nb.v4.new_markdown_cell(
            "## 4. Benchmark ML và Deep Learning trên tập test\n"
            "So sánh ba mô hình scikit-learn và PyTorch MLP trên cùng 14.998 mẫu test "
            "(1.275 mẫu dương tính). Mỗi mô hình dùng ngưỡng được chọn trên validation. "
            "Cell này đọc số liệu đã lưu, có thể chạy riêng để xem bảng."
        ),
        nb.v4.new_code_cell("""from pathlib import Path
import json
import pandas as pd
from IPython.display import display

root = Path.cwd()
if root.name == "notebooks":
    root = root.parent

ml = json.loads((root / "artifacts/model_metadata.json").read_text(encoding="utf-8"))
dl = json.loads((root / "artifacts/pytorch_metadata.json").read_text(encoding="utf-8"))

rows = [
    {**entry["test"], "model": entry["test"]["model"] + " (scikit-learn)"}
    for entry in ml["models"]
]
rows.append(dl["test"])
columns = ["model", "threshold", "accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc", "fn"]
benchmark = pd.DataFrame(rows)[columns].set_index("model")
display(benchmark.style.format({
    "threshold": "{:.3f}", "accuracy": "{:.2%}", "precision": "{:.2%}",
    "recall": "{:.2%}", "f1": "{:.4f}", "roc_auc": "{:.4f}", "pr_auc": "{:.4f}",
    "fn": "{:d}",
}))
"""),
        nb.v4.new_markdown_cell(
            "**Nhận xét.** Hai bản MLP có F1 gần như nhau (0,7925 và 0,7924). "
            "MLP scikit-learn bỏ sót 414 mẫu dương tính, còn PyTorch MLP bỏ sót 424. "
            "Logistic Regression có Recall cao nhất (72,55%) và F1 thấp nhất (0,7032). "
            "Random Forest có Accuracy cao nhất (97,04%). "
            "Trong app, PyTorch MLP là mô hình chính và MLP scikit-learn dùng để đối chiếu. "
            "Các chỉ số phản ánh kết quả trên tập test của project."
        ),
    ]


def make_notebook():
    source = (ROOT / 'tools/training/train_torch_model.py').read_text(encoding='utf-8')
    source = source.replace(
        'ROOT = Path(__file__).resolve().parents[2]',
        "sys.path.insert(0, str(ROOT/'tools/training'))",
    )
    source = source.replace(
        "    df = pd.read_csv(ROOT/'data/diabetes_prediction_dataset.csv').drop_duplicates()\n",
        "",
    )
    source = source.replace("if __name__ == '__main__': main()", "main()")
    return nb.v4.new_notebook(cells=[
        nb.v4.new_markdown_cell(
            "# Huấn luyện PyTorch từ CSV đến checkpoint\n"
            "Chạy các cell theo thứ tự từ trên xuống."
        ),
        nb.v4.new_markdown_cell(
            "## 1. Đọc CSV và loại dòng trùng\n"
            "Kiểm tra dòng trùng trên toàn bộ các cột, gồm cả nhãn. "
            "Giữ lần xuất hiện đầu tiên của mỗi dòng và loại các bản sao trước khi chia tập, "
            "để bản sao giống hệt không xuất hiện ở cả tập train và tập đánh giá. "
            "Bảng bên dưới cũng đếm giá trị thiếu trong dữ liệu sau khi loại trùng."
        ),
        nb.v4.new_code_cell(
            "from pathlib import Path\n"
            "import pandas as pd\n"
            "\n"
            "ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\n"
            "csv_path = ROOT / 'data' / 'diabetes_prediction_dataset.csv'\n"
            "raw = pd.read_csv(csv_path)\n"
            "duplicate_count = int(raw.duplicated().sum())\n"
            "df = raw.drop_duplicates(keep='first')\n"
            "\n"
            "print(f'Số dòng ban đầu: {len(raw):,}')\n"
            "print(f'Số dòng trùng đã loại: {duplicate_count:,}')\n"
            "print(f'Số dòng sau khi loại trùng: {len(df):,}')\n"
            "display(df.isna().sum().rename('Số giá trị thiếu').to_frame())"
        ),
        nb.v4.new_markdown_cell(
            "## 2. Chia tập, tiền xử lý và huấn luyện\n"
            "Cell này dùng dữ liệu đã loại trùng từ cell trên. Chia train/validation/test "
            "theo tỷ lệ 70/15/15 và giữ tỷ lệ nhãn bằng stratify. Các cột số được điền thiếu "
            "bằng median rồi chuẩn hóa. Hai cột phân loại được điền bằng giá trị phổ biến nhất "
            "rồi mã hóa one-hot. Pipeline học tham số trên train với `fit_transform(xt)`; "
            "validation và test dùng lại các tham số đó. Chọn checkpoint theo validation loss, "
            "chọn ngưỡng theo validation F1 và đánh giá cuối trên test. "
            "Chạy cell này sẽ lưu lại checkpoint và các kết quả huấn luyện."
        ),
        nb.v4.new_code_cell(source),
        nb.v4.new_markdown_cell(
            "## 3. Giải thích vòng lặp\n"
            "`train()` bật dropout và `randperm` xáo thứ tự mẫu. `zero_grad()` xóa gradient, "
            "`backward()` lan truyền ngược và `step()` cập nhật trọng số. `eval()` tắt dropout "
            "khi đo validation, còn `inference_mode()` tắt theo dõi gradient. "
            "`deepcopy(state_dict)` giữ checkpoint tốt nhất. Adam dùng learning rate 0,001, "
            "tối đa 60 epoch và patience 8."
        ),
        *benchmark_cells(),
        *integration_cells(),
    ], metadata={'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}})


if __name__ == '__main__':
    import sys, os
    os.environ['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '')
    if '--integration-only' in sys.argv:
        path = ROOT / 'notebooks/09_pytorch_training_full.ipynb'
        notebook = nb.read(path, as_version=4)
        appendix = nb.v4.new_notebook(cells=integration_cells(), metadata=notebook.metadata)
        if '--in-process' in sys.argv:
            # Execute real cells through IPython when local kernel startup is unavailable.
            from IPython.core.interactiveshell import InteractiveShell
            from IPython.utils.capture import capture_output
            shell = InteractiveShell()
            shell.execution_count = max((cell.get('execution_count') or 0 for cell in notebook.cells if TAG not in cell.metadata.get('tags', [])), default=0) + 1
            previous = Path.cwd()
            os.chdir(ROOT)
            try:
                for cell in appendix.cells:
                    if cell.cell_type != 'code':
                        continue
                    count = shell.execution_count
                    with capture_output() as captured:
                        executed = shell.run_cell(cell.source, store_history=True)
                    executed.raise_error()
                    cell.execution_count = count
                    cell.outputs = []
                    if captured.stdout:
                        cell.outputs.append(nb.v4.new_output('stream', name='stdout', text=captured.stdout))
                    if captured.stderr:
                        cell.outputs.append(nb.v4.new_output('stream', name='stderr', text=captured.stderr))
                    cell.outputs.extend(nb.v4.new_output('display_data', data=item.data, metadata=item.metadata)
                                        for item in captured.outputs)
            finally:
                os.chdir(previous)
        else:
            NotebookClient(appendix, timeout=180, startup_timeout=30, resources={'metadata': {'path': str(ROOT)}}).execute()
        notebook.cells = [cell for cell in notebook.cells if TAG not in cell.metadata.get('tags', [])] + appendix.cells
        nb.write(notebook, path)
        print(path)
        raise SystemExit(0)
    notebook = make_notebook()
    NotebookClient(notebook, timeout=600, resources={'metadata': {'path': str(ROOT)}}).execute()
    path = ROOT / 'notebooks/09_pytorch_training_full.ipynb'
    nb.write(notebook, path)
    print(path)
