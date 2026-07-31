---
slug: yeu-cau-cap-quyen
title: Quy trình yêu cầu cấp quyền truy cập
category: huong-dan-chung
ticket_category: access
tags: [cap-quyen, truy-cap, thu-muc]
summary: Cách xin quyền truy cập thư mục chung, ứng dụng nội bộ và hệ thống nghiệp vụ.
---

## Nguyên tắc cấp quyền

Công ty áp dụng nguyên tắc **quyền tối thiểu**: mỗi người chỉ được cấp đúng quyền cần thiết cho công việc của mình, không hơn. Vì vậy mọi yêu cầu cấp quyền đều cần được người có thẩm quyền phê duyệt.

## Thông tin cần có khi yêu cầu

Tạo một yêu cầu hỗ trợ và ghi đầy đủ:

1. **Tài nguyên cần truy cập** — tên chính xác của thư mục, ứng dụng hoặc hệ thống. Ví dụ: `\\fileserver\DuAnX\TaiLieu` chứ không phải "thư mục dự án X"
2. **Mức quyền cần** — chỉ đọc, hay đọc và ghi
3. **Lý do** — bạn cần quyền này để làm việc gì
4. **Thời hạn** — vĩnh viễn theo vị trí công việc, hay tạm thời trong một giai đoạn
5. **Người phê duyệt** — quản lý trực tiếp hoặc chủ sở hữu tài nguyên

Yêu cầu thiếu một trong các thông tin trên sẽ bị đội IT hỏi lại và mất thêm thời gian.

## Ai là người phê duyệt

| Loại tài nguyên | Người phê duyệt |
|---|---|
| Thư mục chung của phòng ban | Trưởng phòng ban đó |
| Thư mục dự án | Quản lý dự án |
| Ứng dụng nghiệp vụ | Chủ sở hữu ứng dụng |
| Hệ thống có dữ liệu nhạy cảm | Trưởng phòng + đội Bảo mật |

Nếu không rõ ai là người phê duyệt, cứ tạo yêu cầu — đội IT sẽ định tuyến giúp.

## Thời gian xử lý

- Yêu cầu thông thường đã có phê duyệt: trong **một ngày làm việc**
- Yêu cầu cần chờ phê duyệt: phụ thuộc người duyệt phản hồi
- Hệ thống có dữ liệu nhạy cảm: có thể mất **3–5 ngày làm việc**

Nếu công việc gấp, hãy ghi rõ deadline trong phần mô tả và chọn mức ưu tiên phù hợp.

## Khi chuyển bộ phận hoặc nghỉ việc

Quyền truy cập gắn với vị trí công việc, không gắn với cá nhân. Khi bạn chuyển sang bộ phận khác:

- Quyền cũ sẽ được thu hồi
- Bạn cần tạo yêu cầu mới cho các quyền cần dùng ở vị trí mới

Đây là quy định bắt buộc, không phải thủ tục thừa — nó ngăn việc một người tích luỹ quá nhiều quyền theo thời gian.
