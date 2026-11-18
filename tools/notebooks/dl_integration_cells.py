"""Executable documentation cells for the deployed DL service; no training."""
import nbformat as nb

TAG = 'dl_integration_7_1'

def integration_cells():
    cells = []
    def md(text): cells.append(nb.v4.new_markdown_cell(text))
    def code(text): cells.append(nb.v4.new_code_cell(text))

    md("""## 5. Tích hợp Deep Learning theo mục 7.1 của yêu cầu thầy

**Patient Features → bộ tiền xử lý đã fit → PyTorch MLP → sigmoid → score và nhãn theo ngưỡng validation.**

Phần này dùng lại checkpoint đang được app gọi, không train lại. Chạy cell thiết lập dưới đây rồi chạy các cell 5.1–5.7 theo thứ tự; có thể bắt đầu từ đây nếu chỉ demo service.

Luồng trong MAS: `DataAgent.validate → DLAgent.predict → DiabetesModelService.predict → TorchPipeline.predict_proba`. Kết quả tiếp tục đi vào Rule Agent và Explanation Agent.
""")
    code("""from pathlib import Path
import sys, json, hashlib
import pandas as pd
import joblib
from IPython.display import display
pd.set_option('display.max_columns', None)

ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()
if not (ROOT / 'artifacts/pytorch_mlp.pt').is_file():
    raise FileNotFoundError('Mở notebook từ thư mục final hoặc final/notebooks.')
sys.path.insert(0, str(ROOT / 'src'))
ml_meta = json.loads((ROOT / 'artifacts/model_metadata.json').read_text(encoding='utf-8'))
dl_meta = json.loads((ROOT / 'artifacts/pytorch_metadata.json').read_text(encoding='utf-8'))
preprocess = joblib.load(ROOT / 'artifacts/pytorch_preprocess.joblib')
from services.model_service import DiabetesModelService
from agents.data_agent import validate as validate_patient
from agents.dl_agent import predict as predict_dl
model_service = DiabetesModelService()
print('Model app đang dùng:', model_service.model_name)
print('Notebook:', ROOT / 'notebooks/09_pytorch_training_full.ipynb')
""")
    md("""### 5.1. Kiến trúc mô hình

Mạng MLP nhận vector sau tiền xử lý. Hai lớp ẩn có 64 và 32 neuron; ReLU tạo phi tuyến; Dropout 0,15 giảm overfitting khi train. Lớp cuối trả **logit**, `BCEWithLogitsLoss` dùng trong huấn luyện. Khi suy luận, `sigmoid` chuyển logit thành score trong [0, 1]. `eval()` tắt Dropout và `inference_mode()` tắt theo dõi gradient.

Code gốc: `src/services/torch_model.py` (`RiskMLP`, `TorchPipeline`).
""")
    code("""print(model_service.pipeline.model)
print('Kích thước ghi trong artifact:', dl_meta['architecture'])
print('Số tham số:', sum(p.numel() for p in model_service.pipeline.model.parameters()))
print('Chế độ training:', model_service.pipeline.model.training)
""")
    md("""### 5.2. Dữ liệu huấn luyện và thiết lập thực nghiệm

CSV dùng nhãn `diabetes` (0/1). Loại bản ghi trùng trên toàn bộ cột trước khi chia tập. Chia train/validation/test theo 70/15/15, stratify theo nhãn và random_state=42. Chọn checkpoint theo validation loss và ngưỡng theo validation F1; test được giữ riêng để đánh giá cuối.

Nguồn trực tiếp của thí nghiệm là file CSV trong repository, được nhận diện bằng SHA-256 dưới đây. Đường dẫn và hash không thay thế thông tin xuất xứ/giấy phép của nhà cung cấp dataset.
""")
    code("""dataset_path = ROOT / ml_meta['dataset']['path']
data_raw = pd.read_csv(dataset_path)
data_clean = data_raw.drop_duplicates()
dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
print('CSV:', dataset_path)
print('SHA-256:', dataset_hash)
print('Khớp metadata:', dataset_hash == ml_meta['dataset']['sha256'])
print('Dòng gốc / sau loại trùng:', len(data_raw), '/', len(data_clean))
display(data_clean.head())
display(data_clean['diabetes'].value_counts().sort_index().rename('Số mẫu').to_frame())
display(pd.Series(dl_meta['splits'], name='Số mẫu').to_frame())
print('Seed:', dl_meta['seed'], '| Epoch đã chạy:', dl_meta['epochs'])
print('Optimizer: Adam; learning_rate=0.001; batch_size=512; patience=8')
""")
    md("""### 5.3. Tên feature và thứ tự đầu vào

Có 8 feature thô. Service dựng DataFrame theo đúng `model_metadata.json`, nên thứ tự key trong JSON người dùng không quyết định thứ tự tensor. `ColumnTransformer` xuất các cột số trước, sau đó các cột one-hot; thứ tự thực tế sau mã hóa được đọc từ **bộ tiền xử lý đã fit**, không tự liệt kê bằng tay.
""")
    code("""raw_feature_order = ml_meta['features']
encoded_feature_order = preprocess.get_feature_names_out().tolist()
display(pd.DataFrame({'Thứ tự': range(1, len(raw_feature_order)+1), 'Feature gốc': raw_feature_order}))
display(pd.DataFrame({'Thứ tự tensor': range(1, len(encoded_feature_order)+1), 'Feature sau xử lý': encoded_feature_order}))
assert len(encoded_feature_order) == dl_meta['architecture'][0]
""")
    md("""### 5.4. Tiền xử lý và kiểm soát rò rỉ dữ liệu

- Cột số: điền thiếu bằng median trên train, sau đó StandardScaler.
- Cột phân loại: điền thiếu bằng mode trên train, sau đó OneHotEncoder với handle_unknown='ignore'.
- Train dùng `fit_transform(xt)`; validation/test và app chỉ dùng `transform`.
- App xác thực hồ sơ trước khi dự đoán. Bộ imputer phục vụ pipeline; không có nghĩa giao diện tự chấp nhận hồ sơ thiếu trường bắt buộc.

Cell dưới chỉ gọi transform trên artifact đã fit, không thay đổi tham số hay ghi đè checkpoint. Code train ở `tools/training/train_torch_model.py`.
""")
    code("""display(preprocess)
example_features = {name: data_clean.iloc[0][name].item()
                    if hasattr(data_clean.iloc[0][name], 'item') else data_clean.iloc[0][name]
                    for name in raw_feature_order}
validated = validate_patient({'profile': example_features}, model=model_service)
assert validated['status'] == 'ok', validated['errors']
example_frame = pd.DataFrame([validated['validated_features']], columns=raw_feature_order)
example_tensor = preprocess.transform(example_frame)
print('Kích thước trước xử lý:', example_frame.shape)
print('Kích thước sau xử lý:', example_tensor.shape)
display(pd.DataFrame(example_tensor, columns=encoded_feature_order))
""")
    md("""### 5.5. Định dạng đầu ra và demo DL Prediction Agent

`DLAgent` nhận `features` đã xác thực, trả output có cấu trúc:

| Trường | Ý nghĩa |
| --- | --- |
| probability | Score sigmoid của model; chưa phải xác suất lâm sàng đã hiệu chỉnh |
| threshold | Ngưỡng chọn trên validation |
| predicted_class | 1 khi score ≥ threshold, ngược lại 0; nhãn mô hình, không phải chẩn đoán |
| model, model_version | Tên và phiên bản service model |
| feature_names | Thứ tự feature gốc |
| feature_impacts | Chênh lệch score khi thay từng đặc trưng bằng baseline; không chứng minh nhân quả |
| second_opinion | Kết quả model scikit-learn đối chiếu |

Cell dùng một dòng CSV để minh họa định dạng và đường gọi service; **không coi ví dụ này là đánh giá trên dữ liệu mới**.
""")
    code("""prediction_output = predict_dl({'features': validated['validated_features']}, model=model_service)
print(json.dumps(prediction_output, ensure_ascii=False, indent=2))
assert prediction_output['predicted_class'] == int(prediction_output['probability'] >= prediction_output['threshold'])
""")
    md("""### 5.6. Phiên bản và nhận diện artifact

`model_version` hiện do service công bố. Hash checkpoint và bộ tiền xử lý giúp xác định chính xác các file dùng cho lần demo, vì chuỗi phiên bản thủ công chưa tự thay đổi khi retrain. Phiên bản Agent và schema message là hai khái niệm riêng.
""")
    code("""version_rows = []
for relative in ('artifacts/pytorch_mlp.pt', 'artifacts/pytorch_preprocess.joblib', 'artifacts/pytorch_metadata.json'):
    path = ROOT / relative
    version_rows.append({'Artifact': relative, 'SHA-256': hashlib.sha256(path.read_bytes()).hexdigest()})
print('Model version:', prediction_output['model_version'])
print('Ngưỡng model service / metadata:', model_service.threshold, '/', dl_meta['threshold'])
display(pd.DataFrame(version_rows))
""")
    md("""### 5.7. Chỉ số đánh giá và giới hạn

Các chỉ số dưới đây đọc từ kết quả train đã lưu; cell không đo lại hoặc thay đổi số liệu. Validation dùng chọn mô hình/ngưỡng; test dùng báo cáo kết quả cuối. Accuracy cần đọc cùng Recall, Precision, F1, ROC-AUC, PR-AUC, Brier và confusion matrix vì nhãn dương tính ít hơn nhiều.

**Accuracy cao không chứng minh mô hình đã được kiểm định lâm sàng.** Còn thiếu đánh giá ngoại viện/ngoại miền, hiệu chỉnh xác suất độc lập, đánh giá nhóm và xác nhận chuyên môn. Không dùng output để tự chẩn đoán hoặc quyết định điều trị.
""")
    code("""metric_names = ['threshold', 'accuracy', 'precision', 'recall', 'f1', 'roc_auc', 'pr_auc', 'brier', 'tn', 'fp', 'fn', 'tp']
metrics = pd.DataFrame({split: {key: dl_meta[split][key] for key in metric_names}
                        for split in ('validation', 'test')}).T
display(metrics)
test = dl_meta['test']
display(pd.DataFrame([[test['tn'], test['fp']], [test['fn'], test['tp']]],
                     index=['Thực tế 0', 'Thực tế 1'], columns=['Dự đoán 0', 'Dự đoán 1']))
positive_count = test['tp'] + test['fn']
print(f"Accuracy test: {test['accuracy']:.2%}; Recall: {test['recall']:.2%}; F1: {test['f1']:.4f}.")
print(f"Bỏ sót {test['fn']}/{positive_count} mẫu dương tính trên test.")
print('Đây là đánh giá trên dataset của project, chưa phải bằng chứng kiểm định lâm sàng.')
""")
    for cell in cells: cell.metadata['tags'] = [TAG]
    return cells
