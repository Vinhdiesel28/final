"""Expanded, monochrome Project 01 report with a detailed academic outline."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm


def _heading(doc, text, level=1):
    if level == 1:
        # Remove spacer paragraphs left by a preceding table; otherwise Word
        # can push the spacer to a new page and create a blank page before the
        # chapter heading's page-break-before setting.
        while doc.paragraphs and not doc.paragraphs[-1].text.strip():
            node = doc.paragraphs[-1]._element
            node.getparent().remove(node)
    p = doc.add_heading(text, level)
    if level == 1:
        p.paragraph_format.page_break_before = True
    return p


def _paragraphs(br, doc, heading, paragraphs, level=2):
    _heading(doc, heading, level)
    for text in paragraphs:
        br.add_text(doc, text)


def _bullets(br, doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        br.font()(p.add_run(item))


def _caption(doc, text):
    p = doc.add_paragraph(text)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def _flow_image(path: Path):
    im = Image.new("RGB", (1600, 900), "white")
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype("arial.ttf", 28)
        fb = ImageFont.truetype("arialbd.ttf", 31)
    except OSError:
        f = fb = ImageFont.load_default()
    boxes = [
        (60, 320, 310, 520, "Yêu cầu\nngười dùng"),
        (390, 90, 700, 240, "Coordinator\nđịnh tuyến intent"),
        (390, 285, 700, 435, "Validation\nkiểm tra schema"),
        (390, 480, 700, 630, "Specialist\nmodel / RAG / thống kê"),
        (790, 285, 1110, 500, "Critic + Workflow\nExplanation"),
        (1200, 285, 1510, 500, "Verifier Safety\ntrạng thái cuối"),
        (1200, 650, 1510, 800, "Trace + citation\nhiển thị web"),
    ]
    for x1, y1, x2, y2, text in boxes:
        fill = "#e5e5e5" if "Verifier" in text else "#ffffff"
        d.rounded_rectangle((x1, y1, x2, y2), radius=20, fill=fill, outline="black", width=4)
        for i, line in enumerate(text.split("\n")):
            d.text(((x1+x2)//2, y1+48+i*52), line, font=fb if i == 0 else f, fill="black", anchor="mm")
    arrows = [
        ((310, 420), (390, 165)), ((310, 420), (390, 360)), ((310, 420), (390, 555)),
        ((700, 165), (790, 330)), ((700, 360), (790, 390)), ((700, 555), (790, 450)),
        ((1110, 392), (1200, 392)), ((1355, 500), (1355, 650)),
    ]
    for a, b in arrows:
        d.line((*a, *b), fill="black", width=6)
        x, y = b
        d.polygon([(x, y), (x-18, y-11), (x-18, y+11)], fill="black")
    im.save(path)


def _deployment_image(path: Path):
    im = Image.new("RGB", (1600, 760), "white")
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype("arial.ttf", 27)
        fb = ImageFont.truetype("arialbd.ttf", 31)
    except OSError:
        f = fb = ImageFont.load_default()
    boxes = [
        (70, 260, 360, 500, "Web UI\nHTML / CSS / JS"),
        (480, 200, 820, 560, "FastAPI\n/api/run\n/api/compare\n/api/benchmark"),
        (940, 60, 1280, 250, "ML + PyTorch\njoblib + pt + JSON"),
        (940, 285, 1280, 475, "Neo4j\nKB + KG"),
        (940, 510, 1280, 700, "Datasets\nCSV dự đoán + CDC"),
        (1370, 260, 1560, 500, "Render\nWeb Service"),
    ]
    for x1, y1, x2, y2, text in boxes:
        d.rectangle((x1, y1, x2, y2), fill="white", outline="black", width=4)
        for i, line in enumerate(text.split("\n")):
            d.text(((x1+x2)//2, y1+55+i*48), line, font=fb if i == 0 else f, fill="black", anchor="mm")
    for a, b in [((360,380),(480,380)),((820,310),(940,155)),((820,380),(940,380)),((820,450),(940,605)),((1280,380),(1370,380))]:
        d.line((*a,*b), fill="black", width=6)
        x,y=b; d.polygon([(x,y),(x-18,y-11),(x-18,y+11)], fill="black")
    im.save(path)


def _model_chart(path: Path, models):
    im = Image.new("RGB", (1500, 760), "white")
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype("arial.ttf", 25)
        fb = ImageFont.truetype("arialbd.ttf", 29)
    except OSError:
        f = fb = ImageFont.load_default()
    metrics = [("F1", "f1"), ("ROC AUC", "roc_auc"), ("PR AUC", "pr_auc")]
    shades = ["#cfcfcf", "#777777", "#222222"]
    for i, (label, key) in enumerate(metrics):
        y = 105 + i*190
        d.text((40, y+35), label, font=fb, fill="black")
        for j, model in enumerate(models):
            value = model["test"][key]
            yy = y + j*48
            d.rectangle((260, yy, 260+int(1050*value), yy+32), fill=shades[j])
            d.text((1360, yy+16), f"{value:.4f}", font=f, fill="black", anchor="mm")
    for j, model in enumerate(models):
        x = 240+j*390
        d.rectangle((x, 690, x+40, 720), fill=shades[j])
        d.text((x+55, 705), model["test"]["model"], font=f, fill="black", anchor="lm")
    im.save(path)


def build_project_expanded(br):
    br.MONOCHROME = True
    doc = Document()
    torch_meta = json.loads((br.ROOT/'artifacts/pytorch_metadata.json').read_text())
    benchmark = json.loads((br.ROOT/'results/agent_benchmark_summary.json').read_text())
    br.configure(doc)
    br.cover(
        doc,
        "Project 01",
        "Hệ đa Agent hỗ trợ đánh giá nguy cơ bệnh tiểu đường",
        "Single Agent và Multi Agent trên cùng mô hình, dữ liệu và kho tri thức",
    )

    toc = [
        "DANH MỤC TỪ VIẾT TẮT", "DANH MỤC HÌNH VÀ BẢNG", "TÓM TẮT",
        "CHƯƠNG 1  GIỚI THIỆU", "1.1  Bài toán và động lực", "1.2  Mục tiêu và phạm vi", "1.3  Đóng góp và cấu trúc báo cáo",
        "CHƯƠNG 2  HỆ ĐA AGENT", "2.1  Agent", "2.2  Hệ đa agent", "2.3  Giao tiếp và trạng thái dùng chung", "2.4  Guardrail và khả năng kiểm toán",
        "CHƯƠNG 3  KIẾN TRÚC TỔNG QUAN", "3.1  Ánh xạ đề bài sang hệ thống", "3.2  Vai trò của các agent", "3.3  Luồng một lượt xử lý", "3.4  Công nghệ và tổ chức mã nguồn",
        "CHƯƠNG 4  CÁC THÀNH PHẦN CỦA HỆ THỐNG", "4.1  Machine Learning thành Prediction Agent", "4.1.1  Dữ liệu và bài toán", "4.1.2  Tiền xử lý và chia dữ liệu", "4.1.3  Mô hình và huấn luyện", "4.1.4  Từ mô hình thành agent", "4.2  Knowledge Base và RAG", "4.2.1  Nguồn tri thức", "4.2.2  BM25 và Knowledge Graph", "4.2.3  Kiểm soát bằng chứng", "4.3  Statistics Agent", "4.4  Validation và Safety", "4.5  Single Agent và Multi Agent",
        "CHƯƠNG 5  CODE, DEMO VÀ ĐÁNH GIÁ", "5.1  Cấu trúc mã nguồn", "5.2  Các lớp và hàm chính", "5.3  Cách chạy", "5.4  Demo câu hỏi kiến thức", "5.5  Demo đánh giá hồ sơ", "5.6  Demo safety và ngoài phạm vi", "5.7  Thiết kế benchmark", "5.8  Kết quả và phân tích", "5.9  Triển khai Render", "5.10  Hạn chế và hướng phát triển", "KẾT LUẬN",
    ]
    toc.insert(toc.index('CHƯƠNG 5  CODE, DEMO VÀ ĐÁNH GIÁ'), '4.6  PyTorch Neo4j và điều phối có phản biện')
    toc.insert(toc.index('KẾT LUẬN'), '5.11  Notebook thực thi và giải thích từng cell')
    toc.insert(toc.index('KẾT LUẬN'), '5.12  Code huấn luyện và kết quả PyTorch')
    br.add_static_toc(doc, toc)

    _heading(doc, "DANH MỤC TỪ VIẾT TẮT", 1)
    br.table(doc, ["Viết tắt", "Tiếng Anh", "Ý nghĩa trong project"], [
        ["API", "Application Programming Interface", "Giao diện dịch vụ FastAPI"],
        ["AUC", "Area Under the Curve", "Thước đo xếp hạng mô hình"],
        ["BM25", "Best Matching 25", "Thuật toán truy xuất văn bản"],
        ["BMI", "Body Mass Index", "Chỉ số khối cơ thể"],
        ["CDC", "Centers for Disease Control and Prevention", "Nguồn bộ dữ liệu thống kê"],
        ["F1", "F1-score", "Trung bình điều hòa precision và recall"],
        ["KG", "Knowledge Graph", "Đồ thị tri thức có quan hệ và nguồn"],
        ["MAS", "Multi-Agent System", "Hệ nhiều tác tử chuyên trách"],
        ["MLP", "Multilayer Perceptron", "Mô hình được chọn cho risk score"],
        ["RAG", "Retrieval-Augmented Generation", "Trả lời dựa trên tài liệu truy xuất"],
        ["ROC", "Receiver Operating Characteristic", "Đường cong đánh giá phân loại"],
    ], [2.5, 6, 7])
    doc.add_page_break()

    _heading(doc, "DANH MỤC HÌNH VÀ BẢNG", 1)
    _heading(doc, "Danh mục hình", 2)
    for item in [
        "Hình 3.1  Kiến trúc tổng quan của DiaAgents",
        "Hình 3.2  Luồng xử lý một yêu cầu",
        "Hình 3.3  Thành phần triển khai và nơi lưu dữ liệu",
        "Hình 4.1  So sánh metric của ba mô hình trên tập test",
        "Hình 5.1  Benchmark Single Agent và Multi Agent",
    ]:
        br.add_text(doc, item)
    _heading(doc, "Danh mục bảng", 2)
    for item in [
        "Bảng 1.1  Mục tiêu và artifact kiểm chứng", "Bảng 2.1  Single Agent và Multi Agent",
        "Bảng 2.2  Trạng thái đầu ra", "Bảng 3.1  Vai trò của các agent", "Bảng 3.2  Công nghệ sử dụng",
        "Bảng 4.1  Thống kê dataset dự đoán", "Bảng 4.2  Chia train-validation-test", "Bảng 4.3  Kết quả mô hình",
        "Bảng 4.4  Corpus và Knowledge Graph", "Bảng 5.1  Cấu trúc mã nguồn", "Bảng 5.2  Endpoint API",
        "Bảng 5.3  Kết quả benchmark", "Bảng 5.4  Nhóm tình huống benchmark",
    ]:
        br.add_text(doc, item)
    doc.add_page_break()

    _heading(doc, "TÓM TẮT", 1)
    br.add_text(doc, "Project xây dựng DiaAgents, một hệ hỗ trợ học tập về nguy cơ bệnh tiểu đường, trong đó cùng một yêu cầu được xử lý bởi baseline Single Agent hoặc hệ Multi-Agent. Hai kiến trúc dùng chung checkpoint, dataset, kho tri thức, thuật toán thống kê và policy; nhờ vậy phép so sánh tập trung vào cách tổ chức và khả năng quan sát thay vì lợi thế dữ liệu hoặc mô hình.")
    br.add_text(doc, f"Khối dự đoán gồm Logistic Regression, Random Forest, MLP sklearn và MLP PyTorch trên Diabetes Prediction Dataset 100.000 dòng. PyTorch của demo đạt test F1 {torch_meta['test']['f1']:.4f}, dùng threshold {torch_meta['threshold']:.3f}; model sklearn được giữ để đối chiếu. CDC BRFSS 2015 có 253.680 dòng dùng thống kê mô tả. Neo4j lưu tám tài liệu và 16 quan hệ tri thức. MessageBus, Critic và Q-learning phối hợp các bước xử lý có kiểm soát.")
    br.add_text(doc, "Benchmark kiểm soát gồm 58 tình huống cho mỗi kiến trúc. Hai hệ cùng đạt 100% routing accuracy, task success, citation recall và safety block trên bộ contract hiện tại. Multi-Agent tạo trace chuyên trách cho toàn bộ case nên audit coverage đạt 100%, trong khi Single Agent chỉ có một trace tổng hợp. Kết quả này minh họa lợi ích kiểm toán của việc tách tác tử; không được diễn giải thành bằng chứng rằng Multi-Agent luôn chính xác hơn hoặc hệ thống có giá trị chẩn đoán.")

    _heading(doc, "CHƯƠNG 1  GIỚI THIỆU", 1)
    _paragraphs(br, doc, "1.1  Bài toán và động lực", [
        "Một mô hình dự đoán đơn lẻ có thể tạo risk score từ hồ sơ, nhưng chưa giải quyết toàn bộ nhu cầu của một hệ thống thông minh: kiểm tra đầu vào, giải thích bằng nguồn, trả lời câu hỏi kiến thức, tính thống kê, từ chối yêu cầu nguy hiểm và ghi lại bước nào đã tạo kết quả. Khi những trách nhiệm này nằm trong một hàm lớn, lỗi khó định vị và người dùng khó biết kết luận đến từ model, dữ liệu hay luật.",
        "Bệnh tiểu đường là miền phù hợp để minh họa kiến trúc vì dữ liệu có cả số, danh mục và tri thức văn bản. Tuy nhiên đây cũng là miền nhạy cảm: một score học thuật không thể thay thế xét nghiệm hoặc chẩn đoán. Do đó project đặt validation, citation và safety thành thành phần kiến trúc thay vì chỉ ghi chú ở cuối giao diện.",
        "Ý tưởng trung tâm là tách các trách nhiệm thành agent chuyên trách nhưng giữ chung dịch vụ nền. Coordinator định tuyến, Validation kiểm tra schema, Prediction gọi checkpoint, Statistics tính trực tiếp từ CDC, Retrieval và Graph tìm bằng chứng, Explanation tổng hợp, còn Verifier Safety quyết định trạng thái cuối. Baseline Single Agent dùng cùng dịch vụ nhưng thực hiện trong một khối để tạo đối chứng công bằng.",
    ])
    _paragraphs(br, doc, "1.2  Mục tiêu và phạm vi", [
        "Mục tiêu thứ nhất là tạo một pipeline dự đoán có thể tái lập: dữ liệu được kiểm tra, chia train-validation-test có phân tầng, threshold và model được chọn trên validation, test chỉ dùng báo cáo cuối. Mục tiêu thứ hai là nối model với RAG, Knowledge Graph và thống kê chính xác trong một API thống nhất.",
        "Mục tiêu thứ ba là so sánh Single Agent và Multi-Agent trên cùng đầu vào và cùng công cụ. Bộ benchmark phải đo đúng định tuyến, hoàn thành nhiệm vụ, citation, guardrail và trace thay vì chỉ quan sát một vài câu trả lời đẹp. Mục tiêu thứ tư là có notebook đã chạy và web có thể triển khai bằng Render Blueprint.",
        "Phạm vi của project là sàng lọc học thuật và minh họa kiến trúc. Hệ thống không nhận ảnh y khoa, không phân tích đơn thuốc, không kê liều, không lưu hồ sơ định danh và không thay thế nhân viên y tế. Corpus nhỏ nên câu hỏi ngoài phạm vi hoặc thiếu bằng chứng phải được trả trạng thái rõ ràng thay vì tạo câu trả lời khẳng định.",
    ])
    br.table(doc, ["Mục tiêu", "Cách thực hiện", "Artifact kiểm chứng"], [
        ["Dự đoán tái lập", "Pipeline + checkpoint + metadata", "artifacts/model_metadata.json"],
        ["Tri thức có nguồn", "BM25 + KG + citation guard", "knowledge/corpus.json, graph.json"],
        ["So sánh công bằng", "Cùng Services và cùng 58 case", "results/agent_benchmark.csv"],
        ["Demo chạy được", "FastAPI + notebook + Render", "app, notebooks, render.yaml"],
    ], [4, 6, 6])
    _paragraphs(br, doc, "1.3  Đóng góp và cấu trúc báo cáo", [
        "Đóng góp chính của project là một hệ thống đầu-cuối gồm model, hai dataset, kho tri thức, đồ thị, API, giao diện, notebook và benchmark. Mọi số liệu trong báo cáo được đọc từ artifact của repository; báo cáo không gán cho hệ thống khả năng điều trị hay hiệu quả lâm sàng chưa được kiểm chứng.",
        "Chương 2 trình bày agent, hệ đa agent, giao tiếp bằng State và trace. Chương 3 ánh xạ yêu cầu sang kiến trúc, mô tả vai trò và công nghệ. Chương 4 đi vào model, dữ liệu, RAG, KG, statistics, validation và safety. Chương 5 trình bày code, demo, benchmark, triển khai và giới hạn.",
    ])

    _heading(doc, "CHƯƠNG 2  HỆ ĐA AGENT", 1)
    _paragraphs(br, doc, "2.1  Agent", [
        "Agent là thành phần nhận quan sát, duy trì trạng thái cần thiết, chọn hành động và trả kết quả hướng tới mục tiêu. Trong project, quan sát là câu hỏi và hồ sơ; trạng thái là State có schema; hành động là gọi model, truy xuất, tính thống kê, chặn yêu cầu hoặc tạo câu trả lời có nguồn.",
        "Một agent không nhất thiết phải dùng mô hình ngôn ngữ. Coordinator của project dùng rule định tuyến có thể kiểm tra; Statistics Agent dùng phép tính DataFrame; Prediction Agent dùng checkpoint; Retrieval Agent dùng BM25; Verifier dùng contract bằng chứng và safety. Cách tiếp cận lai giúp kết quả ổn định và chạy cục bộ.",
        "Chu trình xử lý gồm nhận input, chuẩn hóa, chọn intent, gọi công cụ, cập nhật State, kiểm tra điều kiện và phát đầu ra. Nếu validation thất bại hoặc yêu cầu nguy hiểm, chu trình kết thúc sớm trước model. Đây là hành vi chủ ý để giảm bề mặt rủi ro.",
    ])
    _paragraphs(br, doc, "2.2  Hệ đa agent", [
        "Hệ đa agent phân rã một nhiệm vụ thành nhiều vai trò. Lợi ích là mỗi vai trò có contract nhỏ, dễ thay thế và dễ quan sát. Chi phí là cần coordinator, schema dùng chung và quy tắc kết thúc; nếu phân rã không hợp lý, nhiều agent chỉ làm tăng độ phức tạp mà không tăng chất lượng.",
        "Project không so một Multi-Agent mạnh với một Single Agent yếu. Cả hai nhận cùng question và profile, dùng cùng DiabetesModelService và KnowledgeService. Single Agent vẫn có validation, prediction, retrieval và safety nhưng chỉ ghi một trace tổng hợp. Multi-Agent ghi trace theo specialist, nhờ đó có thể biết bước nào chạy và bước nào dừng.",
    ])
    br.table(doc, ["Tiêu chí", "Single Agent", "Multi Agent"], [
        ["Tổ chức", "Một khối xử lý toàn bộ", "Nhiều tác tử chuyên trách"],
        ["Model và dữ liệu", "Dùng chung", "Dùng chung"],
        ["Trace", "Một bước tổng hợp", "Nhiều bước có tên agent"],
        ["Định vị lỗi", "Khó xác định công đoạn", "Có thể xác định specialist"],
        ["Chi phí phối hợp", "Thấp", "Có thêm điều phối và State"],
        ["Độ chính xác mặc định", "Không đảm bảo thấp hơn", "Không đảm bảo cao hơn"],
    ], [4.5, 5.5, 5.5])
    _paragraphs(br, doc, "2.3  Giao tiếp và trạng thái dùng chung", [
        "Các agent trao đổi qua đối tượng State thay vì chuỗi văn bản tự do. State gồm mode, question, profile, request_id, intent, prediction, statistics, knowledge, validation_errors, traces, status, answer và safety_flags. Schema cố định giúp notebook, API và giao diện đọc cùng cấu trúc.",
        "Trace ghi agent, status, duration_ms, summary và tool. total_duration_ms đo wall time từ đầu đến serialize. MessageBus lưu REQUEST, INFORM, CHALLENGE, RESPONSE hoặc FAILURE. Message có thể chứa profile nên demo không nhập dữ liệu định danh. Bus chạy trong tiến trình, chưa có broker phân tán hoặc persistence.",
        "Giao tiếp được tổ chức theo pipeline có điều kiện. Coordinator chọn intent; Validation có thể chặn; specialist ghi kết quả vào State; Explanation chỉ đọc kết quả đã tạo; Verifier kiểm tra citation và cờ an toàn trước khi trả trạng thái cuối. Nhờ vậy mỗi agent có đầu vào và đầu ra rõ ràng.",
    ])
    br.code(doc, "bus.register('ValidationAgent', lambda p: {\n    'errors': services.model.validate(p['profile'])\n})\nresult = bus.request('CoordinatorAgent', 'ValidationAgent',\n                     {'profile': profile})\nprint(result['errors'])")
    _paragraphs(br, doc, "2.4  Guardrail và khả năng kiểm toán", [
        "Guardrail không phải một dòng cảnh báo trang trí. Yêu cầu kê đơn, chọn thuốc, tăng giảm liều hoặc kết luận chắc chắn được nhận diện trước khi gọi model. Câu hỏi tài chính, thời tiết và chủ đề ngoài bệnh tiểu đường trả out_of_scope. Hồ sơ sai miền trả invalid_input với lỗi theo trường.",
        "Câu trả lời kiến thức chỉ được đánh dấu supported khi có citation. Nếu retrieval không tìm được nguồn phù hợp, Verifier đặt insufficient_evidence. Risk score trả supported_with_limitations và luôn kèm ngưỡng cùng thông báo không phải chẩn đoán.",
    ])
    br.table(doc, ["Status", "Điều kiện", "Hành vi"], [
        ["supported", "Có bằng chứng hoặc phép tính", "Hiển thị kết quả và nguồn"],
        ["supported_with_limitations", "Có risk score", "Hiển thị giới hạn"],
        ["invalid_input", "Sai schema hoặc miền", "Liệt kê lỗi trường"],
        ["blocked_unsafe_request", "Yêu cầu điều trị nguy hiểm", "Từ chối, hướng tới chuyên gia"],
        ["out_of_scope", "Ngoài bệnh tiểu đường", "Thông báo phạm vi"],
        ["insufficient_evidence", "Không có nguồn", "Không khẳng định"],
    ], [4.5, 6, 5])

    _heading(doc, "CHƯƠNG 3  KIẾN TRÚC TỔNG QUAN", 1)
    _paragraphs(br, doc, "3.1  Ánh xạ đề bài sang hệ thống", [
        "Kiến trúc hiện thực ba luồng. Luồng dữ liệu bảng đi qua tiền xử lý và model để tạo risk score. Luồng tri thức đi qua BM25 và Knowledge Graph để tạo evidence có URL. Luồng kiểm soát đi qua Coordinator, Validation và Verifier Safety. Ba luồng gặp nhau ở Explanation Agent và được trả cùng trace.",
        "Khác với kiến trúc có LLM ở mọi bước, project chỉ dùng thành phần tất định. Điều này phù hợp mục tiêu tái lập: cùng input và cùng artifact cho cùng route và kết quả. Hạn chế là câu trả lời ít tự nhiên hơn, nhưng mỗi claim có thể truy ngược tới tài liệu hoặc phép tính.",
    ])
    arch = br.ASSETS / "architecture_project_bw.png"
    br.architecture_image(arch)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(arch), width=Cm(15.5))
    _caption(doc, "Hình 3.1  Kiến trúc tổng quan của DiaAgents")
    _paragraphs(br, doc, "3.2  Vai trò của các agent", [
        "CoordinatorAgent xác định intent theo thứ tự ưu tiên: unsafe và out of scope trước, sau đó profile và câu hỏi. ValidationAgent kiểm tra trường bắt buộc, kiểu và miền. PredictionAgent chỉ chạy sau validation. StatisticsAgent tính trực tiếp từ CDC. RetrievalAgent trả tài liệu; GraphAgent trả đường đi; ExplanationAgent ghép; VerifierSafetyAgent quyết định status.",
        "Tách Graph Agent khỏi Retrieval Agent giúp phân biệt hai loại bằng chứng. Retrieval trả đoạn văn có điểm BM25, phù hợp câu hỏi diễn đạt tự do. Graph trả các quan hệ có nhãn và evidence id, phù hợp truy vết thực thể. Nếu câu hỏi không chứa seed phù hợp, Graph Agent có thể không tạo đường đi nhưng Retrieval vẫn hoạt động.",
    ])
    br.table(doc, ["Agent", "Công cụ", "Đầu vào", "Đầu ra"], [
        ["Coordinator", "intent_router", "question, profile", "intent"],
        ["Validation", "schema_validator", "profile", "errors hoặc valid"],
        ["Prediction", "joblib checkpoint", "profile hợp lệ", "score, threshold"],
        ["Statistics", "pandas_exact", "question nhóm", "count, positive, rate"],
        ["Retrieval", "BM25", "question", "documents, citations"],
        ["Graph", "Cypher 2 hop", "entities", "paths"],
        ["Explanation", "grounded composer", "evidence", "answer"],
        ["Verifier Safety", "contract guard", "state", "final status"],
    ], [3.2, 3.5, 4.5, 4.5])
    _paragraphs(br, doc, "3.3  Luồng một lượt xử lý", [
        "Một request bắt đầu tại FastAPI và được chuyển thành State. Coordinator chọn nhánh. Với risk assessment, Validation chạy trước Prediction; sau đó Retrieval bổ sung tri thức giải thích và Verifier chốt trạng thái. Với knowledge, Retrieval và Graph tạo bằng chứng rồi Explanation tổng hợp. Với statistics, kết quả được tính từ DataFrame và trả kèm công thức.",
        "Nhánh unsafe, outside và invalid kết thúc sớm. Early return không chỉ giảm thời gian mà còn ngăn model hoặc retrieval biến yêu cầu nguy hiểm thành chỉ dẫn. Multi-Agent ghi một trace cho mỗi bước; Single Agent trả cùng status nhưng chỉ ghi trace tổng hợp.",
    ])
    flow = br.ASSETS / "flow_project_bw.png"; _flow_image(flow)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(flow), width=Cm(15.5))
    _caption(doc, "Hình 3.2  Luồng xử lý một yêu cầu")
    _paragraphs(br, doc, "3.4  Công nghệ và tổ chức mã nguồn", [
        "Backend dùng FastAPI và Pydantic. Checkpoint scikit-learn lưu joblib; mạng PyTorch lưu state_dict trong tệp pt. Metadata giữ split, metric và threshold. Dataset giữ CSV; Neo4j lưu văn bản, thực thể, quan hệ và bằng chứng. JSON là nguồn nhập dữ liệu và chế độ chạy gọn được chọn tường minh.",
        "KNOWLEDGE_BACKEND=neo4j yêu cầu kết nối database thật; lỗi kết nối không tự chuyển sang JSON. Bản cục bộ dùng Neo4j Community trong Docker. Khi đưa lên Render, cần cấu hình URI, tài khoản và mật khẩu của Neo4j bên ngoài. Mật khẩu không nằm trong notebook hoặc GitHub.",
    ])
    deploy = br.ASSETS / "deployment_project_bw.png"; _deployment_image(deploy)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(deploy), width=Cm(15.5))
    _caption(doc, "Hình 3.3  Thành phần triển khai và nơi lưu dữ liệu")
    br.table(doc, ["Thành phần", "Công nghệ", "Vai trò"], [
        ["API", "FastAPI + Pydantic", "Schema và endpoint"],
        ["Model", "scikit-learn + PyTorch", "ML và mạng 15–64–32–1"],
        ["Xử lý dữ liệu", "pandas + NumPy", "Huấn luyện và thống kê"],
        ["Kho tri thức", "Neo4j + BM25 + Cypher", "KB và KG có nguồn"],
        ["Notebook", "Jupyter", "Giải thích và tái lập"],
        ["Web", "HTML/CSS/JavaScript", "Demo so sánh"],
        ["Triển khai", "Render Blueprint", "Web Service"],
    ], [4, 5, 6])

    _heading(doc, "CHƯƠNG 4  CÁC THÀNH PHẦN CỦA HỆ THỐNG", 1)
    meta = json.loads((br.ROOT / "artifacts/model_metadata.json").read_text(encoding="utf-8"))
    models = meta["models"]
    _paragraphs(br, doc, "4.1  Machine Learning thành Prediction Agent", [
        "Prediction Agent không huấn luyện model khi nhận request. Toàn bộ huấn luyện được thực hiện ngoại tuyến; checkpoint lưu cả preprocessing và estimator. Khi chạy web, agent chỉ kiểm tra schema, sắp trường đúng contract, gọi predict_proba và so sánh với threshold đã chọn trên validation.",
        "Cách tách train và inference tránh rò rỉ dữ liệu và giảm thời gian khởi động. Metadata đi kèm giúp giao diện hiển thị tên model, threshold, metric và thông báo giới hạn. Model service không tự tạo giải thích y khoa; phần đó thuộc Retrieval và Explanation.",
    ])
    _paragraphs(br, doc, "4.1.1  Dữ liệu và bài toán", [
        "Diabetes Prediction Dataset có 100.000 dòng gốc. Sau loại dòng trùng còn 99.986 dòng; tỷ lệ nhãn dương khoảng 8,50%. Tám đặc trưng gồm gender, smoking_history, age, bmi, hbA1c_level, blood_glucose_level, hypertension và heart_disease.",
        "Bài toán là phân loại nhị phân. Mất cân bằng lớp khiến accuracy không đủ để chọn model; vì vậy project báo cáo precision, recall, F1, ROC AUC, PR AUC, Brier score và confusion matrix. Model được chọn bằng F1 validation để cân bằng precision và recall trong phạm vi bài học.",
    ])
    br.table(doc, ["Thuộc tính", "Giá trị"], [
        ["Số dòng gốc", f"{meta['dataset']['raw_rows']:,}"],
        ["Sau loại trùng", f"{meta['dataset']['deduplicated_rows']:,}"],
        ["Tỷ lệ nhãn dương", f"{meta['dataset']['positive_rate']*100:.2f}%"],
        ["Biến số", ", ".join(meta['numeric'])],
        ["Biến danh mục", ", ".join(meta['categorical'])],
        ["Nhãn", "diabetes"],
    ], [5, 10.5])
    _paragraphs(br, doc, "4.1.2  Tiền xử lý và chia dữ liệu", [
        "Script train_models.py loại trùng và kiểm tra dữ liệu trước khi chia. Train, validation và test được tạo có stratify và random_state cố định. Mọi biến đổi chỉ fit trên train. Validation dùng chọn threshold và model; test bị giữ kín tới giai đoạn báo cáo.",
        "Các cột danh mục được mã hóa trong pipeline. Các cột số được đưa qua preprocessing phù hợp với estimator. Việc đóng gói preprocessing cùng model bảo đảm một request mới không dùng encoder hoặc scaler khác với lúc huấn luyện.",
    ])
    br.table(doc, ["Split", "Số dòng", "Tỷ lệ", "Mục đích"], [
        ["Train", meta["splits"]["train"], "70%", "Fit preprocessing và model"],
        ["Validation", meta["splits"]["validation"], "15%", "Chọn threshold và model"],
        ["Test", meta["splits"]["test"], "15%", "Báo cáo cuối"],
    ], [3.5, 3.5, 3, 6])
    _paragraphs(br, doc, "4.1.3  Mô hình và huấn luyện", [
        "Ba mô hình được huấn luyện trên cùng split: Logistic Regression làm baseline tuyến tính; Random Forest mô hình hóa quan hệ phi tuyến; MLP là mạng nhiều lớp. Với mỗi mô hình, threshold được quét trên validation để tối ưu F1 thay vì mặc định 0,5.",
        "MLP có validation F1 cao nhất 0,8159 và được chọn. Trên test, MLP đạt F1 0,7925, ROC AUC 0,9749 và PR AUC 0,8704. Random Forest có test F1 0,7910 và precision rất cao; khác biệt nhỏ cho thấy kết luận lựa chọn cần gắn với tiêu chí đã định trước.",
        "Audit theo giới tính cho thấy recall của nhóm Female và Male gần nhau trong split test, còn nhóm Other chỉ có bốn mẫu nên không đủ để kết luận. Báo cáo giữ con số này như cảnh báo về kích thước nhóm, không coi recall bằng 0 của bốn mẫu là bằng chứng thiên lệch đã xác nhận.",
    ])
    br.table(doc, ["Model", "Val F1", "Test Precision", "Test Recall", "Test F1", "ROC AUC"], [
        [m["test"]["model"], f"{m['validation']['f1']:.4f}", f"{m['test']['precision']:.4f}", f"{m['test']['recall']:.4f}", f"{m['test']['f1']:.4f}", f"{m['test']['roc_auc']:.4f}"] for m in models
    ], [3.8, 2.3, 2.6, 2.4, 2.3, 2.6])
    model_chart = br.ASSETS / "model_metrics_project_bw.png"; _model_chart(model_chart, models)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(model_chart), width=Cm(15.5))
    _caption(doc, "Hình 4.1  So sánh metric của ba mô hình trên tập test")
    _paragraphs(br, doc, "4.1.4  Từ mô hình thành agent", [
        "DiabetesModelService nạp checkpoint sklearn làm ý kiến đối chiếu và checkpoint PyTorch làm đầu ra chính của demo mở rộng. validate kiểm tra trường và miền; predict trả probability, threshold, predicted_class, model và second_opinion. Không thay đổi threshold theo câu hỏi.",
        "Risk score được trình bày như đầu ra của model trên dataset cụ thể, không phải xác suất lâm sàng đã hiệu chuẩn cho một cá nhân. Explanation Agent ghép score với citation về xét nghiệm và yếu tố nguy cơ, còn Verifier buộc thông báo không chẩn đoán.",
    ])
    br.code(doc, "service = DiabetesModelService()\nerrors = service.validate(profile)\nif not errors:\n    result = service.predict(profile)\n    print(result['probability'], result['second_opinion'])")

    _paragraphs(br, doc, "4.2  Knowledge Base và RAG", [
        "KnowledgeService chuẩn hóa câu hỏi, chấm BM25 trên title và text, lấy ba tài liệu rồi bổ sung evidence từ đồ thị, tối đa năm tài liệu. Câu trả lời trích câu phù hợp với token truy vấn. Citation đầu ra chứa id, title, URL và score; metadata nguồn đầy đủ được lưu trong KB. Đây là truy xuất và trích xuất tất định, chưa có LLM sinh văn bản.",
        "Knowledge Graph bổ sung quan hệ có cấu trúc. Graph không thay thế văn bản mà cho biết entity liên quan qua cạnh nào và evidence nào chứng minh. Câu trả lời cuối vẫn phải có citation từ corpus.",
    ])
    corpus = json.loads((br.ROOT / "knowledge/corpus.json").read_text(encoding="utf-8"))
    graph = json.loads((br.ROOT / "knowledge/graph.json").read_text(encoding="utf-8"))
    nodes = sorted({e["subject"] for e in graph} | {e["object"] for e in graph})
    _paragraphs(br, doc, "4.2.1  Nguồn tri thức", [
        "Corpus gồm tám tài liệu tóm lược từ WHO, CDC, NIDDK và model card nội bộ. Mỗi tài liệu có id, title, URL, organization, as_of và text. Ngày as_of giúp nhận biết nội dung cần cập nhật; model card ghi rõ dataset và giới hạn của risk score.",
        "Các nguồn được chọn cho câu hỏi tổng quan, triệu chứng, xét nghiệm, phòng ngừa và yếu tố nguy cơ. Corpus không chứa hướng dẫn kê đơn hoặc phác đồ điều trị, vì vậy hệ thống không được dùng để trả lời liều thuốc.",
    ])
    br.table(doc, ["Thành phần", "Quy mô", "Ví dụ"], [
        ["Corpus", f"{len(corpus)} tài liệu", "WHO, CDC, NIDDK, model card"],
        ["Knowledge Graph", f"{len(nodes)} nút, {len(graph)} cạnh", "A1C phản ánh glucose trung bình"],
        ["Độ sâu graph", "Tối đa 2 hop", "Entity -> relation -> entity"],
        ["Retrieval", "Top 3", "BM25 theo title + text"],
    ], [4.5, 4, 7])
    _paragraphs(br, doc, "4.2.2  BM25 và Knowledge Graph", [
        "BM25 tăng trọng số token hiếm và điều chỉnh theo độ dài tài liệu. Với corpus nhỏ, chỉ mục được tính khi KnowledgeService khởi tạo. Kết quả sắp theo điểm giảm dần rồi theo id để ổn định khi bằng điểm. Chuẩn hóa tiếng Việt giúp truy vấn có và không dấu chia sẻ token cơ bản.",
        "Neo4j lưu DiaEntity và DIA_RELATION kèm evidence id. Cypher tìm seed xuất hiện trong câu hỏi rồi duyệt tối đa hai hop, giới hạn 16 cạnh. Quan hệ SUPPORTED_BY nối thực thể với DiaDocument. Chế độ JSON dùng BFS cho cùng contract; backend luôn được công khai trong kết quả.",
    ])
    br.code(doc, "MATCH (s:DiaEntity) WHERE s.name IN $seeds\nMATCH p=(s)-[:DIA_RELATION*1..2]-(o:DiaEntity)\nUNWIND relationships(p) AS r\nRETURN DISTINCT startNode(r).name AS subject,\n       r.relation AS relation,\n       endNode(r).name AS object, r.evidence AS evidence\nLIMIT 16")
    _paragraphs(br, doc, "4.2.3  Kiểm soát bằng chứng", [
        "Retrieval Agent trả tài liệu và citations riêng biệt. Explanation chỉ tổng hợp câu có trong evidence; Verifier kiểm tra số citation. Nếu không có citation, status thành insufficient_evidence. Với câu hỏi có nguồn, status supported và giao diện hiển thị link.",
        "Benchmark đo citation recall theo gold source tối thiểu và precision theo số nguồn trả về. Các số đo phiên bản hiện tại nằm ở mục 5.8. Graph có thể bổ sung nguồn ngoài gold tối thiểu, vì vậy precision cần được đọc cùng chất lượng annotation; không chỉnh sửa nguồn trả về chỉ để làm đẹp metric.",
    ])

    _paragraphs(br, doc, "4.3  Statistics Agent", [
        "Statistics Agent dùng CDC BRFSS 2015 gồm 253.680 dòng và 22 cột. Agent lọc DataFrame, đếm Diabetes_012 lớn hơn 0 và tính rate. Nhãn này gộp tiền tiểu đường (1) và tiểu đường (2), không phải tỷ lệ riêng người mắc tiểu đường. Đây là thống kê mẫu không trọng số, không suy rộng thành tỷ lệ dân số.",
        "Các nhóm hỗ trợ gồm toàn bộ mẫu, nữ, nam, tăng huyết áp và nhóm tuổi mã 10 đến 13. Mã tuổi là biến đã tiền xử lý của BRFSS; không được diễn giải tuyệt đối thành mọi người trên 60 tuổi. Giới hạn này được ghi trong báo cáo để tránh biến nhãn nhóm kỹ thuật thành kết luận dân số.",
        "Tách Statistics Agent khỏi Prediction Agent ngăn nhầm lẫn giữa thống kê mô tả và dự đoán cá nhân. Một rate của nhóm không phải xác suất của một người; risk score của model cũng không phải prevalence.",
    ])
    _paragraphs(br, doc, "4.4  Validation và Safety", [
        "Validation kiểm tra các trường gender, smoking_history, age, bmi, hbA1c_level, blood_glucose_level, hypertension và heart_disease. Miền hợp lệ ngăn giá trị âm, BMI bằng 0, glucose hoặc HbA1c bất hợp lý đi vào pipeline. Lỗi được trả theo trường để giao diện hiển thị rõ.",
        "Safety nhận diện câu kê đơn, chọn thuốc, tăng giảm liều hoặc yêu cầu chắc chắn. Hệ thống trả blocked_unsafe_request và khuyên liên hệ nhân viên y tế. Ngoài phạm vi được tách thành out_of_scope để không đánh đồng câu hỏi vô hại với yêu cầu nguy hiểm.",
        "Các rule hiện dựa trên từ khóa nên có thể bỏ sót cách diễn đạt mới. Khi mở rộng, cần policy engine, classifier riêng và bộ kiểm thử tiếng Việt đa dạng. Dù dùng kỹ thuật nào, safety phải chạy trước model và được đánh giá cả false refusal.",
    ])
    br.table(doc, ["Nhóm kiểm soát", "Ví dụ", "Kết quả"], [
        ["Invalid schema", "BMI = 0", "invalid_input"],
        ["Unsafe", "Hãy kê đơn thuốc", "blocked_unsafe_request"],
        ["Outside", "Giá Bitcoin ngày mai", "out_of_scope"],
        ["Thiếu nguồn", "Câu hỏi ngoài corpus", "insufficient_evidence"],
        ["Risk score", "Hồ sơ hợp lệ", "supported_with_limitations"],
    ], [4, 6, 5.5])
    _paragraphs(br, doc, "4.5  Single Agent và Multi Agent", [
        "SingleAgent.run tạo State, route, gọi các dịch vụ cần thiết và ghi một trace tên SingleAgent. MultiAgent.run thực hiện cùng logic nghiệp vụ nhưng ghi CoordinatorAgent, ValidationAgent, PredictionAgent, StatisticsAgent, RetrievalAgent, GraphAgent, ExplanationAgent và VerifierSafetyAgent theo nhánh thực tế.",
        "Cả hai được khởi tạo từ cùng Services. Vì vậy task success bằng nhau trên contract hiện tại là kết quả hợp lý. Giá trị đo được của Multi-Agent nằm ở trace, khả năng định vị specialist và mở rộng từng contract, không phải một lời khẳng định tổng quát về trí thông minh.",
        "Thiết kế benchmark tách metric đầu ra và metric kiến trúc. Routing accuracy, task success, safety và citation phản ánh hành vi người dùng thấy. Audit coverage và trace steps phản ánh khả năng quan sát. Khi trình bày kết quả phải giữ hai nhóm metric này riêng.",
    ])

    _paragraphs(br, doc, '4.6  PyTorch Neo4j và điều phối có phản biện', [
        'Mạng PyTorch nhận 15 giá trị sau tiền xử lý, đi qua các lớp 64 và 32 neuron với ReLU, Dropout 0,15 rồi một logit. Adam dùng learning rate 0,001, batch 512 và BCEWithLogitsLoss. Checkpoint được giữ theo validation loss; threshold được chọn riêng trên validation F1. Lịch sử từng epoch được lưu CSV.',
        f"Lần chạy ghi nhận {torch_meta['epochs']} epoch, threshold {torch_meta['threshold']:.3f}, test F1 {torch_meta['test']['f1']:.4f} và ROC AUC {torch_meta['test']['roc_auc']:.4f}. PyTorch là nhánh deep learning được triển khai để khảo sát và trình diễn, không phải tuyên bố tốt hơn sklearn. Hai model cùng dữ liệu nên sự đồng thuận không phải xác nhận độc lập.",
        'MessageBus đăng ký các handler Validation, Prediction, Retrieval, Critic và WorkflowRL. REQUEST tạo lời gọi, INFORM trả kết quả; lỗi tạo FAILURE rồi được ném lên lớp gọi. Các agent chạy đồng bộ trong một tiến trình Python. Các stage Coordinator, Graph, Explanation và Verifier cũng có trace, nhưng không phải tất cả là tiến trình hay LLM riêng biệt.',
        'Critic kiểm tra bất đồng nhãn, khoảng cách score với threshold dưới 0,05 và thiếu citation. Nếu cần, Critic gửi CHALLENGE; Prediction trả RESPONSE về checkpoint và cách chọn ngưỡng. Phản biện theo luật giúp làm rõ giới hạn, không tự sửa score để đạt đồng thuận. Single Agent cũng dùng cùng reviewer để phép so sánh giữ công bằng.',
        'Q-learning dùng tám trạng thái biểu diễn thiếu dữ liệu, có bằng chứng và cần xem xét. Bốn hành động là hỏi thêm, xem nguồn, giải thích score và yêu cầu người kiểm tra. Môi trường tổng hợp huấn luyện 3.000 episode; alpha 0,2, gamma 0,9, epsilon 0,15. Reward biểu diễn độ hoàn thành quy trình, không biểu diễn lợi ích sức khỏe. Action mask chặn các lựa chọn không phù hợp. Không có hành động kê đơn hoặc thay đổi điều trị.',
    ])

    _heading(doc, "CHƯƠNG 5  CODE, DEMO VÀ ĐÁNH GIÁ", 1)
    _paragraphs(br, doc, "5.1  Cấu trúc mã nguồn", [
        "Repository được chia theo trách nhiệm: src chứa logic agent và dịch vụ; app chứa FastAPI và tài nguyên web; tools chứa huấn luyện, benchmark và tạo báo cáo; notebooks chứa notebook đã chạy; data, knowledge, artifacts và results chứa đầu vào và đầu ra có thể kiểm tra.",
        "Cách tổ chức này giúp notebook không sao chép logic của web. Notebook import cùng lớp trong src, còn API cũng dùng các lớp đó. Khi sửa model service hoặc knowledge service, demo và notebook nhận cùng hành vi.",
    ])
    br.table(doc, ["Thư mục/file", "Nội dung", "Vai trò"], [
        ["src/agent_system.py", "State, Services, SingleAgent, MultiAgent", "Điều phối"],
        ["src/model_service.py", "Validate và inference", "Prediction"],
        ["src/knowledge_service.py", "BM25, graph, statistics", "Tri thức"],
        ["app/main.py", "FastAPI endpoints", "Backend"],
        ["app/static", "HTML, CSS, JavaScript", "Giao diện"],
        ["notebooks", "Notebook bảy cell code", "Tái lập"],
        ["artifacts", "Checkpoint và metadata", "Model"],
        ["results", "CSV/JSON benchmark", "Đánh giá"],
    ], [5, 6, 4.5])
    _paragraphs(br, doc, "5.2  Các lớp và hàm chính", [
        "Trace và State là schema trung tâm. Services nạp DiabetesModelService, KnowledgeService và DataFrame CDC một lần. intent_of định tuyến. serialize chuyển dataclass thành JSON. Các lớp agent chỉ phối hợp dịch vụ, không tự đọc file tùy ý trong từng request.",
        "app/main.py khởi tạo hai runner dùng chung Services. /api/run chạy một kiến trúc theo mode; /api/compare chạy cả hai trên cùng payload; /api/benchmark đọc artifact đã lưu; /api/metadata và /api/graph phục vụ model card và trực quan hóa.",
    ])
    br.table(doc, ["Endpoint", "Method", "Mục đích"], [
        ["/health", "GET", "Kiểm tra model, corpus, graph"],
        ["/api/metadata", "GET", "Đọc model card và metric"],
        ["/api/graph", "GET", "Danh sách cạnh KG"],
        ["/api/run", "POST", "Chạy Single hoặc Multi"],
        ["/api/compare", "POST", "Chạy hai hệ cùng input"],
        ["/api/benchmark", "GET", "Đọc summary và case"],
    ], [5, 3, 7.5])
    br.code(doc, "@app.post('/api/compare')\ndef compare(payload: Request):\n    return {\n        'single': single.run(payload.question, payload.profile),\n        'multi': multi.run(payload.question, payload.profile),\n    }")
    _paragraphs(br, doc, "5.3  Cách chạy", [
        "Từ thư mục repository, cài requirements rồi chạy uvicorn. Không cần huấn luyện lại khi chỉ demo vì checkpoint và metadata đã có trong artifacts. Khi cần tái tạo kết quả, chạy train_models.py trước, sau đó run_agent_benchmark.py.",
        "Notebook mở bằng Jupyter trong đúng môi trường. Chọn kernel, Restart Kernel and Run All, sau đó kiểm tra execution count và error output. Các cell đọc artifact, chạy câu hỏi A1C, dự đoán hồ sơ, kiểm tra guardrail và hiển thị benchmark.",
    ])
    br.code(doc, "python -m pip install -r requirements.txt\npython tools/train_models.py\npython tools/run_agent_benchmark.py\npython -m uvicorn app.main:app --host 127.0.0.1 --port 8010")
    _paragraphs(br, doc, "5.4  Demo câu hỏi kiến thức", [
        "Người dùng chọn kịch bản A1C hoặc nhập câu hỏi. Single Agent trả câu trả lời trong một trace tổng hợp. Multi-Agent tạo Coordinator, Retrieval, Graph nếu có seed, Explanation và Verifier. Hai câu trả lời có thể giống nhau vì cùng corpus; phần khác biệt là trace.",
        "Giao diện hiển thị citations với tổ chức, tiêu đề và URL. Nếu câu hỏi không có nguồn, hệ thống không dùng model ngôn ngữ để lấp chỗ trống mà trả insufficient_evidence. Đây là hành vi quan trọng khi demo trước giảng viên.",
    ])
    _paragraphs(br, doc, "5.5  Demo đánh giá hồ sơ", [
        "Người dùng điền giới tính, tuổi, BMI, HbA1c, blood glucose, smoking history, tăng huyết áp và bệnh tim. Endpoint compare gửi cùng profile cho hai runner. Kết quả hiển thị risk score, threshold, predicted label, explanation, nguồn và trace.",
        "Nếu hồ sơ hợp lệ, cả hai dùng cùng MLP checkpoint. Multi-Agent hiển thị Validation, Prediction, Retrieval, Explanation và Verifier. Nếu tuổi âm hoặc BMI bằng 0, cả hai trả invalid_input; Multi-Agent cho biết ValidationAgent blocked, còn Single chỉ có trace tổng hợp.",
    ])
    _paragraphs(br, doc, "5.6  Demo safety và ngoài phạm vi", [
        "Câu 'Hãy kê đơn thuốc cho tôi' được route unsafe_medical_request và trả blocked_unsafe_request trước model. Câu 'Giá Bitcoin ngày mai' trả out_of_scope. Hai kịch bản cho thấy hệ thống phân biệt nguy hiểm và không liên quan.",
        "Khi demo, cần mở phần trace để chứng minh early return: không có PredictionAgent hoặc RetrievalAgent sau bước chặn. Đây là bằng chứng kiến trúc rõ hơn việc chỉ đọc câu từ chối.",
    ])
    _paragraphs(br, doc, "5.7  Thiết kế benchmark", [
        "Bộ benchmark có 58 case cho mỗi hệ, tổng 116 lượt. Sáu nhóm gồm knowledge, statistics, prediction, unsafe, outside và invalid. Các case có tiếng Việt có dấu, không dấu, diễn đạt thay thế và hồ sơ biên.",
        "evaluate so sánh intent, status, citation, safety và yêu cầu specialist trace. P95 được tính từ latency của các case. Artifact CSV giữ từng dòng để kiểm tra; summary JSON chỉ là bản tổng hợp. Bộ này là contract test, chưa phải đánh giá lâm sàng hoặc đánh giá chất lượng ngôn ngữ bởi chuyên gia.",
    ])
    cases = json.loads((br.ROOT / "results/benchmark_cases.json").read_text(encoding="utf-8"))
    counts = {}
    for row in cases:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    br.table(doc, ["Nhóm", "Số case mỗi hệ", "Mục tiêu"], [
        ["Knowledge", counts["knowledge"], "Route và citation"],
        ["Statistics", counts["statistics"], "Nhóm và phép tính"],
        ["Prediction", counts["prediction"], "Checkpoint và disclaimer"],
        ["Unsafe", counts["unsafe"], "Chặn yêu cầu nguy hiểm"],
        ["Outside", counts["outside"], "Giới hạn phạm vi"],
        ["Invalid", counts["invalid"], "Validation biên"],
    ], [4, 4, 7.5])
    _paragraphs(br, doc, "5.8  Kết quả và phân tích", [
        "Hai hệ đạt routing accuracy và task success 100% trên contract. Citation recall và safety block đều 100%; false refusal và unsupported claim bằng 0. Kết quả cho thấy các route đã định nghĩa hoạt động trên 58 case, không chứng minh hệ thống đúng cho mọi câu hỏi ngoài bộ benchmark.",
        f"Mean latency Single là {benchmark[0]['mean_latency_ms']} ms và Multi là {benchmark[1]['mean_latency_ms']} ms. Số trace trung bình tương ứng {benchmark[0]['mean_trace_steps']} và {benchmark[1]['mean_trace_steps']}. Đây là một lượt chạy theo thứ tự Single rồi Multi, có thể chịu ảnh hưởng cache; chưa đủ để kết luận ưu thế tốc độ.",
        f"Citation precision Single/Multi là {benchmark[0]['citation_precision']:.4f}/{benchmark[1]['citation_precision']:.4f}. Gold chỉ ghi nguồn tối thiểu nên cần mở rộng annotation để đánh giá chất lượng nguồn đầy đủ. Unsupported claim trong script chỉ là proxy thiếu nguồn hoặc thiếu thông báo giới hạn, không phải kiểm chứng mọi phát biểu.",
    ])
    summary = json.loads((br.ROOT / "results/agent_benchmark_summary.json").read_text(encoding="utf-8"))
    chart = br.ASSETS / "benchmark_project_bw.png"; br.benchmark_image(chart, summary)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(chart), width=Cm(15.5))
    _caption(doc, "Hình 5.1  Benchmark Single Agent và Multi Agent")
    br.table(doc, ["Metric", "Single", "Multi", "Cách hiểu"], [
        ["Routing accuracy", "100%", "100%", "Định tuyến đúng contract"],
        ["Task success", "100%", "100%", "Hoàn thành điều kiện case"],
        ["Citation recall", "100%", "100%", "Có gold source tối thiểu"],
        ["Citation precision", f"{benchmark[0]['citation_precision']*100:.2f}%", f"{benchmark[1]['citation_precision']*100:.2f}%", "Nguồn thuộc gold tối thiểu"],
        ["Safety block", "100%", "100%", "Chặn unsafe case"],
        ["False refusal", "0%", "0%", "Không từ chối nhầm case hợp lệ"],
        ["Audit coverage", "0%", "100%", "Có specialist trace kỳ vọng"],
        ["Mean trace steps", benchmark[0]['mean_trace_steps'], benchmark[1]['mean_trace_steps'], "Độ chi tiết trace"],
        ["Mean latency", benchmark[0]['mean_latency_ms'], benchmark[1]['mean_latency_ms'], "Thời gian ms của lần benchmark"],
    ], [4.2, 2.5, 2.5, 6.5])
    _paragraphs(br, doc, "5.9  Triển khai Render", [
        "render.yaml định nghĩa Web Service Python. Bản Neo4j cần database bên ngoài với NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD; ingest corpus vào database đó trước khi chạy app. Không dùng localhost của máy cá nhân làm URI trên Render. Checkpoint và CSV nằm trong repository, mật khẩu nằm trong Environment.",
        "Sau khi deploy, kiểm tra /health trước. Tiếp theo thử knowledge, prediction, safety và benchmark. Nếu dịch vụ ngủ theo gói Render, request đầu có thể chậm; đây là cold start của nền tảng, không phải latency benchmark trong artifact.",
    ])
    _paragraphs(br, doc, "5.10  Hạn chế và hướng phát triển", [
        "Benchmark là contract suite tự xây dựng, chưa có bác sĩ gán nhãn chất lượng và chưa có external validation. Corpus chỉ có tám tài liệu, Knowledge Graph 16 cạnh, rule safety dựa trên từ khóa. Dataset dự đoán có nguồn công khai nhưng không đại diện mọi bệnh viện hoặc dân số.",
        "Hướng tiếp theo là mở rộng corpus, xây reranker, đánh giá calibration, drift và fairness với nhóm đủ mẫu. MessageBus hiện dispatch thật trong tiến trình; cần thêm persistence, retry và fault injection trước khi sử dụng như một hệ phân tán.",
        "Một nghiên cứu triển khai thực tế còn cần bảo mật, đồng thuận, kiểm định lâm sàng, giám sát con người và quy trình cập nhật tri thức. Project hiện chỉ hỗ trợ học tập và trình diễn kỹ thuật.",
    ])

    _heading(doc, '5.11  Notebook thực thi và giải thích từng cell', 2)
    br.add_text(doc, 'Các hình dưới được chụp từ bản HTML của notebook đã thực thi. Nội dung gồm code và output thực; đây không phải ảnh mượn từ bài mẫu. Mỗi cell import cùng source mà web sử dụng. Notebook đầy đủ nằm tại notebooks/08_project_ml_neo4j_multiagent.ipynb.')
    notebook=json.loads((br.ROOT/'notebooks/08_project_ml_neo4j_multiagent.ipynb').read_text(encoding='utf-8'))
    number=0
    explanation=''
    for cell in notebook['cells']:
        source=''.join(cell['source'])
        if cell['cell_type']=='markdown':
            explanation=source
            continue
        number+=1
        h=_heading(doc, f'5.11.{number}  '+explanation.splitlines()[0].lstrip('# ').split('. ',1)[-1],3)
        h.paragraph_format.page_break_before=True
        br.add_text(doc, '\n'.join(explanation.splitlines()[1:])).paragraph_format.keep_with_next=True
        pics=sorted((br.ASSETS/'notebook').glob(f'cell-{number:02d}-*.png'))
        for part,pic in enumerate(pics,1):
            from PIL import Image
            with Image.open(pic) as im:
                width=min(15.5,19*im.width/im.height)
            p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str(pic),width=Cm(width))
            p.paragraph_format.keep_with_next=True
            _caption(doc,f'Hình 5.{number+1}.{part}  Code và output cell {number}')

    _heading(doc, '5.12  Code huấn luyện và kết quả PyTorch',2)
    br.add_text(doc, 'Notebook 09_pytorch_training_full.ipynb chứa toàn bộ script huấn luyện trong cell và output đã thực thi. Các ảnh nối tiếp dưới đây cho thấy cách chia dữ liệu, fit preprocessing, vòng lặp train và kết quả đánh giá. Đây là huấn luyện ngoại tuyến; web chỉ nạp checkpoint khi chạy demo.')
    for part,pic in enumerate(sorted((br.ASSETS/'training').glob('cell-01-*.png')),1):
        p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next=True
        p.add_run().add_picture(str(pic),width=Cm(15.5))
        _caption(doc,f'Hình 5.14.{part}  Huấn luyện PyTorch và output')
    br.add_text(doc, 'Trong mỗi batch, zero_grad xóa gradient cũ; forward tạo logit; BCEWithLogitsLoss tính sai số; backward lan truyền ngược; Adam step cập nhật trọng số. eval và inference_mode được dùng khi đo validation. deepcopy giữ trạng thái tốt nhất theo validation loss; choose_threshold dùng validation F1. Checkpoint, preprocessing, metric JSON và lịch sử CSV được lưu riêng để kiểm chứng.')
    _heading(doc, "KẾT LUẬN", 1)
    br.add_text(doc, "Project đã hiện thực một baseline Single Agent và một hệ Multi-Agent dùng chung model, dữ liệu, kho tri thức và policy. Hệ thống nối pipeline dự đoán, thống kê CDC, BM25, Knowledge Graph, validation, safety, API, notebook và web trong một luồng có thể chạy lại.")
    br.add_text(doc, "Kết quả benchmark cho thấy hai kiến trúc cùng hoàn thành contract hiện tại; Multi-Agent tạo trace chuyên trách đầy đủ hơn. Kết luận phù hợp là Multi-Agent cải thiện khả năng quan sát và phân tách trách nhiệm trong project, không phải mặc định chính xác hơn. Mọi risk score chỉ phục vụ học tập, không phải chẩn đoán hay khuyến nghị điều trị.")

    br.add_footer(doc)
    path = br.OUT / f"project01_CT_08_{br.STUDENT_ID.split('B23DCCN')[-1]}_NguyenMinhVinh.docx"
    doc.save(path)
    return path
