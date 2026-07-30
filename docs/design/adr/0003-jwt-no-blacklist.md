# ADR-0003: Không dùng blacklist cho access token

**Trạng thái:** Accepted · **Ngày:** 2026-07-30

## Bối cảnh
Khi người dùng đăng xuất hoặc bị Admin khoá tài khoản, access token đã cấp vẫn còn hiệu lực cho tới khi hết hạn. Cách xử lý triệt để là lưu danh sách token bị thu hồi (blacklist) trong Redis và kiểm tra ở **mọi** request.

## Quyết định
**Không** dùng blacklist. Thay vào đó:
- Access token TTL ngắn: **15 phút**
- Refresh token lưu trong DB, thu hồi được ngay lập tức
- Đăng xuất / khoá tài khoản / đổi mật khẩu ⇒ thu hồi refresh token
- Hệ quả: người dùng bị khoá vẫn thao tác được **tối đa 15 phút**

## Hệ quả

### Tích cực
- Xác thực hoàn toàn không cần tra cứu ⇒ tiết kiệm một lượt Redis trên **mọi** request.
- Không có phụ thuộc Redis trên đường xác thực ⇒ Redis hỏng không làm sập việc đăng nhập.
- Đơn giản hơn đáng kể, ít chỗ sai hơn.

### Tiêu cực
- Cửa sổ tối đa 15 phút mà token bị thu hồi vẫn dùng được.
- Với hệ thống tài chính hoặc dữ liệu tối mật, đánh đổi này **không** chấp nhận được.

## Vì sao chấp nhận được ở đây
Đây là hệ thống helpdesk nội bộ. Kịch bản xấu nhất: một nhân viên vừa bị khoá tài khoản còn xem được ticket của chính mình thêm 15 phút. Không có thao tác tài chính, không có dữ liệu tối mật.

## Cân nhắc lại khi
Hệ thống mở rộng để xử lý dữ liệu nhân sự nhạy cảm, hoặc có yêu cầu compliance đòi thu hồi phiên tức thời.
