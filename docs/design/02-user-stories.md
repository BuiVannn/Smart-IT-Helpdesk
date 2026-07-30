# 02 — User Stories & Tiêu chí Chấp nhận

| | |
|---|---|
| Phiên bản | 1.0 |
| Nguồn | Bóc tách từ 8 Feature trong `Mo-Ta-Du-An-Smart-IT-Helpdesk.docx` + FR trong `02.Project-Requirement.pdf` |
| Quy ước ước lượng | Story Point theo Fibonacci: 1 = vài giờ, 2 = nửa ngày, 3 = 1 ngày, 5 = 2 ngày, 8 = 3–4 ngày |

---

## 0. Cách đọc tài liệu này

- **MoSCoW**: `M` = Must (không có thì hệ thống vô nghĩa), `S` = Should (quan trọng, có thể lùi), `C` = Could (làm nếu dư thời gian), `W` = Won't (đã loại, ghi lại để không ai đề xuất lại).
- **Định nghĩa Hoàn thành (DoD)** áp dụng cho mọi story, theo `Phan-Cong-Cong-Viec-v2.docx` §6:
  1. Code đã merge qua PR có ít nhất 1 reviewer
  2. Có unit test cho service layer, test pass
  3. Đã deploy lên staging (không chỉ chạy máy cá nhân)
  4. API doc (OpenAPI) và README liên quan đã cập nhật
  5. **Bổ sung:** mọi tiêu chí chấp nhận (AC) dưới đây đã được QA kiểm chứng thủ công hoặc bằng test tự động
- Story được viết theo mẫu: *Là \<vai trò>, tôi muốn \<hành động>, để \<giá trị>.*
- AC viết theo Gherkin rút gọn: **Cho** (Given) — **Khi** (When) — **Thì** (Then).

### Bảng tổng hợp

| Feature | Số story | Tổng SP | MoSCoW chủ đạo |
|---|---|---|---|
| F1 — Auth & Phân quyền | 7 | 24 | Must |
| F2 — Quản lý Ticket | 11 | 45 | Must |
| F3 — AI Phân loại | 4 | 21 | Must |
| F4 — AI Chatbot RAG | 5 | 29 | Must |
| F5 — Kho Tài liệu | 5 | 18 | Must |
| F6 — Thông báo | 4 | 16 | Should |
| F7 — Dashboard | 4 | 16 | Should |
| F8 — Đánh giá | 3 | 8 | Should |
| **Tổng** | **43** | **177 SP** | |

> **Cảnh báo về năng lực (capacity) — cần đưa ra Sprint Planning:** 177 SP trong Sprint 1 với 7 người code (4 BE + 2 FE + 1 DevOps/BE), mỗi người ~8 ngày làm việc thực tế ⇒ ~56 người-ngày. Với tỉ lệ ~3 SP/người-ngày thì năng lực khoảng **160 SP** — tức là **không có vùng đệm nào**. Đề xuất: đẩy các story `C` (Could) sang Sprint 2 và chấp nhận F7/F8 ở mức tối thiểu. Xem §10.

---

## F1 — Đăng nhập & Phân quyền

### US-01 — Đăng ký tài khoản
> Là **nhân viên**, tôi muốn đăng ký bằng email công ty, để có thể gửi yêu cầu hỗ trợ IT.

`M` · 3 SP · PIC: Lại Duy Đông

**AC**
- Cho email hợp lệ thuộc tên miền công ty và mật khẩu ≥ 8 ký tự (có chữ hoa, chữ thường, số) — Khi gửi đăng ký — Thì tài khoản được tạo với vai trò mặc định `EMPLOYEE`, trạng thái `is_active = true`, và trả về `201`.
- Cho email đã tồn tại — Khi gửi đăng ký — Thì trả về `409 EMAIL_ALREADY_EXISTS`, **không** tiết lộ thêm thông tin nào về tài khoản đó.
- Cho mật khẩu không đạt chính sách — Khi gửi đăng ký — Thì trả về `422` kèm danh sách lỗi cụ thể theo từng field.
- Mật khẩu được hash bằng **bcrypt cost ≥ 12**; không bao giờ xuất hiện trong response, log, hay bản ghi audit.
- Email được chuẩn hoá về chữ thường trước khi lưu và kiểm tra trùng.

### US-02 — Đăng nhập nhận JWT
> Là **người dùng**, tôi muốn đăng nhập và nhận access token + refresh token, để dùng hệ thống mà không phải nhập lại mật khẩu liên tục.

`M` · 3 SP

**AC**
- Cho thông tin đúng — Khi đăng nhập — Thì nhận `access_token` (TTL 15 phút) và `refresh_token` (TTL 7 ngày), kèm thông tin người dùng và vai trò.
- Cho thông tin sai — Khi đăng nhập — Thì trả về `401 INVALID_CREDENTIALS` với **cùng một thông điệp** dù sai email hay sai mật khẩu (chống dò tài khoản).
- Cho tài khoản bị khoá (`is_active = false`) — Khi đăng nhập — Thì trả về `403 ACCOUNT_DISABLED`.
- Cho 5 lần đăng nhập sai liên tiếp trong 15 phút — Khi đăng nhập lần 6 — Thì trả về `429` kèm `Retry-After`, kể cả khi mật khẩu đúng.
- Thời gian xử lý khi sai mật khẩu và khi không tồn tại email phải tương đương (chống timing attack): luôn thực hiện một phép hash giả.

### US-03 — Làm mới phiên bằng refresh token
> Là **người dùng**, tôi muốn hệ thống tự động gia hạn phiên, để không bị đăng xuất giữa chừng.

`M` · 3 SP

**AC**
- Cho refresh token hợp lệ, chưa hết hạn, chưa bị thu hồi — Khi gọi `/auth/refresh` — Thì nhận access token mới **và** refresh token mới; token cũ bị đánh dấu thu hồi (**xoay vòng token — token rotation**).
- Cho một refresh token đã dùng rồi được dùng lại — Khi gọi `/auth/refresh` — Thì thu hồi **toàn bộ** refresh token của người dùng đó và trả về `401` (phát hiện dấu hiệu token bị đánh cắp).
- Refresh token lưu trong DB dưới dạng **hash**, không lưu bản rõ.

### US-04 — Đăng xuất
> Là **người dùng**, tôi muốn đăng xuất, để phiên của tôi không bị dùng tiếp trên thiết bị chung.

`M` · 1 SP

**AC**
- Khi đăng xuất — Thì refresh token hiện tại bị thu hồi; các lần gọi `/auth/refresh` sau đó trả về `401`.
- Có tuỳ chọn `logout_all_devices` để thu hồi mọi refresh token của người dùng.
- Access token còn hiệu lực tối đa 15 phút sau đăng xuất — **đây là đánh đổi có chủ đích** (không dùng blacklist để tránh phải tra Redis mỗi request). Ghi rõ trong ADR-0003.

### US-05 — Đổi mật khẩu
> Là **người dùng**, tôi muốn đổi mật khẩu, để bảo vệ tài khoản của mình.

`M` · 2 SP

**AC**
- Bắt buộc nhập mật khẩu hiện tại; sai thì trả về `403`.
- Đổi thành công thì **thu hồi toàn bộ refresh token** của người dùng (buộc đăng nhập lại trên mọi thiết bị).
- Ghi một bản ghi audit `PASSWORD_CHANGED` (không kèm giá trị mật khẩu).

### US-06 — Phân quyền theo vai trò
> Là **Admin**, tôi muốn hệ thống phân quyền theo 3 vai trò, để mỗi người chỉ thấy đúng phần dữ liệu được phép.

`M` · 5 SP

**AC**
- Có 3 vai trò: `EMPLOYEE`, `IT_AGENT`, `ADMIN`. Mỗi người dùng có đúng một vai trò.
- Mọi endpoint nghiệp vụ đều phải qua dependency kiểm tra vai trò; **không có endpoint nghiệp vụ nào để trống** (kiểm chứng bằng một test tự động quét toàn bộ route — xem tài liệu 08 §2.4).
- Employee chỉ đọc/sửa được ticket **do chính mình tạo**; truy cập ticket người khác trả về `404` (không phải `403` — để không lộ sự tồn tại của ticket).
- IT Agent đọc được mọi ticket, nhưng chỉ **chuyển trạng thái** được ticket được giao cho mình (trừ khi Admin cấp quyền).
- Admin đọc/ghi mọi thứ; các hành động của Admin trên dữ liệu người khác đều được ghi audit.
- Có test tự động cho **ma trận phân quyền** ở tài liệu 08 §2.2: mỗi ô (vai trò × hành động) có ít nhất 1 test khẳng định cho phép và 1 test khẳng định từ chối.

### US-07 — Quản trị người dùng
> Là **Admin**, tôi muốn tạo/khoá/mở khoá/tìm kiếm người dùng và gán vai trò, để quản lý truy cập hệ thống.

`M` · 5 SP

**AC**
- Admin tạo được người dùng với vai trò bất kỳ và gán phòng ban.
- Khoá người dùng ⇒ thu hồi toàn bộ refresh token; access token còn lại tối đa 15 phút.
- Tìm kiếm người dùng theo tên/email/vai trò/phòng ban, có phân trang và sắp xếp.
- **Không cho phép Admin tự khoá chính mình** hoặc hạ vai trò chính mình nếu là Admin cuối cùng đang hoạt động.
- Không xoá cứng người dùng (hard delete) — chỉ vô hiệu hoá, vì `tickets.requester_id` tham chiếu tới.

---

## F2 — Quản lý Ticket

### US-08 — Tạo ticket
> Là **nhân viên**, tôi muốn tạo yêu cầu hỗ trợ kèm mô tả sự cố, để đội IT biết và xử lý.

`M` · 5 SP · PIC: Chu Quang Vũ

**AC**
- Trường bắt buộc: `title` (5–200 ký tự), `description` (10–5.000 ký tự). Tuỳ chọn: `category_id`, `priority`, file đính kèm.
- Nếu người dùng **không** chọn category/priority — Thì ticket được tạo với `category_id = NULL`, `priority = MEDIUM`, `ai_status = PENDING`, và một tác vụ phân loại AI được đưa vào hàng đợi.
- Ticket nhận `code` dạng `HD-YYYYMM-NNNN` (duy nhất, dễ đọc, dùng khi trao đổi qua chat/điện thoại).
- Trạng thái khởi tạo là `NEW`, `requester_id` = người đang đăng nhập (**không** lấy từ body request — chống giả mạo).
- API trả về trong **< 500 ms**: phân loại AI **không** nằm trên đường phản hồi này.
- Một bản ghi `ticket_events` loại `CREATED` được ghi **trong cùng transaction**.
- Chống trùng: header `Idempotency-Key` được hỗ trợ; gửi lại cùng key trong 10 phút trả về đúng ticket cũ, không tạo bản ghi mới.

### US-09 — Đính kèm file
> Là **nhân viên**, tôi muốn đính kèm ảnh chụp màn hình lỗi, để mô tả sự cố rõ hơn.

`S` · 5 SP

**AC**
- Cho phép định dạng: `png, jpg, jpeg, pdf, txt, log, docx, xlsx, zip`. Tối đa **10 MB/file**, **5 file/ticket**.
- Kiểm tra **cả** phần mở rộng **và** magic bytes (không tin `Content-Type` do client gửi).
- File lưu ở object storage (MinIO/S3) với tên ngẫu nhiên (UUID); tên gốc chỉ lưu trong DB làm metadata → chống path traversal.
- Tải file phải qua kiểm tra quyền như chính ticket đó; link tải là **pre-signed URL hết hạn sau 10 phút**.
- Response khi tải luôn có `Content-Disposition: attachment` (chống stored XSS qua file HTML/SVG).

### US-10 — Xem danh sách ticket của tôi
> Là **nhân viên**, tôi muốn xem danh sách ticket của mình cùng trạng thái, để biết yêu cầu đang xử lý tới đâu.

`M` · 3 SP

**AC**
- Mặc định trả về ticket của chính người đang đăng nhập, sắp xếp `created_at DESC`, phân trang 20 bản ghi.
- Lọc được theo `status`, `priority`, `category`, khoảng thời gian tạo.
- Response trả kèm `pagination: {page, page_size, total_items, total_pages}`.
- p95 < 300 ms với 28.800 ticket trong DB (có index — xem tài liệu 04 §5).

### US-11 — Xem chi tiết ticket
> Là **nhân viên**, tôi muốn xem chi tiết ticket gồm mô tả, bình luận, file đính kèm và lịch sử thay đổi.

`M` · 3 SP

**AC**
- Trả về ticket + bình luận (phân trang) + đính kèm + timeline sự kiện + kết quả phân loại AI + đánh giá (nếu đã có).
- Bình luận `is_internal = true` (nội bộ giữa các Agent) **không** trả về cho Employee.
- Employee truy cập ticket không phải của mình ⇒ `404`.

### US-12 — Hàng chờ của IT Agent
> Là **IT Agent**, tôi muốn xem danh sách ticket được giao cho mình, để sắp xếp thứ tự ưu tiên xử lý.

`M` · 3 SP

**AC**
- Chế độ xem "Của tôi" (`assignee_id = tôi`) và "Chưa giao" (`assignee_id IS NULL`).
- Sắp xếp mặc định: `priority DESC`, rồi `sla_due_at ASC` (sắp trễ hạn lên trước).
- Có cờ hiển thị SLA: `on_track` / `at_risk` (còn < 25% thời gian) / `breached`.
- Lọc theo category, trạng thái, người yêu cầu, phòng ban.

### US-13 — Nhận việc / giao việc
> Là **IT Agent**, tôi muốn tự nhận ticket hoặc được giao ticket, để rõ ai chịu trách nhiệm.

`M` · 5 SP

**AC**
- Agent tự nhận (`claim`) ticket chưa giao ⇒ `assignee_id = tôi`, trạng thái `NEW → ASSIGNED`.
- Admin/Agent giao ticket cho Agent khác ⇒ ghi `ticket_events` loại `ASSIGNED` kèm giá trị cũ/mới.
- **Chống tranh chấp (race condition):** hai Agent cùng nhận một ticket — chỉ một người thành công, người còn lại nhận `409 TICKET_ALREADY_ASSIGNED`. Cài đặt bằng optimistic lock trên cột `version` (xem tài liệu 03 §7).
- Chỉ giao được cho người dùng có vai trò `IT_AGENT` và đang hoạt động.

### US-14 — Cập nhật trạng thái / đóng ticket
> Là **IT Agent**, tôi muốn cập nhật trạng thái và đóng ticket sau khi xử lý xong, để hệ thống ghi nhận kết quả.

`M` · 5 SP

**AC**
- Chỉ chấp nhận các bước chuyển hợp lệ theo máy trạng thái ở tài liệu 03 §5; bước chuyển sai ⇒ `422 INVALID_STATUS_TRANSITION` kèm danh sách trạng thái được phép.
- Chuyển sang `RESOLVED` **bắt buộc** có `resolution_note` (≥ 10 ký tự) — bảo vệ chất lượng dữ liệu cho báo cáo và cho việc bổ sung kho tri thức.
- Mốc thời gian được ghi tự động: `first_response_at` (lần đầu Agent bình luận hoặc đổi trạng thái), `resolved_at`, `closed_at`.
- Mọi lần chuyển trạng thái đều ghi `ticket_events` **trong cùng transaction** với thay đổi.
- Ticket `RESOLVED` tự động chuyển sang `CLOSED` sau 3 ngày nếu người yêu cầu không phản hồi (job định kỳ).

### US-15 — Bình luận trên ticket
> Là **nhân viên và IT Agent**, tôi muốn trao đổi qua bình luận trên ticket, để mọi thông tin nằm cùng một chỗ.

`M` · 3 SP

**AC**
- Employee bình luận được trên ticket của mình; Agent/Admin bình luận trên ticket bất kỳ.
- Agent có tuỳ chọn `is_internal = true` — ghi chú nội bộ, Employee không thấy.
- Bình luận của Agent lần đầu ⇒ ghi `first_response_at` nếu chưa có.
- Bình luận không sửa/xoá được sau 15 phút (bảo toàn dấu vết trao đổi).

### US-16 — Tìm kiếm ticket
> Là **IT Agent**, tôi muốn tìm ticket theo từ khoá, để tra cứu sự cố tương tự đã xử lý.

`S` · 5 SP

**AC**
- Tìm full-text trên `title` + `description` bằng PostgreSQL `tsvector` (cấu hình `simple` để hoạt động với tiếng Việt không dấu — xem ADR-0004).
- Kết hợp được với các bộ lọc và phân trang.
- Kết quả tôn trọng quyền: Employee chỉ tìm trong ticket của mình.
- p95 < 500 ms với 28.800 bản ghi.

### US-17 — Xem lịch sử thay đổi ticket
> Là **Admin**, tôi muốn xem toàn bộ lịch sử thay đổi của một ticket, để truy vết khi có tranh cãi.

`S` · 3 SP

**AC**
- Timeline liệt kê: ai, làm gì, lúc nào, giá trị trước → sau.
- Bảng `ticket_events` là **chỉ ghi thêm (append-only)**: không có API sửa/xoá.
- Bao gồm cả hành động của hệ thống (AI phân loại, tự động đóng, cảnh báo SLA) với `actor_id = NULL` và `actor_type = SYSTEM`.

### US-18 — Huỷ ticket
> Là **nhân viên**, tôi muốn huỷ ticket đã tạo nhầm, để không làm nhiễu hàng chờ của đội IT.

`C` · 2 SP

**AC**
- Chỉ huỷ được khi trạng thái là `NEW` hoặc `ASSIGNED` và người huỷ là người tạo.
- Bắt buộc nhập lý do huỷ; ticket chuyển `CANCELLED`, không xoá khỏi DB.

---

## F3 — AI Phân loại Ticket

### US-19 — Tự động phân loại và gán mức ưu tiên
> Là **hệ thống**, khi ticket được tạo, tôi muốn AI phân tích mô tả để gán loại sự cố và mức độ ưu tiên, để giảm thao tác thủ công.

`M` · 8 SP · PIC: Bùi Mậu Văn

**AC**
- Cho ticket vừa tạo — Khi worker xử lý — Thì trong **≤ 30 giây** ticket có `category_id`, `priority` và một bản ghi `ai_classifications` kèm `confidence`.
- Nếu `confidence < 0,6` — Thì **không** tự áp dụng; đặt `ai_status = LOW_CONFIDENCE` và để ticket vào hàng chờ phân loại thủ công. Ngưỡng này để trong config, không hardcode.
- **Nếu LLM lỗi hoặc timeout (> 20 s)** — Thì thử lại 3 lần với exponential backoff + jitter; thất bại hoàn toàn ⇒ `ai_status = FAILED`, ticket vẫn dùng bình thường ở trạng thái chưa phân loại và xuất hiện trong hàng chờ thủ công. **Ticket không bao giờ bị kẹt vì AI hỏng.**
- Nếu người dùng đã tự chọn category — Thì AI vẫn chạy để ghi nhận kết quả so sánh nhưng **không ghi đè** lựa chọn của con người.
- Mọi lời gọi LLM ghi lại: model, độ trễ, token vào/ra, chi phí ước tính.

### US-20 — Gợi ý người xử lý theo workload
> Là **IT Agent**, tôi muốn ticket được gợi ý người xử lý phù hợp dựa trên loại sự cố và khối lượng công việc hiện tại, để phân bổ công việc đồng đều.

`M` · 5 SP · PIC: Lại Duy Đông

**AC**
- Điểm gợi ý = `w1 × (kỹ năng khớp category) + w2 × (1 − tải hiện tại chuẩn hoá) + w3 × (đang trong ca trực)`. Trọng số nằm trong config.
- Tải hiện tại = số ticket đang mở của Agent đó có trọng số theo mức ưu tiên.
- Chỉ gợi ý Agent đang hoạt động; **gợi ý, không tự động giao** ở phiên bản 1 (con người vẫn quyết định) — giảm rủi ro giao sai. Việc tự động giao là Could.
- Trả về top 3 ứng viên kèm điểm và lý do có thể đọc được ("chuyên môn Mạng, đang mở 3 ticket").
- Thuật toán này là **luật thuần tuý, không gọi LLM** ⇒ nhanh, rẻ, kiểm thử được bằng unit test.

### US-21 — Agent sửa lại phân loại của AI
> Là **IT Agent**, tôi muốn sửa lại category/priority nếu AI gán sai, để dữ liệu đúng và AI được đo lường.

`M` · 3 SP

**AC**
- Khi Agent sửa — Thì bản ghi `ai_classifications` tương ứng được cập nhật `was_accepted = false` và `corrected_category_id`.
- Nếu Agent không sửa trong vòng vòng đời ticket — Thì tính là `was_accepted = true`.
- Ghi `ticket_events` loại `RECLASSIFIED`.

### US-22 — Theo dõi độ chính xác của AI
> Là **Admin**, tôi muốn xem độ chính xác phân loại của AI theo thời gian, để đánh giá và cải thiện mô hình.

`S` · 5 SP

**AC**
- Báo cáo hiển thị: tỉ lệ chấp nhận tổng thể, theo từng category, theo tuần; ma trận nhầm lẫn (confusion matrix) giữa category AI gán và category cuối cùng.
- Hiển thị tỉ lệ ticket rơi vào `LOW_CONFIDENCE` và `FAILED`.
- Hiển thị độ trễ trung bình và chi phí LLM ước tính theo tháng.

---

## F4 — AI Chatbot Hỗ trợ (RAG)

### US-23 — Hỏi chatbot trước khi tạo ticket
> Là **nhân viên**, tôi muốn hỏi chatbot trước khi tạo ticket, để nhận câu trả lời ngay nếu là vấn đề thường gặp.

`M` · 8 SP · PIC: Bùi Mậu Văn

**AC**
- Người dùng gửi câu hỏi ⇒ token đầu tiên xuất hiện trong **< 3 giây** (trả lời dạng stream qua SSE).
- Chatbot chỉ trả lời dựa trên các đoạn văn bản lấy được từ kho tài liệu (xem US-24).
- Mỗi phiên hội thoại giữ ngữ cảnh của **5 lượt gần nhất** (giới hạn để kiểm soát chi phí token).
- Nếu LLM lỗi ⇒ hiển thị thông báo rõ ràng kèm nút "Tạo ticket ngay", **không** hiển thị lỗi kỹ thuật.
- Có giới hạn tốc độ: 20 tin nhắn/người/giờ (chống lạm dụng và chống vỡ ngân sách).

### US-24 — Câu trả lời dựa trên tài liệu chính thức, có trích dẫn
> Là **nhân viên**, tôi muốn chatbot trả lời dựa trên tài liệu hướng dẫn nội bộ chính thức, để thông tin nhận được đáng tin cậy.

`M` · 8 SP

**AC**
- Mỗi câu trả lời kèm **1–3 trích dẫn** trỏ tới bài viết KB cụ thể; người dùng bấm vào là mở được bài viết.
- Cho câu hỏi **không có** tài liệu liên quan (điểm tương đồng cao nhất < ngưỡng) — Thì chatbot trả lời "Tôi chưa tìm thấy tài liệu về vấn đề này" và gợi ý tạo ticket. **Tuyệt đối không bịa.**
- Chatbot chỉ truy xuất bài viết ở trạng thái `PUBLISHED`; bài `DRAFT` không bao giờ lọt vào ngữ cảnh.
- Prompt hệ thống chỉ dẫn rõ: chỉ dùng thông tin trong ngữ cảnh được cung cấp.
- Nội dung tài liệu được đưa vào prompt bên trong khối phân tách rõ ràng, kèm chỉ dẫn coi đó là **dữ liệu, không phải mệnh lệnh** (chống prompt injection qua nội dung bài viết).

### US-25 — Chuyển từ chat sang tạo ticket
> Là **nhân viên**, tôi muốn tạo ticket ngay từ cuộc trò chuyện nếu chatbot không giúp được, để không phải gõ lại vấn đề.

`S` · 3 SP

**AC**
- Nút "Tạo ticket từ hội thoại này" ⇒ điền sẵn `title` và `description` được tóm tắt từ hội thoại.
- Ticket tạo ra lưu `source = CHATBOT` và `chat_session_id` để phân tích về sau.
- Chỉ số **tỉ lệ tự giải quyết** = số phiên chat *không* dẫn tới ticket / tổng số phiên → phục vụ G3.

### US-26 — Đánh dấu câu trả lời hữu ích / không hữu ích
> Là **nhân viên**, tôi muốn đánh giá câu trả lời của chatbot, để hệ thống biết chỗ nào còn kém.

`S` · 3 SP

**AC**
- Mỗi câu trả lời có nút 👍 / 👎; 👎 mở ô nhập lý do (tuỳ chọn).
- Lưu vào `chat_feedback`, gắn với `message_id`.

### US-27 — Xem các câu hỏi chatbot trả lời kém
> Là **IT Agent**, tôi muốn xem các câu hỏi chatbot chưa trả lời tốt, để bổ sung tài liệu hướng dẫn còn thiếu.

`S` · 5 SP

**AC**
- Danh sách gồm: câu bị 👎, câu không tìm được tài liệu (`no_context = true`), và các câu dẫn tới việc tạo ticket ngay sau đó.
- Gom nhóm các câu hỏi tương tự (theo độ tương đồng embedding) để thấy chủ đề nào thiếu tài liệu.
- Có nút "Tạo bài viết KB từ câu hỏi này" (điền sẵn tiêu đề).

---

## F5 — Kho Tài liệu Hướng dẫn

### US-28 — Soạn và đăng bài hướng dẫn
> Là **Admin**, tôi muốn đăng/chỉnh sửa bài hướng dẫn xử lý sự cố, để làm nguồn dữ liệu cho chatbot và cho nhân viên tự tra cứu.

`M` · 5 SP · PIC: Nguyễn Tiến Lưỡng

**AC**
- Bài viết có: `title`, `content` (Markdown), `kb_category_id`, `tags[]`, `status` (`DRAFT`/`PUBLISHED`/`ARCHIVED`).
- Chỉ bài `PUBLISHED` mới hiển thị cho nhân viên và mới được đưa vào chỉ mục RAG.
- Markdown được **làm sạch (sanitize)** khi render ở frontend — chống stored XSS.
- Lưu `version` tăng dần mỗi lần sửa nội dung; giữ lại phiên bản trước trong `kb_article_revisions` (Could — nếu kịp).

### US-29 — Tự động index bài viết cho chatbot
> Là **hệ thống**, khi bài viết được publish, tôi muốn tự chia nhỏ và tạo embedding, để chatbot dùng được ngay.

`M` · 5 SP · PIC: Bùi Mậu Văn

**AC**
- Khi `status` chuyển sang `PUBLISHED` hoặc nội dung bài `PUBLISHED` được sửa ⇒ đưa tác vụ re-index vào hàng đợi.
- Trong **≤ 5 phút**, các chunk cũ của bài bị xoá và chunk mới + embedding được ghi vào `article_chunks`.
- Khi bài chuyển `ARCHIVED` hoặc bị xoá ⇒ chunk bị xoá ngay (không được để chatbot trích dẫn tài liệu đã gỡ).
- Có lệnh CLI `reindex-all` để dựng lại toàn bộ chỉ mục từ đầu — **đường phục hồi bắt buộc phải có và phải được chạy thử ít nhất một lần**.

### US-30 — Tìm kiếm tài liệu theo từ khoá
> Là **nhân viên**, tôi muốn tìm tài liệu hướng dẫn theo từ khoá, để tự giải quyết vấn đề đơn giản.

`M` · 3 SP

**AC**
- Tìm full-text trên `title` + `content`, sắp xếp theo độ liên quan, có phân trang.
- Kết quả hiển thị đoạn trích có làm nổi bật từ khoá.
- Chỉ trả về bài `PUBLISHED`.

### US-31 — Phân loại tài liệu theo chủ đề
> Là **Admin**, tôi muốn phân loại tài liệu theo chủ đề, để quản lý kho tri thức có hệ thống.

`M` · 2 SP

**AC**
- CRUD `kb_categories` (có thể lồng 1 cấp cha–con).
- Không xoá được category còn bài viết; phải chuyển bài sang category khác trước.

### US-32 — Gợi ý bài viết khi đang tạo ticket
> Là **nhân viên**, tôi muốn được gợi ý bài hướng dẫn liên quan ngay khi đang gõ mô tả sự cố, để có thể tự xử lý mà không cần gửi ticket.

`C` · 3 SP

**AC**
- Sau khi người dùng gõ ≥ 30 ký tự vào ô mô tả (có debounce 500 ms) ⇒ hiển thị tối đa 3 bài viết liên quan.
- Có nút "Bài viết này đã giải quyết vấn đề của tôi" ⇒ huỷ việc tạo ticket và ghi nhận vào chỉ số tự phục vụ.

---

## F6 — Thông báo

### US-33 — Thông báo khi ticket có cập nhật
> Là **nhân viên**, tôi muốn nhận thông báo khi ticket của mình có cập nhật, để không phải kiểm tra thủ công.

`S` · 5 SP · PIC: Nguyễn Đăng Trường

**AC**
- Sinh thông báo khi: ticket được giao, đổi trạng thái, có bình luận mới (không phải của chính mình), được resolve.
- Thông báo có `type`, `title`, `body`, `entity_type`, `entity_id` để frontend điều hướng đúng chỗ.
- **Không tự thông báo cho người vừa thực hiện hành động đó.**
- Gộp thông báo: nhiều sự kiện trên cùng ticket trong 5 phút gộp thành một.

### US-34 — Thông báo khi có ticket mới được giao
> Là **IT Agent**, tôi muốn nhận thông báo khi có ticket mới được giao, để xử lý kịp thời.

`S` · 2 SP

**AC**
- Sinh ngay khi `assignee_id` đổi sang người đó; nội dung kèm mã ticket, tiêu đề, mức ưu tiên, hạn SLA.

### US-35 — Nhắc trước hạn SLA
> Là **IT Agent**, tôi muốn được nhắc khi ticket sắp trễ hạn, để ưu tiên xử lý trước.

`S` · 5 SP

**AC**
- Job chạy mỗi 5 phút, quét ticket đang mở có `sla_due_at` còn ≤ 25% thời gian ⇒ thông báo `SLA_AT_RISK` cho assignee.
- Khi đã quá hạn ⇒ thông báo `SLA_BREACHED` cho assignee **và** cho Admin.
- **Mỗi ticket chỉ nhận mỗi loại cảnh báo đúng một lần** (cột `sla_warned_at`, `sla_breached_notified_at`) — job phải idempotent, chạy lại nhiều lần không sinh trùng.
- Nếu job không chạy trong một khoảng thời gian (hệ thống tắt) — Khi chạy lại — Thì vẫn phát hiện đúng các ticket đã quá hạn trong khoảng đó.

### US-36 — Xem và đánh dấu đã đọc
> Là **người dùng**, tôi muốn xem danh sách thông báo và đánh dấu đã đọc, để quản lý những việc cần chú ý.

`S` · 3 SP

**AC**
- Endpoint đếm số chưa đọc (frontend polling 30 giây — **không** dùng WebSocket ở v1, xem ADR-0008).
- Đánh dấu đã đọc từng cái hoặc tất cả.
- Chỉ xem được thông báo của chính mình.

---

## F7 — Dashboard & Báo cáo

### US-37 — Tổng quan ticket theo trạng thái và mức ưu tiên
> Là **Admin**, tôi muốn xem tổng số ticket theo trạng thái và mức ưu tiên, để nắm tình hình chung.

`S` · 3 SP · PIC: Nguyễn Tiến Lưỡng

**AC**
- Chọn được khoảng thời gian (mặc định 30 ngày gần nhất).
- Trả về số liệu gộp theo `status` và theo `priority`.
- Kết quả cache 5 phút (Redis), có tham số `?refresh=true` để bỏ qua cache.

### US-38 — Thời gian xử lý trung bình theo loại sự cố
> Là **Admin**, tôi muốn xem thời gian xử lý trung bình theo từng loại sự cố, để đánh giá hiệu suất đội IT.

`S` · 5 SP

**AC**
- Hai chỉ số riêng: **thời gian phản hồi đầu tiên** và **thời gian giải quyết**.
- Hiển thị **trung vị (p50) và p90**, không chỉ trung bình — trung bình bị một ticket kéo dài làm méo.
- Loại trừ khoảng thời gian ticket ở trạng thái `PENDING_REQUESTER` (đang chờ người dùng phản hồi, không phải lỗi của Agent).

### US-39 — Workload theo từng IT Agent
> Là **Admin**, tôi muốn xem khối lượng công việc theo từng IT Agent, để cân đối phân công.

`S` · 3 SP

**AC**
- Mỗi Agent: số ticket đang mở, đã đóng trong kỳ, thời gian xử lý trung bình, tỉ lệ vi phạm SLA, điểm hài lòng trung bình.
- Sắp xếp được theo từng cột.

### US-40 — Xuất báo cáo CSV
> Là **Admin**, tôi muốn xuất danh sách ticket ra CSV, để phân tích thêm bằng Excel.

`C` · 5 SP

**AC**
- Xuất theo bộ lọc hiện tại; giới hạn 10.000 dòng/lần xuất.
- Xuất theo kiểu stream (`StreamingResponse`), không nạp toàn bộ vào bộ nhớ.
- **Chống CSV injection:** ô bắt đầu bằng `= + - @` phải được thêm tiền tố `'`.

---

## F8 — Đánh giá Sau Xử lý

### US-41 — Nhân viên đánh giá sau khi ticket đóng
> Là **nhân viên**, tôi muốn đánh giá mức độ hài lòng sau khi ticket được đóng, để phản hồi chất lượng dịch vụ.

`S` · 3 SP · PIC: Nguyễn Đăng Trường

**AC**
- Chỉ đánh giá được khi ticket ở trạng thái `RESOLVED` hoặc `CLOSED`, và chỉ người tạo ticket mới được đánh giá.
- `score` từ 1–5 (bắt buộc), `comment` tối đa 1.000 ký tự (tuỳ chọn).
- **Mỗi ticket đúng một đánh giá** (unique constraint trên `ticket_id`); gửi lần hai ⇒ `409`.
- Sửa được đánh giá trong 24 giờ đầu, sau đó khoá.
- Gửi thông báo mời đánh giá khi ticket chuyển `RESOLVED`.

### US-42 — Tổng hợp điểm hài lòng
> Là **Admin**, tôi muốn tổng hợp điểm hài lòng theo từng IT Agent và theo kỳ, để đưa vào báo cáo đánh giá hiệu suất.

`S` · 3 SP

**AC**
- Điểm trung bình + phân bố 1–5 sao theo Agent, theo category, theo tháng.
- Hiển thị **tỉ lệ phản hồi** (số đánh giá / số ticket đã đóng) — điểm trung bình mà tỉ lệ phản hồi thấp thì không đáng tin, phải hiển thị kèm.
- Ẩn tên người đánh giá khi hiển thị cho Agent (Agent chỉ thấy điểm và nhận xét, không thấy ai chấm).

### US-43 — Agent xem đánh giá về mình
> Là **IT Agent**, tôi muốn xem điểm và nhận xét về các ticket mình đã xử lý, để tự cải thiện.

`C` · 2 SP

**AC**
- Agent chỉ xem được đánh giá của ticket do chính mình xử lý, ở dạng ẩn danh người chấm.

---

## 10. Đề xuất thứ tự ưu tiên cho Sprint Planning

Do rủi ro vượt năng lực đã nêu ở §0, đề xuất chia làm 3 lớp:

**Lớp 1 — Xương sống, phải xong trước ngày 7 của Sprint 1 (khoảng 60 SP)**
US-01, 02, 03, 06 (auth + phân quyền) · US-08, 10, 11, 12, 13, 14 (vòng đời ticket) · US-28, 30 (KB cơ bản)

> Lý do: đây là luồng demo "nhân viên tạo ticket → Agent xử lý → đóng ticket". Nếu ngày 7 chưa chạy được luồng này thì phải báo động ngay, không đợi cuối sprint.

**Lớp 2 — Giá trị AI, ngày 8–12 (khoảng 55 SP)**
US-19, 20, 21 (phân loại + gợi ý) · US-23, 24, 29 (RAG chatbot) · US-15 (bình luận) · US-33, 34 (thông báo)

> Lý do: đây là phần khác biệt của đề tài. Bắt đầu song song từ ngày 1 (chuẩn bị dữ liệu, dựng pipeline) nhưng chỉ tích hợp khi Lớp 1 ổn định.

**Lớp 3 — Hoàn thiện, ngày 12–14 và Sprint 2 (khoảng 62 SP)**
US-04, 05, 07, 09, 16, 17, 22, 25, 26, 27, 31, 35, 36, 37, 38, 39, 41, 42

**Cắt trước nếu chậm tiến độ (đã thống nhất trước để không phải tranh cãi lúc gấp):**
US-18 (huỷ ticket), US-32 (gợi ý bài viết realtime), US-40 (xuất CSV), US-43 (Agent xem đánh giá), lưu phiên bản bài viết KB.

---

## 11. Đối chiếu với FR bắt buộc trong `02.Project-Requirement.pdf`

Tài liệu yêu cầu gốc mô tả hệ thống quản lý dự án; đề tài của nhóm là helpdesk. Bảng dưới chứng minh **mọi FR bắt buộc đều có phần tương ứng**, để Trainer đối chiếu khi chấm.

| FR gốc | Ánh xạ trong Smart IT Helpdesk | User Story |
|---|---|---|
| FR-01 Authentication | Đăng ký/đăng nhập/đăng xuất/refresh/đổi mật khẩu | US-01 → US-05 |
| FR-02 User Management | Admin CRUD user, khoá/mở khoá, tìm kiếm | US-07 |
| FR-03 Project Management | *Không áp dụng* → thay bằng quản lý Phòng ban + Category | US-07, US-31 |
| FR-04 Sprint Management | *Không áp dụng* → thay bằng SLA Policy | US-35 |
| FR-05 Task Management | Quản lý Ticket: tạo, giao, đổi người phụ trách, deadline (SLA), priority, đổi trạng thái, comment, attachment | US-08 → US-15 |
| FR-06 Dashboard | Dashboard ticket theo trạng thái/priority/quá hạn | US-37 → US-39 |
| FR-07 Search | Tìm kiếm ticket, tài liệu, user + filter/sort/pagination | US-16, US-30, US-07 |
| FR-08 Notification | In-app notification + nhắc deadline | US-33 → US-36 |
| FR-09 Reporting | Xuất CSV danh sách ticket + báo cáo hiệu suất | US-40, US-42 |
| Bonus: AI Assistant, gợi ý phân công AI, Chatbot | F3 + F4 — **trọng tâm của đề tài** | US-19 → US-27 |
| Bonus: Audit Log | `ticket_events` append-only | US-17 |
| Bonus: Rate limiting, API versioning, CI/CD | Có trong thiết kế (tài liệu 08) | — |
