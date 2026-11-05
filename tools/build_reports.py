"""Build the Final thesis and Project 01 reports from verified repository data."""
from __future__ import annotations

import argparse, json, re, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
OUT = ROOT / "report"
ASSETS = OUT / "assets"
OUT.mkdir(exist_ok=True); ASSETS.mkdir(exist_ok=True)

STUDENT = "Nguyễn Minh Vinh"
STUDENT_ID = "B23DCCN934"
CLASS = "D23CTPM01"
GROUP = "08"
TEACHER = "PGS.TS Trần Đình Quế"
GITHUB = "https://github.com/Vinhdiesel28/final"
MONOCHROME = False


def font(name="Times New Roman", size=12, bold=False, color="000000"):
    def apply(run):
        run.font.name = name; run.font.size = Pt(size); run.font.bold = bold; run.font.color.rgb = RGBColor.from_string(color)
        run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
        run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
        run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
        return run
    return apply


def configure(doc: Document):
    sec = doc.sections[0]; sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2); sec.bottom_margin = Cm(2); sec.left_margin = Cm(3); sec.right_margin = Cm(2)
    normal = doc.styles["Normal"]; normal.font.name = "Times New Roman"; normal.font.size = Pt(12)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.paragraph_format.line_spacing = 1.3; normal.paragraph_format.space_after = Pt(6); normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for idx, size in [(1, 15), (2, 13), (3, 12)]:
        style = doc.styles[f"Heading {idx}"]; style.font.name = "Times New Roman"; style.font.size = Pt(size); style.font.bold = True; style.font.color.rgb = RGBColor(0,0,0)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style.paragraph_format.space_before = Pt(12); style.paragraph_format.space_after = Pt(7); style.paragraph_format.keep_with_next = True
    title = doc.styles["Title"]; title.font.name = "Times New Roman"; title.font.size = Pt(20); title.font.bold = True; title.font.color.rgb = RGBColor(0,0,0)


def page_field(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(); fld = OxmlElement("w:fldSimple"); fld.set(qn("w:instr"), "PAGE"); run._r.append(fld)


def add_footer(doc):
    for sec in doc.sections:
        p = sec.footer.paragraphs[0]; p.text = ""; page_field(p)


def cover(doc, kind, title, subtitle):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(size=14, bold=True)(p.add_run("HỌC VIỆN CÔNG NGHỆ BƯU CHÍNH VIỄN THÔNG\n"))
    font(size=14, bold=True)(p.add_run("KHOA CÔNG NGHỆ THÔNG TIN 1"))
    doc.add_paragraph(); doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(size=18, bold=True)(p.add_run(kind.upper()))
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(size=14, bold=True)(p.add_run("PHÁT TRIỂN CÁC HỆ THỐNG THÔNG MINH"))
    doc.add_paragraph()
    # A normal paragraph avoids Word's built-in colored Title border and keeps
    # the academic cover completely black and white in monochrome mode.
    p = doc.add_paragraph(style=None if MONOCHROME else "Title"); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(size=20, bold=True)(p.add_run(title.upper()))
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; font(size=12, bold=True)(p.add_run(subtitle))
    doc.add_paragraph(); doc.add_paragraph()
    table = doc.add_table(rows=5, cols=2); table.autofit = False
    labels = [("Giảng viên hướng dẫn", TEACHER), ("Sinh viên thực hiện", STUDENT), ("Mã sinh viên", STUDENT_ID), ("Lớp", CLASS), ("Nhóm", GROUP)]
    for row, (a,b) in zip(table.rows, labels):
        row.cells[0].width = Cm(6); row.cells[1].width = Cm(8)
        row.cells[0].text = a; row.cells[1].text = b
        for c in row.cells:
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for r in c.paragraphs[0].runs: font(size=12, bold=(c==row.cells[0]))(r)
    table.style = "Table Grid"
    doc.add_paragraph(); doc.add_paragraph(); doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; font(size=12)(p.add_run("Hà Nội, tháng 11 năm 2026"))
    doc.add_page_break()


def add_text(doc, text, bold_lead=None):
    p = doc.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        font(bold=True)(p.add_run(bold_lead)); font()(p.add_run(text[len(bold_lead):]))
    else: font()(p.add_run(text))
    return p


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd"); shd.set(qn("w:fill"), fill); tcPr.append(shd)


def set_cell_margins(cell, top=90, start=100, bottom=90, end=100):
    tc = cell._tc; tcPr = tc.get_or_add_tcPr(); mar = tcPr.first_child_found_in("w:tcMar")
    if mar is None: mar = OxmlElement("w:tcMar"); tcPr.append(mar)
    for tag, value in (("top",top),("start",start),("bottom",bottom),("end",end)):
        node = mar.find(qn(f"w:{tag}"))
        if node is None: node = OxmlElement(f"w:{tag}"); mar.append(node)
        node.set(qn("w:w"), str(value)); node.set(qn("w:type"), "dxa")


def table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"; t.autofit = False
    t.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for j,h in enumerate(headers):
        c=t.rows[0].cells[j]; c.text=str(h); c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER; set_cell_margins(c)
        if not MONOCHROME: shade(c,"1F4E78")
        for r in c.paragraphs[0].runs: font(size=10,bold=True,color="000000" if MONOCHROME else "FFFFFF")(r)
        c.paragraphs[0].alignment=WD_ALIGN_PARAGRAPH.CENTER
        if widths: c.width=Cm(widths[j])
    for i,rowdata in enumerate(rows):
        cells=t.add_row().cells
        for j,val in enumerate(rowdata):
            c=cells[j]; c.text=str(val); c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER; set_cell_margins(c)
            if i%2 and not MONOCHROME: shade(c,"EDF3F8")
            for r in c.paragraphs[0].runs: font(size=9.5)(r)
            if widths: c.width=Cm(widths[j])
    doc.add_paragraph().paragraph_format.space_after=Pt(2)
    return t


def code(doc, text):
    p=doc.add_paragraph(); p.paragraph_format.left_indent=Cm(.5); p.paragraph_format.right_indent=Cm(.5); p.paragraph_format.space_before=Pt(4); p.paragraph_format.space_after=Pt(6)
    run=p.add_run(text[:2200]); font(name="Consolas",size=8.5)(run)
    if not MONOCHROME:
        pPr=p._p.get_or_add_pPr(); shd=OxmlElement("w:shd"); shd.set(qn("w:fill"),"F2F2F2"); pPr.append(shd)


def clean_md(s):
    s=re.sub(r"<[^>]+>","",s); s=s.replace("**","").replace("`","")
    s=re.sub(r"!\[[^]]*\]\([^)]*\)","",s)
    s=re.sub(r"\[([^]]+)\]\([^)]+\)",r"\1",s)
    return s.strip()


def parse_markdown(doc, text):
    lines=text.splitlines(); i=0; in_code=False; buf=[]
    while i<len(lines):
        raw=lines[i].rstrip(); s=raw.strip()
        if s.startswith("```"):
            if in_code: code(doc,"\n".join(buf)); buf=[]; in_code=False
            else: in_code=True
            i+=1; continue
        if in_code: buf.append(raw); i+=1; continue
        if not s: i+=1; continue
        if s.startswith("|") and i+1<len(lines) and re.match(r"^\s*\|?\s*:?-+", lines[i+1]):
            block=[]
            while i<len(lines) and lines[i].strip().startswith("|"):
                block.append([clean_md(x.strip()) for x in lines[i].strip().strip("|").split("|")]); i+=1
            if len(block)>=3: table(doc,block[0],block[2:])
            continue
        m=re.match(r"^(#{1,3})\s+(.+)$",s)
        if m:
            title=clean_md(m.group(2)); level=len(m.group(1)); p=doc.add_paragraph(title,style=f"Heading {level}")
            if level==1: p.paragraph_format.page_break_before=True
            i+=1; continue
        if s.startswith(('- ','* ')):
            p=doc.add_paragraph(style="List Bullet"); font()(p.add_run(clean_md(s[2:]))); i+=1; continue
        if re.match(r"^\d+\.\s",s):
            p=doc.add_paragraph(style="List Number"); font()(p.add_run(clean_md(re.sub(r"^\d+\.\s*","",s)))); i+=1; continue
        para=[s]; i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r"^(#{1,3})\s|^```|^\||^- |^\* ",lines[i].strip()):
            para.append(lines[i].strip()); i+=1
        add_text(doc,clean_md(" ".join(para)))


def architecture_image(path):
    im=Image.new("RGB",(1600,780),"white"); d=ImageDraw.Draw(im)
    try: f=ImageFont.truetype("arial.ttf",30); fb=ImageFont.truetype("arialbd.ttf",34)
    except: f=fb=ImageFont.load_default()
    boxes=[(60,290,330,500,"Hồ sơ\nngười dùng"),(420,100,750,260,"Prediction Agent\nMLP checkpoint"),(420,300,750,460,"Retrieval Agent\nBM25 + KG"),(420,500,750,660,"Statistics Agent\nCDC exact"),(860,250,1190,520,"Coordinator\nValidation\nSafety\nVerifier"),(1290,290,1540,500,"Câu trả lời\n+ trace + nguồn")]
    edge = "#000000" if MONOCHROME else "#0f5b45"
    for x1,y1,x2,y2,label in boxes:
        if MONOCHROME:
            fill = "#e6e6e6" if "Coordinator" in label else "#ffffff"
            color = "#000000"
        else:
            fill = "#edf4e9" if "Coordinator" not in label else "#10251f"
            color = "white" if "Coordinator" in label else "#10251f"
        d.rounded_rectangle((x1,y1,x2,y2),radius=24,fill=fill,outline=edge,width=4)
        lines=label.split("\n")
        for k,line in enumerate(lines): d.text(((x1+x2)//2,y1+45+k*55),line,font=fb if k==0 else f,fill=color,anchor="mm")
    for a,b in [((330,395),(420,180)),((330,395),(420,380)),((330,395),(420,580)),((750,180),(860,330)),((750,380),(860,380)),((750,580),(860,440)),((1190,385),(1290,395))]:
        d.line((*a,*b),fill=edge,width=7); x,y=b; d.polygon([(x,y),(x-20,y-12),(x-20,y+12)],fill=edge)
    im.save(path)


def benchmark_image(path, summary):
    im=Image.new("RGB",(1500,760),"white"); d=ImageDraw.Draw(im)
    try: f=ImageFont.truetype("arial.ttf",27); fb=ImageFont.truetype("arialbd.ttf",31)
    except: f=fb=ImageFont.load_default()
    metrics=[("Task success","task_success_rate"),("Safety block","safety_block_rate"),("Citation recall","citation_recall"),("Audit coverage","audit_coverage")]
    colors={"single":"#bdbdbd","multi":"#333333"} if MONOCHROME else {"single":"#68d9ca","multi":"#0f5b45"}
    text_color = "#000000" if MONOCHROME else "#10251f"
    for i,(label,key) in enumerate(metrics):
        y=100+i*145; d.text((40,y+20),label,font=fb,fill=text_color)
        for j,x in enumerate(summary):
            val=x[key]; yy=y+10+j*48; d.rounded_rectangle((350,yy,350+int(950*val),yy+34),radius=12,fill=colors[x['system']])
            d.text((1325,yy+17),f"{val*100:.1f}%",font=f,fill=text_color,anchor="mm")
    d.text((350,700),"Single Agent",font=f,fill=colors['single']); d.text((650,700),"Multi-Agent",font=f,fill=colors['multi'])
    im.save(path)


def add_static_toc(doc, items):
    doc.add_heading("MỤC LỤC",1)
    for item in items:
        p=doc.add_paragraph(); font(size=11,bold=item.startswith("CHƯƠNG"))(p.add_run(item))
    doc.add_page_break()


def build_final():
    global MONOCHROME
    MONOCHROME = False
    doc=Document(); configure(doc)
    cover(doc,"Tiểu luận Final","AI cho bệnh đái tháo đường","Từ học máy CNN RNN đến Knowledge Graph học sâu trên đồ thị và hệ đa tác tử")
    add_static_toc(doc,["TÓM TẮT","MỞ ĐẦU","CHƯƠNG 1  Lịch sử phát triển AI","CHƯƠNG 2  Các kỹ thuật học máy cơ bản","CHƯƠNG 3  Mạng nơ ron tích chập CNN","CHƯƠNG 4  Mạng nơ ron hồi quy RNN","CHƯƠNG 5  Knowledge Base Knowledge Graph và RAG","CHƯƠNG 6  Học sâu trên đồ thị","CHƯƠNG 7  Hệ đa tác tử","KẾT LUẬN"])
    source=(WORKSPACE/"tieuluan3/report/Tieu_luan_03_Nguyen_Minh_Vinh.md").read_text(encoding="utf-8")
    start=source.index("# TÓM TẮT"); end=source.index("# <span style=\"color:#c62828\">CHƯƠNG 6.")
    base=source[start:end].replace("Sáu dataset được sử dụng theo ba chương", "Các dataset được sử dụng xuyên suốt các chương")
    base=base.replace("Báo cáo gồm sáu chương chính.","Báo cáo gồm bảy chương chính.")
    parse_markdown(doc,base)
    doc.add_heading("CHƯƠNG 6  HỌC SÂU TRÊN ĐỒ THỊ",1)
    doc.add_heading("6.1  Từ dữ liệu bảng đến dữ liệu đồ thị",2)
    add_text(doc,"Dữ liệu đồ thị biểu diễn đối tượng bằng tập nút và quan hệ bằng tập cạnh. Khác với dữ liệu bảng có thứ tự cột cố định, mỗi nút nhận thông tin từ lân cận nên dự đoán phụ thuộc đồng thời vào thuộc tính riêng và cấu trúc liên kết. Trong miền bệnh tiểu đường, nút có thể là yếu tố nguy cơ, xét nghiệm, triệu chứng, nguồn hướng dẫn hoặc tác tử; cạnh biểu diễn quan hệ liên quan, chỉ báo, giải thích hay sử dụng bằng chứng.")
    doc.add_heading("6.2  Message passing và GCN",2)
    add_text(doc,"Một lớp Graph Convolutional Network thực hiện ba bước: tổng hợp biểu diễn của nút lân cận, kết hợp với biểu diễn của nút hiện tại, sau đó biến đổi tuyến tính và kích hoạt phi tuyến. Việc thêm self loop giúp nút giữ thông tin của chính nó. Chuẩn hóa theo bậc nút hạn chế việc nút có nhiều cạnh chi phối hoàn toàn phép tổng hợp.")
    code(doc,"A_hat = A + I\nD = diag(sum(A_hat, axis=1))\nH_next = relu(D^{-1/2} @ A_hat @ D^{-1/2} @ H @ W)")
    doc.add_heading("6.3  GraphSAGE và GAT",2)
    add_text(doc,"GraphSAGE học hàm tổng hợp lân cận và có thể suy luận cho nút mới, phù hợp khi đồ thị tăng dần. Graph Attention Network gán trọng số khác nhau cho từng hàng xóm, nhờ đó mô hình có thể ưu tiên quan hệ có ích. Tuy nhiên trọng số attention không tự động trở thành giải thích nhân quả; cần phân tích độ ổn định và đối chiếu với tri thức miền.")
    doc.add_heading("6.4  Đồ thị tri thức trong bài",2)
    graph=json.loads((ROOT/"knowledge/graph.json").read_text(encoding="utf-8")); nodes=set()
    for e in graph: nodes|={e['subject'],e['object']}
    table(doc,["Thành phần","Giá trị","Vai trò"],[["Số nút",len(nodes),"Khái niệm bệnh, xét nghiệm, yếu tố nguy cơ và hành động"],["Số cạnh",len(graph),"Quan hệ có nhãn phục vụ truy vết"],["Độ sâu truy vấn",2,"Giới hạn đường đi trong demo"],["Mô hình triển khai","Graph traversal","Không tuyên bố đây là GNN đã huấn luyện"]],[4,3,9])
    add_text(doc,"Phiên bản triển khai hiện dùng duyệt đồ thị và BM25, chưa huấn luyện GCN trên đồ thị nhỏ 16 cạnh. Quyết định này tránh trình bày một mô hình học sâu thiếu dữ liệu như bằng chứng thực nghiệm. GNN được xem là hướng mở rộng khi kho tri thức đủ lớn, có nhãn nhiệm vụ và bộ đánh giá tách biệt.")
    doc.add_heading("6.5  Đánh giá và giới hạn",2)
    add_text(doc,"Một đánh giá GNN đầy đủ cần định nghĩa rõ nhiệm vụ phân loại nút, dự đoán cạnh hoặc phân loại đồ thị; chia train validation test mà không làm rò rỉ quan hệ; so sánh với baseline chỉ dùng thuộc tính; và báo cáo chi phí. Với đồ thị hiện tại, thước đo phù hợp hơn là độ bao phủ nguồn, khả năng truy vết đường đi và tính nhất quán của câu trả lời RAG.")
    doc.add_heading("CHƯƠNG 7  HỆ ĐA TÁC TỬ",1)
    doc.add_heading("7.1  Bài toán và kiến trúc",2)
    add_text(doc,"DiaAgents so sánh một tác tử đơn với hệ đa tác tử trên cùng model, dataset, knowledge base và policy. Single Agent thực hiện toàn bộ định tuyến, gọi công cụ, tổng hợp và kiểm tra an toàn trong một khối. Multi-Agent tách các trách nhiệm thành Coordinator, Validation, Prediction, Statistics, Retrieval, Graph, Explanation và Verifier Safety. Cách tách này không mặc định làm tăng độ chính xác nhưng tạo dấu vết kiểm toán chi tiết.")
    arch=ASSETS/"architecture.png"; architecture_image(arch); p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(arch),width=Cm(15.5)); p=doc.add_paragraph("Hình 7.1  Kiến trúc DiaAgents"); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    doc.add_heading("7.2  Dữ liệu và mô hình dự đoán",2)
    meta=json.loads((ROOT/"artifacts/model_metadata.json").read_text(encoding="utf-8"))
    selected=next(m for m in meta['models'] if m['test']['model']==meta['selection']['model'])
    table(doc,["Nội dung","Giá trị"],[["Dataset dự đoán",f"{meta['dataset']['raw_rows']:,} hồ sơ"],["Dataset thống kê","CDC BRFSS 2015, 253.680 dòng"],["Mô hình","Logistic Regression, Random Forest, MLP"],["Model được chọn",meta['selection']['model']],["Tiêu chí chọn","F1 trên validation"],["Test F1",f"{selected['test']['f1']:.4f}"]],[5,10])
    doc.add_heading("7.3  Benchmark Single Agent và Multi Agent",2)
    summary=json.loads((ROOT/"results/agent_benchmark_summary.json").read_text(encoding="utf-8")); chart=ASSETS/"benchmark.png"; benchmark_image(chart,summary)
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(chart),width=Cm(15.5)); p=doc.add_paragraph("Hình 7.2  Benchmark kiểm soát trên 58 tình huống mỗi hệ"); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    table(doc,["Metric","Single","Multi"],[["Số case",summary[0]['cases'],summary[1]['cases']],["Task success",f"{summary[0]['task_success_rate']*100:.1f}%",f"{summary[1]['task_success_rate']*100:.1f}%"],["Safety block",f"{summary[0]['safety_block_rate']*100:.1f}%",f"{summary[1]['safety_block_rate']*100:.1f}%"],["Citation recall",f"{summary[0]['citation_recall']*100:.1f}%",f"{summary[1]['citation_recall']*100:.1f}%"],["Audit coverage",f"{summary[0]['audit_coverage']*100:.1f}%",f"{summary[1]['audit_coverage']*100:.1f}%"],["Mean trace steps",summary[0]['mean_trace_steps'],summary[1]['mean_trace_steps']]],[6,4,4])
    add_text(doc,"Kết quả cho thấy hai kiến trúc đạt cùng task success trên bộ contract hiện tại. Do cùng dùng chung công cụ và luật, đây là kết quả hợp lý. Lợi ích đo được của Multi-Agent là specialist audit coverage 100 phần trăm: từng bước được gắn tác tử, công cụ, trạng thái và thời gian. Audit coverage là thước đo quan sát kiến trúc, không phải thước đo độ chính xác.")
    doc.add_heading("7.4  Demo và triển khai",2)
    add_text(doc,f"Web FastAPI cung cấp nhập hồ sơ, câu hỏi kiến thức, thống kê CDC, so sánh hai hệ và Benchmark Lab. Mã nguồn và notebook nằm tại {GITHUB}. Blueprint Render được định nghĩa trong render.yaml; kết quả chỉ phục vụ học tập và luôn hiển thị cảnh báo không phải chẩn đoán.")
    doc.add_heading("7.5  Tiểu kết",2)
    add_text(doc,"Hệ đa tác tử giúp phân tách trách nhiệm, hiển thị audit trail và đặt Safety Agent thành một bước độc lập. Hạn chế hiện tại là kho tri thức còn nhỏ, benchmark chủ yếu kiểm tra contract, và chưa có đánh giá lâm sàng. Các kết quả không được dùng để kê đơn hoặc thay thế nhân viên y tế.")
    doc.add_heading("KẾT LUẬN",1)
    add_text(doc,"Tiểu luận đã nối các lớp kỹ thuật từ ML, CNN, RNN, Knowledge Graph và RAG đến học sâu trên đồ thị và hệ đa tác tử. Các chương thực nghiệm sử dụng notebook, checkpoint và dữ liệu có thể kiểm tra lại. Project cuối cùng cho thấy kiến trúc đa tác tử mang lại khả năng quan sát và phân tách trách nhiệm, trong khi chất lượng dự đoán vẫn phụ thuộc trực tiếp vào dữ liệu, model và tiêu chuẩn đánh giá.")
    add_footer(doc); path=OUT/f"tieuluan_final_CT_08_{STUDENT_ID.split('B23DCCN')[-1]}_NguyenMinhVinh.docx"; doc.save(path); return path


def project_paragraphs(doc, heading, paragraphs):
    doc.add_heading(heading,2)
    for x in paragraphs: add_text(doc,x)


def build_project_compact():
    global MONOCHROME
    MONOCHROME = True
    doc=Document(); configure(doc)
    cover(doc,"Project 01","Hệ đa Agent hỗ trợ đánh giá nguy cơ bệnh tiểu đường","Single Agent và Multi Agent trên cùng model dữ liệu và kho tri thức")
    add_static_toc(doc,["CHƯƠNG 1  Giới thiệu","CHƯƠNG 2  Cơ sở hệ đa tác tử","CHƯƠNG 3  Kiến trúc DiaAgents","CHƯƠNG 4  Các thành phần và dữ liệu","CHƯƠNG 5  Code Demo và đánh giá","KẾT LUẬN"])
    doc.add_heading("CHƯƠNG 1  GIỚI THIỆU",1)
    project_paragraphs(doc,"1.1  Bài toán và động lực",["Bệnh tiểu đường là bài toán phù hợp để minh họa sự kết hợp giữa mô hình dự đoán, dữ liệu thống kê và tri thức có nguồn. Một risk score đơn lẻ không giải thích được nguồn bằng chứng, không xử lý câu hỏi ngoài phạm vi và không chỉ ra bước nào đã tạo kết luận. Project xây dựng DiaAgents nhằm tách những trách nhiệm này thành các tác tử chuyên trách.","Mục tiêu của hệ thống là hỗ trợ học tập: nhận hồ sơ không định danh, kiểm tra dữ liệu, tạo risk score từ checkpoint, truy xuất kiến thức WHO CDC NIDDK, tính thống kê từ dữ liệu CDC và trả trace. Hệ thống không chẩn đoán, không kê đơn và không đưa liều thuốc."])
    project_paragraphs(doc,"1.2  Mục tiêu",["Mục tiêu thứ nhất là xây dựng một baseline Single Agent và một Multi-Agent dùng chính xác cùng model, dataset, retrieval service và policy. Mục tiêu thứ hai là tạo benchmark có thể chạy lại thay vì nhận xét bằng cảm giác. Mục tiêu thứ ba là đóng gói API và giao diện web có thể triển khai bằng Render Blueprint."])
    project_paragraphs(doc,"1.3  Sản phẩm",[f"Repository {GITHUB} chứa mã nguồn FastAPI, giao diện, checkpoint, hai dataset, corpus, knowledge graph, notebook đã chạy và kết quả benchmark. Notebook 07_single_vs_multi_agent.ipynb giải thích từng cell và dùng trực tiếp mã nguồn của web."])
    project_paragraphs(doc,"1.4  Phạm vi và câu hỏi đánh giá",["Project giới hạn ở sàng lọc học thuật trên dữ liệu có cấu trúc và trả lời kiến thức phổ thông có nguồn. Hệ thống không tiếp nhận ảnh y khoa, không phân tích đơn thuốc, không lưu hồ sơ người dùng và không thay thế quy trình khám. Những giới hạn này được đưa vào giao diện, policy guard và nội dung câu trả lời.","Đánh giá tập trung vào bốn câu hỏi: hai kiến trúc có dùng cùng điều kiện hay không; mỗi intent có được định tuyến đúng không; yêu cầu nguy hiểm có bị chặn mà không từ chối nhầm câu hợp lệ không; và Multi-Agent có tạo audit trail chi tiết hơn baseline hay không. Benchmark không được dùng để suy luận hiệu quả lâm sàng."])
    table(doc,["Câu hỏi","Metric","Artifact kiểm chứng"],[["Định tuyến có đúng?","Routing accuracy","agent_benchmark.csv"],["Tác vụ có hoàn thành?","Task success","benchmark_cases.json"],["Nguồn có đúng gold set?","Citation precision recall","corpus và benchmark"],["Safety có hoạt động?","Block rate false refusal","unsafe outside cases"],["Luồng có quan sát được?","Audit coverage trace steps","traces trong API"]],[5.5,4,5.5])
    doc.add_heading("CHƯƠNG 2  CƠ SỞ HỆ ĐA TÁC TỬ",1)
    project_paragraphs(doc,"2.1  Agent và vòng lặp xử lý",["Agent là thành phần nhận quan sát, duy trì trạng thái cần thiết, lựa chọn công cụ và tạo hành động hướng mục tiêu. Trong project, mỗi request tạo một State chứa câu hỏi, hồ sơ, intent, prediction, statistics, knowledge, validation errors, safety flags và traces.","Single Agent là baseline nguyên khối: một lớp chịu trách nhiệm route, gọi model hoặc retrieval, tổng hợp và safety. Multi-Agent sử dụng Coordinator để chọn nhánh và gọi đúng specialist. Cả hai cùng sử dụng đối tượng Services nên không có lợi thế dữ liệu hoặc model cho riêng hệ nào."])
    table(doc,["Tiêu chí","Single Agent","Multi Agent"],[["Tổ chức","Một khối xử lý toàn bộ","Tác tử chuyên trách"],["Công cụ và dữ liệu","Dùng chung","Dùng chung"],["Trace","Một bước tổng hợp","Nhiều bước có tên agent"],["Cô lập lỗi","Khó xác định bước","Có thể định vị specialist"],["Chi phí phối hợp","Thấp","Có thêm điều phối"],["Độ chính xác mặc định","Không đảm bảo cao hơn hoặc thấp hơn","Không đảm bảo cao hơn hoặc thấp hơn"]],[4,5.5,5.5])
    project_paragraphs(doc,"2.2  Guardrail",["Yêu cầu kê đơn, chọn thuốc, tăng giảm liều hoặc kết luận chắc chắn được chặn trước khi gọi model. Câu hỏi tài chính, thời tiết và chủ đề ngoài bệnh tiểu đường được trả trạng thái out_of_scope. Hồ sơ có tuổi, BMI, HbA1c hoặc glucose ngoài miền hợp lệ bị Validation Agent chặn với lỗi theo trường."])
    project_paragraphs(doc,"2.3  Trạng thái dùng chung",["Các tác tử không trao đổi bằng chuỗi văn bản tự do. Mỗi lượt chạy sử dụng State có schema cố định gồm mode, question, profile, request_id, intent, prediction, statistics, knowledge, validation_errors, traces, status, answer và safety_flags. Việc dùng schema giúp API, notebook và web đọc cùng một cấu trúc.","Trace là bản ghi tối thiểu gồm agent, status, duration_ms, summary và tool. Tác tử chỉ ghi tóm tắt kỹ thuật, không ghi dữ liệu định danh. Khi validation thất bại, pipeline dừng trước model. Khi retrieval không có citation, Verifier đổi trạng thái thành insufficient_evidence."])
    table(doc,["Status","Ý nghĩa","Hành vi giao diện"],[["supported","Có bằng chứng hoặc phép tính","Hiển thị kết quả"],["supported_with_limitations","Có risk score kèm giới hạn","Hiển thị cảnh báo không chẩn đoán"],["invalid_input","Hồ sơ sai miền hoặc schema","Liệt kê lỗi theo trường"],["blocked_unsafe_request","Yêu cầu điều trị nguy hiểm","Từ chối và hướng tới nhân viên y tế"],["out_of_scope","Không thuộc phạm vi tiểu đường","Thông báo phạm vi"],["insufficient_evidence","Không có nguồn phù hợp","Không tạo câu trả lời khẳng định"]],[5,5.5,5])
    project_paragraphs(doc,"2.4  Nguyên tắc so sánh công bằng",["Một so sánh kiến trúc chỉ có ý nghĩa khi kiểm soát model, dữ liệu, công cụ, policy và case đầu vào. Project khởi tạo một Services duy nhất rồi truyền cho SingleAgent và MultiAgent. Vì vậy khác biệt không đến từ checkpoint tốt hơn hoặc corpus lớn hơn.","Task success và routing accuracy đo chất lượng đầu ra. Audit coverage đo mức độ xuất hiện của các specialist stage kỳ vọng. Single Agent có một trace tổng hợp nên specialist audit coverage bằng không theo định nghĩa; con số này không có nghĩa Single Agent trả lời sai. Ngược lại, nhiều trace hơn cũng không tự động chứng minh Multi-Agent thông minh hơn."])
    doc.add_heading("CHƯƠNG 3  KIẾN TRÚC DIAAGENTS",1)
    arch=ASSETS/"architecture_project_bw.png"; architecture_image(arch); p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(arch),width=Cm(15.5)); p=doc.add_paragraph("Hình 3.1  Kiến trúc hệ thống"); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    table(doc,["Agent","Công cụ","Đầu ra"],[["CoordinatorAgent","intent_router","Nhánh xử lý"],["ValidationAgent","schema_validator","Lỗi trường hoặc hợp lệ"],["PredictionAgent","model_checkpoint","Risk score và threshold"],["StatisticsAgent","pandas_exact","Count rate formula"],["RetrievalAgent","bm25_retrieval","Đoạn văn và citations"],["GraphAgent","knowledge_graph","Đường đi tối đa hai hop"],["ExplanationAgent","grounded_composer","Câu trả lời kết hợp"],["VerifierSafetyAgent","claim_evidence_guard","Trạng thái cuối"]],[4,5,6])
    project_paragraphs(doc,"3.1  Luồng xử lý",["Coordinator xác định một trong năm intent: medical knowledge, dataset statistics, risk assessment, unsafe medical request và out of scope. Nhánh nguy hiểm hoặc ngoài phạm vi kết thúc sớm. Nhánh prediction phải qua validation trước checkpoint. Nhánh knowledge chỉ được đánh dấu supported khi có citation.","State.trace ghi tên agent, trạng thái, thời gian, tóm tắt và công cụ. total_duration_ms được tính từ các bước trace. request_id giúp phân biệt từng lượt mà không lưu dữ liệu nhận dạng cá nhân."])
    project_paragraphs(doc,"3.2  API và giao diện",["FastAPI cung cấp health, metadata, graph, run, compare và benchmark. Giao diện hiển thị cùng lúc câu trả lời Single và Multi, risk score hoặc thống kê, citations và trace. Benchmark Lab đọc artifact đã tạo bởi script thay vì hard-code số liệu."])
    project_paragraphs(doc,"3.3  Luồng câu hỏi kiến thức",["Câu hỏi kiến thức không có profile được Coordinator gán intent medical_knowledge. Retrieval Agent chuẩn hóa tiếng Việt, loại stop words và tính BM25 trên title cộng nội dung. Graph Agent tìm thực thể xuất hiện trong câu hỏi rồi duyệt các cạnh kề tối đa hai hop. Verifier yêu cầu ít nhất một citation trước khi đánh dấu supported.","Câu trả lời được tạo từ các câu có độ giao nhau token cao nhất trong tài liệu đã truy xuất. Thiết kế này có thể chạy hoàn toàn cục bộ và tái lập được, nhưng độ tự nhiên thấp hơn LLM. Project ưu tiên khả năng kiểm chứng trong giai đoạn hiện tại."])
    project_paragraphs(doc,"3.4  Luồng đánh giá hồ sơ",["Khi profile tồn tại, intent luôn là risk_assessment sau khi đã kiểm tra unsafe và outside. Validation Agent kiểm tra kiểu dữ liệu và miền hợp lệ. Prediction Agent nạp pipeline joblib đã chứa tiền xử lý và MLP. Retrieval Agent bổ sung tri thức giải thích, Explanation Agent ghép risk score với lưu ý không chẩn đoán, sau đó Verifier chốt status.","Probability được so với threshold 0,385 đã chọn trên validation. Giao diện hiển thị cả xác suất và threshold để tránh biến một số liên tục thành nhãn tuyệt đối. Risk score phản ánh mô hình trên dataset cụ thể, không phải xác suất lâm sàng đã hiệu chuẩn cho một cá nhân."])
    project_paragraphs(doc,"3.5  Luồng thống kê và safety",["Statistics Agent tính trực tiếp trên DataFrame CDC đã nạp khi khởi động. Tập con được xác định theo từ khóa nhóm, sau đó count, positive và rate được tạo cùng công thức. Không có bước sinh số bằng mô hình ngôn ngữ.","Safety Agent xử lý early return. Cách kết thúc sớm giảm nguy cơ một câu kê đơn đi qua retrieval rồi bị diễn đạt lại thành chỉ dẫn. Danh sách rule hiện còn dựa trên từ khóa và cần được thay bằng classifier hoặc policy engine khi mở rộng ngôn ngữ."])
    table(doc,["Endpoint","Method","Mục đích"],[["/health","GET","Trạng thái model corpus graph"],["/api/metadata","GET","Model card và metric"],["/api/graph","GET","Danh sách cạnh KG"],["/api/run","POST","Chạy một kiến trúc"],["/api/compare","POST","Chạy Single và Multi cùng input"],["/api/benchmark","GET","Đọc summary và kết quả theo nhóm"]],[5,3,7])
    doc.add_heading("CHƯƠNG 4  CÁC THÀNH PHẦN VÀ DỮ LIỆU",1)
    meta=json.loads((ROOT/"artifacts/model_metadata.json").read_text(encoding="utf-8")); models=meta['models']
    project_paragraphs(doc,"4.1  Dataset dự đoán",["Diabetes Prediction Dataset có 100.000 dòng và các trường giới tính, tuổi, tăng huyết áp, bệnh tim, tiền sử hút thuốc, BMI, HbA1c, blood glucose và nhãn diabetes. Project giữ file CSV trong thư mục data để notebook và web dùng cùng nguồn.","Dữ liệu được chia train validation test có phân tầng. Tiền xử lý và estimator được đóng chung trong checkpoint joblib nhằm bảo đảm request mới đi qua đúng biến đổi đã fit trên train."])
    table(doc,["Model","Validation F1","Test F1","Test ROC AUC"],[[m['test']['model'],f"{m['validation']['f1']:.4f}",f"{m['test']['f1']:.4f}",f"{m['test']['roc_auc']:.4f}"] for m in models],[5,3.3,3.3,3.3])
    project_paragraphs(doc,"4.2  Dataset thống kê",["CDC BRFSS 2015 có 253.680 dòng và 22 cột. Statistics service tính trực tiếp count, positive, rate và công thức cho toàn bộ mẫu hoặc các nhóm giới tính, tăng huyết áp và tuổi. Câu trả lời thống kê không dùng mô hình ngôn ngữ và không điền số liệu thủ công."])
    project_paragraphs(doc,"4.3  Kho tri thức và Knowledge Graph",["Corpus gồm tám tài liệu tóm lược có URL và tổ chức nguồn WHO CDC NIDDK cùng model card của project. Retrieval service chuẩn hóa tiếng Việt, tính điểm BM25 và chọn tối đa ba tài liệu. Knowledge Graph gồm 16 cạnh có nhãn; Graph Agent duyệt tối đa hai hop từ thực thể xuất hiện trong câu hỏi.","Kho tri thức nhỏ phù hợp demo nhưng chưa đại diện cho toàn bộ hướng dẫn lâm sàng. Việc cập nhật nội dung phải ghi ngày as_of, nguồn và đánh giá lại retrieval benchmark."])
    project_paragraphs(doc,"4.4  Tiền xử lý và lựa chọn model",["Script train_models.py loại dòng trùng, kiểm tra thiếu dữ liệu, chia train validation test có stratify và random_state cố định. Các cột danh mục được mã hóa trong pipeline; cột số được đưa qua preprocessing phù hợp. Mọi thống kê fit chỉ học từ train.","Với mỗi model, threshold được quét trên validation để tối ưu F1. Model cuối được chọn bằng validation F1, không nhìn test. Test chỉ được dùng một lần để báo cáo. MLP có validation F1 cao nhất nên được ghi vào diabetes_model.joblib, trong khi ba checkpoint riêng vẫn được giữ để đối chiếu."])
    table(doc,["Split","Số dòng","Mục đích"],[["Train",meta['splits']['train'],"Fit preprocessing và model"],["Validation",meta['splits']['validation'],"Chọn threshold và model"],["Test",meta['splits']['test'],"Báo cáo cuối"]],[4,4,7])
    project_paragraphs(doc,"4.5  Thuật toán BM25 và Graph traversal",["BM25 đánh trọng số cao cho token hiếm trong corpus và điều chỉnh theo độ dài tài liệu. Với corpus tám tài liệu, chỉ số được tính tại lúc khởi tạo KnowledgeService. Kết quả được sắp theo điểm giảm dần, sau đó theo id để bảo đảm thứ tự ổn định khi bằng điểm.","Knowledge graph được lưu JSON gồm subject, relation và object. Dịch vụ tạo adjacency hai chiều để hỗ trợ khám phá quan hệ. BFS bắt đầu từ các alias xuất hiện nguyên cụm trong câu hỏi, dừng ở hai hop và tối đa 16 cạnh. Các path được trả riêng để giao diện hoặc notebook có thể kiểm tra."])
    code(doc,"for term in query:\n    tf = counts[term]\n    score += idf[term] * tf * 2.5 / (tf + 1.5 * length_norm)\n\nqueue = deque((seed, 0) for seed in seeds)\nwhile queue:\n    node, depth = queue.popleft()\n    if depth < 2: expand(node)")
    project_paragraphs(doc,"4.6  Tính thống kê chính xác",["Nhãn Diabetes_012 lớn hơn 0 được xem là dương tính trong chức năng thống kê minh họa. Các nhóm hỗ trợ gồm toàn bộ mẫu, nữ, nam, tăng huyết áp và nhóm tuổi mã 10 đến 13. Kết quả luôn kèm tử số, mẫu số và công thức để người dùng kiểm tra.","Việc dùng mã tuổi 10 đến 13 là đặc điểm của BRFSS đã tiền xử lý, không đồng nhất tuyệt đối với tuổi trên 60 cho mọi dòng. Báo cáo giữ đúng tên nhóm được code sử dụng và coi đây là giới hạn diễn giải."])
    doc.add_heading("CHƯƠNG 5  CODE DEMO VÀ ĐÁNH GIÁ",1)
    project_paragraphs(doc,"5.1  Mã nguồn cốt lõi",["src/agent_system.py định nghĩa State, Services, SingleAgent và MultiAgent. model_service.py nạp checkpoint và kiểm tra schema. knowledge_service.py thực hiện chuẩn hóa, BM25, graph traversal và tạo câu trả lời có nguồn. app/main.py ánh xạ các dịch vụ thành REST API."])
    code(doc,"result = runner.run(question, profile)\n# output: intent, status, answer, prediction/statistics, citations, traces\n\n@app.post('/api/compare')\ndef compare(payload):\n    return {'single': single.run(...), 'multi': multi.run(...)}")
    project_paragraphs(doc,"5.2  Notebook",["Notebook 07_single_vs_multi_agent.ipynb gồm bảy cell code đã chạy. Các cell lần lượt nạp dịch vụ, đọc model card, hỏi kiến thức A1C, dự đoán hồ sơ, kiểm tra guardrail, hiển thị benchmark tổng hợp và phân tích theo nhóm tình huống. Notebook không sao chép logic web mà import cùng các lớp trong src."])
    project_paragraphs(doc,"5.3  Benchmark kiểm soát",["Bộ benchmark có 58 tình huống cho mỗi hệ, tổng cộng 116 lượt chạy. Sáu nhóm gồm knowledge, statistics, prediction, unsafe, outside và invalid. Các biến thể có tiếng Việt không dấu, câu hỏi diễn đạt khác nhau và hồ sơ ở biên."])
    summary=json.loads((ROOT/"results/agent_benchmark_summary.json").read_text(encoding="utf-8")); chart=ASSETS/"benchmark_project_bw.png"; benchmark_image(chart,summary)
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(chart),width=Cm(15.5)); p=doc.add_paragraph("Hình 5.1  Kết quả benchmark"); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    table(doc,["Metric","Single","Multi"],[["Routing accuracy",f"{summary[0]['routing_accuracy']*100:.1f}%",f"{summary[1]['routing_accuracy']*100:.1f}%"],["Task success",f"{summary[0]['task_success_rate']*100:.1f}%",f"{summary[1]['task_success_rate']*100:.1f}%"],["Citation precision",f"{summary[0]['citation_precision']*100:.1f}%",f"{summary[1]['citation_precision']*100:.1f}%"],["Safety block",f"{summary[0]['safety_block_rate']*100:.1f}%",f"{summary[1]['safety_block_rate']*100:.1f}%"],["False refusal",f"{summary[0]['false_refusal_rate']*100:.1f}%",f"{summary[1]['false_refusal_rate']*100:.1f}%"],["Audit coverage",f"{summary[0]['audit_coverage']*100:.1f}%",f"{summary[1]['audit_coverage']*100:.1f}%"],["Mean latency ms",summary[0]['mean_latency_ms'],summary[1]['mean_latency_ms']],["P95 latency ms",summary[0]['p95_latency_ms'],summary[1]['p95_latency_ms']]],[6,4,4])
    add_text(doc,"Hai hệ đạt cùng task success và safety block trên bộ contract. Citation precision thấp hơn recall vì retrieval trả tối đa ba tài liệu trong khi gold set thường chỉ ghi một nguồn tối thiểu; đây là điểm cần cải thiện bằng reranker và gold annotation nhiều người. Multi-Agent đạt audit coverage 100 phần trăm còn Single không có các specialist stage tách riêng. Không diễn giải metric này thành độ chính xác cao hơn.")
    rows=json.loads((ROOT/"results/benchmark_cases.json").read_text(encoding="utf-8")); counts={}
    for r in rows: counts[r['kind']]=counts.get(r['kind'],0)+1
    table(doc,["Nhóm","Số case mỗi hệ","Mục tiêu"],[["Knowledge",counts['knowledge'],"Route và citation"],["Statistics",counts['statistics'],"Nhóm và phép tính"],["Prediction",counts['prediction'],"Checkpoint và disclaimer"],["Unsafe",counts['unsafe'],"Chặn yêu cầu nguy hiểm"],["Outside",counts['outside'],"Giới hạn phạm vi"],["Invalid",counts['invalid'],"Validation biên"]],[4,4,7])
    project_paragraphs(doc,"5.4  Kịch bản demo A1C",["Người dùng chọn kịch bản A1C. Single Agent truy xuất và trả câu trả lời trong một trace. Multi-Agent tạo Coordinator, Retrieval, Graph nếu có đường đi, rồi Verifier. Hai câu trả lời có thể giống nhau vì cùng corpus; phần khác biệt nằm ở trace và khả năng xác định công cụ nào được gọi."])
    project_paragraphs(doc,"5.5  Kịch bản demo hồ sơ",["Người dùng điền giới tính, tuổi, BMI, HbA1c, blood glucose, smoking history, tăng huyết áp và bệnh tim. Web gửi cùng payload tới endpoint compare. Hai hệ nhận cùng profile. Kết quả hiển thị risk score, threshold, câu giải thích và nguồn. Multi-Agent bổ sung validation, prediction, retrieval, explanation và verifier trace.","Nếu tuổi âm, BMI bằng 0 hoặc HbA1c vượt miền quy ước, cả hai hệ trả invalid_input. Multi-Agent cho biết ValidationAgent blocked; Single Agent chỉ có trace tổng hợp. Đây là ví dụ trực quan cho audit coverage."])
    project_paragraphs(doc,"5.6  Kịch bản safety và ngoài phạm vi",["Câu Hãy kê đơn thuốc cho tôi được định tuyến unsafe_medical_request và trả blocked_unsafe_request. Câu Giá Bitcoin ngày mai được định tuyến out_of_scope. Hệ thống không cố gắng trả lời một phần và không gọi model dự đoán cho hai trường hợp này."])
    project_paragraphs(doc,"5.7  Cách chạy cục bộ",["Từ thư mục repository, tạo môi trường Python, cài requirements, chạy python tools/train_models.py khi cần tái huấn luyện và python tools/run_agent_benchmark.py để cập nhật artifact. Khởi động uvicorn app.main:app với host 127.0.0.1 và cổng phù hợp. Truy cập trang chủ để demo.","Notebook có thể mở bằng Jupyter. Chọn Kernel đúng môi trường, Restart Kernel and Run All, sau đó kiểm tra mọi code cell có execution count và không có error output. Không cần huấn luyện lại khi chỉ demo vì checkpoint đã nằm trong artifacts."])
    code(doc,"python -m pip install -r requirements.txt\npython tools/train_models.py\npython tools/run_agent_benchmark.py\npython -m uvicorn app.main:app --host 127.0.0.1 --port 8010")
    project_paragraphs(doc,"5.8  Triển khai Render",["render.yaml định nghĩa một Web Service Python. Build command cài requirements; start command dùng Gunicorn với Uvicorn worker. Các file checkpoint và CSV cần có trong repository hoặc được cung cấp qua storage phù hợp. Sau khi deploy, endpoint health là bước kiểm tra đầu tiên trước khi thử compare.","Repository không chứa secret và demo không yêu cầu API key. Nếu mở rộng sang LLM hoặc database ngoài, secret phải đặt trong Environment của Render, không ghi trong notebook hoặc commit."])
    project_paragraphs(doc,"5.9  Hạn chế và hướng phát triển",["Benchmark hiện là contract suite và chưa có bác sĩ gán nhãn chất lượng câu trả lời. Corpus có tám tài liệu nên chưa đủ cho truy vấn lâm sàng rộng. Model được đánh giá trên split nội bộ, chưa có external validation theo bệnh viện hoặc nhóm dân số.","Hướng tiếp theo là mở rộng corpus có version, bổ sung fault injection để đo cô lập lỗi, đánh giá calibration, theo dõi drift, kiểm thử prompt injection khi tích hợp LLM và xây dựng bộ câu hỏi do nhiều người gán nhãn. Một nghiên cứu triển khai thật còn cần quy trình bảo mật, đồng thuận, kiểm định lâm sàng và giám sát con người."])
    doc.add_heading("KẾT LUẬN",1)
    add_text(doc,"Project đã hiện thực một baseline Single Agent và một hệ Multi-Agent dùng chung model, dữ liệu và công cụ. Demo thực hiện prediction, thống kê, RAG, Knowledge Graph, validation và safety; notebook và benchmark có thể chạy lại. Kết quả hiện tại hỗ trợ kết luận về khả năng quan sát kiến trúc, không hỗ trợ tuyên bố Multi-Agent luôn chính xác hơn hoặc hệ thống có giá trị chẩn đoán.")
    add_footer(doc); path=OUT/f"project01_CT_08_{STUDENT_ID.split('B23DCCN')[-1]}_NguyenMinhVinh.docx"; doc.save(path); return path


def build_project():
    """Build the expanded Project 01 report using the detailed Kien-style outline."""
    from project_report_expanded import build_project_expanded
    return build_project_expanded(sys.modules[__name__])


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-only", action="store_true", help="Build only the monochrome Project 01 report")
    args = parser.parse_args()
    if args.project_only:
        print(build_project())
    else:
        print(build_final()); print(build_project())
