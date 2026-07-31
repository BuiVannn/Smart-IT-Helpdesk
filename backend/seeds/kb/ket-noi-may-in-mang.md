---
slug: ket-noi-may-in-mang
title: Kết nối máy in mạng của công ty
category: huong-dan-chung
ticket_category: hardware
tags: [may-in, mang, cai-dat]
summary: Cách thêm máy in mạng vào máy tính và xử lý khi không in được.
---

## Danh sách máy in

Mỗi tầng có máy in đặt tại khu vực chung. Tên máy in được dán trên vỏ, theo dạng `PRT-<tầng>-<số>`, ví dụ `PRT-03-01` là máy in số 1 tầng 3.

Bạn chỉ in được trên máy in cùng tầng hoặc các tầng được cấp quyền.

## Thêm máy in vào máy tính

1. Mở **Settings → Bluetooth & devices → Printers & scanners**
2. Bấm **Add device**
3. Đợi hệ thống quét, chọn máy in theo đúng mã dán trên vỏ
4. Nếu không thấy, bấm **Add manually**, chọn **Select a shared printer by name** và nhập `\\printserver\PRT-03-01`
5. Đợi Windows tự tải driver
6. Bấm chuột phải vào máy in vừa thêm, chọn **Print test page** để kiểm tra

Nếu bạn đang làm việc từ xa, cần bật VPN trước khi thêm máy in.

## In được nhưng không ra giấy

1. **Kiểm tra hàng đợi in**: bấm đúp vào biểu tượng máy in, xem có lệnh in nào bị kẹt không. Nếu có, bấm chuột phải chọn **Cancel** để xoá rồi in lại.
2. **Kiểm tra bạn có in đúng máy không** — nhiều người in nhầm sang máy tầng khác rồi đi tìm ở tầng mình.
3. **Ra kiểm tra máy in trực tiếp**: có báo hết giấy, hết mực, hay kẹt giấy không.
4. **Kiểm tra đèn tín hiệu** trên máy in.

## Bản in mờ, sọc, hoặc lem

- **Mờ đều toàn trang** → sắp hết mực. Báo IT để thay hộp mực.
- **Sọc dọc** → hộp mực có vấn đề hoặc trống in bẩn
- **Lem, dính** → bộ phận sấy có vấn đề, cần IT kiểm tra
- **Chữ bị nhoè một bên** → giấy ẩm, thử thay xấp giấy mới

## In hai mặt và tiết kiệm

- Đặt in hai mặt mặc định: vào **Printer properties → Printing Defaults → Two-sided**
- Với tài liệu nội bộ, chọn chế độ **Draft** để tiết kiệm mực
- Cân nhắc xem có thật sự cần in không — phần lớn tài liệu chỉ cần xem trên màn hình

## Khi cần báo IT

Ghi rõ **mã máy in** và **hiện tượng**. Nếu máy in báo lỗi trên màn hình của nó, hãy chụp ảnh. Nếu sự cố ảnh hưởng cả phòng (máy in hỏng hoàn toàn), chọn mức ưu tiên Cao.
