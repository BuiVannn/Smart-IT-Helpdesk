# ADR-0011: Dùng UUIDv7 làm khoá chính

**Trạng thái:** Accepted · **Ngày:** 2026-07-30

## Bối cảnh
Ba lựa chọn cho khoá chính: `BIGSERIAL` tự tăng, `UUIDv4` ngẫu nhiên, hoặc `UUIDv7` (có tiền tố timestamp).

## Quyết định
Dùng **UUIDv7**, sinh ở **tầng ứng dụng** (thư viện `uuid6`/`uuid-utils`), không dùng `gen_random_uuid()` của database.

Riêng ticket có thêm cột `code` dạng `HD-YYYYMM-NNNNN` sinh từ sequence — dùng khi con người trao đổi với nhau.

## Hệ quả

### Tích cực
- **Có tính thứ tự theo thời gian** ⇒ bản ghi mới luôn chèn vào cuối B-tree index, không gây phân mảnh như UUIDv4. Đây là điểm khác biệt quyết định.
- **Không lộ thông tin nghiệp vụ**: `BIGSERIAL` cho phép đoán được hệ thống có bao nhiêu ticket và tốc độ tăng trưởng chỉ bằng cách xem ID của mình.
- Sinh được ở tầng ứng dụng **trước khi** ghi DB ⇒ dựng được cả đồ thị đối tượng liên kết rồi mới insert một lần.
- Không đụng độ khi gộp dữ liệu từ nhiều nguồn (seed, import, nhiều môi trường).

### Tiêu cực
- 16 byte thay vì 8 byte ⇒ index lớn hơn. Ở quy mô này (1,1 GB) hoàn toàn không đáng kể.
- Khó đọc bằng mắt khi debug ⇒ giải quyết bằng cột `code` cho ticket.
- UUIDv7 có nhúng timestamp ⇒ lộ thời điểm tạo bản ghi. Không phải vấn đề ở đây vì `created_at` vốn đã công khai.

## Phương án đã cân nhắc
- **`BIGSERIAL`**: nhỏ, nhanh, dễ đọc — nhưng lộ số lượng bản ghi và không sinh được trước khi ghi DB.
- **`UUIDv4`**: có tính riêng tư nhưng phân mảnh index nghiêm trọng khi bảng lớn.
