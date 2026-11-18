# Communication and Data Contracts — 7 Agent

Phiên bản hợp đồng Agent: `1.0.0`. Schema message: `2.0`. Luồng live không dùng RL.
Code điều phối: `src/conversational_agents.py`, hàm `ConversationAgents.run`.

## 1. Envelope chung

Mọi REQUEST, CHALLENGE, INFORM, RESPONSE và FAILURE đều được tạo qua
`src/contracts/message_bus.py`, hàm `MessageBus.emit`.

| Trường | Kiểu | Ý nghĩa |
| --- | --- | --- |
| request_id | string | Một mã `req_<uuid>` cho toàn lượt xử lý, cũng xuất hiện ở kết quả và audit |
| agent | string | Agent nhận việc với REQUEST/CHALLENGE; Agent phát kết quả với INFORM/RESPONSE/FAILURE |
| status | string | `pending` khi gửi việc; trạng thái nghiệp vụ nếu handler trả status; `ok` nếu hoàn thành bình thường; `error` khi handler ném exception |
| payload | object | Dữ liệu đầu vào hoặc đầu ra theo thao tác |
| evidence | array | Các nguồn truy xuất; với Rule là rationale có `kind=rule_rationale`; rỗng nếu không áp dụng |
| version | string | Phiên bản hợp đồng/handler của Agent, mặc định `1.0.0` |
| model_version | string hoặc null | Phiên bản checkpoint do model service trả về; không suy ra từ schema message |
| schema_version | string | Phiên bản envelope `2.0` |
| sender, receiver | string | Bên gửi và bên nhận |
| performative | string | REQUEST, CHALLENGE, INFORM, RESPONSE hoặc FAILURE |
| sequence | integer | Số thứ tự trong request |
| duration_ms | number | Thời gian thực thi handler cho message kết quả |
| content | object | Bản tương thích của payload cho UI và benchmark hiện tại |

Envelope được chụp sâu tại lúc phát; sửa object bên ngoài không sửa lịch sử message.
`register(name, handler, version=...)` đăng ký phiên bản handler.
Thông điệp FAILURE chỉ ghi tên loại exception; không đưa chi tiết exception vào payload.

Ví dụ minh họa, score không phải số đo thực nghiệm:

```json
{
  "request_id": "req_example",
  "agent": "DLAgent",
  "status": "ok",
  "payload": {"predicted_class": 1, "probability": 0.78, "model_version": "2.0.0"},
  "evidence": [],
  "version": "1.0.0",
  "model_version": "2.0.0",
  "schema_version": "2.0"
}
```

Tên `predicted_class` và `probability` giữ đúng model service hiện tại.
Score là đầu ra mô hình học thuật, chưa phải xác suất lâm sàng đã được hiệu chỉnh.

## 2. Hợp đồng 7 Agent

### DataAgent — src/agents/data_agent.py

Entry point: `handle(payload, *, model)`; mặc định action=validate.

- validate input: `{action: "validate", profile: object}`.
- output: `{status: "ok" | "validation_failed", validated_features: object | null, errors: array}`.
- errors gồm `{field: string, message: string}`; chỉ trả feature mapping khi không có lỗi.
- Tập feature lấy từ model metadata (fallback danh sách 8 feature của project); loại trường ngoài danh sách.
- clarify input: `{action: "clarify", questions: string[], status?: string}`.
- clarify output: status, questions (tối đa 3), requested_fields, answer, summary.
- Hồ sơ lỗi dừng trước DL, Rule và KG/RAG; vẫn có hướng dẫn bổ sung, verification và audit.
- Yêu cầu hội thoại thiếu bối cảnh dùng needs_clarification, khác lỗi hồ sơ validation_failed.

### DLAgent — src/agents/dl_agent.py

Entry point: `predict(payload, *, model)`.

- input: `{features: object}` từ validated_features của DataAgent.
- output: status=ok, model, model_version, feature_names, probability, threshold,
  predicted_class, risk_level, feature_impacts và second_opinion theo model service.
- Chấp nhận profile ở đầu vào để tương thích code cũ.
- Metadata phiên bản lấy từ kết quả model; không tự gán phiên bản nếu service không cung cấp.
- Không đổi checkpoint, threshold, score hoặc nhãn trong bước chuẩn hóa hợp đồng.

### RuleAgent — src/agents/rule_agent.py

Entry point: `rules(payload, *, review_policy)`.

- input: `{features: object | null, prediction: object | null}`.
- output: status, assessment, rule_results, review_required, reason_codes, summary.
- validated_features_present kiểm tra các feature của mô hình có trong mapping.
- prediction_feature_consistency đối chiếu giá trị hồ sơ với value trong feature_impacts;
  chỉ kiểm tra được những feature model công bố trong danh sách này.
- ReviewPolicy đánh giá bất đồng và khoảng cách score/ngưỡng theo artifact validation.
- Rule lỗi nhất quán hoặc policy yêu cầu review sẽ bật review_required; không sửa score.
- Với hỏi kiến thức không có prediction, assessment=null, rule_results=[] và không đánh giá hồ sơ.
- Các luật hiện tại là kiểm tra nhất quán và policy review; không phải bộ luật chẩn đoán lâm sàng.

### KnowledgeAgent — src/agents/knowledge_agent.py

Entry point: `handle(payload, *, knowledge, services, reader, queries, requested_sources)`.

- retrieve input: `{action: "retrieve", queries: string[]}`.
- output: evidence, citations/metadata truy xuất và phân tích truy vấn theo KnowledgeService.
- evidence giữ evidence_id, text và source (nguồn PDF/web, vị trí nếu có trong KB).
- read input: `{action: "read", evidence: object[]}`; output: evidence đã chọn/chuẩn bị.
- statistics input: `{action: "statistics", question: string}`; output: group, positive, count, rate.
- Không tạo dữ liệu benchmark giả làm bằng chứng trong KB.

### CoordinatorAgent — src/agents/coordinator_agent.py và src/conversational_agents.py

`analyze(payload, *, task, llm)` nhận question, conversation, available_profile_fields,
additional_context; trả intent, goal, queries, clarification_questions, can_answer_general,
requested_sources và summary.
`ConversationAgents.run(question, profile, testing_context, conversation, task)` thực thi điều phối,
request ID, gọi handler và trả kết quả tổng hợp có cấu trúc.

Assessment: Data validate → DL → Rule → Knowledge retrieve/read → Explanation.
Knowledge: phân tích câu hỏi → Knowledge → Explanation; không chạy DL.
Nếu dữ liệu không hợp lệ, trả validation_failed cùng errors và hướng dẫn.
Khi cần sửa: critique → revise hoặc retrieve_again → draft lại → critique.
Tối đa 3 vòng soạn/phản biện. Thiếu bằng chứng thì từ chối kết luận phù hợp.

### ExplanationAgent — src/agents/explanation_agent.py

Entry point: `handle(payload, *, task, llm, user_numbers)`.

- draft (mặc định): question, goal, intent, conversation, evidence, challenge và previous_draft nếu có.
  Trả claims (text, evidence_id, quote), followup_questions, evidence_sufficient, missing_information.
- critique: draft, evidence và ngữ cảnh câu hỏi; trả action=accept/revise/retrieve_again/clarify/abstain,
  lý do, revised_query và câu hỏi cần làm rõ.
- compose: prediction, rules, evidence, draft, critique, intent, clarification_questions.
  Trả explanation có sections, decision, evidence và citations.
- verify: status, answer, draft, review, evidence, prediction; trả passed, issues, scope, summary.
- Phần LLM soạn nháp chỉ nhận bằng chứng và ngữ cảnh được chọn; score/luật được tổng hợp cục bộ
  tại compose để giữ nguyên dự đoán. Cờ review bắt buộc giữ final_label=null.

### MonitoringAgent — src/agents/monitoring_agent.py

Entry point: `monitor(payload, *, state)`.

- input payload: request_id, status, started_at (UTC ISO 8601), task.
  State cung cấp trace và metadata của lượt chạy qua dependency injection.
- output: status, steps, audit_record, summary.
- audit_record gồm request ID, status, started_at, recorded_at, duration_ms, task,
  architecture_version, agent_contract_version, message_schema_version,
  executions (agent, status, duration_ms, summary, tool), steps, message_count,
  validation_error_count, model_version, knowledge_backend, retrieved_evidence_ids,
  citation_ids, revision_count, verification_passed và review_required.
- Snapshot audit được tạo trước khi handler Monitoring trả về; steps/message_count không tính
  trace/response Monitoring sau đó. duration_ms đo đến lúc tạo record.
- API trả audit_record ở cấp ngoài cùng. Đây là audit trong kết quả request, chưa phải kho audit lưu bền.
- Record không chứa giá trị hồ sơ/câu hỏi. Message payload vẫn có thể chứa dữ liệu bệnh nhân;
  cần kiểm soát quyền nếu sau này lưu toàn bộ message vào hệ thống log.

## 3. Lỗi và kiểm chứng

Exception handler: bus phát FAILURE, điều phối trả error/partial theo loại lỗi, kết thúc qua verification và audit.
Chỉ lỗi xác thực hồ sơ dùng validation_failed. Các trường hợp thiếu bằng chứng hoặc thiếu bối cảnh
có trạng thái riêng và không tự biến thành kết luận chẩn đoán.

Kiểm tra tại tests/test_agent_contracts.py và tests/test_conversation_agents.py:
định danh request, schema/version, message lỗi, snapshot bất biến, chuyển feature đã xác thực,
Rule bật review khi feature bất nhất mà không đổi score, và audit cả nhánh thành công/lỗi hồ sơ.
