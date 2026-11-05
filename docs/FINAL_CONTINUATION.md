# Quyển Final tiếp nối tiểu luận 3

Bố cục tham khảo quyển Final của Nguyễn Tự Kiên: bảy chương lịch sử AI, ML, CNN, RNN, KG/RAG, học sâu trên đồ thị và hệ đa tác tử. Dataset, checkpoint và số đo sử dụng kết quả của Nguyễn Minh Vinh.

| Phần | Nguồn nội dung và kết quả |
|---|---|
| Chương 1–5 | `Vinhdiesel28/tieuluan3`, báo cáo `Tieu_luan_03_Nguyen_Minh_Vinh.md`, giữ biểu đồ và bảng kết quả |
| Agent cũ | Tóm lược Chương 6 của tiểu luận 3 tại mục 7.2, không trộn với benchmark project mới |
| Chương 6 mới | `tools/train_graph_chapter.py`, `notebooks/10_deep_graph_cdc.ipynb`, `results/deep_graph/` |
| Chương 7 | `src/agent_system.py`, notebook 07–09, checkpoint PyTorch/sklearn, Neo4j và benchmark 58 case/hệ |
| Minh họa chuột/mèo | Demo Agent01 của sinh viên; chỉ chuột học, mèo chạy theo luật, không tự nhận là hai agent cùng học |

Chương 6 lấy 1.600 mẫu phân tầng từ CSV CDC BRFSS 2015 đã có trong project; dùng giao thức transductive, kNN=10. Loss chỉ dùng nhãn train; toàn bộ đặc trưng và graph được thấy khi học. Đây không phải Pubmed của bài mẫu và không phải KG Neo4j. Checkpoint GNN chưa được đưa vào web.

Chương 7 giữ Diabetes Prediction Dataset, CDC BRFSS 2015 và KB hiện tại của sinh viên. Không thay bằng NHANES, BRFSS nhiều năm, RetinaMNIST hay ShanghaiT1DM của bài mẫu.

Build bằng `python tools/build_final_continued.py`. Cần checkout `tieuluan3` cạnh `final` để lấy nội dung gốc; ảnh được sao chép vào `report/assets/final_continued/`. PDF nộp bài và DOCX nằm trong `report/`. Mục lục Word được cập nhật khi chạy `tools/export_reports_pdf.ps1 -FinalOnly`.
