---
slug: khac-phuc-outlook
title: Khắc phục sự cố Outlook không nhận được email
category: phan-mem
ticket_category: email
tags: [outlook, email, phan-mem]
summary: Các bước xử lý khi Outlook không nhận, không gửi được email hoặc bị treo.
---

## Outlook không nhận được email mới

Thử lần lượt các bước sau:

1. **Kiểm tra trạng thái kết nối** ở góc dưới bên phải cửa sổ Outlook. Nếu hiện *Disconnected* hoặc *Working Offline*, vào tab **Send / Receive** và bấm bỏ chọn **Work Offline**.
2. **Bấm Send/Receive All Folders** hoặc nhấn phím `F9` để buộc đồng bộ ngay.
3. **Kiểm tra thư mục Junk Email** — email có thể đã bị lọc nhầm vào đó.
4. **Kiểm tra quy tắc lọc thư**: vào **File → Manage Rules & Alerts**, xem có quy tắc nào tự chuyển email vào thư mục khác hoặc xoá không. Quy tắc tạo từ lâu rồi quên là nguyên nhân rất phổ biến.
5. **Kiểm tra hộp thư đã đầy chưa**: vào **File → Info**, xem dung lượng. Hộp thư đầy sẽ không nhận thêm email mới.
6. **Khởi động lại Outlook**, sau đó khởi động lại máy nếu vẫn lỗi.

## Outlook không gửi được email

Email nằm mãi trong **Outbox** thường do một trong các nguyên nhân:

- **File đính kèm quá lớn** — giới hạn là 25 MB. Với file lớn hơn, hãy tải lên thư mục chung rồi gửi đường dẫn.
- **Địa chỉ người nhận sai** — kiểm tra kỹ chính tả
- **Mất kết nối mạng** — xem bài *Khắc phục khi mất kết nối mạng*

Nếu email kẹt ở Outbox, mở email đó, bấm **Save**, đóng lại rồi bấm `F9`.

## Outlook chạy chậm hoặc bị treo

1. Đóng Outlook hoàn toàn, đợi 30 giây rồi mở lại
2. Nếu vẫn chậm, thử mở Outlook ở chế độ an toàn: nhấn `Windows + R`, gõ `outlook /safe`, nhấn Enter. Nếu ở chế độ này Outlook chạy mượt, nguyên nhân là một tiện ích bổ sung (add-in) nào đó.
3. Hộp thư quá lớn cũng làm Outlook chậm. Hãy lưu trữ (archive) các email cũ hơn một năm.

## Yêu cầu xác thực lại liên tục

Nếu Outlook liên tục hiện cửa sổ đòi nhập mật khẩu:

- Bạn vừa đổi mật khẩu công ty? Hãy nhập mật khẩu mới và tick **Remember my credentials**
- Nếu nhập đúng mà vẫn hỏi lại, hãy tạo yêu cầu hỗ trợ — thường cần đội IT xoá thông tin đăng nhập đã lưu trên máy

## Khi cần báo IT

Ghi rõ trong yêu cầu hỗ trợ:
- Sự cố cụ thể: không nhận, không gửi, hay treo
- Bắt đầu xảy ra từ khi nào
- Thông báo lỗi hiển thị, kèm ảnh chụp màn hình
- Các bước bạn đã thử
