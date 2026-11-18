# Benchmark conversation_v3

Đây là bộ đo mới cho `MultiAgent` mặc định, không gọi `LegacyMultiAgent`.
Giao diện chỉ nạp `/api/benchmark/v3`; các JSON/CSV cũ được giữ riêng để tái
lập lịch sử, không trộn vào bộ đo này.

## Ba phần

1. **PredictionAgent/model:** chạy checkpoint đang dùng trên toàn bộ 14.998
   mẫu test của phép chia stratified 70/15/15, seed 42 sau drop_duplicates.
   Không train lại, không chỉnh threshold/calibration trên test. Đây là
   metric phân loại của model, không phải pass rate của MAS.
2. **Retrieval:** 8 câu hỏi có qrels từ nguồn PDF/web thực trong KB, lặp 3
   lần với query cố định. Đo Hit@5, Recall@5, MRR@5 và latency. Qrels/anchor
   được cố định trong `benchmarks/v3_cases.json` và kiểm tra lại với nguồn;
   không đưa các nhãn này vào Agent. Đây là đánh giá retriever độc lập với
   việc Coordinator diễn giải tiếng Việt thành query.
3. **End-to-end:** 10 ca × 3 lần qua engine v3 thật và Groq thật: kiến thức,
   kê đơn bị chặn, ngoài phạm vi, hồ sơ dương/âm trong test, hồ sơ thiếu/lỗi,
   hai ca sửa lỗi citation/số liệu. Cache LLM tắt. Thứ tự đảo ở lượt lặp lẻ.

## Chấm điểm

- Chấm đúng intent và đảm bảo task knowledge không chạy DL.
- Hồ sơ lỗi phải bị chặn trước inference, có validation_errors.
- Score/nhãn inference phải khớp trực tiếp checkpoint; không thay đổi để
  cải thiện điểm MAS. Ground truth của hồ sơ chỉ dùng trong evaluator.
- Trích dẫn phải có ID thật, quote khớp nguồn, số liệu được quote hỗ trợ.
- Ý chính theo nhóm keyword/số cố định từ nguồn. Không dùng self-score của
  Critic như bằng chứng độc lập về tính đúng y khoa.
- Repair: sau LLM tạo draft đầu, evaluator tiêm ID citation sai hoặc mã số
  999999 ngoài quote, trong RAM riêng. Critic/ExplanationAgent thực tế phải
  phát hiện/sửa. Đo riêng phát hiện, sửa thành công và before/after đổi
  state. Không upload fault vào corpus, graph hay Qdrant.
- Contract/provenance của các Agent được tách khỏi chất lượng nội dung.
  Monitoring chỉ được chấm contract hiện có, không giả là đã có audit bền.

## Latency và availability

Đo wall time engine, không gồm startup Services/model hoặc HTTP từ trình
duyệt. Có gồm các call cloud, retry và thời gian chờ quota. Báo tất cả lượt,
median và p95, không loại bỏ lỗi provider. Thời gian handler bao gồm retry
của handler đó. Không cộng các handler thành percentile của toàn workflow.

Đây là pilot nhỏ: 3 lần lặp cùng case không phải 3 bệnh nhân/câu hỏi độc lập.
Các khoảng Wilson lưu trong JSON chỉ mang tính mô tả theo lượt, chưa hiệu
chỉnh phụ thuộc giữa các lần lặp; không dùng để suy rộng lâm sàng. p95 ở
nhóm 3–6 lượt gần giá trị lớn nhất, chưa phải kiểm thử tải hay SLA. Quota
Groq dùng chung với app có thể ảnh hưởng latency.

Nếu sửa lỗi trong evaluator, `--resume --rescore` chấm lại output đã lưu,
không chạy lại hoặc sửa câu trả lời. JSON giữ `previous_grade`, lịch sử
`scoring_revisions` và hash evaluator. Kiểm tra rule phân biệt việc từ chối
kết luận vì thiếu evidence với yêu cầu chuyển review do bất định model;
trường hợp review bắt buộc phải có cả flag review và nhãn cuối để trống.

Nếu gặp rate limit không xử lý được trong ngân sách chờ, script lưu cả
lượt thất bại và chuyển `phase=quota_limited`. UI hiển thị đã chạy/đã lên
kế hoạch. Các ca chưa chạy không được tính là đạt; phần thiếu không được
điền bằng số cũ. Có thể tiếp tục bằng --resume sau khi provider khả dụng.

## Chạy và kết quả

```powershell
python tools/benchmarks/benchmark_conversation_v3.py --phase components --repeats 3
python tools/benchmarks/benchmark_conversation_v3.py --phase live --repeats 3 --resume
```

Kết quả: `results/benchmark_v3.json`, `results/benchmark_v3_trials.csv`.
Mỗi lượt lưu output, trace, thông điệp, trạng thái, before/after và kiểm tra
cụ thể. Ghi hash runtime, checkpoint, dataset, case và KBVersion. UI cảnh
báo nếu runtime hoặc KB không khớp phiên bản đã đo. Không suy ra ưu thế
Multi so với Single vì bộ đo này không phải thí nghiệm so sánh hai hệ.

## Hai chế độ app

API nhận `task=assessment|knowledge|auto`. `assessment` ép validation trước
DL; profile sai không gọi LLM/model. `knowledge` bỏ profile, và không cho
planner chạy PredictionAgent. Hỏi tiếp là task knowledge, không âm thầm
chạy lại score. `auto` giữ tương thích client cũ. Kết quả có task và trace
thực tế; sơ đồ trên UI mô tả nhánh tác vụ, không thay thế trace thực thi.
