---
slug: may-tinh-cham
title: Máy tính chạy chậm — cách tự kiểm tra
category: huong-dan-chung
ticket_category: hardware
tags: [may-tinh, cham, hieu-nang]
summary: Các nguyên nhân thường gặp khiến máy tính chậm và cách tự khắc phục.
---

## Bước 1 — Khởi động lại máy

Nghe đơn giản nhưng đây là cách hiệu quả nhất. Nhiều người để máy ở chế độ ngủ (sleep) hàng tuần mà không tắt hẳn. Bộ nhớ bị chiếm dần bởi các chương trình chạy nền, và chỉ khởi động lại mới giải phóng được.

Vào **Start → Power → Restart**, không phải Shut down rồi bật lại (Windows có chế độ khởi động nhanh nên tắt máy không giải phóng bộ nhớ hoàn toàn).

## Bước 2 — Kiểm tra chương trình đang chiếm tài nguyên

1. Nhấn `Ctrl + Shift + Esc` để mở **Task Manager**
2. Chọn tab **Processes**
3. Bấm vào cột **CPU** rồi cột **Memory** để sắp xếp giảm dần
4. Xem chương trình nào đang chiếm nhiều nhất

Thường gặp:
- **Trình duyệt mở quá nhiều tab** — mỗi tab Chrome chiếm 100–300 MB bộ nhớ. Mở 40 tab là hết sạch RAM.
- **Phần mềm diệt virus đang quét** — chờ quét xong
- **Windows Update đang tải** — chờ hoàn tất
- **Ứng dụng đồng bộ file đang chạy** — bình thường sau vài phút

## Bước 3 — Kiểm tra dung lượng ổ đĩa

Mở **This PC**, xem ổ C còn trống bao nhiêu. Nếu **dưới 10%**, máy sẽ chậm rõ rệt vì Windows không còn chỗ cho bộ nhớ ảo.

Cách giải phóng nhanh:
- Dọn thùng rác (Recycle Bin)
- Xoá thư mục **Downloads** những file không cần
- Chạy **Disk Cleanup**: gõ `Disk Cleanup` ở ô tìm kiếm
- Chuyển các file dữ liệu lớn lên thư mục chung trên file server

## Bước 4 — Giảm chương trình khởi động cùng máy

1. Mở **Task Manager**, chọn tab **Startup**
2. Xem cột **Startup impact**
3. Bấm chuột phải vào chương trình có mức **High** mà bạn không cần dùng ngay khi mở máy, chọn **Disable**

Lưu ý: không tắt phần mềm diệt virus và các phần mềm bảo mật của công ty.

## Khi cần báo IT

Tạo yêu cầu hỗ trợ nếu:
- Đã thử hết các bước trên mà máy vẫn chậm
- Máy chậm đột ngột sau khi cài một phần mềm nào đó
- Nghe tiếng ổ cứng kêu lạch cạch, hoặc quạt kêu to liên tục
- Máy nóng bất thường

Trong yêu cầu, ghi rõ máy chậm khi làm việc gì (mở file Excel lớn, chạy phần mềm cụ thể, hay chậm mọi lúc) — thông tin này giúp đội IT khoanh vùng nhanh hơn nhiều.
