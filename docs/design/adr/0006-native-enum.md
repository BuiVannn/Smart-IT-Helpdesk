# ADR-0006: Dùng PostgreSQL native ENUM cho tập giá trị ổn định

**Trạng thái:** Accepted · **Ngày:** 2026-07-30

## Bối cảnh
Nhiều cột có tập giá trị hữu hạn: `user_role`, `ticket_status`, `ticket_priority`, `article_status`... Có ba lựa chọn: native ENUM, `VARCHAR` + `CHECK`, hoặc bảng tra cứu (lookup table).

## Quyết định
- **Native ENUM** cho các tập giá trị **ổn định**: `user_role`, `ticket_status`, `ticket_priority`, `ai_status`, `actor_type`, `event_type`, `article_status`, `message_role`.
- **`VARCHAR` + `CHECK`** cho tập giá trị **sẽ còn được bổ sung**: `notification_type`, `source`.
- **Bảng tra cứu** cho dữ liệu người dùng tự quản lý: `ticket_categories`, `kb_categories` (Admin thêm/sửa được qua giao diện).

## Hệ quả

### Tích cực
- Ràng buộc được cưỡng chế ở tầng database — dữ liệu sai không lọt vào được kể cả khi ghi thẳng bằng SQL.
- Tiết kiệm không gian, so sánh nhanh.
- Ánh xạ trực tiếp sang `enum.Enum` của Python và enum của TypeScript.

### Tiêu cực
- **Không xoá được giá trị** khỏi ENUM (chỉ ngừng dùng).
- Thêm giá trị cần `ALTER TYPE ... ADD VALUE` — ở PostgreSQL < 12 không chạy được trong transaction.
- Đổi thứ tự giá trị ENUM là thao tác phức tạp.

## Vì sao chấp nhận được
Ba tập giá trị quan trọng nhất (`role`, `status`, `priority`) là **quyết định nghiệp vụ cốt lõi**, đã được thiết kế kỹ ở tài liệu 03 §5 và không nên thay đổi tuỳ tiện. Việc ENUM khiến thay đổi trở nên "khó" ở đây là **tính năng, không phải khuyết điểm** — nó buộc mọi thay đổi phải đi qua một migration có review.

Ngược lại `notification_type` chắc chắn sẽ được bổ sung thêm loại mới ⇒ dùng `VARCHAR` + `CHECK` cho dễ mở rộng.
