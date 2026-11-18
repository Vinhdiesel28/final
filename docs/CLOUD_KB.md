# Chuyển cả Neo4j và Qdrant lên cloud

Trạng thái chỉ được coi là hoàn tất khi `results/cloud_migration_receipt.json`
có `status=verified` và `activated=true`. Chưa có thông tin đăng nhập thì
code sẵn sàng không có nghĩa dữ liệu đã được chuyển.

## Cấu hình riêng trước khi chuyển

Tạo AuraDB ở https://console.neo4j.io và Qdrant cluster ở
https://cloud.qdrant.io. Chọn Free nếu phù hợp và còn được cung cấp. Lưu
password/credentials file của Neo4j ngay khi tạo. Với Qdrant, cần **Database
API key** có quyền ghi và tạo collection, không phải Cloud Management key.

Điền file `.env.cloud` (đã được Git ignore):

```dotenv
NEO4J_URI=neo4j+s://<instance>.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password>
NEO4J_DATABASE=neo4j
QDRANT_URL=https://<cluster-endpoint>
QDRANT_API_KEY=<database-api-key>
QDRANT_COLLECTION_PREFIX=diaguard
```

Không sửa `.env` đang dùng local trước khi kiểm tra xong. Không gửi key
vào chat, không commit `.env.cloud` hay `.env`.

## Thực hiện từ thư mục final

```powershell
python tools/kb/migrate_cloud_kb.py
python tools/kb/migrate_cloud_kb.py --apply --activate
```

Lệnh đầu kiểm tra cấu hình và kết nối, chưa ghi dữ liệu. Lệnh sau:

1. Đọc snapshot Neo4j đang hoạt động, cả legacy DiaDocument/DiaEntity và
   Hybrid Document/Chunk/Entity/Fact. Đọc vector/payload thật từ Qdrant local.
2. Upload 2 collection Qdrant có tên theo phiên bản: một collection cho
   Hybrid KB hiện tại, một cho vector cũ. Không trộn hai loại chunk ID.
3. So sánh mọi payload và hướng vector sau upload, kiểm tra số point.
4. Nạp graph, nội dung, vector và index vào AuraDB; đối chiếu với nguồn local.
5. Chỉ sau khi đạt kiểm tra mới đổi các biến liên quan trong `.env`; giữ
   nguyên cấu hình Groq và những thiết lập khác. Khởi động lại app sau đó.

Nguồn local không bị xóa. Script không delete/recreate collection hoặc xóa
graph cloud. Khi lỗi giữa chừng, `.env` chưa được chuyển; các bản upload dở
có thể nạp lại theo cùng phiên bản. Không chạy `--apply` lần nữa để cập nhật
KB sau khi đã chuyển; dùng lệnh cập nhật bên dưới.

## Kiến trúc khi đã kích hoạt

```text
Ứng dụng → AuraDB: tài liệu, chunk, fulltext, Entity/Fact và nguồn
         → Qdrant Cloud: vector search cho đúng phiên bản Hybrid KB
         → Groq: diễn giải và phản biện
```

`HYBRID_VECTOR_BACKEND=qdrant` làm nhánh vector thực sự gọi Qdrant Cloud.
Fulltext và graph vẫn gọi Neo4j. Vector cũng còn trong Neo4j để giữ bản sao
và khả năng dùng lại nhánh Neo4j. Các file embedding LSA, PDF và snapshot
web vẫn ở project; việc chuyển database không tự đưa những file này lên
object storage. Cần mang chúng theo khi deploy Render.

## Thêm PDF/web sau khi chuyển

```powershell
python tools/kb/build_hybrid_kb.py --fetch-web --ingest
```

Ingestion upload/verify collection Qdrant phiên bản mới trước, rồi nạp Neo4j
và đổi KBVersion. Khi app khởi động lại, collection được chọn theo chính
KBVersion đó. Không trỏ graph mới sang collection vector cũ.

## Render

Đặt các giá trị cloud từ `.env` đã kích hoạt vào Environment của dịch vụ:
`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `QDRANT_URL`,
`QDRANT_API_KEY`, `QDRANT_COLLECTION_PREFIX`, `QDRANT_LEGACY_COLLECTION`.
Đặt `KNOWLEDGE_BACKEND=neo4j`, `HYBRID_KB=enabled`,
`HYBRID_VECTOR_BACKEND=qdrant`. Không đưa secret vào render.yaml/GitHub.

Kiểm tra `/health`: vector backend phải hiện
`Qdrant Cloud vector + Neo4j fulltext + graph`. Không cần gọi Groq để kiểm
tra kết nối/migration database.
