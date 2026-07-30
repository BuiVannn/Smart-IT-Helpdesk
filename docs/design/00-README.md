# Smart IT Helpdesk — Bộ tài liệu Phân tích & Thiết kế

> Hệ thống hỗ trợ IT nội bộ thông minh, tích hợp AI phân loại ticket và chatbot RAG.
> Mock Project — FSA/FPT Software · Agile Scrum · 9 thành viên · 4 tuần.

| | |
|---|---|
| Phiên bản bộ tài liệu | 1.0 |
| Ngày | 2026-07-30 |
| Trạng thái | **Draft — chờ review với Trainer (Product Owner)** |
| Chủ trì | Bùi Mậu Văn (Scrum Master / AI Engineer) |

---

## Đọc theo thứ tự nào

```
01 Phân tích yêu cầu ──► 02 User Story ──► 03 Mô hình miền ──► 04 ERD & Database
                                              │                      │
                                              ▼                      ▼
                                     05 Kiến trúc & Module ──► 06 API Design
                                              │                      │
                              ┌───────────────┼──────────────┐       │
                              ▼               ▼              ▼       ▼
                      07 Thiết kế AI   08 Bảo mật & Vận hành   09 Frontend
                              │               │              │       │
                              └───────────────┴──────────────┴───────┘
                                              ▼
                                     10 Chiến lược kiểm thử
                                              │
                                              ▼
                                        adr/ — 11 quyết định kiến trúc
```

| # | Tài liệu | Nội dung chính | Ai cần đọc kỹ nhất |
|---|---|---|---|
| [01](01-requirement-analysis.md) | **Phân tích yêu cầu** | Bối cảnh, mục tiêu, **phạm vi KHÔNG làm**, actor, use case, NFR có số, ước lượng dung lượng, câu hỏi cho PO | Tất cả — đặc biệt §3 Non-goals và §8 Ước lượng |
| [02](02-user-stories.md) | **User Story & Tiêu chí chấp nhận** | 43 story, AC dạng Given/When/Then, MoSCoW, story point, đề xuất thứ tự ưu tiên | Tất cả · QA (nguồn viết test case) |
| [03](03-domain-model.md) | **Mô hình miền & Sơ đồ lớp** | Từ điển thuật ngữ, bóc tách chức năng, sơ đồ lớp, **máy trạng thái ticket**, quy tắc SLA, 20 quy tắc nghiệp vụ | Backend developers |
| [04](04-erd-and-database.md) | **ERD & Cơ sở dữ liệu** | ERD, schema DDL đầy đủ, ràng buộc, **chiến lược index**, seed, vòng đời dữ liệu, kế hoạch migration | Nguyễn Đăng Trường · Cao Mạnh Hà |
| [05](05-architecture-and-modules.md) | **Kiến trúc & Module** | C4 L1/L2/L3, **ma trận phụ thuộc module**, cấu trúc thư mục, DI, deployment, CI/CD | Tất cả backend |
| [06](06-api-design.md) | **Thiết kế API** | Quy ước, định dạng lỗi, phân trang, **ma trận phân quyền**, danh mục endpoint, rate limit | Backend + Frontend |
| [07](07-ai-design.md) | **Thiết kế AI** | Pipeline phân loại, pipeline RAG, prompt, chống injection, đánh giá chất lượng, kiểm soát chi phí | Bùi Mậu Văn |
| [08](08-nfr-security-ops.md) | **Bảo mật & Vận hành** | Mô hình mối đe doạ, **3 lớp phân quyền**, quản lý bí mật, log/metrics/alert, runbook, checklist nộp bài | Lại Duy Đông · Cao Mạnh Hà |
| [09](09-frontend-design.md) | **Thiết kế Frontend** | Route, wireframe, cây component, quản lý state, trạng thái UI, thứ tự làm việc | Nguyễn Văn Quang · Nguyễn Văn Dũng |
| [10](10-test-strategy.md) | **Chiến lược kiểm thử** | Kim tự tháp test, test bắt buộc, kiểm thử AI, kịch bản demo, cổng chất lượng CI | Trần Quang Ngọc |
| [adr/](adr/) | **Quyết định kiến trúc** | 11 ADR — mỗi quyết định lớn kèm phương án bị loại và lý do | Tất cả |

---

## Ánh xạ tới Deliverable bắt buộc của Guideline

| Deliverable (Guideline §10, §11) | Tài liệu tương ứng |
|---|---|
| Backend Design — Kiến trúc | `05-architecture-and-modules.md` §1–3 |
| Backend Design — API Design | `06-api-design.md` |
| Backend Design — Module Design | `05-architecture-and-modules.md` §4–6 |
| Frontend Design — Wireframe | `09-frontend-design.md` §3 |
| Frontend Design — Component Design | `09-frontend-design.md` §4–5 |
| Database Design — ERD | `04-erd-and-database.md` §1 |
| Database Design — Schema | `04-erd-and-database.md` §3–4 |
| Database Design — Index | `04-erd-and-database.md` §5 |
| API Document (Swagger/OpenAPI) | Sinh tự động — chiến lược ở `06-api-design.md` §9 |
| Test Plan / Test Cases / Test Report | Khung ở `10-test-strategy.md`, QA soạn chi tiết |

---

## Danh sách 11 quyết định kiến trúc

| ADR | Quyết định | Đánh đổi chính |
|---|---|---|
| [0001](adr/0001-modular-monolith.md) | Modular Monolith, không microservices | Không scale riêng từng phần — không cần ở tải 1,5 rps |
| [0002](adr/0002-single-postgres.md) | PostgreSQL là kho dữ liệu duy nhất | Full-text search yếu hơn Elasticsearch |
| [0003](adr/0003-jwt-no-blacklist.md) | Không blacklist access token | Cửa sổ 15 phút sau khi thu hồi |
| [0004](adr/0004-postgres-fulltext.md) | PostgreSQL FTS + `unaccent`, không Elasticsearch | Không phân tích hình thái tiếng Việt |
| [0005](adr/0005-pgvector.md) | `pgvector`, không vector DB riêng | Không có tính năng vector nâng cao |
| [0006](adr/0006-native-enum.md) | Native ENUM cho tập giá trị ổn định | Thêm giá trị cần migration |
| [0007](adr/0007-celery-no-outbox.md) | Celery trực tiếp + job đối soát, chưa dùng outbox | Có cửa sổ mất tác vụ, bù bằng đối soát |
| [0008](adr/0008-polling-not-websocket.md) | Polling, không WebSocket | Độ trễ thông báo tối đa 30 giây |
| [0009](adr/0009-async-ai-classification.md) | Phân loại AI bất đồng bộ | Có trạng thái trung gian "đang phân loại" |
| [0010](adr/0010-react-spa.md) | React SPA (Vite), không Next.js | Không SSR — không cần cho hệ thống nội bộ |
| [0011](adr/0011-uuidv7-primary-key.md) | UUIDv7 làm khoá chính | Index lớn hơn `BIGSERIAL` |

---

## Năm điều quan trọng nhất rút ra từ bộ tài liệu này

**1. Hệ thống này rất nhỏ về mặt tải — và đó là thông tin quan trọng nhất.**
Tải đỉnh ~1,5 rps, dữ liệu 3 năm ~1,1 GB. Một FastAPI + một PostgreSQL dư sức, dư 2 bậc độ lớn. Mọi đề xuất thêm Kafka, Elasticsearch, vector DB riêng, hay microservices đều phải đối chiếu lại với `01 §8`. **Công sức tiết kiệm được ở đây phải dồn sang bốn chỗ thật sự rủi ro:** phân quyền dữ liệu, máy trạng thái ticket, chất lượng RAG, và ranh giới module.

**2. Nút thắt là LLM provider, không phải database.**
Độ trễ 2–5 giây và rate limit của LLM là ràng buộc thật duy nhất. Vì vậy phân loại chạy **bất đồng bộ** (ADR-0009) và chatbot **stream** (SSE). Mọi thành phần AI hỏng thì hệ thống vẫn phải chạy ở mức suy giảm — không bao giờ chặn vòng đời ticket.

**3. Rủi ro lớn nhất là rò rỉ dữ liệu giữa người dùng, không phải hiệu năng.**
Nhân viên đọc được ticket của người khác là sự cố nghiêm trọng nhất mà hệ thống này có thể gây ra. Ba lớp kiểm soát ở `08 §2`, lọc ngay trong truy vấn, trả `404` thay vì `403`, và hai bài test bắt buộc quét toàn bộ route.

**4. Ranh giới module chỉ tồn tại nếu có công cụ chặn.**
5 backend dev code song song trong 2 tuần. Nếu không có `import-linter` trong CI (`05 §4.6`), sau 2 tuần ranh giới module sẽ chỉ còn tồn tại trong tài liệu này.

**5. Có ba việc làm được NGAY mà không cần chờ code — và chúng quyết định chất lượng demo.**
- Viết **15–20 bài KB thật** (không phải lorem ipsum) — nếu không, chatbot RAG không có gì để trả lời
- Dựng **tập đánh giá AI**: 50 ticket có nhãn + 30 câu hỏi, trong đó 5 câu cố tình ngoài phạm vi
- Chuẩn bị **60 ticket mẫu** — nếu không, dashboard trống trơn khi demo

---

## Việc cần làm tiếp theo

| # | Việc | Ai | Khi nào |
|---|---|---|---|
| 1 | **Trả lời 6 câu hỏi mở** ở `01 §11` với Trainer (đặc biệt Q1 về phân quyền xem ticket và Q4 về SLA theo giờ hành chính) | Bùi Mậu Văn | Buổi họp tuần 1 |
| 2 | Chốt lại phân công PIC theo module ở `01 §10` — **mỗi module đúng một chủ sở hữu** | Cả nhóm | Sprint Planning |
| 3 | Đối chiếu năng lực: 177 SP vs ~160 SP khả dụng (`02 §0`) — quyết định cắt story nào trước | Cả nhóm | Sprint Planning |
| 4 | Dựng repo, Docker Compose, CI, **staging** — nằm trên đường găng | Cao Mạnh Hà | Sprint 0 |
| 5 | Viết bài KB + tập đánh giá + dữ liệu mẫu | Bùi Mậu Văn | Sprint 0, song song |
| 6 | Chốt hợp đồng API ở `06` và dựng **mock API (MSW)** cho frontend | Chu Quang Vũ + FE | 2 ngày đầu Sprint 1 |
| 7 | Cập nhật trạng thái tài liệu từ Draft → Approved sau khi PO duyệt | Bùi Mậu Văn | Sau họp tuần 1 |

---

## Quy ước bảo trì tài liệu

- Tài liệu được cập nhật **cuối mỗi sprint** (yêu cầu Guideline §10: "Mỗi Sprint cần cập nhật tài liệu").
- Thay đổi thiết kế lớn ⇒ **viết ADR mới**, không sửa ADR cũ (ADR là bất biến sau khi Accepted; muốn đổi thì tạo ADR mới `Supersedes ADR-XXXX`).
- Ma trận truy vết ở `01 §10` cập nhật khi hoàn thành mỗi feature.
- Sơ đồ dùng **Mermaid** nhúng trong Markdown — hiển thị trực tiếp trên GitHub, không cần công cụ vẽ ngoài, và diff được trong PR.
