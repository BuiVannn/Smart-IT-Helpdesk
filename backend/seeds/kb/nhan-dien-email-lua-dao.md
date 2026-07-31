---
slug: nhan-dien-email-lua-dao
title: Nhận diện và xử lý email lừa đảo
category: bao-mat
ticket_category: security
tags: [bao-mat, lua-dao, phishing, email]
summary: Cách nhận biết email giả mạo và việc cần làm khi nhận được hoặc đã lỡ bấm vào.
---

## Dấu hiệu nhận biết

**Tạo cảm giác gấp gáp và sợ hãi**
"Tài khoản của bạn sẽ bị khoá trong 24 giờ", "Phát hiện đăng nhập trái phép, xác thực ngay". Kẻ lừa đảo muốn bạn hành động trước khi kịp suy nghĩ.

**Địa chỉ người gửi sai lệch tinh vi**
Kiểm tra kỹ phần sau dấu `@`. Ví dụ `it-support@company-vn.com` không phải là `company.com`. Chỉ khác một dấu gạch nối.

**Đường link không khớp với chữ hiển thị**
Rê chuột lên đường link (đừng bấm) và nhìn địa chỉ thật hiện ở góc dưới trình duyệt. Chữ hiển thị là `portal.company.com` nhưng địa chỉ thật lại là một tên miền lạ.

**Yêu cầu cung cấp thông tin đăng nhập**
Đội IT **không bao giờ** hỏi mật khẩu qua email, chat hay điện thoại. Không có ngoại lệ nào.

**File đính kèm bất ngờ**
Đặc biệt là file `.zip`, `.exe`, `.html`, hoặc file Office yêu cầu bật macro.

**Lời chào chung chung và lỗi diễn đạt**
"Kính gửi quý khách hàng" thay vì tên bạn; câu văn lủng củng như dịch máy.

## Khi nghi ngờ một email

1. **Không bấm vào bất kỳ đường link nào**
2. **Không mở file đính kèm**
3. **Không trả lời**
4. Nếu email tự xưng là từ một bộ phận nội bộ, hãy **liên hệ trực tiếp bộ phận đó** qua số điện thoại hoặc kênh chat nội bộ để xác minh — đừng dùng thông tin liên hệ ghi trong chính email đó
5. **Báo cáo cho đội IT**: chuyển tiếp email tới địa chỉ báo cáo bảo mật, hoặc tạo yêu cầu hỗ trợ với mức ưu tiên khẩn cấp

## Nếu đã lỡ bấm vào link hoặc nhập mật khẩu

**Hành động ngay, đừng chờ đợi và đừng ngại báo cáo.**

1. **Đổi mật khẩu ngay lập tức** tại portal.company.com
2. **Ngắt kết nối mạng** nếu bạn đã tải và mở file đính kèm
3. **Tạo yêu cầu hỗ trợ mức Khẩn cấp**, ghi rõ:
   - Bạn đã bấm vào gì, nhập thông tin gì
   - Thời điểm xảy ra
   - Chuyển tiếp email gốc kèm theo

Báo cáo sớm giúp đội IT chặn được thiệt hại. **Không ai bị khiển trách vì báo cáo sự cố bảo mật** — chỉ có việc giấu đi mới gây hậu quả nghiêm trọng.

## Phòng tránh

- Bật xác thực hai lớp cho tài khoản công ty
- Không dùng email công ty để đăng ký các dịch vụ cá nhân
- Cảnh giác cao hơn với email nhận vào cuối giờ chiều thứ Sáu — đây là thời điểm kẻ tấn công hay chọn vì mọi người vội và ít cảnh giác
