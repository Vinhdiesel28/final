# Bảy tác tử của DiaGuard

| File | Tác tử | Trách nhiệm |
|---|---|---|
| coordinator_agent.py | CoordinatorAgent | Phân tích ý định, tạo truy vấn và lựa chọn luồng. |
| data_agent.py | DataAgent | Kiểm tra hồ sơ và yêu cầu làm rõ. |
| dl_agent.py | DLAgent | Gọi mô hình dự đoán đã train. |
| rule_agent.py | RuleAgent | Kiểm tra kết quả theo chính sách review. |
| knowledge_agent.py | KnowledgeAgent | Truy xuất Hybrid RAG, chuẩn bị đoạn bằng chứng và thống kê dữ liệu. |
| explanation_agent.py | ExplanationAgent | Soạn nháp, phản biện, tổng hợp điểm/luật/bằng chứng và kiểm chứng. |
| monitoring_agent.py | MonitoringAgent | Ghi thông tin thực thi của lượt chạy. |

Luồng tổng thể nằm trong ../conversational_agents.py. Các dịch vụ dùng chung nằm trong ../services và hợp đồng thông điệp nằm trong ../contracts. Coordinator điều phối qua MessageBus, các handler của bảy tác tử được đăng ký ở đầu lượt chạy.

Message có request_id, agent, status, payload, evidence, version (phiên bản Agent), model_version và schema_version; giữ sender, receiver, performative, content để tương thích. Trường action trong content xác định thao tác khi một tác tử làm nhiều việc. Trace hiển thị thao tác ở trường tool.

Trong luồng đánh giá hồ sơ, ExplanationAgent có các thao tác draft, critique, compose và verify. Nếu cần tìm thêm nguồn, bước critique yêu cầu KnowledgeAgent xử lý lại. Kết quả trước/sau vẫn lưu trong revisions. Luồng hỏi kiến thức bỏ qua DLAgent khi không có yêu cầu dự đoán.

Tên tác tử của benchmark lịch sử được giữ trong file kết quả đã lưu. Bộ chấm hiện tại hỗ trợ cả kết quả lịch sử và hợp đồng bảy tác tử. Báo cáo và ảnh code đã xuất trước thay đổi cần cập nhật nếu dùng để trình bày bản bảy tác tử.

Hợp đồng đầy đủ về input/output, phiên bản, lỗi và audit record được mô tả ở [docs/AGENT_CONTRACTS.md](../../docs/AGENT_CONTRACTS.md).
