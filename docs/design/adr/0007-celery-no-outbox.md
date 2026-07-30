# ADR-0007: Đưa tác vụ vào Celery trực tiếp, chưa dùng transactional outbox

**Trạng thái:** Accepted · **Ngày:** 2026-07-30

## Bối cảnh
Nhiều thao tác cần "ghi database **và** kích hoạt việc gì đó": tạo ticket → phân loại AI; đổi trạng thái → gửi thông báo; publish bài viết → index vector.

Đây là bài toán **dual-write** kinh điển: nếu ghi DB thành công nhưng đẩy tác vụ vào hàng đợi thất bại (hoặc tiến trình chết ở giữa), tác vụ đó **mất vĩnh viễn**. Giải pháp chuẩn là **transactional outbox**: ghi sự kiện vào bảng `outbox` trong cùng transaction, một relay đọc bảng đó và publish.

## Quyết định
**Chưa dùng outbox.** Đẩy tác vụ vào Celery **sau khi transaction commit thành công**:

```python
with session.begin():
    ticket = repo.add(ticket)
    events.record(ticket, EventType.CREATED, actor)
# commit đã xong
classify_ticket_task.delay(str(ticket.id))
```

Bù lại bằng **cơ chế đối soát định kỳ (reconciliation)**:
- Job mỗi 10 phút: tìm ticket có `ai_status = 'PENDING'` và `created_at < now() - 5 phút` ⇒ đẩy lại vào hàng đợi.
- Job mỗi giờ: tìm bài viết `PUBLISHED` có `indexed_at IS NULL` hoặc `indexed_at < updated_at` ⇒ đẩy lại index.
- Thông báo bị mất thì **chấp nhận mất** (đã ghi ở tài liệu 01 §7: thông báo là eventual, cho phép mất).

## Hệ quả

### Tích cực
- Đơn giản hơn nhiều: không có bảng outbox, không có tiến trình relay, không có bài toán "đã publish hay chưa".
- Job đối soát bắt được đúng loại lỗi mà outbox phòng ngừa, chỉ chậm hơn vài phút — hoàn toàn chấp nhận được vì SLA của phân loại AI là 30 giây nhưng không có hậu quả nghiêm trọng nếu thành 5 phút.
- Tiết kiệm khoảng 1,5 ngày công trong một dự án 4 tuần.

### Tiêu cực
- Có cửa sổ mất tác vụ nếu tiến trình chết giữa commit và `.delay()`.
- Phụ thuộc vào job đối soát chạy đều — **phải có cảnh báo khi job này ngừng chạy** (tài liệu 08 §7.3).
- Thông báo có thể mất mà không ai biết.

## Vì sao chấp nhận được
Không có thao tác nào liên quan tới tiền, tới danh tính, hay tới hành động không thể hoàn tác. Hệ quả xấu nhất: một ticket không được AI phân loại trong 10 phút, sau đó job đối soát xử lý. Với hệ thống thanh toán, quyết định này sẽ **hoàn toàn sai**.

## Cân nhắc lại khi
Xuất hiện tác vụ nền có hậu quả nghiêm trọng nếu mất (gửi tiền, cấp quyền tự động, tích hợp với hệ thống bên ngoài có tính pháp lý).
