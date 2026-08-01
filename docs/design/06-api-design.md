# 06 — Thiết kế API

| | |
|---|---|
| Phiên bản | 1.0 |
| Base URL | `/api/v1` |
| Đặc tả sinh tự động | OpenAPI 3.1 tại `/api/v1/openapi.json`, Swagger UI tại `/docs` |
| PIC | Chu Quang Vũ (API doc), các module owner (đặc tả từng nhóm endpoint) |

> **Hợp đồng trước, cài đặt sau.** Frontend (2 người) và Backend (5 người) làm song song trong cùng một sprint. Nếu hợp đồng API không được chốt trong 2 ngày đầu, hai phía sẽ chờ nhau. Tài liệu này là hợp đồng đó.

---

## 1. Quy ước chung

| Hạng mục | Quy ước | Ví dụ |
|---|---|---|
| Đường dẫn | Danh từ số nhiều, không có động từ | `GET /tickets` ✓ · `GET /getTickets` ✗ |
| Tài nguyên con | Lồng một cấp, không sâu hơn | `/tickets/{id}/comments` ✓ · `/tickets/{id}/comments/{cid}/reactions` ✗ |
| Hành động không phải CRUD | Tài nguyên con dạng động từ | `POST /tickets/{id}/assign`, `POST /tickets/{id}/status` |
| Tham số truy vấn | `camelCase` | `?pageSize=20&sortBy=createdAt` |
| Trường JSON | `camelCase` | `{ "createdAt": "...", "assigneeId": "..." }` |
| Enum | `UPPER_SNAKE_CASE` | `"IN_PROGRESS"`, `"URGENT"` |
| Thời gian | ISO 8601 UTC, có `Z` | `"2026-07-30T09:15:00Z"` |
| ID | UUID dạng chuỗi | `"018f9c2e-..."` |
| Versioning | Tiền tố đường dẫn `/api/v1` | Phá vỡ tương thích ⇒ `/api/v2`, không sửa v1 |
| Ngôn ngữ | Thông điệp lỗi bằng **tiếng Việt** cho người dùng; `code` bằng tiếng Anh cho máy | |

**Nguyên tắc mở rộng:** chỉ **thêm** trường tuỳ chọn, không bao giờ đổi kiểu hoặc xoá trường đã công bố. Frontend có thể đang phụ thuộc vào bất kỳ trường nào đã trả về.

---

## 2. Xác thực

Mọi endpoint (trừ những endpoint đánh dấu công khai) yêu cầu header:

```
Authorization: Bearer <access_token>
```

| Token | TTL | Nội dung (claims) | Lưu ở đâu (frontend) |
|---|---|---|---|
| Access | 15 phút | `sub` (user id), `role`, `exp`, `iat`, `jti` | Trong bộ nhớ (biến JS), **không** localStorage |
| Refresh | 7 ngày | Chuỗi ngẫu nhiên 256-bit (không phải JWT) | Cookie `HttpOnly; Secure; SameSite=Strict` |

**Vì sao access token để trong bộ nhớ, refresh token trong cookie HttpOnly:** access token nằm ở localStorage sẽ bị đánh cắp nếu có bất kỳ lỗ hổng XSS nào. Cookie `HttpOnly` thì JavaScript không đọc được. Đánh đổi: mất token khi refresh trang ⇒ SPA gọi `/auth/refresh` lúc khởi động.

---

## 3. Định dạng lỗi thống nhất

**Mọi** lỗi đều có đúng hình dạng này — không có ngoại lệ:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Dữ liệu không hợp lệ",
    "details": [
      { "field": "title", "message": "Tiêu đề phải từ 5 đến 200 ký tự" }
    ],
    "requestId": "018f9c2e-4a1b-7c3d-9e5f-a1b2c3d4e5f6"
  }
}
```

| HTTP | `code` | Khi nào |
|---|---|---|
| 400 | `BAD_REQUEST` | Request sai định dạng |
| 401 | `UNAUTHENTICATED` | Thiếu/sai/hết hạn access token |
| 401 | `INVALID_CREDENTIALS` | Sai email hoặc mật khẩu (**không phân biệt** — chống dò tài khoản) |
| 403 | `FORBIDDEN` | Đã xác thực nhưng không đủ quyền |
| 403 | `ACCOUNT_DISABLED` | Tài khoản bị khoá |
| 404 | `NOT_FOUND` | Không tồn tại **hoặc** không có quyền xem (xem §5) |
| 409 | `CONFLICT` | Trùng dữ liệu, xung đột phiên bản |
| 409 | `TICKET_ALREADY_ASSIGNED` | Hai Agent cùng nhận một ticket |
| 422 | `VALIDATION_ERROR` | Dữ liệu không qua được validation |
| 422 | `INVALID_STATUS_TRANSITION` | Bước chuyển trạng thái không hợp lệ (kèm `allowedStatuses`) |
| 429 | `RATE_LIMITED` | Vượt giới hạn tốc độ (kèm header `Retry-After`) |
| 502 | `UPSTREAM_ERROR` | LLM / object storage lỗi |
| 503 | `SERVICE_UNAVAILABLE` | Đang bảo trì |

`requestId` xuất hiện trong **mọi** response lỗi và trong mọi dòng log ⇒ người dùng báo lỗi kèm mã này là truy được ngay đúng request trong log.

---

## 4. Phân trang, lọc, sắp xếp

**Request:**
```
GET /api/v1/tickets?page=1&pageSize=20&sortBy=createdAt&sortOrder=desc
                   &status=IN_PROGRESS&status=ASSIGNED&priority=HIGH
                   &categoryId=<uuid>&assigneeId=<uuid>&q=không+vào+được+wifi
                   &createdFrom=2026-07-01T00:00:00Z&createdTo=2026-07-31T23:59:59Z
```

**Response:**
```json
{
  "data": [ /* ... */ ],
  "pagination": { "page": 1, "pageSize": 20, "totalItems": 142, "totalPages": 8 }
}
```

| Quy tắc | Giá trị |
|---|---|
| `pageSize` mặc định / tối đa | 20 / 100 |
| Tham số lặp lại (`status=A&status=B`) | Hiểu là `OR` trong cùng một trường, `AND` giữa các trường khác nhau |
| `sortBy` | Chỉ chấp nhận danh sách trường cho phép (allowlist) — **không bao giờ** nối thẳng vào SQL |
| Danh sách rỗng | `200` với `data: []`, **không phải** `404` |

> **Mọi endpoint danh sách đều phải có phân trang ngay từ đầu.** Thêm phân trang sau khi frontend đã code là một thay đổi phá vỡ tương thích.

---

## 5. Ma trận phân quyền

Đây là bảng tham chiếu để cài đặt và để viết test. Mỗi ô có ít nhất một test khẳng định **cho phép** và một test khẳng định **từ chối**.

| Endpoint | Employee | IT Agent | Admin |
|---|---|---|---|
| `POST /auth/register` | Công khai | Công khai | Công khai |
| `POST /auth/login` · `/refresh` · `/logout` | Công khai / Đã đăng nhập | ✓ | ✓ |
| `GET /users/me` | ✓ | ✓ | ✓ |
| `GET /users` | ✗ | ✓ (chỉ tên + phòng ban) | ✓ (đầy đủ) |
| `POST /users` · `PATCH /users/{id}` · `/activate` · `/deactivate` | ✗ | ✗ | ✓ |
| `POST /tickets` | ✓ | ✓ | ✓ |
| `GET /tickets` | Chỉ ticket của mình | Tất cả | Tất cả |
| `GET /tickets/{id}` | Chỉ của mình (khác ⇒ **404**) | Tất cả | Tất cả |
| `PATCH /tickets/{id}` | Chỉ `title`/`description`, chỉ khi `NEW` | ✓ | ✓ |
| `POST /tickets/{id}/assign` | ✗ | ✓ | ✓ |
| `POST /tickets/{id}/claim` | ✗ | ✓ | ✗ |
| `POST /tickets/{id}/status` | Chỉ `CANCELLED` (ticket của mình, khi `NEW`/`ASSIGNED`), `CLOSED`, reopen | Chỉ ticket được giao | ✓ |
| `POST /tickets/{id}/comments` | Ticket của mình, `isInternal` bị **bỏ qua** | ✓ (được dùng `isInternal`) | ✓ |
| `GET /tickets/{id}/comments` | **Không thấy** comment nội bộ | ✓ | ✓ |
| `POST /tickets/{id}/attachments` | Ticket của mình | ✓ | ✓ |
| `GET /tickets/{id}/events` | Ticket của mình | ✓ | ✓ |
| `POST /tickets/{id}/rating` | Chỉ requester, ticket `RESOLVED`/`CLOSED` | ✗ | ✗ |
| `GET /tickets/{id}/assignee-suggestions` | ✗ | ✓ | ✓ |
| `GET /tickets/{id}/ai-classification` | Ticket của mình | ✓ | ✓ |
| `GET /kb/articles` (đã publish) | ✓ | ✓ | ✓ |
| `POST` · `PATCH` · `DELETE /kb/articles` | ✗ | ✗ | ✓ |
| `GET /kb/articles?status=DRAFT` | ✗ | ✗ | ✓ |
| `POST /chat/sessions` · `/messages` | ✓ | ✓ | ✓ |
| `GET /chat/sessions/{id}` | Chỉ của mình | Chỉ của mình | Chỉ của mình |
| `GET /chat/quality/gaps` | ✗ | ✓ | ✓ |
| `GET /notifications` | Chỉ của mình | Chỉ của mình | Chỉ của mình |
| `GET /reports/*` | ✗ | ✓ (chỉ số liệu của chính mình) | ✓ (toàn bộ) |
| `GET /reports/ai-accuracy` | ✗ | ✓ | ✓ |

> **Vì sao trả `404` thay vì `403` khi Employee xem ticket của người khác:** `403` xác nhận rằng ticket đó **tồn tại**. Kẻ tấn công có thể dò ID để biết hệ thống có bao nhiêu ticket. `404` không tiết lộ gì.

---

## 6. Danh mục Endpoint

### 6.1 `auth` — Xác thực

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| `POST` | `/auth/register` | Đăng ký tài khoản | Công khai |
| `POST` | `/auth/login` | Đăng nhập, trả access + refresh | Công khai |
| `POST` | `/auth/refresh` | Xoay vòng token | Cookie refresh |
| `POST` | `/auth/logout` | Thu hồi refresh token hiện tại | Bearer |
| `POST` | `/auth/logout-all` | Thu hồi toàn bộ phiên | Bearer |
| `POST` | `/auth/change-password` | Đổi mật khẩu, thu hồi mọi phiên | Bearer |

<details>
<summary><code>POST /auth/login</code> — chi tiết</summary>

```jsonc
// Request
{ "email": "nam.bui@company.com", "password": "••••••••" }

// 200 OK   (refresh token được đặt trong cookie HttpOnly, không nằm trong body)
{
  "accessToken": "eyJhbGciOi...",
  "tokenType": "Bearer",
  "expiresIn": 900,
  "user": {
    "id": "018f...", "email": "nam.bui@company.com", "fullName": "Bùi Mậu Văn",
    "role": "ADMIN", "department": { "id": "018f...", "name": "Kỹ thuật" }
  }
}

// 401 — sai email HOẶC sai mật khẩu, cùng một thông điệp
{ "error": { "code": "INVALID_CREDENTIALS",
             "message": "Email hoặc mật khẩu không đúng", "requestId": "..." } }

// 429
{ "error": { "code": "RATE_LIMITED",
             "message": "Bạn đã thử quá nhiều lần. Vui lòng thử lại sau 15 phút.",
             "requestId": "..." } }
```
</details>

### 6.2 `users` — Người dùng & Phòng ban

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/users/me` | Thông tin người đang đăng nhập |
| `PATCH` | `/users/me` | Cập nhật hồ sơ cá nhân (`fullName`, `phone`, `avatarUrl`) |
| `GET` | `/users` | Danh sách (lọc `role`, `departmentId`, `isActive`, `q`) |
| `POST` | `/users` | Admin tạo người dùng |
| `GET` | `/users/{id}` | Chi tiết |
| `PATCH` | `/users/{id}` | Cập nhật (gồm đổi `role`) |
| `POST` | `/users/{id}/activate` · `/deactivate` | Mở/khoá tài khoản |
| `GET` | `/users/agents` | Danh sách IT Agent đang hoạt động kèm tải hiện tại |
| `PUT` | `/users/{id}/skills` | Gán kỹ năng theo category (phục vụ US-20) |
| `GET` | `/departments` · `POST` · `PATCH` | Quản lý phòng ban |

### 6.3 `tickets` — Nhóm endpoint lớn nhất

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/tickets` | Tạo ticket (hỗ trợ `Idempotency-Key`) |
| `GET` | `/tickets` | Danh sách có lọc/tìm kiếm/phân trang |
| `GET` | `/tickets/{id}` | Chi tiết đầy đủ |
| `PATCH` | `/tickets/{id}` | Sửa tiêu đề/mô tả/category/priority |
| `POST` | `/tickets/{id}/claim` | Agent tự nhận |
| `POST` | `/tickets/{id}/assign` | Giao cho Agent khác |
| `POST` | `/tickets/{id}/status` | Chuyển trạng thái |
| `GET` | `/tickets/{id}/allowed-transitions` | Các trạng thái kế tiếp hợp lệ **cho vai trò hiện tại** |
| `GET` · `POST` | `/tickets/{id}/comments` | Bình luận |
| `GET` · `POST` | `/tickets/{id}/attachments` | Đính kèm |
| `GET` | `/tickets/{id}/attachments/{aid}/download` | Trả về `302` tới pre-signed URL |
| `GET` | `/tickets/{id}/events` | Lịch sử thay đổi |
| `GET` | `/tickets/{id}/assignee-suggestions` | Top 3 gợi ý người xử lý |
| `GET` | `/tickets/{id}/ai-classification` | Gợi ý phân loại gần nhất của AI; trả `null` khi worker chưa xong |
| `POST` | `/tickets/{id}/rating` · `PATCH` | Đánh giá sau xử lý |
| `GET` | `/tickets/stats/queue` | Số đếm nhanh cho thanh bên của Agent |

<details>
<summary><code>POST /tickets</code> — chi tiết</summary>

```jsonc
// Request
// Header (tuỳ chọn): Idempotency-Key: 018f9c2e-...
{
  "title": "Không kết nối được WiFi công ty tại tầng 5",
  "description": "Từ sáng nay máy tôi không thấy mạng CTY-WIFI...",
  "categoryId": null,          // để null → AI tự phân loại
  "priority": null,            // để null → mặc định MEDIUM, AI có thể chỉnh
  "attachmentIds": ["018f..."],
  "chatSessionId": null        // có giá trị nếu tạo từ cuộc trò chuyện với chatbot
}

// 201 Created
{
  "id": "018f9c2e-...", "code": "HD-202607-00142",
  "title": "Không kết nối được WiFi công ty tại tầng 5",
  "status": "NEW", "priority": "MEDIUM",
  "category": null,
  "aiStatus": "PENDING",       // ← phân loại đang chạy nền, sẽ có sau ≤ 30s
  "requester": { "id": "018f...", "fullName": "Nguyễn Văn A" },
  "assignee": null,
  "slaResolutionDueAt": "2026-07-31T09:30:00Z",
  "createdAt": "2026-07-30T02:30:00Z"
}
```

**Đây là ví dụ điển hình của "bất đồng bộ nhưng vẫn dùng được ngay":** API trả về trong < 500 ms với `aiStatus: PENDING`. Frontend hiển thị ticket bình thường kèm nhãn "Đang phân loại...", rồi cập nhật sau. Nếu AI hỏng, ticket vẫn hoàn toàn dùng được.
</details>

<details>
<summary><code>POST /tickets/{id}/status</code> — chi tiết</summary>

```jsonc
// Request
{ "status": "RESOLVED", "resolutionNote": "Đã reset lại cấu hình DHCP trên switch tầng 5.",
  "version": 3 }              // optimistic lock

// 200 OK → trả về ticket đầy đủ đã cập nhật

// 422 — bước chuyển không hợp lệ
{ "error": { "code": "INVALID_STATUS_TRANSITION",
             "message": "Không thể chuyển từ NEW sang RESOLVED",
             "details": { "currentStatus": "NEW", "allowedStatuses": ["ASSIGNED", "CANCELLED"] },
             "requestId": "..." } }

// 409 — người khác vừa sửa ticket này
{ "error": { "code": "CONFLICT",
             "message": "Ticket đã được người khác cập nhật. Vui lòng tải lại.",
             "details": { "currentVersion": 4 }, "requestId": "..." } }
```

Endpoint `GET /tickets/{id}/allowed-transitions` tồn tại để frontend **chỉ hiển thị các nút hợp lệ** thay vì hiện hết rồi báo lỗi — máy trạng thái vẫn nằm ở backend, frontend chỉ hỏi.
</details>

### 6.4 `knowledge` — Kho tài liệu

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/kb/articles` | Danh sách/tìm kiếm (`q`, `categoryId`, `tags`, `status`) |
| `GET` | `/kb/articles/{slug}` | Chi tiết theo slug (tăng `viewCount`) |
| `POST` · `PATCH` | `/kb/articles` · `/kb/articles/{id}` | Admin soạn thảo |
| `POST` | `/kb/articles/{id}/publish` · `/unpublish` | Đổi trạng thái, kích hoạt index |
| `POST` | `/kb/articles/{id}/reindex` | Ép index lại một bài |
| `GET` | `/kb/articles/suggest?q=...` | Gợi ý khi đang gõ mô tả ticket (US-32) |
| `GET` · `POST` · `PATCH` · `DELETE` | `/kb/categories` | Quản lý chủ đề |

### 6.5 `chatbot`

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/chat/sessions` | Mở phiên mới |
| `GET` | `/chat/sessions` | Lịch sử phiên của tôi |
| `GET` | `/chat/sessions/{id}` | Chi tiết phiên kèm tin nhắn |
| `POST` | `/chat/sessions/{id}/messages` | **Gửi câu hỏi — trả về SSE stream** |
| `POST` | `/chat/messages/{id}/feedback` | 👍/👎 |
| `POST` | `/chat/sessions/{id}/create-ticket` | Chuyển hội thoại thành ticket |
| `GET` | `/chat/quality/gaps` | Câu hỏi chatbot trả lời kém (US-27) |

<details>
<summary><code>POST /chat/sessions/{id}/messages</code> — giao thức SSE</summary>

```
Request:  { "content": "Làm sao để đổi mật khẩu email công ty?" }
Response: Content-Type: text/event-stream

event: citations
data: {"citations":[{"articleId":"018f...","title":"Hướng dẫn đổi mật khẩu email","slug":"doi-mat-khau-email","score":0.89}]}

event: token
data: {"delta":"Bạn có thể"}

event: token
data: {"delta":" đổi mật khẩu"}

event: done
data: {"messageId":"018f...","latencyMs":2840,"noContextFound":false}

// hoặc khi lỗi:
event: error
data: {"code":"UPSTREAM_ERROR","message":"Trợ lý ảo tạm thời không phản hồi. Bạn có thể tạo ticket để đội IT hỗ trợ trực tiếp.","canCreateTicket":true}
```

**Trích dẫn được gửi TRƯỚC nội dung** — người dùng thấy ngay nguồn tham chiếu trong khi câu trả lời còn đang sinh, và biết chắc câu trả lời dựa trên tài liệu nội bộ.
</details>

### 6.6 `notifications`

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/notifications` | Danh sách (lọc `isRead`) |
| `GET` | `/notifications/unread-count` | Chỉ trả `{ "count": 3 }` — frontend gọi mỗi 30 s, phải cực nhẹ |
| `POST` | `/notifications/{id}/read` · `/read-all` | Đánh dấu đã đọc |

### 6.7 `reports`

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/reports/overview?from&to` | Tổng số theo trạng thái + mức ưu tiên (US-37) |
| `GET` | `/reports/resolution-time?from&to&groupBy=category` | p50/p90 thời gian phản hồi & giải quyết (US-38) |
| `GET` | `/reports/agent-workload?from&to` | Workload theo Agent (US-39) |
| `GET` | `/reports/satisfaction?from&to&groupBy=agent` | Điểm hài lòng + tỉ lệ phản hồi (US-42) |
| `GET` | `/reports/sla-compliance?from&to` | Tỉ lệ đạt/vi phạm SLA |
| `GET` | `/reports/ai-accuracy?from&to` | Độ chính xác phân loại AI theo tuần (US-22) |
| `GET` | `/reports/tickets/export?format=csv` | Xuất CSV dạng stream (US-40) |

Mọi endpoint báo cáo trả kèm `"generatedAt"` và `"cached": true|false`.

### 6.8 Vận hành

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| `GET` | `/health/live` | Tiến trình còn sống (không kiểm tra phụ thuộc) | Công khai |
| `GET` | `/health/ready` | Sẵn sàng nhận traffic (kiểm tra DB, Redis) | Công khai |
| `GET` | `/metrics` | Prometheus | Chỉ nội bộ |

> **Vì sao `live` không kiểm tra database:** nếu health check phụ thuộc DB, một sự cố DB ngắn sẽ khiến orchestrator khởi động lại **toàn bộ** instance cùng lúc — biến một sự cố suy giảm thành một sự cố sập hoàn toàn.

---

## 7. Giới hạn tốc độ (Rate limiting)

| Endpoint | Giới hạn | Theo | Lý do |
|---|---|---|---|
| `POST /auth/login` | 5 lần / 15 phút | email + IP | Chống dò mật khẩu |
| `POST /auth/register` | 3 lần / giờ | IP | Chống tạo tài khoản hàng loạt |
| `POST /chat/.../messages` | 20 lần / giờ | user | **Chống vỡ ngân sách LLM** |
| `POST /tickets` | 10 lần / giờ | user | Chống spam ticket |
| `POST /tickets/{id}/attachments` | 20 lần / giờ | user | Chống lạm dụng lưu trữ |
| Toàn cục | 300 lần / phút | user | Lưới an toàn |

Cài đặt bằng thuật toán token bucket trên Redis. Khi vượt: `429` + header `Retry-After`. **Redis hỏng ⇒ cho qua (fail-open)**, ghi cảnh báo — thà mất giới hạn tốc độ còn hơn chặn toàn bộ người dùng.

---

## 8. Ràng buộc cho Frontend

| Ràng buộc | Nội dung |
|---|---|
| Timeout | Mọi lời gọi API: 10 s. Riêng chat SSE: 60 s |
| Thử lại | Chỉ thử lại `GET` và chỉ khi lỗi mạng/`5xx`; tối đa 2 lần, backoff 1 s → 3 s. **Không bao giờ tự thử lại `POST`** trừ khi có `Idempotency-Key` |
| Hết hạn token | Nhận `401` ⇒ gọi `/auth/refresh` một lần rồi thử lại request gốc; vẫn `401` ⇒ chuyển về trang đăng nhập |
| Polling | `unread-count` mỗi 30 s; chi tiết ticket mỗi 20 s **chỉ khi tab đang hiển thị** (dùng Page Visibility API) |
| Hiển thị lỗi | Luôn hiển thị `error.message` (đã là tiếng Việt, thân thiện). Hiển thị `requestId` ở chỗ kín đáo để người dùng báo lỗi |
| Trạng thái rỗng | Danh sách rỗng là `200` + `data: []` — phải có giao diện "chưa có dữ liệu", không phải màn hình lỗi |

---

## 9. Chiến lược tài liệu API

1. **Sinh tự động từ Pydantic schema** — `response_model` phải khai báo đầy đủ trên mọi endpoint. Không viết tay OpenAPI.
2. Mỗi endpoint có `summary`, `description`, và `responses` cho các mã lỗi chính.
3. **Xuất `openapi.json` ra file và commit vào repo** ở mỗi lần release ⇒ diff của file này trong PR cho thấy ngay thay đổi có phá vỡ tương thích hay không. Đây là cách rẻ nhất để chống phá vỡ hợp đồng khi 5 người cùng sửa API.
4. Frontend sinh TypeScript type từ `openapi.json` (`openapi-typescript`) ⇒ đổi API mà quên sửa frontend sẽ **lỗi lúc biên dịch**, không phải lỗi lúc chạy.
5. Postman/Bruno collection cho QA, xuất từ cùng một `openapi.json`.
