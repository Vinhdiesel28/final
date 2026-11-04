# Kiến trúc DiaAgents Lab

## Mục tiêu

So sánh công bằng một Single Agent với một hệ Multi-Agent trên cùng model, dataset, Knowledge Base và bộ công cụ. Hệ thống chỉ cung cấp risk score học thuật và thông tin có nguồn; không chẩn đoán hoặc kê đơn.

## Luồng Single Agent

`request → SingleAgent(route + tool + compose + safety) → response`

Single Agent sở hữu toàn bộ quyết định. Trace có một bước, thuận tiện và ít overhead nhưng khó chỉ ra lỗi thuộc khâu nào.

## Luồng Multi-Agent

`Coordinator → Validation/Prediction/Statistics → Retrieval/Graph → Explanation → VerifierSafety`

Không phải mọi Agent đều chạy cho mọi yêu cầu. Coordinator chọn đúng đường dựa trên intent. Mỗi Trace ghi agent, tool, thời gian và tóm tắt output.

## Hợp đồng trạng thái

- `request_id`, `mode`, `intent`, `status`.
- `prediction`, `statistics`, `knowledge`.
- `validation_errors`, `safety_flags`.
- `traces`, `total_duration_ms`.

## Trạng thái cuối

- `supported`
- `supported_with_limitations`
- `invalid_input`
- `insufficient_evidence`
- `blocked_unsafe_request`
- `out_of_scope`

## Nguyên tắc benchmark

- Cùng 28 trường hợp đầu vào.
- Cùng checkpoint và threshold.
- Cùng corpus, graph và top-k.
- Không sửa riêng prompt hoặc gold cho một hệ.
- Báo route accuracy, task success, citation recall, latency và trace steps.

Benchmark ban đầu là kiểm tra contract; trước báo cáo cuối sẽ tăng độ khó bằng paraphrase, nhiễu, câu nhiều bước và evidence xung đột.
