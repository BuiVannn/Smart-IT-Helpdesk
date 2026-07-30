# ADR-0008: Dùng polling thay vì WebSocket cho thông báo và cập nhật ticket

**Trạng thái:** Accepted · **Ngày:** 2026-07-30

## Bối cảnh
Yêu cầu US-33 nói "theo dõi trạng thái ticket **theo thời gian thực**" và cần hiển thị số thông báo chưa đọc. Guideline gợi ý WebSocket là một lựa chọn cho FR-08.

## Quyết định
Dùng **HTTP polling**:
- `GET /notifications/unread-count` mỗi **30 giây**
- Chi tiết ticket làm mới mỗi **20 giây**, và **chỉ khi tab đang hiển thị** (Page Visibility API)
- Danh sách ticket làm mới khi cửa sổ được focus lại

Ngoại lệ duy nhất dùng streaming: **chatbot dùng SSE** (Server-Sent Events) — vì ở đó độ trễ token thực sự ảnh hưởng trải nghiệm.

## Hệ quả

### Tích cực
- Không cần quản lý kết nối lâu dài, không cần xử lý reconnect, không cần sticky session ở load balancer.
- Không cần kênh pub/sub giữa worker và các instance API (worker sinh thông báo, nhưng người dùng có thể đang kết nối tới instance khác — với WebSocket đây là bài toán thật sự).
- Tải phát sinh không đáng kể: 100 người dùng × 2 request/phút = **3,3 rps** — nằm gọn trong ngân sách (tài liệu 01 §8).
- Đơn giản để test, để debug, để triển khai.

### Tiêu cực
- Độ trễ tối đa 30 giây cho thông báo — **"thời gian thực" ở đây nghĩa là "trong vòng nửa phút"**, cần thống nhất cách hiểu này với PO.
- Có request thừa khi không có gì thay đổi.

## Phương án đã cân nhắc
- **WebSocket**: cần quản lý kết nối, reconnect với backoff, sticky session hoặc Redis pub/sub để phát tán sự kiện tới đúng instance. Chi phí đáng kể cho một hệ thống mà "trong vòng 30 giây" đã là quá đủ.
- **SSE cho thông báo**: nhẹ hơn WebSocket nhưng vẫn cần pub/sub giữa các instance; lợi ích không tương xứng.

## Cân nhắc lại khi
Có yêu cầu nghiệp vụ thật sự cần độ trễ dưới 5 giây (ví dụ: nhiều Agent cùng chỉnh sửa một ticket và cần thấy nhau theo thời gian thực).
