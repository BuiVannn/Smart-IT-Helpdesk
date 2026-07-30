# ADR-0002: PostgreSQL là kho dữ liệu duy nhất

**Trạng thái:** Accepted · **Ngày:** 2026-07-30

## Bối cảnh
Hệ thống có 5 loại nhu cầu dữ liệu khác nhau: dữ liệu quan hệ (ticket, user), tìm kiếm toàn văn (ticket, bài viết), tìm kiếm vector (RAG), cache/hàng đợi, và file nhị phân. Cách làm phổ biến là mỗi nhu cầu một hệ thống chuyên dụng.

## Quyết định
Dùng **PostgreSQL 16 cho bốn nhu cầu đầu tiên**:
- Dữ liệu quan hệ → bảng thông thường
- Tìm kiếm toàn văn → `tsvector` + GIN index (ADR-0004)
- Tìm kiếm vector → extension `pgvector` (ADR-0005)
- Dữ liệu bán cấu trúc → cột `JSONB`

Thêm **Redis** chỉ cho cache + broker Celery + đếm rate limit (không giữ dữ liệu nguồn sự thật), và **object storage** cho file nhị phân.

## Hệ quả

### Tích cực
- Một nguồn sự thật duy nhất ⇒ không có bài toán đồng bộ giữa các kho dữ liệu.
- Một chiến lược backup, một điểm cần giám sát, một thứ cần biết cách vận hành.
- Chunk vector và bài viết nằm trong **cùng một transaction** ⇒ không bao giờ lệch nhau.
- Truy vấn kết hợp dễ dàng: lọc vector search theo `status = 'PUBLISHED'` chỉ là một JOIN.

### Tiêu cực
- Tìm kiếm toàn văn của PostgreSQL yếu hơn Elasticsearch (không có phân tích hình thái tiếng Việt, khả năng tinh chỉnh relevance hạn chế).
- PostgreSQL trở thành điểm hỏng đơn duy nhất ⇒ bắt buộc backup hằng ngày + diễn tập khôi phục.

## Phương án đã cân nhắc
- **PostgreSQL + Elasticsearch + Qdrant**: 3 hệ thống phải vận hành, 2 pipeline đồng bộ, cho một tập dữ liệu 1,1 GB. Chi phí vận hành vượt xa lợi ích.

## Cân nhắc lại khi
Kho tài liệu vượt 500.000 chunk, hoặc người dùng phản ánh chất lượng tìm kiếm kém mà đã tinh chỉnh hết khả năng của PostgreSQL.
