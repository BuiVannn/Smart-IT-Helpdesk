# ADR-0009: Phân loại ticket bằng AI chạy bất đồng bộ

**Trạng thái:** Accepted · **Ngày:** 2026-07-30 · **Người quyết định:** Bùi Mậu Văn

## Bối cảnh
F3 yêu cầu AI tự động phân loại ticket ngay khi được tạo. Cách làm trực tiếp nhất là gọi LLM ngay trong `POST /tickets` và trả về ticket đã có category.

Ràng buộc: NFR bắt buộc **p95 < 500 ms**. Độ trễ LLM thực tế: **2–5 giây**.

## Quyết định
`POST /tickets` trả về ngay với `ai_status = 'PENDING'`. Một Celery task được đẩy vào hàng đợi và hoàn tất phân loại trong **≤ 30 giây**. Frontend hiển thị nhãn "Đang phân loại…" rồi cập nhật.

AI worker chỉ ghi khi `ai_status = 'PENDING' AND category_id IS NULL` — **con người luôn thắng AI**.

## Hệ quả

### Tích cực
- API tạo ticket giữ được p95 < 500 ms — đạt NFR bắt buộc.
- **LLM provider hỏng không làm mất khả năng tạo ticket.** Điều này cực kỳ quan trọng: lúc xảy ra sự cố IT diện rộng (đúng lúc cần hệ thống nhất) mà không tạo được ticket vì một dịch vụ bên thứ ba là kịch bản không chấp nhận được.
- Rate limit của provider không trở thành rate limit của việc tạo ticket.
- Retry, backoff, circuit breaker được xử lý gọn ở tầng worker.

### Tiêu cực
- Frontend phải xử lý trạng thái trung gian và làm mới để lấy kết quả.
- Có khoảng thời gian ticket chưa được phân loại (chấp nhận được — đã ghi trong bảng nhất quán ở tài liệu 01 §7).
- Cần job đối soát cho các tác vụ bị mất (ADR-0007).

## Phương án đã cân nhắc
- **Đồng bộ**: vi phạm NFR, và biến LLM provider thành phụ thuộc cứng của chức năng quan trọng nhất hệ thống.
- **Đồng bộ có timeout ngắn (1 s), thất bại thì bỏ qua**: phần lớn lời gọi sẽ timeout, tốn tiền mà không được kết quả.
