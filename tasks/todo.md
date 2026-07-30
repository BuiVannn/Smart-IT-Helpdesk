# TODO — Base Smart IT Helpdesk

Chi tiết đầy đủ (tiêu chí chấp nhận, cách xác minh, file liên quan): [`plan.md`](plan.md)

**Quy ước:** đánh dấu `[x]` chỉ khi **đã qua bước Xác minh** trong `plan.md`, không phải khi "code xong".

---

## Trước khi bắt đầu

- [ ] Chốt package manager Python (đề xuất: `uv`)
- [ ] Tạo repo GitHub, thêm 9 thành viên, bật branch protection cho `main`
- [ ] Chốt nơi deploy staging (đề xuất: Render / Railway)
- [ ] Hỏi Trainer: **Q1** (Employee xem ticket cùng phòng ban?) và **Q4** (SLA giờ hành chính hay 24/7?)
- [ ] Chốt LLM provider + ngân sách (không chặn — dùng `FakeLlmClient` trước)

---

## Phase 0 — Hạ tầng & Khung `Sprint 0`

- [ ] **T01** Khởi tạo repo + cấu trúc thư mục + branch protection · `XS` · Hà
- [ ] **T02** Docker Compose (Postgres+pgvector, Redis, MinIO) · `S` · Hà · ⇐ T01
- [ ] **T03** Khung backend: `core/` + `main.py` + health check · `M` · Đông · ⇐ T01
- [ ] **T04** Tầng `db/` + Alembic + migration 001–002 · `S` · Trường · ⇐ T02,T03
- [ ] **T05** CI: 9 cổng chất lượng (gồm `import-linter`) · `M` · Hà · ⇐ T03,T04
- [ ] **T06** Khung frontend + MSW mock + component chung · `M` · Quang+Dũng · ⇐ T01

### ⛳ CHECKPOINT A — Khung sẵn sàng
- [ ] `docker compose up` từ máy sạch: 3/3 healthy trong < 3 phút
- [ ] `/health/ready` → 200; dừng Postgres → `/health/ready` 503 nhưng `/health/live` vẫn 200
- [ ] `alembic upgrade head` → `downgrade base` → `upgrade head` sạch
- [ ] `npm run dev` hiện layout, MSW hoạt động khi **tắt hẳn backend**
- [ ] CI xanh trên PR thử; PR vi phạm ranh giới module bị **chặn**
- [ ] **Cả 9 người clone và chạy được trên máy mình**

---

## Phase 1 — Lát cắt dọc #1: Xác thực `chứng minh khuôn mẫu`

- [ ] **T07** Migration 003: `departments`, `users`, `refresh_tokens` + seed · `S` · Trường · ⇐ T04
- [ ] **T08** Module `auth` + `users`: register/login/refresh/logout/me · `M` · Đông · ⇐ T07
- [ ] **T09** Dependency phân quyền + test quét toàn bộ route · `S` · Đông · ⇐ T08
- [ ] **T10** Bộ khung test: conftest, factory, cấu trúc unit/integration/api · `M` · Ngọc+Đông · ⇐ T08
- [ ] **T11** Frontend: AuthProvider, Login, ProtectedRoute, auto-refresh · `M` · Quang · ⇐ T06,T08

### ⛳ CHECKPOINT B — Khuôn mẫu được chứng minh
- [ ] Browser: đăng nhập → vào trang có bảo vệ → F5 vẫn giữ phiên
- [ ] Hạ TTL access token xuống 10 s → thao tác tiếp vẫn chạy nhờ auto-refresh
- [ ] Dùng lại refresh token cũ → 401 **và** toàn bộ chuỗi token bị thu hồi
- [ ] Bỏ dependency của một endpoint → test quét route **fail**
- [ ] Coverage module `auth` ≥ 70%
- [ ] 🔴 **Buổi rà soát bắt buộc — 5 BE cùng đọc module `auth`, chốt khuôn mẫu**

---

## Phase 2 — Lát cắt dọc #2: Ticket tối thiểu

- [ ] **T13** ⚠️ Lớp thuần: `TicketStateMachine` + `SlaCalculator` + `TicketAccessPolicy` · `M` · Vũ · ⇐ T03
  - [ ] Test phủ **toàn bộ 49 ô** bảng chuyển trạng thái
  - [ ] Ca bắt buộc: ticket URGENT tạo 17:00 thứ Sáu → hạn **11:30 thứ Hai**
  - [ ] Coverage ≥ 90%, chạy < 2 s, **không cần database**
- [ ] **T12** Migration 004–005: danh mục, SLA policy, `tickets` + 7 index + seed · `M` · Trường · ⇐ T04
- [ ] **T14** Module `tickets`: models, repository, service (create/get/list) · `M` · Vũ · ⇐ T12,T13,⛳B
- [ ] **T15** Router `tickets`: 3 endpoint + phân quyền bản ghi + idempotency · `M` · Vũ · ⇐ T14,T09
- [ ] **T16** Frontend: danh sách + tạo + chi tiết ticket (API thật) · `M` · Dũng · ⇐ T11,T15
- [ ] **T17** Xuất OpenAPI → sinh TS types + CI chống trôi hợp đồng · `S` · Vũ · ⇐ T15

### ⛳ CHECKPOINT C — Lát cắt dọc hoàn chỉnh
- [ ] End-to-end browser: đăng nhập → tạo ticket → danh sách → chi tiết
- [ ] Employee A mở ticket của Employee B → **404** (không phải 403)
- [ ] Tạo ticket → có **đúng 1** dòng `ticket_events`; lỗi giữa chừng → rollback cả hai
- [ ] List 20 ticket → ≤ 4 câu SQL (không N+1)
- [ ] Gửi 2 lần cùng `Idempotency-Key` → chỉ 1 ticket
- [ ] `openapi.json` đã commit; đổi schema mà quên export → CI fail
- [ ] 🔴 **Buổi rà soát — chốt khuôn mẫu module nghiệp vụ, sẵn sàng fan-out**

---

## Phase 3 — Base AI

- [ ] **T23** ⚡ Dữ liệu: 20 bài KB + 50 ticket có nhãn + 30 câu eval + 60 ticket demo · `M` · Văn · **BẮT ĐẦU NGÀY 1**
  - [ ] 15–20 bài KB thật, mỗi bài 300–800 từ (không phải lorem ipsum)
  - [ ] `classification_eval.jsonl` — 50 ca (35 rõ / 10 mơ hồ / 5 lắt léo)
  - [ ] `rag_eval.jsonl` — 30 câu, trong đó **5 câu cố tình ngoài tài liệu**
  - [ ] `scripts/seed_demo.py` — 60 ticket rải 60 ngày
- [ ] **T18** Migration 007: `kb_*`, `article_chunks` + index HNSW · `S` · Trường · ⇐ T04
- [ ] **T19** `app/ai`: interfaces + Fake clients + resilience + cost_guard · `M` · Văn · ⇐ T03
  - [ ] `pytest` chạy sạch khi **`unset LLM_API_KEY`**
  - [ ] Circuit breaker: 5 lỗi → lần 6 fail ngay, không gọi mạng
  - [ ] Retry có **jitter** (2 lần chạy cho khoảng chờ khác nhau)
- [ ] **T20** `TextChunker` (lớp thuần) + unit test · `S` · Văn · ⇐ T03
- [ ] **T21** Celery + worker + beat + `IndexingService` + `reindex_kb.py` · `M` · Văn+Hà · ⇐ T18,T19,T20,T23
  - [ ] Index 2 lần → số chunk không đổi, không có chunk mồ côi
  - [ ] `reindex_kb.py --all` từ DB trống chunk → dựng lại đủ ✅ **phải chạy thử thật**
- [ ] **T22** Phân loại ticket bất đồng bộ + `RuleBasedClassifier` + eval script · `M` · Văn · ⇐ T14,T19,T21,T23

### ⛳ CHECKPOINT D — Base AI hoạt động
- [ ] Tạo ticket → ≤ 30 s có category + priority + confidence
- [ ] 🔴 **Đặt API key sai → tạo ticket VẪN thành công**, `ai_status=FAILED` (kiểm thử suy giảm chức năng)
- [ ] Ticket đã có category do người chọn → AI **không ghi đè**
- [ ] 20 bài KB đã index, đếm được số chunk
- [ ] `eval_classification.py` in ra độ chính xác trên 50 ca
- [ ] Toàn bộ test xanh **không cần API key**

---

## Phase 4 — Staging & Bàn giao

- [ ] **T24** Deploy staging: compose prod, Nginx+TLS, auto-deploy, backup · `M` · Hà · ⇐ ⛳C
  - [ ] Merge vào `develop` → staging tự cập nhật < 10 phút
  - [ ] 🔴 **Khôi phục backup thành công một lần**, ghi lại thời gian thực tế
- [ ] **T25** `README.md` (7 mục Guideline) + `CONTRIBUTING.md` (hướng dẫn thêm module) · `S` · Văn+Hà · ⇐ T24

### ⛳ CHECKPOINT E — Base hoàn thành
- [ ] 5 điều kiện "base xong" ở `plan.md` §1 đều đúng
- [ ] 🔴 **Bài kiểm chứng cuối:** một thành viên chưa đụng base đọc `CONTRIBUTING.md` và tự thêm module rỗng `feedback` chạy được trong **< 1 giờ, không hỏi ai**
- [ ] Sprint Planning: chia 8 feature, **mỗi module đúng một chủ sở hữu**

---

## Bảng theo dõi theo người

| Người | Vai trò | Task | Ngày bận nhất |
|---|---|---|---|
| Cao Mạnh Hà | DevOps | T01, T02, T05, T21, T24 | S0-1 → S1-6 (đường găng) |
| Lại Duy Đông | Backend | T03, T08, T09, T10 | S1-1 → S1-3 |
| Nguyễn Đăng Trường | Backend/DB | T04, T07, T12, T18 | S0-2 → S1-3 |
| Chu Quang Vũ | Backend | T13, T14, T15, T17 | S1-3 → S1-5 |
| Nguyễn Tiến Lưỡng | Backend | *(chưa có task base — hỗ trợ T10, chuẩn bị module `knowledge`)* | — |
| Nguyễn Văn Quang | Frontend | T06, T11 | S0-1 → S1-2 |
| Nguyễn Văn Dũng | Frontend | T06, T16 | S0-1 → S1-4 |
| Trần Quang Ngọc | QA | T10 + soạn Test Plan song song | Xuyên suốt |
| Bùi Mậu Văn | SM / AI | T19, T20, T21, T22, T23, T25 | Ngày 1 → S1-6 |

> **Nguyễn Tiến Lưỡng chưa có task trên đường găng** — đề xuất: hỗ trợ T10 (viết test cho `auth`), rồi bắt đầu module `knowledge` (F5) ngay sau Checkpoint B, vì F5 là đầu vào của RAG và cần xong sớm.
