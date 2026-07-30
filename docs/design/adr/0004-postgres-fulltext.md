# ADR-0004: Dùng PostgreSQL full-text search thay vì Elasticsearch

**Trạng thái:** Accepted · **Ngày:** 2026-07-30

## Bối cảnh
Cần tìm kiếm toàn văn cho ticket (US-16) và bài viết kho tri thức (US-30). Quy mô dữ liệu sau 3 năm: ~28.800 ticket và ~300 bài viết. Nội dung chủ yếu tiếng Việt, người dùng thường gõ **không dấu**.

## Quyết định
Dùng `tsvector` + GIN index của PostgreSQL với cấu hình `simple` kết hợp extension `unaccent`.

Trigger tự động cập nhật `search_vector` khi `title`/`description` thay đổi, có đánh trọng số (title = A, description = B).

## Hệ quả

### Tích cực
- Không thêm hệ thống nào phải vận hành.
- Không có pipeline đồng bộ ⇒ không bao giờ lệch giữa dữ liệu và chỉ mục.
- Kết quả tìm kiếm tự động tôn trọng phân quyền (chỉ là thêm điều kiện `WHERE` vào cùng câu truy vấn) — với Elasticsearch, việc này phải cài đặt lại từ đầu và rất dễ sai.
- `unaccent` giải quyết đúng vấn đề thực tế của người dùng Việt: gõ "mat khau" tìm ra "mật khẩu".

### Tiêu cực
- Không có phân tích hình thái tiếng Việt ⇒ không tự tách từ ghép. Cấu hình `simple` tách theo khoảng trắng.
- Không có gợi ý sửa lỗi chính tả, không có synonym, khả năng tinh chỉnh relevance hạn chế.
- Không có faceted search phức tạp (nhưng lọc theo category/status bằng SQL là đủ).

## Phương án đã cân nhắc
- **Elasticsearch**: +1 service (JVM, ~1 GB RAM), +1 pipeline đồng bộ, +1 điểm hỏng, +1 thứ phải học vận hành — cho 300 bài viết. Không tương xứng.
- **Chỉ dùng `ILIKE '%...%'`**: không có xếp hạng độ liên quan, không dùng được index, chậm dần theo dữ liệu.

## Cân nhắc lại khi
Người dùng phản ánh chất lượng tìm kiếm kém **và** đã thử `pg_trgm` cho tìm gần đúng; hoặc kho tài liệu vượt 10.000 bài.
