"""Final thesis continuing the student's Thesis 03 with a seven-chapter outline."""
import json,re,shutil,sys
from pathlib import Path
from docx import Document
from docx.shared import Cm,Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image
import build_reports as br
ROOT=br.ROOT
LEGACY=ROOT.parent/'tieuluan3'
ASSETS=ROOT/'report/assets/final_continued'
ASSETS.mkdir(exist_ok=True)

def clean(text):
    text=re.sub(r'<[^>]+>','',text)
    text=text.replace('Age nt','Agent').replace('Multi- Agent','Multi-Agent')
    for a,b in {'BM 25':'BM25','Uni code':'Unicode','B 0':'B0','B 1':'B1','B 2':'B2','B 3':'B3','B 4':'B4','Recall @3':'Recall@3','Deep Learning':'Deep Learning'}.items():text=text.replace(a,b)
    text=re.sub(r'\[\d+(?:[,–-]\d+)*\]','',text)
    text=re.sub(r'\[([^]]+)\]\(([^)]+)\)',r'\1 (\2)',text)
    return text.replace('**','').replace('`','').strip()

def text(doc,value):return br.add_text(doc,clean(value))
def heading(doc,title,level=2):
    p=doc.add_heading(title,level)
    if level==1:p.paragraph_format.page_break_before=True
    return p
def figure(doc,path,caption,maxheight=17):
    with Image.open(path) as im:width=min(15.5,maxheight*im.width/im.height)
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next=True
    p.add_run().add_picture(str(path),width=Cm(width))
    c=doc.add_paragraph(caption);c.alignment=WD_ALIGN_PARAGRAPH.CENTER
def code(doc,source):
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.line_spacing=1.05
    br.font(name='Consolas',size=8.5)(p.add_run(source))

def render_legacy(doc,source):
    lines=source.splitlines();i=0;image_no=0
    while i<len(lines):
        s=lines[i].strip();i+=1
        if not s:continue
        if s.startswith('```'):
            block=[]
            while i<len(lines) and not lines[i].strip().startswith('```'):
                block.append(lines[i]);i+=1
            i+=1;code(doc,'\n'.join(block));continue
        if s.startswith('|'):
            rows=[s]
            while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i].strip());i+=1
            cells=[[clean(v.strip()) for v in row.strip('|').split('|')] for row in rows]
            if len(cells)>2:
                widths=None
                if len(cells[0])==3 and any('Input' in v for v in cells[0]):
                    widths=[2,10.5,3]
                    cells=[[re.sub(r'-?\d+\.\d{5,}(?:e[+-]?\d+)?',lambda m:f'{float(m[0]):.4f}',v) for v in row] for row in cells]
                br.table(doc,cells[0],cells[2:],widths=widths)
            continue
        match=re.match(r'!\[([^]]*)\]\(([^)]+)\)',s)
        if match:
            image_no+=1;original=(LEGACY/'report'/match[2]).resolve()
            if not original.exists():raise FileNotFoundError(original)
            dest=ASSETS/f'legacy-{image_no:02d}{original.suffix}'
            shutil.copy2(original,dest)
            figure(doc,dest,f'Hình kế thừa {image_no}  {clean(match[1])}')
            continue
        if s.startswith('#'):
            title=clean(s.lstrip('# '))
            if title.startswith('CHƯƠNG'):
                parts=re.split(r'\s+-\s+(?=\d+\.\d+)',title,maxsplit=1)
                heading(doc,parts[0],1)
                if len(parts)>1:heading(doc,parts[1],2)
            else:heading(doc,title,3 if re.match(r'^\d+\.\d+\.\d+',title) else 2)
            continue
        if 'PHẦN CẬP NHẬT MỚI CỦA TIỂU LUẬN' in s:continue
        # Source paragraphs stay in the student's voice, with current cross-references.
        s=s.replace('Chương 6','Chương 7').replace('Notebook 08','Notebook 08 của tiểu luận 3')
        s=s.replace('tieuluan 3','tieuluan3')
        text(doc,s)

def section(doc,title,*paragraphs):
    heading(doc,title,3 if re.match(r'^\d+\.\d+\.\d+',title) else 2)
    for p in paragraphs:text(doc,p)

def build():
    br.MONOCHROME=True;doc=Document();br.configure(doc)
    for style_name in ['Normal','Title','Heading 1','Heading 2','Heading 3']:
        fonts=doc.styles[style_name]._element.get_or_add_rPr().rFonts
        for key in ['asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme']:
            fonts.attrib.pop(qn('w:'+key),None)
    br.cover(doc,'Tiểu luận Final','Từ học máy đến hệ đa tác tử','Lý thuyết thực nghiệm và ứng dụng DiaAgents')
    toc_title=doc.add_paragraph('MỤC LỤC')
    toc_title.paragraph_format.page_break_before=True
    br.font(size=15,bold=True)(toc_title.runs[0])
    p=doc.add_paragraph();field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'TOC \\o "1-2" \\h \\z \\u');p._p.append(field)
    heading(doc,'TÓM TẮT',1)
    text(doc,'Tiểu luận tổng hợp quá trình xây dựng hệ thống thông minh từ biểu diễn dữ liệu, học mô hình đến truy xuất tri thức và điều phối tác tử. Quyển Final kế thừa các thực nghiệm của tiểu luận 3: đối chiếu cài đặt scratch, Keras và PyTorch cho dữ liệu bảng, ảnh và chuỗi thời gian; sau đó phát triển thêm học sâu trên đồ thị và ứng dụng đa tác tử. Mục tiêu là nối công thức, mã nguồn, kết quả thực nghiệm và hành vi demo trong một quy trình có thể kiểm tra.')
    text(doc,'Các chương đầu giữ dữ liệu CDC BRFSS 2015, giá nhà Việt Nam, MNIST, EuroSAT, AAPL và Online Retail II của sinh viên. Chương 6 xây đồ thị tương đồng từ một tập con CDC, so sánh MLP, GCN và GraphSAGE. Chương 7 phát triển hệ Agent sử dụng Diabetes Prediction Dataset và CDC BRFSS của project hiện tại, kết hợp mô hình PyTorch, mô hình sklearn đối chiếu, Neo4j, truy xuất bằng chứng, trao đổi thông điệp và Q-learning cho quy trình.')
    text(doc,'Thực nghiệm phân biệt hiệu quả mô hình với hiệu quả kiến trúc phần mềm. Một F1 cao chỉ phản ánh bộ dữ liệu và cách chia đã xác định; một trace nhiều bước chỉ thể hiện khả năng quan sát, không tự chứng minh câu trả lời tốt hơn. Hai hệ Single và Multi được so trên cùng 58 tình huống và cùng công cụ. Các mô hình, số đo và dataset của bài tham khảo không được dùng thay cho kết quả của sinh viên.')
    heading(doc,'MỞ ĐẦU',1)
    section(doc,'0.1 Bối cảnh và mục tiêu','Một ứng dụng AI hoàn chỉnh cần nhiều hơn một mô hình dự đoán. Dữ liệu phải được kiểm tra, đặc trưng và nhãn phải được định nghĩa, tri thức phải có nguồn và đầu ra phải được đặt trong phạm vi phù hợp. Tiểu luận tiếp cận vấn đề theo từng lớp: ML xử lý dữ liệu bảng; CNN khai thác cấu trúc ảnh; RNN mô hình hóa chuỗi; KG và RAG biểu diễn bằng chứng; GNN học trên cấu trúc liên kết; Agent điều phối các công cụ đó.','Mục tiêu của quyển Final là tiếp nối kết quả đã có thay vì thay toàn bộ bài bằng một miền mới. Mỗi chương giữ đường dẫn thực nghiệm, nguồn dữ liệu và các điều kiện đánh giá. Nội dung mới được viết thành chương hoàn chỉnh, đồng thời phần kết luận được cập nhật theo các kết quả hiện có.')
    section(doc,'0.2 Phạm vi dữ liệu và sản phẩm','Chương 1–5 kế thừa tiểu luận 3; phần Agent trước đây ở Chương 6 được đặt lại trong mạch phát triển của Chương 7. Chương 6 mới trình bày học sâu trên đồ thị để tương ứng cấu trúc bảy chương của bài tham khảo. Dữ liệu đồ thị ở đây được xây từ CDC của sinh viên, không dùng Pubmed-Diabetes hoặc các bộ NHANES, RetinaMNIST, ShanghaiT1DM của bài mẫu.','Mã nguồn và notebook Chương 1–5: https://github.com/Vinhdiesel28/tieuluan3 . Mã nguồn và notebook phần phát triển mới: https://github.com/Vinhdiesel28/final . Demo Agent cục bộ: http://127.0.0.1:8010 . Địa chỉ localhost chỉ hoạt động trên máy đang chạy server, không phải liên kết triển khai công khai.')
    br.table(doc,['Chương','Dữ liệu của sinh viên','Sản phẩm kiểm chứng'],[
        ['1','Các dataset đại diện của bài','Notebook lịch sử và thống kê dữ liệu'],
        ['2','CDC Diabetes và giá nhà Việt Nam','MLP scratch/Keras/PyTorch và baseline ML'],
        ['3','MNIST và EuroSAT','CNN và so sánh kiến trúc'],
        ['4','AAPL và Online Retail II','RNN và so sánh kiến trúc'],
        ['5','Corpus CDC và AAPL của tiểu luận 3','12 tài liệu, 23 quan hệ, benchmark 15 câu'],
        ['6','1.600 mẫu từ CDC BRFSS 2015','MLP, GCN, GraphSAGE và notebook 10'],
        ['7','Diabetes Prediction, CDC và KB project','Notebook 07–09 và demo Single/Multi']])
    section(doc,'0.3 Nguyên tắc thực nghiệm','Dữ liệu train dùng để fit; validation dùng chọn checkpoint hoặc threshold; test dùng để báo cáo. Các chương chuỗi giữ thứ tự thời gian. Riêng thí nghiệm graph mới sử dụng giao thức transductive và công khai việc dùng thuộc tính của nút test trong cấu trúc đồ thị; nhãn test không đi vào loss. Không trộn số đo từ các giao thức khác nhau để kết luận kiến trúc tốt nhất.','Quyển báo cáo sử dụng bảng đơn sắc, code căn trái và ảnh notebook có output. Kết quả kế thừa không được huấn luyện lại chỉ để tăng điểm. Phần mới ghi rõ file kết quả và cách chạy. Các giới hạn được đặt cùng thí nghiệm để người đọc hiểu điều gì đã chứng minh và điều gì còn là hướng phát triển.')
    source=(LEGACY/'report/Tieu_luan_03_Nguyen_Minh_Vinh.md').read_text(encoding='utf-8')
    first=source.index('# CHƯƠNG 1.');last=source.index('# <span style="color:#c62828">CHƯƠNG 6.')
    render_legacy(doc,source[first:last])
    chapter6(doc);chapter7(doc)
    heading(doc,'KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN',1)
    text(doc,'Quyển Final tiếp nối tiểu luận 3 bằng một mạch nội dung từ lịch sử AI đến ứng dụng đa tác tử. Các chương ML, CNN, RNN và KG/RAG giữ dữ liệu và thực nghiệm riêng của sinh viên. Chương học sâu trên đồ thị bổ sung thí nghiệm có kiểm soát trên CDC; Chương Agent tích hợp mô hình đã huấn luyện, kho tri thức Neo4j và cơ chế điều phối vào demo hiện tại.')
    text(doc,'Bài học chung là hiệu quả phụ thuộc cả dữ liệu, thuật toán và cách đánh giá. Graph không mặc nhiên cải thiện phân loại; nhiều agent không mặc nhiên chính xác hơn một agent. Kết quả chỉ có ý nghĩa khi công khai split, threshold, nguồn bằng chứng và tiêu chí thành công. Hệ thống hiện phục vụ học tập, chưa có kiểm định lâm sàng hoặc khả năng tự lựa chọn điều trị.')
    text(doc,'Hướng phát triển gồm mở rộng corpus có phiên bản, đánh giá nhiều seed, kiểm tra ngoài mẫu độc lập, cải thiện gán nhãn benchmark và theo dõi chi phí thực trên máy triển khai. Nếu mở rộng thành hệ LLM hoặc broker phân tán, cần đánh giá lại độ tin cậy, quyền công cụ, thời gian phản hồi và tính nhất quán dữ liệu.')
    for report_table in doc.tables:
        for row in report_table.rows:
            row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
    br.add_footer(doc)
    path=ROOT/'report/tieuluan_final_CT_08_934_NguyenMinhVinh.docx';doc.save(path)
    print(path)
    return path

def chapter6(doc):
    m=json.loads((ROOT/'results/deep_graph/metrics.json').read_text())
    heading(doc,'CHƯƠNG 6 HỌC SÂU TRÊN ĐỒ THỊ',1)
    section(doc,'6.1 Dữ liệu đồ thị và bài toán học','Đồ thị G=(V,E) gồm tập nút và tập cạnh. Thuộc tính nút được biểu diễn bằng ma trận X; cấu trúc liên kết được biểu diễn bằng ma trận kề A. Nhiệm vụ có thể là phân loại nút, dự đoán cạnh hoặc phân loại toàn đồ thị. Việc chọn nhiệm vụ quyết định cách chia dữ liệu và loại đầu ra cần đánh giá.','Trong thực nghiệm này, mỗi nút là một bản ghi CDC; cạnh nối hai bản ghi có đặc trưng tương đồng. Nhãn là Diabetes_012 > 0, gộp tiền tiểu đường và tiểu đường. Cạnh kNN không biểu diễn quan hệ nhân quả hay quan hệ xã hội giữa người tham gia khảo sát. Đồ thị tương đồng này cũng không phải Knowledge Graph Neo4j của Chương 7.')
    section(doc,'6.2 Từ mạng nhiều lớp đến truyền thông điệp','MLP dùng vector thuộc tính của từng mẫu để tính đầu ra. GNN cho phép nút tổng hợp thông tin từ các nút kề trước khi cập nhật biểu diễn. Một lớp có thể viết h_v mới = U(h_v, AGG({h_u: u thuộc N(v)})). AGG cần không phụ thuộc thứ tự hàng xóm; các lựa chọn thường gặp là tổng, trung bình hoặc attention.','Số lớp quyết định phạm vi lan truyền. Hai lớp có thể đưa thông tin từ hai hop vào biểu diễn của nút. Khi graph chứa nhiều cạnh nối khác nhãn hoặc thông tin không liên quan, phép gộp có thể làm mất đặc trưng riêng. Vì vậy baseline chỉ dùng thuộc tính vẫn cần thiết.')
    section(doc,'6.2.1 Mạng tích chập đồ thị GCN','GCN dùng ma trận kề có self-loop và chuẩn hóa đối xứng theo bậc nút. Self-loop giữ thông tin riêng; chuẩn hóa hạn chế tác động của chênh lệch số hàng xóm. Cài đặt thực nghiệm dùng hai phép biến đổi tuyến tính với ReLU ở lớp ẩn. Nguồn phương pháp: Kipf và Welling, https://arxiv.org/abs/1609.02907 .')
    code(doc,'A_tilde = A + I\nS = D^(-1/2) @ A_tilde @ D^(-1/2)\nH = ReLU(S @ X @ W0 + b0)\nlogits = S @ H @ W1 + b1')
    section(doc,'6.2.2 GraphSAGE với phép lấy trung bình','GraphSAGE học hàm tổng hợp thay vì học một embedding riêng cho từng mã nút. Biến thể trong bài ghép vector riêng với trung bình hàng xóm rồi đưa qua Linear và ReLU. Thí nghiệm dùng toàn bộ hàng xóm, không sử dụng lấy mẫu lân cận theo mini-batch. Nguồn phương pháp: Hamilton, Ying và Leskovec, https://arxiv.org/abs/1706.02216 .','Khả năng áp dụng cho nút mới của họ GraphSAGE không đồng nghĩa thí nghiệm này đã đo hiệu quả inductive. Đồ thị trong lần chạy là cố định; cả GCN và GraphSAGE được đánh giá theo cùng giao thức transductive. Đây là điểm cần phân biệt khi diễn giải bảng kết quả.')
    code(doc,'neighbors = mean_adjacency @ X\nH = ReLU(Linear(concat(X, neighbors)))\nlogits = Linear(concat(H, mean_adjacency @ H))')
    section(doc,'6.2.3 Học trên đồ thị và truy vấn tri thức','Trong GNN, trọng số được điều chỉnh theo loss có nhãn. Trong KG của bài, cạnh có nhãn quan hệ và evidence, được dùng để tìm nguồn giải thích bằng Cypher. GNN tạo dự đoán thống kê; traversal tạo tập quan hệ có thể truy vết. Hai kỹ thuật bổ sung ở mức kiến trúc nhưng không thay thế nhau.','Bản demo hiện tại chưa sử dụng GNN cho dự đoán hồ sơ. Việc giữ thí nghiệm graph ở notebook tránh đưa một mô hình mới chỉ đánh giá trên 1.600 mẫu vào luồng dự đoán đang dùng checkpoint khác. Kết nối hai phần là hướng phát triển cần đánh giá riêng.')
    section(doc,'6.3 Dữ liệu CDC và cách tạo đồ thị',f"Dữ liệu nguồn là CSV CDC BRFSS 2015 của project, gồm {m['raw_rows']:,} dòng; sau loại trùng còn {m['deduplicated_rows']:,} dòng. Chọn phân tầng 1.600 dòng với seed 42; 21 thuộc tính làm đầu vào. Nhãn được loại khỏi ma trận đặc trưng trước khi chuẩn hóa và xây cạnh. Có {m['positive_nodes']} nút mang nhãn dương trong tập con.",'StandardScaler chỉ fit các nút train. Sau biến đổi, mỗi nút nối với 10 hàng xóm gần nhất theo khoảng cách Euclid. Ma trận được đối xứng hóa bằng hợp hai chiều; self-loop chỉ thêm cho phép chuẩn hóa GCN. Không sử dụng nhãn để lựa chọn hàng xóm. Chuẩn hóa các cột thứ bậc như Age hoặc Income vẫn áp đặt khoảng cách số học, là một giới hạn của thiết kế tương đồng.')
    br.table(doc,['Thuộc tính','Giá trị'],[['Nút',m['nodes']],['Cạnh vô hướng không self-loop',m['undirected_edges_without_self_loops']],['Số thuộc tính',m['features']],['Train / validation / test','960 / 320 / 320'],['kNN / seed','10 / 42'],['File mẫu có source_row','results/deep_graph/cdc_graph_sample.csv'],['Giao thức','Transductive; nhãn train trong loss']])
    section(doc,'6.4 Cài đặt và lựa chọn mô hình','Ba mô hình MLP, GCN và GraphSAGE đều có lớp ẩn 32 đơn vị. Adam dùng learning rate 0,01, weight decay 0,0005, 80 epoch. BCEWithLogitsLoss có pos_weight tính từ tỷ lệ lớp train. Checkpoint được giữ theo validation loss thấp nhất; threshold quét trên validation F1. Test không được dùng để lựa chọn hai tham số này.','MLP nhận trực tiếp thuộc tính nút. GCN nhận thuộc tính đã tổng hợp bằng S; GraphSAGE ghép thuộc tính và trung bình hàng xóm. Cùng protocol không có nghĩa cùng số tham số: phép ghép của GraphSAGE làm đầu vào Linear rộng hơn. Vì vậy bảng so sánh thể hiện ba cấu hình triển khai, chưa cô lập hoàn toàn ảnh hưởng số tham số.')
    source=(ROOT/'tools/train_graph_chapter.py').read_text(encoding='utf-8')
    code(doc,source[source.index('    class Network'):source.index("    out=ROOT")])
    section(doc,'6.5 Kết quả và nhận xét','Bảng sau được đọc trực tiếp từ results/deep_graph/metrics.json. F1 phản ánh nhãn nhị phân đã gộp; ROC AUC đánh giá thứ hạng score. Không so trực tiếp với F1 của Diabetes Prediction ở Chương 7 vì khác dataset, tập con và giao thức.')
    br.table(doc,['Mô hình','Val F1','Test F1','AUC','Precision','Recall'],[[r['model'],f"{r['validation_f1']:.4f}",f"{r['test_f1']:.4f}",f"{r['test_auc']:.4f}",f"{r['test_precision']:.4f}",f"{r['test_recall']:.4f}"] for r in m['models']])
    selected=next(r for r in m['models'] if r['model']==m['selected_by_validation'])
    text(doc,f"Theo validation F1, cấu hình được chọn là {selected['model']}; test F1 tương ứng {selected['test_f1']:.4f}. Việc chọn này chỉ áp dụng lần chạy seed 42. Nếu model graph không vượt MLP, kết quả cho thấy cạnh tương đồng hiện tại chưa bổ sung đủ thông tin có ích; không nên sửa graph bằng nhãn test để tạo kết quả tốt hơn.")
    br.table(doc,['Mô hình','Epoch tốt nhất','Threshold','Thời gian giây'],[[r['model'],r['best_epoch'],f"{r['threshold']:.2f}",f"{r['seconds']:.2f}"] for r in m['models']])
    section(doc,'6.6 Notebook và tái lập','Notebook 10_deep_graph_cdc.ipynb chứa mã nguồn và output lần thực thi Python. File train_graph_chapter.py cho phép chạy lại; learning.csv giữ loss từng epoch, các tệp pt giữ state_dict và CSV mẫu giữ chỉ số dòng gốc cùng split. Các artifact được lưu trong results/deep_graph để kiểm tra nguồn.','Chạy từ thư mục final: python tools/build_graph_notebook.py. Thí nghiệm không cần Neo4j vì dùng graph ma trận từ CSV; Neo4j phục vụ kho tri thức ở Chương 7. Khi chỉ đọc báo cáo, không cần train lại để xem số đo đã lưu.')
    section(doc,'6.7 Tiểu kết và giới hạn','Chương này bổ sung thí nghiệm học sâu trên đồ thị bằng chính CDC của sinh viên. Điểm mới là có sự so sánh thuộc tính đơn lẻ với tổng hợp hàng xóm, công khai cách tạo cạnh và protocol. Tập con nhỏ, một seed, graph dựa trên khoảng cách và chưa có external validation là các giới hạn trực tiếp. Hướng mở rộng là so nhiều k, nhiều seed và một chia tập inductive thực sự trước khi tích hợp GNN vào ứng dụng.')

def chapter7(doc):
    meta=json.loads((ROOT/'artifacts/pytorch_metadata.json').read_text())
    benchmark=json.loads((ASSETS/'benchmark_snapshot.json').read_text(encoding='utf-8-sig'))
    heading(doc,'CHƯƠNG 7 HỆ ĐA TÁC TỬ',1)
    section(doc,'7.1 Từ tác tử đơn đến hệ đa tác tử','Một tác tử nhận quan sát, giữ trạng thái và chọn hành động nhằm thực hiện mục tiêu. Trong hệ thống phần mềm, hành động có thể là truy xuất tài liệu, gọi model, tính thống kê hoặc yêu cầu thông tin. Tác tử không bắt buộc là LLM; một handler có vai trò và contract rõ ràng vẫn có thể tham gia cơ chế điều phối.','Hệ đa tác tử chia trách nhiệm giữa nhiều thành phần. Lợi ích cần đo là khả năng truy vết, bảo trì, cô lập bước lỗi hoặc chất lượng nhiệm vụ; số lượng tên agent tự nó không phải bằng chứng hiệu quả. Project dùng một baseline Single Agent và một hệ Multi-Agent trên cùng công cụ để tránh tạo lợi thế không công bằng cho hệ nhiều agent.')
    section(doc,'7.2 Kế thừa Agent trong tiểu luận 3','Tiểu luận 3 đã xây dựng bảy vai trò Router, Knowledge, Model, Vision, Sequence, Guard và Coordinator. Router chọn miền; các specialist đọc tri thức hoặc metadata thực nghiệm; Guard đánh dấu supported hoặc needs_human. Sáu kịch bản cũ có ba trường hợp supported và ba cần người xem xét. Đây là kết quả của policy và kịch bản cũ, không phải accuracy.','Phiên bản Final phát triển thành project DiaAgents tập trung vào bệnh tiểu đường: Prediction gọi checkpoint thực thay vì chỉ mô tả metadata; KB được nạp Neo4j; bus ghi lời gọi giữa các handler; Critic đối chiếu hai model; Q-learning đề xuất bước quy trình. Hai phiên bản có corpus và benchmark khác nhau, nên số lượng tài liệu và số đo phải gắn đúng phiên bản.')
    br.table(doc,['Thành phần','Tiểu luận 3','Project Final'],[['Miền','CDC và AAPL, mô tả ML/CNN/RNN','Hồ sơ diabetes và thống kê CDC'],['KB','12 tài liệu, 23 quan hệ','8 tài liệu, 18 thực thể, 16 quan hệ miền'],['Đánh giá','15 câu RAG, 6 kịch bản Agent','58 case cho mỗi Single/Multi'],['Model agent','Đọc metadata kết quả','PyTorch và sklearn suy luận thật'],['Giao tiếp','Pipeline và trace','MessageBus trong tiến trình và trace']])
    section(doc,'7.3 Minh họa learning agent từ bài Agent 01','Demo Agent 01 của sinh viên dùng mê cung từ mẫu maze_curriculum_sample_100.csv. Chuột là agent, phô mai là mục tiêu; mèo di chuyển tạo nguy hiểm. State gồm vị trí chuột, vị trí mèo và pha lượt; action là bốn hướng. Reward là +100 khi đến đích, −100 khi bị bắt, −8 khi va tường và −1 mỗi bước.','Q-learning cập nhật Q(s,a) từ reward và giá trị hành động tốt nhất ở trạng thái kế tiếp. Trong demo này chỉ chuột học; mèo là động lực môi trường theo quy tắc. Vì thế không gọi đây là hai agent cùng học đối kháng. Notebook gốc giải mê cung và đối chiếu BFS; lớp mèo chuyển động là phần trực quan được bổ sung trên web.','File demo: agent01/demo/index.html trong workspace assignment3. Bấm Huấn luyện 5.000, sau đó Đi 1 bước hoặc Chạy tự động. Không dùng số lần thắng của phiên trình duyệt chưa lưu như kết quả benchmark của project diabetes.')
    code(doc,'Q[s, a] += alpha * (reward + gamma * max(Q[next_s]) - Q[s, a])')
    section(doc,'7.4 Dữ liệu và nhiệm vụ của DiaAgents','Project Final sử dụng Diabetes Prediction Dataset 100.000 dòng để dự đoán nhãn diabetes; sau loại trùng còn 99.986 dòng. Tám đầu vào gồm giới tính, tuổi, BMI, HbA1c, glucose, tiền sử hút thuốc, tăng huyết áp và bệnh tim. CDC BRFSS 2015 có 253.680 dòng dùng thống kê nhóm. Không dùng NHANES hoặc BRFSS nhiều năm của bài Kiên.','CDC được thống kê bằng điều kiện Diabetes_012 > 0, gộp tiền tiểu đường và tiểu đường. Tỷ lệ là mô tả mẫu không trọng số, không phải tỷ lệ dân số. Một tỷ lệ nhóm không được thay cho score cá nhân từ dataset khác. Câu hỏi kiến thức dùng corpus WHO, CDC, NIDDK và model card của project.')
    br.table(doc,['Nguồn trong project','Vai trò','Đầu ra'],[['data/diabetes_prediction_dataset.csv','Train model nhị phân','Probability, threshold, class'],['data/cdc_brfss_2015.csv','Thống kê nhóm','Tử số, mẫu số, tỷ lệ'],['knowledge/corpus.json','Nguồn nhập Neo4j','Văn bản, URL, metadata'],['knowledge/graph.json','Quan hệ có evidence','Đường đi và nguồn'],['results/benchmark_cases.json','Case đối chiếu kiến trúc','58 tình huống có contract']])
    section(doc,'7.5 Mô hình ML và deep learning',f"Các baseline sklearn gồm Logistic Regression, Random Forest và MLP. Demo mở rộng dùng mạng PyTorch 15–64–32–1, Dropout 0,15 và threshold {meta['threshold']:.2f}; checkpoint sklearn được giữ làm ý kiến đối chiếu. PyTorch đạt test F1 {meta['test']['f1']:.4f}, ROC AUC {meta['test']['roc_auc']:.4f}. Lựa chọn PyTorch để minh họa triển khai không có nghĩa nó thắng sklearn theo validation.",'Preprocessing chỉ fit train; checkpoint PyTorch chọn bằng validation loss; threshold chọn bằng validation F1. Hai model cùng nguồn dữ liệu nên đồng thuận không phải bằng chứng y khoa độc lập. Feature impact của service là thay từng đặc trưng bằng baseline rồi đo thay đổi score, không phải SHAP hoặc kết luận nhân quả.')
    section(doc,'7.6 Neo4j Knowledge Base và GraphRAG','Neo4j chứa DiaDocument lưu text và URL; DiaEntity lưu thực thể; DIA_RELATION lưu tên quan hệ và evidence; SUPPORTED_BY nối thực thể với tài liệu. Dữ liệu hiện có 8 tài liệu, 18 thực thể, 16 quan hệ miền và 24 liên kết hỗ trợ. Con số 16 không tính các cạnh SUPPORTED_BY.','KnowledgeService tải tài liệu từ Neo4j, chấm BM25, đồng thời truy vấn các đường tối đa hai hop. Evidence từ graph bổ sung vào danh sách tài liệu, giới hạn tối đa năm nguồn. Câu trả lời chọn các câu có sẵn từ tài liệu. Đây là truy xuất và trích xuất có nguồn; chưa tích hợp LLM hoặc Qdrant, nên không mô tả như sinh ngôn ngữ tự do.')
    code(doc,'MATCH (s:DiaEntity) WHERE s.name IN $seeds\nMATCH p=(s)-[:DIA_RELATION*1..2]-(o:DiaEntity)\nUNWIND relationships(p) AS r\nRETURN DISTINCT startNode(r).name AS subject,\n r.relation AS relation, endNode(r).name AS object,\n r.evidence AS evidence LIMIT 16')
    section(doc,'7.7 Điều phối và phản biện','Coordinator định tuyến intent; Validation kiểm tra schema; Prediction gọi model; Retrieval lấy nguồn; Critic kiểm tra bất đồng nhãn, score gần threshold và thiếu citation. WorkflowRL đề xuất bước kế tiếp. Explanation tổng hợp đầu ra và Verifier kiểm tra trạng thái. Nhánh thống kê dùng phép đếm trực tiếp, nhánh nguy hiểm hoặc ngoài phạm vi kết thúc sớm.','MessageBus đăng ký handler, gửi REQUEST và nhận INFORM; khi có phản biện gửi CHALLENGE và nhận RESPONSE. Lỗi được ghi FAILURE rồi ném lên lớp gọi. Đây là dispatch thật trong một tiến trình, chưa phải các LLM độc lập hoặc broker phân tán. Phản hồi của Prediction giải thích checkpoint và ngưỡng, không tự sửa score để tạo đồng thuận.')
    figure(doc,ROOT/'report/assets/flow_project_bw.png','Hình 7.1 Luồng xử lý DiaAgents',maxheight=12)
    section(doc,'7.8 Học tăng cường cho bước quy trình','Q-learning dùng ba biến Boolean: thiếu thông tin, có bằng chứng, cần người xem xét; tổng cộng tám trạng thái. Bốn hành động là hỏi thêm, hiển thị nguồn, giải thích score và yêu cầu kiểm tra. Policy học 3.000 episode trong môi trường quy trình tổng hợp. Reward cho bước bổ sung thông tin là +0,3, chi phí bước là −0,2 và kết thúc phù hợp là +2.','Action mask ép hỏi thêm khi thiếu dữ liệu và ép chuyển kiểm tra khi có cờ review. Reward này không đo hiệu quả sức khỏe; policy không được học từ diễn biến điều trị và không có hành động kê thuốc. Tách phạm vi này giúp demo có phần RL nhưng không gán cho nó năng lực lâm sàng chưa được kiểm chứng.')
    section(doc,'7.9 So sánh Single Agent và Multi-Agent','Hai hệ dùng cùng model, dữ liệu, KB, reviewer và policy. Single thực hiện trong một luồng điều khiển; Multi phân phối lời gọi tới handler và ghi trace chuyên trách. Bộ 58 tình huống mỗi hệ gồm kiến thức, thống kê, prediction, unsafe, outside và invalid. Tiêu chí task success kiểm tra điều kiện đầu ra đã định nghĩa, không chấm toàn bộ chất lượng y khoa của câu trả lời.')
    br.table(doc,['Chỉ số','Single','Multi'],[[key,benchmark[0][key],benchmark[1][key]] for key in ['cases','task_success_rate','routing_accuracy','citation_recall','citation_precision','safety_block_rate','audit_coverage','mean_latency_ms','p95_latency_ms']])
    text(doc,'Task success bằng nhau là kết quả phù hợp khi dùng chung công cụ. Audit coverage của Multi cao hơn do định nghĩa yêu cầu các stage chuyên trách; không diễn giải thành accuracy cao hơn. Latency là một lượt chạy tuần tự Single rồi Multi, có thể chịu ảnh hưởng cache và lần gọi đầu; chưa phải benchmark tải đồng thời. Citation precision dựa trên tập gold tối thiểu, cần gán nhãn đầy đủ hơn khi đánh giá nguồn bổ sung từ graph.')
    section(doc,'7.10 Notebook và cách demo','Mở notebook 08_project_ml_neo4j_multiagent.ipynb để xem lần lượt dữ liệu, PyTorch, Neo4j, graph, so sánh, message bus và policy. Notebook 09_pytorch_training_full.ipynb chứa toàn bộ code train và output; notebook 07 lưu so sánh tổng hợp. Web dùng cùng module src với notebook, không có một logic dự đoán riêng được viết chỉ để biểu diễn.','Demo bắt đầu bằng hồ sơ mẫu và so sánh hai cột. Chỉ ra score PyTorch, score sklearn, backend Neo4j và các thông điệp. Tiếp theo hỏi về A1C, xem nguồn và quan hệ graph; thử thống kê CDC rồi thử hồ sơ lỗi và yêu cầu kê đơn. Giải thích khác biệt giữa kiểm tra schema, suy luận model, truy xuất bằng chứng và chặn yêu cầu trước khi kết luận về kiến trúc.')
    text(doc,'Bảng so sánh sử dụng snapshot của lần chạy đã lưu cùng ảnh notebook, tại report/assets/final_continued/benchmark_snapshot.json. Chạy lại demo có thể làm thay đổi latency; không trộn thời gian của hai lần chạy trong cùng bảng.')
    for number,(idx,caption) in enumerate([(4,'Kết quả huấn luyện PyTorch'),(6,'Truy vấn Neo4j thực tế'),(9,'Thông điệp và trace của Multi-Agent'),(12,'Benchmark hai kiến trúc')],2):
        figure(doc,ROOT/f'report/assets/notebook/cell-{idx:02d}-1.png',f'Hình 7.{number} {caption}',maxheight=18)
    section(doc,'7.11 Triển khai và phạm vi hoàn thành','Bản cục bộ chạy FastAPI ở cổng 8010 và Neo4j trong Docker. Khi triển khai Render cần Neo4j từ xa cùng URI, tài khoản và mật khẩu trong Environment. File local_config không được commit. Checkpoint và dữ liệu đã có trong repository nên demo không cần huấn luyện tại request. Trạng thái triển khai công khai cần được xác nhận bằng URL hoạt động; một file Blueprint không tự chứng minh đã deploy.','Báo cáo Project 01 là tài liệu chi tiết riêng về hệ DiaAgents. Chương này trình bày hệ thống như bước tích hợp của quyển Final, liên hệ các chương trước mà không thay tất cả dữ liệu cũ thành dữ liệu bệnh tiểu đường. Qdrant, hội đồng LLM, broker phân tán và RL điều trị chưa được triển khai.')
    section(doc,'7.12 Tiểu kết','Agent là lớp tổ chức việc dùng mô hình và tri thức. Project đã có inference thật, truy vấn Neo4j, luồng thông điệp và bằng chứng thực thi từ notebook. Kết quả hỗ trợ nhận xét về khả năng quan sát, điều phối và giới hạn công cụ. Chưa có external validation, đánh giá lâm sàng hoặc chứng minh lợi ích của nhiều tác tử cho mọi nhiệm vụ.')

if __name__=='__main__':build()
