# Kết quả rà soát cấu trúc DiaGuard

Thư mục src chứa bốn điểm vào cấp cao gồm agent_system.py, conversational_agents.py, benchmark_v3.py và settings.py. Các phần triển khai được chia thành thư mục theo trách nhiệm.

## Phần dùng cho ứng dụng

Bảy tác tử nằm trong src/agents. Phản biện và kiểm chứng là thao tác của ExplanationAgent. Chuẩn bị bằng chứng và thống kê thuộc KnowledgeAgent. Các module services chứa dịch vụ mô hình, Groq, cơ sở dữ liệu, encoder và truy xuất. contracts chứa hợp đồng dữ liệu, MessageBus và kiểm tra nguồn.

src/agent_system.py giữ Services, trạng thái, serialization và SingleAgent. Tên LegacyMultiAgent được hỗ trợ bằng import trì hoãn khi chương trình lịch sử cần gọi. Mô hình chính dùng phần giải thích đặc trưng tại src/services/model_explanation.py.

## Phần lưu để tái lập

src/legacy chứa multi_agent.py, specialist_agents.py, evidence_review.py và workflow_policy.py. Notebook 08 và các benchmark lịch sử vẫn tham chiếu các module này. Các tệp nguồn đã được chuyển vào thư mục riêng và các import đã được cập nhật.

src/services/testing_guidance.py còn phục vụ SingleAgent. src/services/vector_store.py cung cấp chế độ vector dự phòng của KnowledgeService. src/services/llm_explanation.py chứa kiểm tra nguồn mà ứng dụng dùng, đồng thời có renderer được SingleAgent và thí nghiệm cũ gọi. Những tệp đó vẫn có người gọi.

Các script trong tools được rà qua import và điểm gọi. Chúng phục vụ train, tạo notebook, xây KB, migration cloud, benchmark, xuất báo cáo hoặc kiểm tra giao diện. Các file kết quả benchmark, artifact, dữ liệu nguồn, notebook và tài liệu được giữ để đối chiếu thực nghiệm.

## Kiểm tra sau khi chuyển

Đã cập nhật import trong src, app, tools, tests và mã notebook. Các module dịch vụ giữ ROOT trỏ về thư mục final. Mã fingerprint benchmark theo đường dẫn mới. Các ảnh code và đường dẫn đã in trong báo cáo PDF/DOCX cũ phản ánh cấu trúc khi xuất tài liệu và cần xuất lại để khớp cấu trúc thư mục hiện tại.

Đã phân tích cú pháp Python và JSON của notebook, chạy bộ test, kiểm tra lệnh thêm web và benchmark qua --help. Dọn bộ nhớ đệm Python dưới src. Các lệnh chạy app và thêm web từ thư mục final giữ nguyên.

Đã bỏ knowledge/reviewed_facts.json, src/knowledge/kb_facts.py và tools/extract_kb_facts.py. Bộ dựng mới chỉ lấy tên thực thể và bí danh để tạo MENTIONS, với danh sách facts rỗng. Mã ingest vẫn đọc được bundle cũ để tương thích các snapshot đã lưu.

## Công cụ

Các script được chia theo chức năng trong tools/kb, tools/benchmarks, tools/training, tools/notebooks, tools/reports và tools/checks. Xem tools/README.md để chọn lệnh.
