# Kế hoạch Xây dựng Base — Smart IT Helpdesk

| | |
|---|---|
| Phiên bản | 1.0 |
| Ngày | 2026-07-30 |
| Đầu vào | `docs/design/` (11 tài liệu + 11 ADR) |
| Phạm vi | **Chỉ xây base** — nền tảng để 9 người fan-out code 8 feature |
| Thời lượng | Sprint 0 (2–3 ngày) + 4 ngày đầu Sprint 1 ≈ **6–7 ngày làm việc** |

---

## 1. "Base xong" nghĩa là gì

Định nghĩa hoàn thành, đo được — không phải cảm tính:

> **Một thành viên bất kỳ nhận module của mình, mở `CONTRIBUTING.md`, copy khuôn mẫu từ module `tickets`, và code được feature của mình mà không cần hỏi ai về cấu trúc, không cần chờ ai merge trước.**

Cụ thể, base hoàn thành khi cả 5 điều sau đúng:

| # | Điều kiện | Cách kiểm chứng |
|---|---|---|
| 1 | `git clone` → `cp .env.example .env` → `docker compose up` → hệ thống chạy | Người chưa từng đụng repo làm được trong < 10 phút |
| 2 | Có **một lát cắt dọc hoàn chỉnh** DB → Repository → Service → API → Frontend đang chạy thật | Đăng nhập từ browser, tạo ticket, xem danh sách |
| 3 | CI chạy đủ 9 cổng chất lượng và **đang xanh** | Mở PR thử, thấy tất cả check pass |
| 4 | Staging đang chạy — điều kiện bắt buộc của DoD | URL staging truy cập được |
| 5 | Hạ tầng AI sẵn sàng, **có `FakeLlmClient`** để cả nhóm test không cần API key | `pytest` chạy sạch không có biến `LLM_API_KEY` |

**Không thuộc phạm vi base:** đầy đủ 8 feature, dashboard, chatbot UI, thông báo, đánh giá. Đó là việc của Sprint 1 sau khi base xong.

---

## 2. Quyết định kiến trúc chi phối kế hoạch này

| Quyết định | Nguồn | Hệ quả với kế hoạch |
|---|---|---|
| **Cắt dọc, không cắt ngang** | Skill planning | Không có task "làm hết database", "làm hết API". Mỗi task đi trọn một đường |
| **Lát cắt đầu tiên là Auth** | Rủi ro cao nhất | Auth chạm mọi tầng: migration, model, repo, service, router, dependency, frontend interceptor. Nó xong = khuôn mẫu được chứng minh |
| **Lớp thuần làm sớm** | `docs/design/03` §2 | `TicketStateMachine`, `SlaCalculator`, `TicketAccessPolicy` là chỗ dễ sai nhất, test được không cần DB ⇒ làm ngay, thất bại sớm |
| **`FakeLlmClient` trước `OpenAiLlmClient`** | ADR-0009, `07` §4 | Gỡ chặn cho cả nhóm; CI không cần API key, không tốn tiền |
| **Mock API (MSW) cho frontend** | `09` §9 | 2 FE dev không ngồi chờ 5 BE dev trong tuần đầu |
| **Staging từ Sprint 0** | DoD của nhóm | "Đã deploy staging" là điều kiện Done ⇒ staging nằm trên **đường găng** |
| **`import-linter` từ ngày đầu** | ADR-0001, `05` §4.6 | Thêm sau khi đã có 5 người code = phải sửa hàng loạt import |

---

## 3. Đồ thị phụ thuộc

```
T01 repo ──┬── T02 docker-compose ──┬── T03 backend skeleton ──┬── T04 db+alembic ──┐
           │                        │                          │                    │
           └── T06 frontend skeleton└── T05 CI ─────────────────┘                    │
                     │                                                               │
                     │                              ┌────────────────────────────────┘
                     │                              ▼
                     │                    T07 migration users ──► T08 module auth ──► T09 authz deps
                     │                                                 │                    │
                     │                                                 ▼                    ▼
                     └──────────────────────────────► T11 FE auth ◄── T10 test harness ─────┘
                                                            │
                    ┌───────────────────────────────────────┘
                    ▼
        T13 lớp thuần (song song, không phụ thuộc)
                    │
        T12 migration tickets ──► T14 module tickets ──► T15 router tickets ──► T17 OpenAPI→TS
                    │                                            │
                    │                                            ▼
                    └────────────────────────────────► T16 FE tickets
                    │
                    ▼
        T18 migration KB ──► T19 ai interfaces ──► T21 celery+indexing ──► T22 classifier
                                    │                    │
                                    └── T20 chunker ─────┘
                                                              T23 dữ liệu (song song từ ngày 1)
                                                                     │
                                    T24 staging ◄────────────────────┘
                                         │
                                         ▼
                                    T25 bàn giao
```

**Đường găng (critical path):** T01 → T02 → T03 → T04 → T07 → T08 → T09 → T12 → T14 → T15 → T24
Bất kỳ chậm trễ nào trên chuỗi này làm chậm cả nhóm. T24 (staging) bị đánh giá thấp nhất nhưng chặn DoD của **mọi** task về sau.

---

## 4. Ba luồng chạy song song

| Luồng | Người | Bắt đầu | Không phụ thuộc ai |
|---|---|---|---|
| **A — Hạ tầng & Backend** | Cao Mạnh Hà, Lại Duy Đông, Nguyễn Đăng Trường, Chu Quang Vũ | Ngày 1 | — |
| **B — Frontend** | Nguyễn Văn Quang, Nguyễn Văn Dũng | Ngày 1 (T06, rồi MSW) | Chỉ phụ thuộc **hợp đồng API** ở `docs/design/06`, không phụ thuộc code backend |
| **C — Dữ liệu & AI** | Bùi Mậu Văn | Ngày 1 (T23 — viết bài KB, tập đánh giá) | **Hoàn toàn không phụ thuộc code** |

QA (Trần Quang Ngọc) tham gia T10 (bộ khung test) và soạn Test Plan song song.

> Luồng C bắt đầu ngay ngày 1 là quyết định quan trọng nhất về mặt lịch: viết 20 bài KB thật mất 2–3 ngày và **không cần một dòng code nào**. Nếu để đến khi chatbot code xong mới viết, chatbot sẽ không có gì để trả lời lúc demo.

---

## 5. Danh sách công việc

### PHASE 0 — Hạ tầng & Khung (Sprint 0)

---

#### T01 — Khởi tạo repository và cấu trúc thư mục
**Mô tả:** Tạo Git repo, cấu trúc thư mục gốc theo `docs/design/05` §4.4, `.gitignore`, `.env.example`, quy ước nhánh và branch protection.

**Tiêu chí chấp nhận**
- [ ] Repo trên GitHub với 2 nhánh `main`, `develop`; `main` bật branch protection (cấm push trực tiếp, yêu cầu ≥1 review, yêu cầu CI pass)
- [ ] Cấu trúc thư mục `backend/`, `frontend/`, `docs/`, `tasks/` đúng như tài liệu thiết kế
- [ ] `.env.example` liệt kê **đủ** biến ở `docs/design/08` §5, giá trị giả
- [ ] `.gitignore` chặn `.env`, `__pycache__`, `node_modules`, `.venv`, `*.db`

**Xác minh:** `git clone` từ máy khác, không thấy file bí mật · thử push thẳng vào `main` bị từ chối

**Phụ thuộc:** Không · **PIC:** Cao Mạnh Hà · **Kích thước:** XS

---

#### T02 — Docker Compose môi trường phát triển
**Mô tả:** Dựng `docker-compose.yml` với PostgreSQL 16 + pgvector, Redis 7, MinIO. Có healthcheck và volume.

**Tiêu chí chấp nhận**
- [ ] `docker compose up` khởi động 3 service, tất cả healthy
- [ ] PostgreSQL dùng image `pgvector/pgvector:pg16`, `CREATE EXTENSION vector` chạy được
- [ ] MinIO có bucket `helpdesk-attachments` được tạo tự động khi khởi động
- [ ] Dữ liệu tồn tại qua `docker compose restart` (volume hoạt động)

**Xác minh:** `docker compose ps` — 3/3 healthy · `psql -c "CREATE EXTENSION IF NOT EXISTS vector;"` thành công

**Phụ thuộc:** T01 · **PIC:** Cao Mạnh Hà · **Kích thước:** S

**File:** `docker-compose.yml`, `.env.example`, `infra/minio-init.sh`

---

#### T03 — Khung backend: `core` + `main.py` + health check
**Mô tả:** Dựng `app/core/` đầy đủ (config, logging JSON có `request_id`, exceptions, error handlers, middleware, pagination, rate_limit) và `main.py` với health endpoint. **Chưa có nghiệp vụ nào.**

**Tiêu chí chấp nhận**
- [ ] `app/core/config.py` dùng Pydantic Settings; **ứng dụng từ chối khởi động** nếu thiếu biến bắt buộc hoặc `JWT_SECRET` còn là giá trị mặc định khi `ENVIRONMENT=production`
- [ ] Mọi lỗi trả về đúng hình dạng `{error: {code, message, details?, requestId}}` theo `docs/design/06` §3
- [ ] Middleware sinh `request_id`, gắn vào log và vào mọi response lỗi
- [ ] Log dạng JSON một dòng, **che** các trường `password`, `token`, `authorization`, `api_key`
- [ ] `GET /health/live` trả 200 không chạm DB; `GET /health/ready` kiểm tra DB + Redis
- [ ] `Page[T]` generic + `PageParams` dùng chung cho mọi endpoint danh sách

**Xác minh:** `curl /health/live` → 200 · dừng Postgres, `curl /health/ready` → 503 còn `/health/live` vẫn 200 · gọi route không tồn tại → đúng định dạng lỗi có `requestId`

**Phụ thuộc:** T01 · **PIC:** Lại Duy Đông · **Kích thước:** M

**File:** `backend/pyproject.toml`, `app/main.py`, `app/core/*.py`, `app/api/health.py`

---

#### T04 — Tầng dữ liệu + Alembic + migration 001–002
**Mô tả:** `app/db/` (base có quy ước đặt tên constraint, session, mixins, kiểu tuỳ chỉnh), khởi tạo Alembic, migration 001 (extensions) và 002 (enums).

**Tiêu chí chấp nhận**
- [ ] `DeclarativeBase` có `naming_convention` — mọi constraint sinh ra có tên xác định (bắt buộc để Alembic autogenerate ổn định)
- [ ] `UUIDPrimaryKeyMixin` sinh **UUIDv7** ở tầng ứng dụng (ADR-0011), `TimestampMixin` có `created_at`/`updated_at`
- [ ] Migration 001 bật `uuid-ossp`, `citext`, `pg_trgm`, `unaccent`, `vector`
- [ ] Migration 002 tạo đủ 8 ENUM ở `docs/design/04` §3
- [ ] `alembic upgrade head` → `downgrade base` → `upgrade head` chạy sạch

**Xác minh:** Lệnh 3 bước ở trên chạy không lỗi · `\dT` trong psql thấy đủ 8 enum

**Phụ thuộc:** T02, T03 · **PIC:** Nguyễn Đăng Trường · **Kích thước:** S

---

#### T05 — Pipeline CI với 9 cổng chất lượng
**Mô tả:** GitHub Actions chạy đủ các cổng ở `docs/design/10` §9.

**Tiêu chí chấp nhận**
- [ ] Các bước: `ruff` → `black --check` → `mypy` → `lint-imports` → unit test → integration/API test (service container PostgreSQL + Redis) → migration up/down/up → coverage ≥ 70% → `gitleaks`
- [ ] `import-linter` cấu hình theo ma trận phụ thuộc ở `docs/design/05` §4.2 và **thực sự chặn** khi vi phạm
- [ ] CI chạy được **không cần** `LLM_API_KEY`
- [ ] Thời gian chạy toàn bộ < 5 phút

**Xác minh:** Cố tình tạo PR có import vi phạm (ví dụ `notifications` import `tickets.models`) → CI phải **fail** · commit thử một chuỗi giống API key → `gitleaks` chặn

**Phụ thuộc:** T03, T04 · **PIC:** Cao Mạnh Hà · **Kích thước:** M

> Bước `import-linter` là thứ dễ bị coi là thừa nhất nhưng bảo vệ đúng tài sản dễ mất nhất: ranh giới module khi 5 người code song song.

---

#### T06 — Khung frontend + mock API
**Mô tả:** Vite + React + TS strict + Tailwind + shadcn/ui, router, `AppLayout`, `api/client.ts`, MSW mock theo hợp đồng ở `docs/design/06`, bộ component chung.

**Tiêu chí chấp nhận**
- [ ] `npm run dev` hiện layout có Sidebar + TopBar; `npm run build` sạch với `tsc --noEmit`
- [ ] `api/client.ts` là wrapper `fetch`: gắn `Authorization`, timeout 10 s, parse lỗi theo định dạng chuẩn, chỉ retry `GET`
- [ ] MSW mock **đủ** các endpoint auth và tickets theo hợp đồng ⇒ frontend chạy được **hoàn toàn không cần backend**
- [ ] Bộ component chung: `StatusBadge`, `PriorityBadge`, `SlaBadge`, `EmptyState`, `ErrorState`, `LoadingSkeleton`, `Pagination`, `ConfirmDialog`
- [ ] Bật/tắt MSW bằng biến môi trường `VITE_USE_MOCK`

**Xác minh:** Tắt hoàn toàn backend, `npm run dev` vẫn duyệt được mọi màn hình khung

**Phụ thuộc:** T01 · **PIC:** Nguyễn Văn Quang + Nguyễn Văn Dũng · **Kích thước:** M

---

### ⛳ CHECKPOINT A — Khung sẵn sàng

- [ ] `docker compose up` từ máy sạch: 3 service healthy trong < 3 phút
- [ ] `curl localhost:8000/health/ready` → 200
- [ ] `alembic upgrade head` chạy được
- [ ] `npm run dev` hiện layout, MSW hoạt động
- [ ] CI xanh trên một PR thử
- [ ] **Rà soát cùng nhóm:** mọi người clone được và chạy được trên máy mình

**Nếu checkpoint này trượt, không được đi tiếp.** Cả nhóm bị chặn ở đây.

---

### PHASE 1 — Lát cắt dọc #1: Xác thực

> Mục tiêu của phase này **không phải** là "làm xong tính năng đăng nhập". Nó là **chứng minh khuôn mẫu**: DB → Model → Repository → Service → Router → Dependency → Test → Frontend, đi trọn một vòng. Mọi module sau đều copy khuôn mẫu này.

---

#### T07 — Migration 003: `departments`, `users`, `refresh_tokens`
**Tiêu chí chấp nhận**
- [ ] 3 bảng đúng schema `docs/design/04` §4.1, đủ CHECK constraint và index
- [ ] `users.email` kiểu `CITEXT` + UNIQUE — thử insert `A@x.com` và `a@x.com` phải bị chặn
- [ ] Seed 6 phòng ban (idempotent — chạy 2 lần không sinh trùng)
- [ ] `refresh_tokens.token_hash` UNIQUE, có `replaced_by_id` tự tham chiếu

**Xác minh:** Test integration: insert email trùng khác hoa/thường → `IntegrityError` · chạy seed 2 lần → vẫn 6 dòng

**Phụ thuộc:** T04 · **PIC:** Nguyễn Đăng Trường · **Kích thước:** S

---

#### T08 — Module `auth` + `users` (backend)
**Mô tả:** Module `users` (models `User`/`Department`, repository, service tối thiểu) và module `auth` đầy đủ: đăng ký, đăng nhập, refresh có xoay vòng, đăng xuất, `GET /users/me`.

**Tiêu chí chấp nhận**
- [ ] Đủ file theo khuôn mẫu `docs/design/05` §4.5: `router / schemas / service / repository / models / exceptions / constants`
- [ ] Mật khẩu hash bcrypt cost 12; **không bao giờ** xuất hiện trong response hay log
- [ ] Login sai email và sai mật khẩu trả về **cùng một** thông điệp `INVALID_CREDENTIALS`; thời gian xử lý tương đương (luôn hash giả)
- [ ] Refresh **xoay vòng token**: token cũ bị thu hồi, sinh token mới
- [ ] **Dùng lại token đã bị thay thế ⇒ thu hồi toàn bộ chuỗi token của user** + trả 401
- [ ] Refresh token lưu **SHA-256 hash**, không lưu bản rõ; đặt trong cookie `HttpOnly; Secure; SameSite=Strict`
- [ ] Rate limit login: 5 lần/15 phút theo email+IP, trả 429 kèm `Retry-After`
- [ ] Service **không** ném `HTTPException` — chỉ ném `DomainError`

**Xác minh:** Test API: đăng ký → đăng nhập → refresh → dùng lại refresh cũ → nhận 401 **và** token mới cũng bị vô hiệu · sai mật khẩu 6 lần → 429

**Phụ thuộc:** T07 · **PIC:** Lại Duy Đông · **Kích thước:** M

---

#### T09 — Dependency phân quyền + test quét route
**Mô tả:** `get_current_user`, `require_role(...)` trong `core/dependencies.py`, và bài test tự động quét toàn bộ route.

**Tiêu chí chấp nhận**
- [ ] `get_current_user` giải mã JWT, kiểm tra `exp`, tra user, chặn user `is_active = false`
- [ ] `require_role(UserRole.ADMIN)` trả 403 với vai trò sai
- [ ] **Test quét toàn bộ `app.routes`**, khẳng định mọi route `/api/` ngoài danh sách công khai đều có dependency xác thực (`docs/design/08` §2.4)
- [ ] Khung `PERMISSION_MATRIX` được dựng sẵn (dù mới có vài dòng) để các module sau chỉ việc thêm dòng

**Xác minh:** Thêm một endpoint mới **cố tình quên** dependency → test phải fail

**Phụ thuộc:** T08 · **PIC:** Lại Duy Đông · **Kích thước:** S

---

#### T10 — Bộ khung kiểm thử
**Mô tả:** `conftest.py` với fixture dùng chung, cấu trúc `tests/unit|integration|api`, factory.

**Tiêu chí chấp nhận**
- [ ] Fixture: `db_session` (transaction + rollback sau mỗi test), `client`, `employee_user`, `agent_user`, `admin_user`, `auth_headers(role)`
- [ ] `factory-boy`: `UserFactory`, `DepartmentFactory`
- [ ] Unit test **không** chạm DB, chạy < 5 giây
- [ ] Mỗi test tự dựng dữ liệu, **không phụ thuộc thứ tự chạy** — chứng minh bằng `pytest -p no:randomly` và `pytest --randomly-seed=…` đều xanh
- [ ] Coverage report sinh ra được

**Xác minh:** `pytest tests/unit` < 5 s · `pytest -n auto` (chạy song song) vẫn xanh

**Phụ thuộc:** T08 · **PIC:** Trần Quang Ngọc + Lại Duy Đông · **Kích thước:** M

---

#### T11 — Frontend: luồng xác thực thật
**Mô tả:** `AuthProvider`, `LoginPage`, `ProtectedRoute`, interceptor tự refresh token — nối vào **backend thật**, tắt MSW.

**Tiêu chí chấp nhận**
- [ ] Đăng nhập thành công → lưu access token **trong bộ nhớ** (không localStorage), điều hướng theo vai trò
- [ ] Nhận `401` → tự gọi `/auth/refresh` **một lần** rồi thử lại request gốc; nhiều request 401 đồng thời chỉ gây **một** lần refresh
- [ ] Refresh thất bại → xoá state, về `/login`
- [ ] `ProtectedRoute` chặn theo vai trò
- [ ] Tải lại trang (F5) → tự khôi phục phiên qua cookie refresh
- [ ] Hiển thị lỗi bằng `error.message` tiếng Việt; sai mật khẩu hiện thông điệp đúng

**Xác minh:** Thủ công trên browser: đăng nhập → F5 → vẫn đăng nhập · đợi access token hết hạn (hạ TTL xuống 10 s để test) → thao tác tiếp vẫn chạy nhờ auto-refresh

**Phụ thuộc:** T06, T08 · **PIC:** Nguyễn Văn Quang · **Kích thước:** M

---

### ⛳ CHECKPOINT B — Khuôn mẫu được chứng minh

- [ ] Từ browser: đăng nhập bằng tài khoản seed → vào được trang có bảo vệ → F5 vẫn giữ phiên
- [ ] Toàn bộ test xanh, coverage ≥ 70% trên module `auth`
- [ ] Test quét route hoạt động (thử bỏ dependency → fail)
- [ ] **Rà soát cùng nhóm — đây là buổi quan trọng nhất:** cả 5 backend dev cùng đọc module `auth`, thống nhất "đây là khuôn mẫu, mọi module sau viết y hệt". Chốt các câu hỏi về cấu trúc **tại đây**, không để mỗi người tự nghĩ một kiểu

---

### PHASE 2 — Lát cắt dọc #2: Ticket tối thiểu

---

#### T13 — Ba lớp thuần: StateMachine, SlaCalculator, AccessPolicy
**Mô tả:** Cài đặt 3 lớp không I/O ở `docs/design/03` §2 kèm unit test đầy đủ. **Làm trước T12/T14 vì đây là chỗ rủi ro nhất và không phụ thuộc gì.**

**Tiêu chí chấp nhận**
- [ ] `TicketStateMachine.ALLOWED` khớp **chính xác** bảng 7×7 ở `docs/design/03` §5, có phân biệt vai trò
- [ ] Unit test phủ **toàn bộ 49 ô** — cả ô cho phép lẫn ô bị cấm
- [ ] `SlaCalculator` xử lý đúng giờ hành chính + ngày lễ; test có các ca: tạo 17:00 thứ Sáu, tạo đúng 17:30, tạo trong ngày lễ, SLA vắt nhiều ngày
- [ ] `TicketAccessPolicy.visible_filter()` trả về **điều kiện SQLAlchemy**, không phải hàm lọc Python
- [ ] Cả 3 lớp **không nhận `Session`**, không import gì từ `db/`
- [ ] Coverage 3 lớp này ≥ 90%

**Xác minh:** `pytest tests/unit/test_state_machine.py tests/unit/test_sla_calculator.py tests/unit/test_access_policy.py` xanh, chạy < 2 giây, không cần database

**Phụ thuộc:** T03 · **PIC:** Chu Quang Vũ · **Kích thước:** M

> Ca test bắt buộc phải có: *ticket URGENT (SLA 4 giờ làm việc) tạo lúc 17:00 thứ Sáu phải có hạn 11:30 sáng thứ Hai.* Nếu code trả về 21:00 thứ Sáu, toàn bộ tính năng cảnh báo SLA sẽ sai và không ai phát hiện cho đến lúc demo.

---

#### T12 — Migration 004–005: danh mục, SLA policy, bảng `tickets`
**Tiêu chí chấp nhận**
- [ ] `ticket_categories`, `sla_policies`, `holidays`, `agent_skills`, `tickets` đúng schema `docs/design/04` §4.2–4.3
- [ ] Đủ CHECK constraint của `tickets` (`ck_ticket_assignee`, `ck_ticket_resolved`, `ck_ticket_closed`, …)
- [ ] Sequence `ticket_code_seq` + trigger `search_vector` hoạt động
- [ ] Seed: 8 category, 4 SLA policy, ngày lễ Việt Nam năm hiện tại
- [ ] Đủ 7 index của `tickets` ở `docs/design/04` §5.1, gồm các partial index

**Xác minh:** Test integration cố tình vi phạm từng CHECK constraint → đều bị chặn · insert ticket → `search_vector` tự có giá trị · `EXPLAIN` truy vấn hàng chờ Agent → dùng `ix_tickets_assignee_open`

**Phụ thuộc:** T04 · **PIC:** Nguyễn Đăng Trường · **Kích thước:** M

---

#### T14 — Module `tickets`: models, repository, service (create/get/list)
**Mô tả:** Module nghiệp vụ theo đúng khuôn mẫu đã chốt ở Checkpoint B. Chỉ 3 thao tác: tạo, lấy chi tiết, liệt kê. **Chưa** có assign/status/comment.

**Tiêu chí chấp nhận**
- [ ] `TicketService.create()`: sinh `code`, tính SLA bằng `SlaCalculator`, ghi `ticket_events` loại `CREATED` **trong cùng transaction**
- [ ] `requester_id` **luôn** lấy từ user đang đăng nhập, không bao giờ từ payload (BR-01)
- [ ] `TicketRepository.list()` **bắt buộc** nhận `access_filter` — không có đường nào truy vấn mà bỏ qua nó
- [ ] `ticket_events` không có phương thức update/delete ở repository (BR-17)
- [ ] Không có N+1 query: dùng `selectinload` cho `requester`, `assignee`, `category`

**Xác minh:** Test integration: tạo ticket → có đúng 1 dòng `ticket_events` · giả lập lỗi giữa chừng → **cả** ticket lẫn event đều rollback · bật `echo=True`, đếm số câu SQL khi list 20 ticket ≤ 4

**Phụ thuộc:** T12, T13, Checkpoint B · **PIC:** Chu Quang Vũ · **Kích thước:** M

---

#### T15 — Router `tickets`: 3 endpoint + phân quyền bản ghi
**Tiêu chí chấp nhận**
- [ ] `POST /tickets` (hỗ trợ `Idempotency-Key`), `GET /tickets` (lọc + phân trang), `GET /tickets/{id}`
- [ ] Employee gọi `GET /tickets` chỉ thấy ticket của mình; `totalItems` cũng chỉ đếm phần được thấy
- [ ] Employee gọi `GET /tickets/{id}` của người khác → **404**, không phải 403
- [ ] `pageSize=1000` bị chặn ở 100; `sortBy` chỉ nhận danh sách trắng
- [ ] Gửi `POST /tickets` hai lần cùng `Idempotency-Key` → chỉ tạo **một** ticket
- [ ] `p95 < 500 ms` với 1.000 ticket trong DB
- [ ] Thêm dòng tương ứng vào `PERMISSION_MATRIX`

**Xác minh:** Test API cho từng gạch đầu dòng trên · đo thời gian phản hồi với dữ liệu seed

**Phụ thuộc:** T14, T09 · **PIC:** Chu Quang Vũ · **Kích thước:** M

---

#### T16 — Frontend: danh sách + tạo + chi tiết ticket (nối API thật)
**Tiêu chí chấp nhận**
- [ ] 3 màn hình: `MyTicketsPage`, `CreateTicketPage`, `TicketDetailPage` (bản tối thiểu)
- [ ] Dùng TanStack Query với `queryKey` phân cấp `['tickets']` / `['tickets', id]` / `['tickets', filters]`
- [ ] Mỗi màn hình xử lý **đủ 4 trạng thái**: loading (skeleton), rỗng (EmptyState có nút hành động), lỗi (có nút thử lại + `requestId`), có dữ liệu
- [ ] Nút "Gửi yêu cầu" bị vô hiệu hoá trong lúc chờ — bấm 2 lần không tạo 2 ticket
- [ ] Form dùng React Hook Form + Zod, ràng buộc **khớp với backend** (title 5–200, description 10–5000)
- [ ] Tắt `VITE_USE_MOCK` → chạy với backend thật

**Xác minh:** Thủ công: tạo ticket từ browser → thấy trong danh sách → mở chi tiết · ngắt mạng → thấy ErrorState có nút thử lại · tài khoản chưa có ticket → thấy EmptyState

**Phụ thuộc:** T11, T15 · **PIC:** Nguyễn Văn Dũng · **Kích thước:** M

---

#### T17 — Xuất OpenAPI → sinh TypeScript types
**Tiêu chí chấp nhận**
- [ ] Script `make openapi` xuất `docs/api/openapi.json` và **commit vào repo**
- [ ] Frontend sinh `src/api/types.ts` bằng `openapi-typescript`
- [ ] CI kiểm tra: nếu code đổi mà `openapi.json` chưa cập nhật → **fail** (chống trôi hợp đồng)
- [ ] Mọi endpoint có `response_model`, `summary`, và khai báo `responses` cho các mã lỗi chính

**Xác minh:** Đổi một schema backend mà không chạy lại export → CI fail · diff `openapi.json` trong PR cho thấy rõ thay đổi có phá vỡ tương thích hay không

**Phụ thuộc:** T15 · **PIC:** Chu Quang Vũ · **Kích thước:** S

---

### ⛳ CHECKPOINT C — Lát cắt dọc hoàn chỉnh

- [ ] End-to-end trên browser: đăng nhập → tạo ticket → xem danh sách → mở chi tiết
- [ ] Employee A **không** xem được ticket của Employee B (nhận 404)
- [ ] Toàn bộ test xanh, coverage ≥ 70%
- [ ] `openapi.json` đã commit, TS types sinh từ đó
- [ ] **Rà soát cùng nhóm:** chốt khuôn mẫu module nghiệp vụ. Từ đây 5 backend dev fan-out được

---

### PHASE 3 — Base AI

---

#### T23 — Bộ dữ liệu: KB, tập đánh giá, dữ liệu demo ⚡ *bắt đầu từ NGÀY 1, song song mọi thứ*
**Mô tả:** Việc **không cần một dòng code nào** nhưng quyết định chất lượng demo.

**Tiêu chí chấp nhận**
- [ ] **15–20 bài viết KB thật** về sự cố IT phổ biến (đổi mật khẩu, WiFi, VPN, máy in, cấp quyền, Outlook, phần mềm…), mỗi bài 300–800 từ, có tiêu đề Markdown phân cấp rõ. **Không phải lorem ipsum**
- [ ] `tests/fixtures/classification_eval.jsonl`: **50 ticket** có nhãn category+priority đúng — 35 rõ ràng, 10 mơ hồ, 5 lắt léo
- [ ] `tests/fixtures/rag_eval.jsonl`: **30 câu hỏi**, trong đó **5 câu cố tình KHÔNG có trong tài liệu**
- [ ] `scripts/seed_demo.py`: 60 ticket rải trong 60 ngày, đủ trạng thái/priority/category, 9 user đủ 3 vai trò

**Xác minh:** Người ngoài nhóm đọc 3 bài KB bất kỳ và làm theo được · 5 câu "phải từ chối" thực sự không có đáp án trong tài liệu

**Phụ thuộc:** Không · **PIC:** Bùi Mậu Văn · **Kích thước:** M

> Đây là task dễ bị hoãn nhất và tốn thời gian thật nhất. Bắt đầu ngày 1.

---

#### T18 — Migration 007: kho tri thức + pgvector
**Tiêu chí chấp nhận**
- [ ] `kb_categories`, `kb_articles`, `article_chunks` đúng schema `docs/design/04` §4.6
- [ ] `article_chunks.embedding` kiểu `VECTOR(1536)`, có index HNSW `(m=16, ef_construction=64)` với `vector_cosine_ops`
- [ ] `kb_articles.search_vector` + trigger full-text
- [ ] Seed `kb_categories`

**Xác minh:** Insert vector giả, chạy truy vấn `ORDER BY embedding <=> ...` → `EXPLAIN` dùng index HNSW

**Phụ thuộc:** T04 · **PIC:** Nguyễn Đăng Trường · **Kích thước:** S

---

#### T19 — `app/ai`: interfaces + FakeLlmClient + lớp chống chịu + cost guard
**Mô tả:** Toàn bộ hạ tầng AI **trừ** logic nghiệp vụ. Đây là task gỡ chặn cho cả nhóm.

**Tiêu chí chấp nhận**
- [ ] `LlmClient` và `EmbeddingClient` là `Protocol`; có `complete()` (hỗ trợ JSON schema) và `stream()`
- [ ] `FakeLlmClient` trả kết quả đặt trước theo từ khoá trong prompt; `FakeEmbeddingClient` sinh vector **tất định** từ hash văn bản
- [ ] `OpenAiLlmClient` cài đặt thật (hoặc provider đã chốt)
- [ ] `resilience.py`: timeout (embed 5 s / classify 20 s / chat 30 s), retry 3 lần backoff mũ **có jitter**, circuit breaker mở sau 5 lỗi liên tiếp trong 60 s
- [ ] `cost_guard.py`: đếm token, cảnh báo ở 80% ngân sách, **chặn cứng ở 100%**
- [ ] Chọn cài đặt qua biến môi trường; **mặc định trong test là Fake**

**Xác minh:** `pytest` chạy sạch với `unset LLM_API_KEY` · unit test circuit breaker: 5 lỗi → lần gọi thứ 6 fail ngay không gọi mạng · test retry có jitter (2 lần chạy cho khoảng chờ khác nhau)

**Phụ thuộc:** T03 · **PIC:** Bùi Mậu Văn · **Kích thước:** M

---

#### T20 — `TextChunker` (lớp thuần)
**Tiêu chí chấp nhận**
- [ ] Chia theo tiêu đề Markdown trước, rồi mới theo độ dài; mục tiêu ~500 token, tối đa 800, chồng lấn 80
- [ ] Mỗi chunk được chèn tiền tố `[Bài viết: {title}] [Mục: {heading}]`
- [ ] Chunk < 100 token được gộp với chunk kế
- [ ] Không I/O, không nhận `Session`
- [ ] Test với văn bản tiếng Việt có dấu, bài không có tiêu đề, tiêu đề lồng nhau, bài rất dài

**Xác minh:** Chạy trên 20 bài KB thật (T23) → kiểm tra bằng mắt 5 chunk ngẫu nhiên: có đọc hiểu được độc lập không?

**Phụ thuộc:** T03 · **PIC:** Bùi Mậu Văn · **Kích thước:** S

---

#### T21 — Celery + worker + beat + IndexingService + `reindex_kb.py`
**Tiêu chí chấp nhận**
- [ ] `celery_app.py`, service `worker` và `beat` trong docker-compose
- [ ] **Hàng đợi riêng cho AI** và cho thông báo (bulkhead — `docs/design/08` §9)
- [ ] `IndexingService.index_article()`: xoá **hết** chunk cũ → chia chunk → embedding theo lô 32 → insert. **Idempotent**
- [ ] Task Celery chỉ là vỏ mỏng gọi service (`docs/design/05` §4.5)
- [ ] `request_id` được truyền từ API sang Celery task và xuất hiện trong log worker
- [ ] `scripts/reindex_kb.py --all` dựng lại toàn bộ chỉ mục — **phải chạy thử thành công ít nhất một lần**
- [ ] Job đối soát (ADR-0007): tìm bài `PUBLISHED` có `indexed_at IS NULL` hoặc `< updated_at` → đẩy lại

**Xác minh:** Index 20 bài KB thật → đếm chunk trong DB · chạy index lại 2 lần → số chunk không đổi, không có chunk mồ côi · `reindex_kb.py --all` từ DB trống chunk → dựng lại đủ

**Phụ thuộc:** T18, T19, T20, T23 · **PIC:** Bùi Mậu Văn + Cao Mạnh Hà · **Kích thước:** M

---

#### T22 — Phân loại ticket bất đồng bộ (F3 bản nền)
**Tiêu chí chấp nhận**
- [ ] Migration `ai_classifications`
- [ ] `RuleBasedClassifier` (đối chiếu từ khoá, `confidence = 0.4`) — dùng làm fallback **và** dùng trong test
- [ ] `LlmTicketClassifier` dùng JSON schema; **kiểm tra `category_slug` trả về có thật trong DB**, không tin đầu ra LLM
- [ ] Task `classify_ticket` chạy sau khi tạo ticket, xong trong ≤ 30 s
- [ ] `confidence < 0.6` → `ai_status = LOW_CONFIDENCE`, **không** áp dụng
- [ ] Câu UPDATE có điều kiện `WHERE ai_status='PENDING' AND category_id IS NULL` (BR-13 — con người luôn thắng)
- [ ] LLM hỏng → retry → fallback rule-based → `ai_status = FAILED`. **Ticket vẫn tạo và dùng được bình thường**
- [ ] Ghi `ticket_events` loại `AI_CLASSIFIED` với `actor_type = AI`
- [ ] `scripts/eval_classification.py` chạy trên 50 ca của T23, in độ chính xác

**Xác minh:** **Tắt hoàn toàn LLM (đặt API key sai)** → tạo ticket vẫn thành công, `ai_status=FAILED` · test: ticket đã có category do người chọn → AI không ghi đè · chạy eval script → in ra số

**Phụ thuộc:** T14, T19, T21, T23 · **PIC:** Bùi Mậu Văn · **Kích thước:** M

---

### ⛳ CHECKPOINT D — Base AI hoạt động

- [ ] Tạo ticket → trong ≤ 30 s có category + priority + độ tin cậy
- [ ] **Tắt LLM → tạo ticket vẫn được** (kiểm thử suy giảm chức năng — bắt buộc)
- [ ] 20 bài KB đã được index, đếm được số chunk
- [ ] `reindex_kb.py --all` chạy thành công
- [ ] `eval_classification.py` in ra độ chính xác trên 50 ca
- [ ] Toàn bộ test xanh **không cần API key**

---

### PHASE 4 — Staging & Bàn giao

---

#### T24 — Deploy staging
**Tiêu chí chấp nhận**
- [ ] `docker-compose.prod.yml` + Nginx (TLS, gzip, `client_max_body_size 12m`, security headers)
- [ ] Staging có URL truy cập được, HTTPS hoạt động, HTTP tự chuyển hướng
- [ ] Migration + seed chạy tự động khi deploy
- [ ] CI tự động deploy khi merge vào `develop`
- [ ] CORS chỉ cho phép domain frontend staging
- [ ] Bí mật nằm trong GitHub Secrets, không trong repo
- [ ] Backup `pg_dump` hằng ngày **và đã khôi phục thử thành công một lần**

**Xác minh:** Merge một PR nhỏ vào `develop` → thấy staging tự cập nhật trong < 10 phút · khôi phục backup vào DB trống → dữ liệu đầy đủ, ghi lại thời gian thực tế

**Phụ thuộc:** Checkpoint C · **PIC:** Cao Mạnh Hà · **Kích thước:** M

---

#### T25 — Tài liệu bàn giao: README + CONTRIBUTING
**Mô tả:** Tài liệu để 8 người còn lại tự làm được mà không hỏi.

**Tiêu chí chấp nhận**
- [ ] `README.md` đủ 7 mục Guideline §11: giới thiệu, thành viên, công nghệ, cài đặt, cách chạy, cấu trúc project, demo
- [ ] `CONTRIBUTING.md` có **hướng dẫn từng bước thêm một module nghiệp vụ mới**, dùng `tickets` làm ví dụ mẫu
- [ ] Ghi rõ quy ước: đặt tên nhánh, định dạng commit, checklist PR, cách chạy test, cách thêm migration
- [ ] Liệt kê ma trận phụ thuộc module và cách chạy `lint-imports` ở máy cá nhân
- [ ] Link tới `docs/design/`

**Xác minh:** **Một thành viên chưa đụng vào base** đọc `CONTRIBUTING.md` và tự thêm được một module rỗng (`feedback`) chạy được — trong < 1 giờ, không hỏi ai

**Phụ thuộc:** T24 · **PIC:** Bùi Mậu Văn + Cao Mạnh Hà · **Kích thước:** S

---

### ⛳ CHECKPOINT E — Base hoàn thành, sẵn sàng fan-out

- [ ] 5 điều kiện ở §1 đều đúng
- [ ] Staging chạy, CI tự deploy
- [ ] Bài kiểm chứng T25 đạt (người mới tự thêm module được trong < 1 giờ)
- [ ] **Sprint Planning:** chia 8 feature cho 9 người, mỗi module **đúng một chủ sở hữu**

---

## 6. Lịch đề xuất

| Ngày | Luồng A (Hạ tầng/BE) | Luồng B (FE) | Luồng C (Dữ liệu/AI) |
|---|---|---|---|
| **S0-1** | T01, T02 | T06 (khởi tạo) | T23 (viết KB) |
| **S0-2** | T03, T04 | T06 (MSW + component) | T23 |
| **S0-3** | T05 · **⛳ A** | T06 · **⛳ A** | T23, T20 |
| **S1-1** | T07, T08 | T11 (dựng, dùng MSW) | T19 |
| **S1-2** | T08, T09, T10 | T11 (nối API thật) | T19, T18 |
| **S1-3** | **⛳ B** · T12, T13 | T16 (dựng) | T21 |
| **S1-4** | T14, T15 | T16 (nối API thật) | T21, T22 |
| **S1-5** | T17 · **⛳ C** | T16 · **⛳ C** | T22 · **⛳ D** |
| **S1-6** | T24 | (bắt đầu feature) | T25 |
| **S1-7** | **⛳ E** — Sprint Planning fan-out | | |

---

## 7. Rủi ro

| Rủi ro | Mức | Biện pháp |
|---|---|---|
| **Staging chậm** ⇒ không task nào đạt DoD | **Cao** | T24 nằm trên đường găng, giao cho DevOps chuyên trách. Nếu đến S1-4 chưa xong, **hạ tiêu chuẩn DoD tạm thời** và ghi vào Retrospective |
| Nhóm không theo khuôn mẫu, mỗi người một kiểu | **Cao** | Checkpoint B là buổi rà soát bắt buộc, cả 5 BE cùng đọc module `auth`. `import-linter` chặn ở CI |
| Kho KB không kịp ⇒ chatbot không có gì trả lời | **Cao** | T23 bắt đầu **ngày 1**, không phụ thuộc code. Kiểm tra tiến độ ở mỗi standup |
| Ước lượng lạc quan — 6–7 ngày cho base | Trung bình | Đây là base, không phải feature. Nếu Checkpoint C trượt quá 1 ngày, **cắt T22 khỏi base** và đẩy vào Sprint 1 |
| `SlaCalculator` giờ hành chính phức tạp hơn dự kiến | Trung bình | T13 làm sớm để thất bại sớm. Nếu PO trả lời Q4 = "24/7" thì logic đơn giản đi rất nhiều — **hỏi trước khi code** |
| Xung đột migration khi nhiều người cùng viết | Trung bình | Chỉ **một người** (Nguyễn Đăng Trường) sở hữu thư mục `migrations/`, giữ `down_revision` tuyến tính |
| Không ai đụng vào frontend trong tuần đầu vì chờ API | Thấp (đã xử lý) | MSW ở T06 gỡ chặn hoàn toàn |

---

## 8. Câu hỏi cần trả lời trước khi bắt đầu

| # | Câu hỏi | Chặn task nào | Ai trả lời | Đề xuất mặc định |
|---|---|---|---|---|
| 1 | Package manager Python? | T03 | Nhóm BE | `uv` |
| 2 | Repo GitHub đã có chưa? Ai là owner? | T01 | Scrum Master | Tạo trong 1 giờ đầu |
| 3 | LLM provider và ngân sách? | T19 (không chặn T01–T18) | PO / Scrum Master | Dùng `FakeLlmClient` trước, chốt muộn nhất S1-1 |
| 4 | Deploy staging ở đâu? | T24 | DevOps | Render hoặc Railway (free tier), quyết trong S0 |
| 5 | **Q1** — Employee xem được ticket cùng phòng ban không? | T13, T15 | Trainer (PO) | Mặc định: **Không**. Đã cô lập trong `TicketAccessPolicy`, đổi sau rẻ |
| 6 | **Q4** — SLA theo giờ hành chính hay 24/7? | T13 | Trainer (PO) | Mặc định: **giờ hành chính**. Nếu 24/7 thì T13 nhẹ đi ~½ ngày |

Câu 5 và 6 nên hỏi trong buổi họp Trainer tuần 1 — **nhưng không chờ câu trả lời để bắt đầu**, vì cả hai đều đã được cô lập trong lớp thuần.

---

## 9. Đối chiếu với checklist của skill

- [x] Mọi task có tiêu chí chấp nhận cụ thể, kiểm chứng được
- [x] Mọi task có bước xác minh bằng lệnh hoặc thao tác cụ thể
- [x] Phụ thuộc được xác định và sắp đúng thứ tự (§3)
- [x] Không task nào chạm quá ~5 file (kích thước tối đa M)
- [x] Có checkpoint giữa các phase (A–E)
- [x] Cắt dọc, không cắt ngang — Phase 1 và 2 mỗi phase là một đường trọn vẹn DB→UI
- [x] Task rủi ro cao đặt sớm (T13 lớp thuần, T08 auth, T24 staging)
- [ ] **Người duyệt đã rà soát và phê duyệt** ← cần bạn xác nhận
