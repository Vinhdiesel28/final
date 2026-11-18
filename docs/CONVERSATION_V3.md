# Luồng hội thoại RAG v3

`MultiAgent` trong `src/agent_system.py` là lớp gọi luồng mới tại
`src/conversational_agents.py`. API `/api/run` và `/api/compare` dùng luồng này.
Đây là thay đổi chung cho câu hỏi kiến thức và tư vấn thông tin, không phải
thêm một câu trả lời cố định cho câu hỏi xét nghiệm.

## Thực thi

1. CoordinatorAgent dùng LLM phân tích câu hỏi, ngữ cảnh và chọn công cụ.
   Có hồ sơ trên form không tự động có nghĩa người dùng muốn dự đoán.
2. Nếu cần dự đoán: ValidationAgent kiểm tra hồ sơ, PredictionAgent gọi
   checkpoint hiện có, RuleBasedAgent áp chính sách bất định. Không thay score.
3. Với kiến thức/tư vấn thông tin: RetrievalAgent tìm trong KB thật qua
   Neo4j hybrid retrieval (vector/fulltext/graph). EvidenceReaderAgent xếp lại
   theo độ phủ thuật ngữ có trọng số IDF từ KB, chọn cửa sổ văn bản liên quan
   và giữ metadata trang PDF, URL, mã chunk. Đây là reranking từ vựng, không
   tự nhận là cross-encoder. Không gọi hàm ghép câu
   theo từ khóa của workflow cũ để tạo câu trả lời mới.
4. ExplanationAgent dùng LLM viết các phát biểu tiếng Việt theo bằng chứng.
   Mỗi phát biểu có evidence_id và quote nguyên văn. Phần score mô hình được
   chương trình trình bày riêng, LLM không được sửa.
   WorkflowRLAgent giữ Q-policy đã có, lựa chọn truy xuất bổ sung hoặc sang
   bước giải thích trong tập hành động được cho phép. Action được dispatch
   tới handler thật và ghi `executed_handler`. Thiếu thông tin bắt buộc thì
   mask chỉ cho hỏi thêm; Q-value không vượt qua ràng buộc này. Critic và
   Verifier giữ quyền chặn câu trả lời. RL chỉ học trên mô phỏng workflow,
   không học lựa chọn xét nghiệm/điều trị cho người bệnh.
5. CriticAgent kiểm tra mã nguồn/quote/số/điều kiện bằng code rồi gọi LLM
   đối chiếu câu hỏi và văn bản nguồn. Quyết định: accept, revise,
   retrieve_again, clarify hoặc abstain.
6. Challenge thực sự gọi lại ExplanationAgent hoặc RetrievalAgent. Mỗi vòng
   lưu before/after, state_changed; tối đa 3 bản nháp. Hết ngân sách mà chưa
   được chấp nhận thì không trình bày bản nháp như đáp án đã kiểm chứng.
7. VerifierSafetyAgent kiểm tra tính nhất quán cuối. MonitoringAgent trả
   metadata thời gian và số bước; không lưu hồ sơ hội thoại vào KB.

Các handler có thực thi và trao đổi REQUEST/CHALLENGE/INFORM qua MessageBus.
Không phải mọi handler đều cần LLM: validation, model, thống kê và kiểm tra
cấu trúc là công cụ xác định. ClarificationAgent đặt câu hỏi theo nhu cầu
thay vì bắt điền một form xét nghiệm cố định. Lượt hỏi tiếp gửi tối đa 8
thông điệp ngữ cảnh, giữ trong phiên trình duyệt, không nhập vào corpus.

Thống kê dataset dùng công cụ thống kê, không ép gọi RAG. Yêu cầu ngoài
phạm vi/kê đơn bị chặn. Nếu nhà cung cấp LLM lỗi hoặc giới hạn quota, trả
trạng thái partial; không dùng đoạn trích ít liên quan để giả làm đáp án.

## Tệp

- `src/services/agent_llm.py`: transport JSON schema, cache RAM 600 giây cho đầu vào
  giống hệt; không lưu key hoặc prompt ra đĩa. Nếu Groq từ chối định dạng
  schema, thử JSON mode đúng một lần; vẫn kiểm tra cùng hợp đồng Pydantic
  tại ứng dụng. Không bỏ validation. Khi HTTP 429 có Retry-After ngắn, chờ
  theo nhà cung cấp và thử lại tối đa 2 lần, tổng chờ tối đa 20 giây/call
  (`LLM_RATE_LIMIT_MAX_WAIT`, chặn trên 30 giây). Không tự chờ lâu cho quota
  theo ngày; trả thời gian chờ và task bị gián đoạn. Các call v3 xếp hàng
  chung để tránh burst. Giao diện mặc định chỉ chạy Multi; checkbox so sánh
  mới chạy thêm Single. Các nút gửi bị khóa trong khi yêu cầu đang chạy.
- `src/contracts/conversation_contracts.py`: hợp đồng Plan, Draft, Critique.
- `knowledge/retrieval_terminology.json`, `src/knowledge/retrieval_terms.py`: đồng nhất
  tên viết tắt/tên đầy đủ khi tìm kiếm và xếp hạng (ví dụ HbA1c/A1C), đồng
  thời xét tiêu đề/section. Không thay văn bản gốc, quote hoặc nạp đáp án mẫu.
- `src/conversational_agents.py`: handler, điều phối, vòng sửa, xác minh.
- `app/main.py`, `app/static/app.js`: API, ngữ cảnh hội thoại, xem kế hoạch,
  quyết định Critic, nguồn và trạng thái trước/sau.
- `tests/test_conversation_agents.py`: dữ liệu giả lập độc lập trong tests,
  chứng minh truy xuất lại/viết lại thay đổi kết quả và từ chối citation giả.
- `tools/checks/check_conversation_v3.py`: kiểm tra tích hợp trên câu hỏi công khai,
  ghi `results/conversation_v3_case*.json`, đối chiếu quote với PDF gốc.

## Giới hạn và số liệu lịch sử

LLM kiểm tra LLM không phải chứng minh đúng y khoa. Có thể cùng bỏ sót lỗi.
Trích đúng câu không đảm bảo diễn giải đúng toàn bộ ngữ cảnh. KB cần nguồn
đúng, đủ và cập nhật. Embedding hiện dùng LSA đã có, không tự nhận là mô hình
embedding ngữ nghĩa chuyên ngành. Ngôn ngữ câu trả lời phụ thuộc Groq,
quota, chất lượng truy xuất và tài liệu có trong KB.

`LegacyMultiAgent` giữ workflow cũ để tái lập các thí nghiệm lịch sử.
Các script benchmark cũ được pin vào lớp này. Các số liệu cũ trên dashboard
không chứng minh chất lượng của v3. SingleAgent vẫn là baseline một lượt
cũ; không thể quy toàn bộ chênh lệch cho số lượng Agent khi hai bên khác
ngân sách LLM/vòng sửa. Chưa chạy một benchmark y khoa ground-truth mới.
Các lần thử trực tiếp và unit test chỉ xác minh tích hợp/cơ chế, không
chứng minh an toàn lâm sàng hoặc Multi-Agent luôn tốt hơn Single-Agent.

Khi Critic yêu cầu sửa, ExplanationAgent nhận cả previous_draft và challenge
trong một lượt sửa riêng, thay vì chỉ nhận mã lỗi rồi trả lời lại từ đầu.
Prompt được rút gọn, metadata nguồn đầy đủ vẫn giữ ở State/UI nhưng chỉ gửi
những trường cần thiết tới LLM để giảm quota token. Giới hạn nhà cung cấp
vẫn có thể làm yêu cầu chờ hoặc dừng, nhất là khi bật so sánh hai hệ.
