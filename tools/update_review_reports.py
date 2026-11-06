"""Create updated report copies, retaining the user's existing documents."""
from pathlib import Path
import json
from docx import Document
from docx.shared import Pt
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'results/paired_agent_evaluation.json').read_text(encoding='utf-8'))
for stem in ['project01_CT_08_934_NguyenMinhVinh','tieuluan_final_CT_08_934_NguyenMinhVinh']:
    doc=Document(ROOT/'report'/f'{stem}.docx')
    doc.add_page_break()
    doc.add_heading('PHỤ LỤC CẬP NHẬT SO SÁNH AGENT',level=1)
    doc.add_paragraph('Bản cập nhật này bổ sung kết quả mới và thay thế cách diễn giải benchmark contract ở các phần trước. Hai hệ chạy trên cùng 100 hồ sơ test có nhãn, lấy ngẫu nhiên seed 73 từ split test gốc; thứ tự thực thi được đảo xen kẽ. Trạng thái human_review là chuyển người xem xét, không tự tính là dự đoán đúng.')
    table=doc.add_table(rows=1,cols=5);table.style='Table Grid'
    for cell,value in zip(table.rows[0].cells,['Hệ','Accuracy thô','Coverage','Accuracy ca nhận','Lỗi chuyển xem xét']):cell.text=value
    for key in ['single','multi']:
        x=data['summary'][key];cells=table.add_row().cells
        for cell,value in zip(cells,[key,f"{x['accuracy_all_raw_predictions']:.3f}",f"{x['coverage']:.3f}",f"{x['selective_accuracy']:.3f}",str(x['errors_referred'])]):cell.text=value
    doc.add_paragraph('Cả hai dùng cùng mô hình; accuracy thô không phản ánh lợi ích kiểm tra lại. Tập mẫu này có bốn lỗi dự đoán, không lỗi nào được chuyển đi xem xét. Không có cơ sở khẳng định Multi-Agent giảm lỗi dự đoán từ phép thử này.')
    doc.add_paragraph('Thử nghiệm lỗi truy xuất: mỗi hệ gặp một lần truy xuất rỗng giả lập, lặp năm lần. Multi-Agent truy xuất lại và có citation 5/5 lần; Single-Agent không thử lại. Đây là lỗi giả lập cụ thể và sự hiện diện citation không chứng minh nguồn hỗ trợ nội dung.')
    t=data['repeated_latency']
    doc.add_paragraph(f"Đo lặp cùng một hồ sơ 20 lần mỗi hệ, thứ tự xen kẽ: trung vị Single {t['single']['median_ms']:.2f} ms, Multi {t['multi']['median_ms']:.2f} ms. Kết quả chỉ áp dụng môi trường và backend JSON lần chạy này; không phải kiểm thử tải đồng thời.")
    doc.add_paragraph('Mã và kết quả: tools/benchmark_review_agents.py; results/paired_agent_evaluation.json; notebooks/11_agent_review_benchmark.ipynb. Policy Q-learning hiện chỉ đề xuất hành động; vòng kiểm tra lại triển khai theo luật. Chưa đánh giá semantic entailment của bằng chứng hoặc giá trị lâm sàng.')
    doc.save(ROOT/'report'/f'{stem}_cap_nhat.docx')
