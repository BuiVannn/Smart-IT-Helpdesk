# Review tổng thể — nghiệp vụ, kiến trúc, bảo mật, chất lượng AI

| | |
|---|---|
| Ngày | 01/08/2026 |
| Nhánh | `develop` @ `db92d32` |
| Phạm vi | Toàn bộ `backend/app` (92 file), `frontend/src`, `migrations/`, `docs/design/` (11 tài liệu + 11 ADR) |
| Cách làm | 4 hướng review độc lập: kiến trúc/tính đúng đắn · bảo mật & phân quyền · đối chiếu kế hoạch (PM/BA) · chất lượng AI & RAG |
| Kiểm chứng | Chạy thật trên PostgreSQL `localhost:5434`, server thử nghiệm cổng 8099, 60+ request HTTP, 2 luồng đồng thời, tập đánh giá 50 ca phân loại + 10 ca RAG |

Mỗi phát hiện ghi rõ **[KIỂM CHỨNG]** (có kết quả chạy thật) hay **[ĐỌC CODE]**.

---

## 0. Kết luận trong một trang

**Chất lượng kỹ thuật của phần đã làm là tốt.** Lõi phân quyền chịu được tấn công: cách ly ticket áp ngay trong `WHERE`, trả 404 thay vì 403 nhất quán, phiên chat riêng tư kể cả với Admin, xoay vòng refresh token phát hiện được replay, vai trò đọc từ DB chứ không tin claim JWT, SQL injection không có đường vào. Model khớp migration tuyệt đối (0 lệch cột, 36/36 khoá ngoại, 9/9 enum). Cơ chế chống bịa đặt của chatbot được thiết kế trên mức yêu cầu.

**Nhưng ba nhóm vấn đề làm hệ thống không đáng tin ở đúng những chỗ nó tự nhận là mạnh nhất:**

1. **Ba cơ chế được quảng cáo trong docstring nhưng không hoạt động** — khoá lạc quan, tạm dừng SLA, chồng lấn chunk. Cả ba đều có cột trong DB, có hàm, có test đơn vị. Không cái nào chạy.
2. **Toàn bộ tính giờ hành chính lệch 7 tiếng** vì so giờ UTC với 8:30–17:30 giờ Việt Nam. Lan sang SLA, hàng chờ, cảnh báo trễ hạn, và thuật toán gán việc.
3. **Chatbot RAG hiện không truy hồi đúng tài liệu nào** — recall@5 = 0/10 — vì embedding giả dùng SHA-256, không có ngữ nghĩa.

**Tiến độ thật:** đối chiếu từng tiêu chí chấp nhận của 43 story — **20/96 SP Must đạt đủ AC (21%)**. 71 SP có code chạy được nhưng chưa thoả AC. F6/F7/F8 gần như bằng 0.

---

## 1. P0 — Phải sửa trước khi demo

### P0-1. Khoá lạc quan `version` hoàn toàn vô hiệu [KIỂM CHỨNG]

`app/modules/tickets/models.py:128` khai `version: Mapped[int]` nhưng **không có** `__mapper_args__ = {"version_id_col": version}`. Hệ quả: SQLAlchemy không thêm `WHERE version = :old` vào câu UPDATE. `_check_version()` đọc rồi so bằng Python; `_load()` không `with_for_update`.

Chạy hai luồng cùng `claim(version=1)`:

```
Agent1 -> HTTP 200 THÀNH CÔNG
Agent2 -> HTTP 200 THÀNH CÔNG
DB: version=2  assignee=<agent2>  status=ASSIGNED
Sự kiện ASSIGNED đã ghi: [<agent1>, <agent2>]
```

Đúng kịch bản mà docstring `claim()` (`service.py:249-251`) tuyên bố đã chặn. Agent1 nhận 200, màn hình hiển thị mình là người xử lý, DB ghi Agent2. `version` chỉ lên 2 thay vì 3 — một lần bump bị mất, nên lần ghi đồng thời kế tiếp cũng lọt.

Ảnh hưởng: `claim`, `assign`, `change_status`, `update` — mọi đường ghi của ticket.

**Sửa (một dòng):**
```python
class Ticket(Base):
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}
```
rồi bỏ `_bump()` thủ công và bắt `StaleDataError` → `ConflictError`.

Ghi chú: `apply_ai_classification()` (`service.py:456`) **có** sinh đúng `SELECT ... FOR UPDATE`. Đường AI an toàn hơn đường con người.

### P0-2. Toàn bộ giờ hành chính tính theo UTC [KIỂM CHỨNG]

`app/modules/tickets/sla.py:75-78` so `cursor.time()` (UTC) với `cal.start_time`/`end_time` (8:30–17:30 giờ VN). Giờ hành chính thực tế thành **15:30–00:30 giờ VN**.

| Tạo ticket (giờ VN) | Hạn URGENT hiện tại | Kỳ vọng |
|---|---|---|
| Thứ 6 17:00 | Thứ 6 21:00 | Thứ 2 11:30 |
| Thứ 2 09:00 | Thứ 2 19:30 | Thứ 2 13:00 |
| Thứ 4 14:00 | Thứ 4 19:30 | Thứ 5 09:30 |

Chính ca kiểm thử mà docstring `sla.py:3-5` gọi là quan trọng nhất cũng sai.

**Lỗi này có ba mặt:**
- `sla.py:75-78` — hạn SLA, `sla_state()`, `queue_stats()` cột `at_risk`/`breached`
- `suggestions.py:265-267` — `is_on_duty()`: 10:00 sáng thứ Tư giờ VN → `now.time()` = 03:00 → **ngoài ca**. Mọi agent bị trừ `w_duty` suốt giờ làm việc thật; trọng số ca trực mất tác dụng hoàn toàn.
- `service.py:756` dựng `BusinessCalendar(holidays=...)` **không truyền** `settings.BUSINESS_HOUR_START/END`, trong khi `suggestions.py:279` có truyền. Đổi giờ hành chính trong `.env` chỉ tác dụng lên gợi ý, không lên SLA.

**Sửa:** thêm `BUSINESS_TIMEZONE = "Asia/Ho_Chi_Minh"` vào config; trong `due_at()` và `is_on_duty()` đổi sang giờ địa phương trước khi so `.time()`/`.date()`, đổi kết quả về UTC khi trả ra. Truyền `start_hour`/`end_hour` từ settings ở `service.py:756`.

### P0-3. Chatbot RAG không truy hồi được tài liệu nào [KIỂM CHỨNG]

`app/ai/embedding/fake_embedding.py:28-32` sinh vector bằng SHA-256. Docstring dòng 3 khẳng định *"văn bản giống nhau cho vector gần nhau"* — **sai**:

```
-0.2095   'Cách đổi mật khẩu email công ty'  vs  'Hướng dẫn đổi mật khẩu email công ty'
-0.0416   'Cách đổi mật khẩu email công ty'  vs  'Máy in tầng 3 bị kẹt giấy'
-0.3566   'quên mật khẩu'                    vs  'quen mat khau'
```

Hai câu gần đồng nghĩa **xa nhau hơn** hai câu không liên quan. SHA-256 là hàm khuếch tán — đổi một ký tự thì đổi toàn bộ digest. Thêm nữa: vector khai 1536 chiều nhưng digest chỉ 32 byte lặp 48 lần ⇒ **32 giá trị độc lập**.

Đo trên 20 bài KB đã index, 65 chunk trong pgvector, 10 câu của `rag_eval.jsonl`:

| Chỉ số | Kết quả | Mục tiêu (07 §5.2) |
|---|---|---|
| Recall@5 | **0/10** | ≥ 85% |
| Từ chối đúng | **0/3** | **100%** |
| Từ chối oan | 2/10 | — |

Hỏi "đổi mật khẩu email" → trả bài **kết nối wifi**. Câu "cho tôi mật khẩu admin của server" (phải từ chối) → tìm thấy ngữ cảnh 0.519 → **gọi LLM**. Câu prompt injection cũng lọt.

**Không phải lỗi kiến trúc.** `Retriever`, ngưỡng 0.35, cơ chế chống bịa đặt đều đúng. Vấn đề là dùng embedding chỉ-dành-cho-test làm đường demo, trong khi `LLM_PROVIDER=fake` là mặc định.

**Sửa:** cắm embedding thật + `reindex_kb.py --all` (~1 giờ). Trước đó không có cách nào chứng minh F4 hoạt động.

### P0-4. AI tự động ghi nhãn sai vào ticket [KIỂM CHỨNG]

`app/ai/llm/fake_client.py:15-20`: khi không từ khoá nào khớp, `FakeLlmClient` trả `category_slug: "other"` với **`confidence: 0.75`**. Ngưỡng áp dụng tự động là 0.6 ⇒ nhãn "không biết" **vượt ngưỡng và ghi thẳng vào ticket**, thay vì vào hàng chờ thủ công.

Bảng luật thiếu hẳn `email` và `access` (chỉ 5 luật). Đo trên 50 ca:

| | rules-only | fake LLM | mục tiêu |
|---|---|---|---|
| Category | **74,0% ✓** | 54,0% ✗ | ≥ 70% |
| Priority ±1 | 84,0% ✓ | 88,0% ✓ | ≥ 80% |

Chế độ fake **tệ hơn cả không dùng LLM**.

**Sửa (~30 phút):** thêm 2 luật `email`/`access`; hạ `DEFAULT_CLASSIFICATION["confidence"]` từ 0,75 xuống 0,3.

### P0-5. Vi phạm BR-13 — AI ghi đè mức ưu tiên do người đặt [KIỂM CHỨNG]

`service.py:466` chỉ bảo vệ `category_id`; `service.py:473` vẫn ghi đè `priority`.

```
1. Vừa tạo   : priority=MEDIUM  ai_status=PENDING  sla_res=05/08 14:30
2. Agent đặt : priority=URGENT                     sla_res=03/08 12:30
3. AI ghi    : priority=MEDIUM                     sla_res=05/08 14:30

Nhật ký: PRIORITY_CHANGED USER MEDIUM->URGENT
         PRIORITY_CHANGED AI   URGENT->MEDIUM
```

Agent nâng lên URGENT vì sự cố gấp; AI hạ về MEDIUM và **nới hạn SLA thêm 2 ngày**. Nhật ký ghi rõ AI đã ghi đè người — đúng thứ BR-13 cấm.

**Sửa:** mở rộng điều kiện ở `service.py:466`, kiểm tra dấu vết con người đã can thiệp qua `TicketEvent` có `actor_type == USER`.

### P0-6. Celery beat gọi hai task không tồn tại [KIỂM CHỨNG]

`celery_app.py:53-56` và `:69-72`:
```
sla-monitor            -> app.modules.notifications.tasks.monitor_sla       KHÔNG TỒN TẠI
cleanup-expired-tokens -> app.modules.auth.tasks.cleanup_expired_tokens     KHÔNG TỒN TẠI
```

Beat đẩy `monitor_sla` **mỗi 5 phút**, worker trả `NotRegistered` và log lỗi liên tục — sẽ chạy ngay trước mắt giám khảo. `sla_warned_at`/`sla_breached_at` không bao giờ được ghi (US-35 coi như không có). Refresh token hết hạn không bao giờ bị dọn.

**Sửa:** viết hai task, hoặc tạm gỡ khỏi `beat_schedule` kèm `# TODO US-35 — <người phụ trách>`.

### P0-7. Agent bất kỳ đóng được ticket của đồng nghiệp [KIỂM CHỨNG]

`state_machine.py:60` và `:69` thiếu `assignee_only=True`:
```python
S.PENDING_REQUESTER: (TransitionRule(S.IN_PROGRESS, ALL_ROLES),   # dòng 60
S.RESOLVED:          (TransitionRule(S.CLOSED,      ALL_ROLES),   # dòng 69
```

Request thật: agent2 (không phải assignee, không phải requester) POST status `CLOSED` → **HTTP 200**.

`CLOSED` là trạng thái cuối ⇒ hành động này **tước vĩnh viễn cửa sổ mở lại 7 ngày của người yêu cầu**, đồng thời `_settle_ai_accuracy` chốt sổ "AI đúng" làm sai báo cáo US-22. Phá huỷ, không hoàn tác, do người không thẩm quyền.

Đối chiếu `docs/design/03` §5: `RESOLVED → CLOSED` chỉ dành cho Requester/Hệ thống/Admin; `PENDING_REQUESTER → IN_PROGRESS` chỉ Assignee/Requester.

**Lỗi kèm theo:** `state_machine.py:44` và `:68` khai `frozenset({EMPLOYEE, ADMIN})` nên **IT_AGENT không huỷ được ticket do chính mình tạo**, cũng không mở lại được. `requester_only=True` đã đủ giới hạn đúng người — nên đổi hai frozenset đó thành `ALL_ROLES`.

### P0-8. Nhân viên tự nâng ticket của mình lên URGENT [KIỂM CHỨNG]

Tài liệu 06 §5: employee chỉ được sửa `title`/`description`. Nhưng `can_edit` (`policies.py:62`) trả True/False cho **cả bản ghi**, còn `UpdateTicketRequest` (`schemas.py:39-44`) có sẵn `priority` và `categoryId`.

```
PATCH /tickets/{id} {"priority":"URGENT","version":1} -> 200
priority: URGENT | slaResolutionDueAt: 2026-08-03T12:30:00Z
```

`_apply_sla()` tính lại hạn theo URGENT ⇒ nhân viên tự đẩy mình lên đầu hàng chờ. Sửa `categoryId` còn kích hoạt `_record_ai_correction` ⇒ nhân viên **tự đánh dấu AI phân loại sai**, bóp méo US-22.

**Sửa:** dùng hai schema riêng — `UpdateOwnTicketRequest` (chỉ `title`/`description`/`version`) cho Employee — để Pydantic chặn thay vì phụ thuộc một câu `if`.

### P0-9. Admin đăng nhập vào màn hình trống [KIỂM CHỨNG]

`App.tsx:32` đẩy ADMIN sang `/dashboard`; dòng 78 render `/dashboard` bằng `<Placeholder title="Báo cáo" />`. `/kb` và `/admin/users` cũng là Placeholder.

Màn hình đầu tiên giám khảo thấy khi đăng nhập bằng tài khoản admin là dòng chữ "sẽ được xây dựng ở task tiếp theo".

**Sửa nhanh (30 phút):** đổi đích của ADMIN sang `/queue` cho tới khi F7 có nội dung.

---

## 2. P1 — Sửa trong tuần này

### P1-1. `paused_seconds` không bao giờ được ghi [KIỂM CHỨNG]

`docs/design/03` §6 quy tắc 2: thời gian ở `PENDING_REQUESTER` không tính vào SLA. Cột có (`models.py:123`), `SlaCalculator.state()` có nhận (`sla.py:99`), unit test truyền tay `paused_seconds=7200`. **Không dòng nghiệp vụ nào cộng dồn** — grep toàn `app/` chỉ ra một chỗ đọc (`service.py:765`), không chỗ nào ghi.

Agent chuyển sang `PENDING_REQUESTER` chờ nhân viên gửi ảnh, nhân viên đi họp cả chiều, ticket vẫn chạy đồng hồ và bị tính vi phạm.

### P1-2. `Idempotency-Key` chưa được cài, dù bảng và index đã có [KIỂM CHỨNG]

`grep -ri idempotenc app/` → **0 kết quả**. Nhưng `02-user-stories.md:138` coi là AC của US-08, `10-test-strategy.md:104` coi là ca kiểm thử bắt buộc, và migration `0002:178` đã tạo bảng, `0003:116` đã tạo index. `select count(*) from idempotency_keys` → 0.

Nhân viên bấm "Gửi" trên mạng chậm rồi bấm lại → hai ticket giống hệt, hai lần gọi LLM.

### P1-3. `alembic autogenerate` sẽ xoá 28 index [KIỂM CHỨNG]

`0003_performance_indexes.py:26-116` tạo 28 index bằng SQL thô; model chỉ khai 3. `compare_metadata` trên DB dựng từ migration cho **28 khác biệt, tất cả `remove_index`** — gồm `ix_chunks_embedding` (HNSW cho RAG), `ix_tickets_assignee_open`, `ix_tickets_sla_monitor`, `ix_users_name_trgm`.

Ai đó thêm một cột, chạy `--autogenerate`, review lướt qua và merge → mất toàn bộ partial index + HNSW.

**Sửa:** thêm `include_object` vào `migrations/env.py`:
```python
def include_object(obj, name, type_, reflected, compare_to):
    return not (type_ == "index" and reflected and compare_to is None)
```

### P1-4. Không có test ma trận phân quyền — và test viết theo tài liệu sẽ chạy rỗng [KIỂM CHỨNG]

`dependencies.py:3-5` khẳng định *"xem tests/api/test_permission_matrix.py"*. **File không tồn tại.** US-06 coi đây là AC bắt buộc; tài liệu 08 §2.4 gọi là "hai bài test bắt buộc".

Nghiêm trọng hơn: FastAPI 0.141.1 bọc router con trong `_IncludedRouter`, nên `app.routes` chỉ có **7 phần tử**, 4 trong đó là `/docs`, `/redoc`, `/openapi.json`. Đoạn mã mẫu ở tài liệu 08 §2.4 sẽ duyệt qua **0 endpoint nghiệp vụ** và báo xanh.

**Sửa:** duyệt đệ quy qua `_IncludedRouter.original_router.routes`, kèm `assert len(routes) >= 33` để test tự vỡ nếu FastAPI đổi cấu trúc lần nữa.

Hiện tại quét tay 33 route: **tất cả đều có xác thực**, và employee gọi 6 endpoint dành cho agent/admin đều nhận 403. Cần viết test **ngay** để chốt trạng thái sạch này lại.

### P1-5. Mất database ⇒ CI vẫn xanh [KIỂM CHỨNG]

`tests/conftest.py:60-61` — fixture `db_connection` có `scope="session"` và `pytest.skip` khi không kết nối được. Postgres chết ⇒ ~173 test API + integration bị bỏ qua im lặng, pytest thoát mã 0. Cộng với 18 test chatbot skip vì thiếu seed, đây là hai tầng "xanh vì không chạy" chồng lên nhau.

**Sửa:** khi `CI=true` thì lỗi cứng thay vì skip. Thêm bước seed vào `ci.yml` sau `alembic upgrade head`:
```yaml
- name: Seed dữ liệu nền và kho tri thức
  run: |
    python scripts/seed.py
    python scripts/seed_kb.py
    python scripts/reindex_kb.py --all
```
Chạy được vì `LLM_PROVIDER: fake` đã đặt sẵn và `build_embedding_client()` trả `FakeEmbeddingClient` — không cần API key.

### P1-6. `mypy` không chặn được gì

`.github/workflows/ci.yml:75` — `mypy app || true`. Cổng chất lượng #2 trong tài liệu 10 §9 ghi "Chặn merge: Có"; thực tế luôn xanh. Nên đo số lỗi trước khi bỏ `|| true`.

### P1-7. US-07 chưa có — không có đường nào gán vai trò [KIỂM CHỨNG]

Chỉ có `GET/PATCH /users/me`. Thiếu `POST /users`, `GET /users`, `/activate`, `/deactivate`, `PATCH /users/{id}`, `/users/agents`, `PUT /users/{id}/skills`. `users/repository.py:44-76` đã viết sẵn hàm `list()` nhưng không ai gọi.

Hệ quả sâu hơn dự kiến: `POST /auth/register` luôn gán `EMPLOYEE`, và không có endpoint nào nâng vai trò ⇒ muốn có IT_AGENT/ADMIN phải `UPDATE` thẳng vào PostgreSQL. **Mô hình 3 vai trò của US-06 không vận hành được qua ứng dụng.** AC "khoá người dùng ⇒ thu hồi toàn bộ refresh token" cũng chưa có chỗ thực thi.

Phần nền đã đúng: `get_current_user` (`dependencies.py:41`) kiểm `is_active` mỗi request, nên đặt `is_active=False` là access token mất hiệu lực ngay. Chỉ thiếu tầng API.

### P1-8. Thiếu toàn bộ security header [KIỂM CHỨNG]

`GET /api/v1/users/me`: `strict-transport-security`, `x-frame-options`, `x-content-type-options`, `content-security-policy`, `referrer-policy` — **đều MISSING**. `server: uvicorn` lộ công nghệ.

Một middleware, mười phút. `nosniff` sẽ thành lỗ hổng thật ngay khi US-09 (tải file) được cài.

### P1-9. Worker giữ transaction PostgreSQL mở suốt lời gọi LLM [KIỂM CHỨNG]

`classifier.py:313` mở transaction, `:339` `await self._ask_llm(...)` chạy 5–20 giây × tối đa 3 lần thử. Quan sát `pg_stat_activity`: kết nối ở trạng thái `idle in transaction`. Với `DB_POOL_SIZE=10`, 10 ticket phân loại đồng thời là hết pool — API bị chặn theo dù không liên quan gì tới AI.

**Sửa:** đọc `title`/`description`/`ai_status` xong thì `commit()` trước khi `await`.

### P1-10. Lịch sử ticket không có thứ tự xác định [KIỂM CHỨNG]

`repository.py:230` — `ORDER BY created_at ASC` không tie-breaker. `TicketEvent.created_at` = `transaction_timestamp()`, nên mọi sự kiện trong cùng transaction có mốc **giống hệt nhau**:
```
STATUS_CHANGED   09:56:15.527490+00
ASSIGNED         09:56:15.527490+00   <- trùng
```
Thứ tự hiển thị do PostgreSQL quyết định, đổi được sau `VACUUM`. `TicketRepository.list` (`:122`) đã thêm `Ticket.id.desc()` đúng cách; chỗ này quên.

**Sửa:** `.order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc())` — id là UUIDv7 nên tự đúng thứ tự.

### P1-11. Cửa sổ mở lại "7 ngày" thực tế gần 8 ngày [KIỂM CHỨNG]

`service.py:681` dùng `timedelta.days` (cắt phần lẻ): 191 giờ → `.days=7` → vẫn cho mở lại. Thông báo lỗi nói "7 ngày", hệ thống cho tới 7 ngày 23 giờ 59 phút.

### P1-12. Resolve lần hai không cần ghi chú mới [KIỂM CHỨNG]

Khi mở lại, `resolved_at` bị xoá (`service.py:358`) nhưng `resolution_note` được giữ. Resolve lần hai không gửi ghi chú mới vẫn được chấp nhận, và người yêu cầu **nhận lại đúng lời giải thích họ vừa bác bỏ**.

**Sửa:** đặt `ticket.resolution_note = None` cùng với `resolved_at = None`.

### P1-13. `auto_close_resolved` không giới hạn số dòng, không khoá [ĐỌC CODE]

`service.py:605-615` SELECT toàn bộ ticket RESOLVED quá hạn, không `LIMIT`, không `with_for_update`, rồi lặp UPDATE từng cái. Đối chiếu: `reconcile_pending` (`tasks.py:35`) có `RECONCILE_BATCH_SIZE = 50`.

Sau vài tháng, một lần chạy 01:00 nạp hàng nghìn ticket vào bộ nhớ, dễ vượt `task_time_limit=300` và bị giết giữa chừng — rollback toàn bộ, lần sau lặp y hệt.

### P1-14. `sub` không phải UUID gây 500 thay vì 401 [ĐỌC CODE]

`dependencies.py:38` — `UUID(subject)` ném `ValueError` → handler `Exception` → **500 INTERNAL_ERROR** + stack trace mỗi request.

---

## 3. Phần AI — cần làm gì để có số liệu báo cáo

### 3.1 Ba việc, sáu giờ, đổi lấy phần chênh lệch điểm lớn nhất

| # | Việc | Công sức |
|---|---|---|
| 1 | Cắm embedding thật + `reindex_kb.py --all` | 1 giờ |
| 2 | Viết `scripts/eval_rag.py` (4 chỉ số của 07 §5.2) | 4 giờ |
| 3 | Sửa `FakeLlmClient` (P0-4) | 30 phút |

`app/modules/chatbot/prompts.py:158` ghi *"Chạy đánh giá: python scripts/eval_rag.py"* — **file chưa bao giờ được viết**. Chỉ tiêu "100% từ chối đúng" hiện không có cách nào đo.

Bốn chỉ số cần cài, đều tự động, không cần người chấm:
1. **Recall@5** — `expect_article_slug` có trong chunk trả về không (dữ liệu đã sẵn, ~40 dòng code)
2. **Tỉ lệ từ chối đúng** — với ca `refusal`, khẳng định `retrieval.has_context is False` **và** `fake_llm.stream_count == 0`. **Đo được không cần API key.**
3. **Tỉ lệ trích dẫn đúng** — mọi `[Nguồn: X]` phải khớp một `citations` đã gửi
4. **Độ trễ tới token đầu**

Thêm cờ `--assert-real-embedding` để script **từ chối chạy** khi phát hiện `FakeEmbeddingClient`.

### 3.2 Tập đánh giá phân loại — bốn thiên lệch

Phân bố 50 ca hiện tại khớp thiết kế §5.1 (34 clear / 11 ambiguous / 5 tricky), cân bằng category tốt. Nhưng:

1. **0/50 ca viết không dấu**, dù `docs/design/07` §7 xếp đây là rủi ro Trung bình và cam kết "đưa các biến thể vào tập đánh giá". Ngược đời: `normalize()` (`classifier.py:92`) được viết riêng cho việc này mà không có ca nào kiểm chứng.
2. **`other` chỉ 2 ca** — lớp mặc định nguy hiểm nhất.
3. **Priority lệch nặng về MEDIUM (26/50)** — một bộ phân loại luôn đoán MEDIUM đạt 52% chính xác và ~90% ±1 bậc, nên chỉ tiêu "±1 ≥ 80%" gần như không kiểm được gì.
4. **Ba ca nhãn đáng tranh cãi** (cls-38, 45, 46) nên có `acceptable_categories` để không phạt oan.

Con số **74% là của tầng dự phòng đối chiếu từ khoá, không phải của AI** — `classify-v1.0` chưa từng được đo. Khi báo cáo tuyệt đối không trình bày 74% như "độ chính xác của AI".

### 3.3 Sửa luật phân loại — 1,5 giờ, dự kiến 74% → 84-86%

| Luật | Thêm từ khoá | Cứu ca |
|---|---|---|
| `security` | `gia danh`, `link la`, `duong link`, `thiet bi la`, `nguoi la`, `dang nhap bat thuong`, `quang cao la`, `pop-up` | 05, 35, 36, 47 |
| `access` | `cap quyen dang nhap`, `khong co quyen`, `mat quyen`, `thu hoi quyen` | 31, 32, 45 |
| `network` | `portal`, `trang noi bo`, `khong mo duoc trang`, `lan` | 39 |
| `hardware` | `khoi dong lai`, `tu tat`, `khong len nguon` | 41 |

Thêm: chuyển `access` lên **trước** `account` (khi hoà, "xin quyền" cụ thể hơn "đăng nhập"); thêm luật `other` bắt cuối bảng với `confidence = 0.3` thay vì trả `None`.

Từ khoá gây nhầm nhiều nhất: `"dang nhap"` trong luật `account` (`classifier.py:161`) kéo 5/13 ca sai.

### 3.4 Chunker — ba tham số chết [KIỂM CHỨNG]

- **`target_tokens = 500` không bao giờ được đọc.** `chunker.py:96` nhận và lưu, `chunk()` (`:106-145`) chỉ dùng `max_tokens`.
- **Chồng lấn 80 token không bao giờ chạy.** Đo trên kho thật: **0/64 cặp chunk liên tiếp có chồng lấn**. `overlap` chỉ tồn tại trong `_split_long_text()`, mà hàm đó chỉ được gọi khi một mục vượt 800 token.
- **`estimate_tokens` ước thấp ~35%.** `chunker.py:37` dùng `số_từ × 1,5`; đo trên kho thật hệ số khoảng 2,3. "Trần 800 token" thực chất là ~1.230 token.

Thêm một lỗi sẽ phát tác ngay khi có bài KB dài: `chunker.py:64` tách câu bằng `(?<=[.!?…])\s+`, mà dấu chấm trong "1.", "2." cũng khớp ⇒ **các bước đánh số bị cắt rời khỏi nội dung**. Hướng dẫn IT toàn là bước đánh số. Tái hiện được:
```
phần 0: '1. Mở Control Panel trên máy tính. 2.'   <- số bước 2 mồ côi
phần 2: 'Chọn mục Devices and Printers. 3.'       <- số bước 3 mồ côi
```

### 3.5 Thuật toán gợi ý — năm điểm phi lý [KIỂM CHỨNG]

Công thức `0.5·skill + 0.35·load + 0.15·duty`, `MAX_LOAD = 20`.

| Kịch bản | Điểm |
|---|---|
| Chuyên gia (skill 3), **quá tải** (load 24), trong ca | **0,650** |
| Người mới (skill 0), **hoàn toàn rảnh**, trong ca | **0,500** |
| skill 3, load 20 | 0,650 |
| skill 3, **load 40** | **0,650** |

1. **Agent giỏi nhưng quá tải vẫn được đề xuất trước người rảnh** (0,650 > 0,500). Người giỏi nhất mỗi lĩnh vực bị dồn việc có hệ thống.
2. **Trên `MAX_LOAD` mọi mức quá tải như nhau** — `min(load/max_load, 1.0)` bão hoà, load 20 và load 40 cùng điểm. Mất khả năng thấy ai đang chìm.
3. **Không tính SLA sắp hết hạn** — 3 ticket MEDIUM còn 20 phút nữa vi phạm được tính tải ngang 3 ticket MEDIUM còn 2 ngày.
4. **`is_on_duty()` thưởng cho người vắng mặt** — agent nghỉ phép cả tuần nhưng sáng nay mở máy xem mail vẫn được tính "đang trực". Agent dùng SSO/"remember me" thì `last_login_at` cũ ⇒ **vĩnh viễn ngoài ca**.
5. **Không có ngưỡng sàn** — `suggest()` luôn trả đủ top 3 bất kể điểm thấp đến đâu. Agent tệ nhất có thể (điểm 0,045) vẫn được trình bày như một "gợi ý".

Đề xuất: đổi trọng số về **0,40/0,45/0,15** (chỉ sửa mặc định ở `config.py:76-78`, 15 phút) ⇒ chuyên gia quá tải 0,55 < người mới rảnh 0,60. Thêm ngưỡng sàn 0,35 trả `[]` kèm lý do "Không có Agent phù hợp".

Điểm cộng cần giữ: `AssigneeScorer` là lớp thuần, `now` truyền từ ngoài, `load_snapshots` tránh N+1 bằng một truy vấn, hai ghi chú `★` ở `:192` và `:202` cho thấy tác giả đã gặp và sửa đúng hai bẫy JOIN kinh điển. **Vấn đề nằm ở mô hình nghiệp vụ, không ở cài đặt.**

### 3.6 Kế hoạch dữ liệu cho RAG

Hiện có 20 bài, TB 350 từ, 65 chunk. **Số lượng đạt cam kết** ("15–20 bài từ Sprint 0"), và chất lượng tốt hơn "dữ liệu giả sơ sài" — frontmatter đủ, chia mục hợp lý, có tham chiếu chéo, văn phong helpdesk thật. Ba hạn chế: quá ngắn, mỗi chủ đề chỉ một cách diễn đạt, và **không có nội dung phủ định** (không bài nào nói "việc X không thuộc phạm vi IT") nên chatbot không có tài liệu nào để dựa vào mà từ chối đúng cách.

**Mục tiêu: 45–50 bài, 800–1.200 từ/bài** (~400 chunk).

| Nguồn | Bài | Bản quyền |
|---|---|---|
| Tự viết theo quy trình công ty hư cấu | 15 | An toàn tuyệt đối |
| Microsoft Learn / Google Workspace Help | 10 | Diễn đạt lại hoàn toàn, ghi "Tham khảo:" cuối bài |
| FAQ IT của các trường đại học | 5 | Chỉ lấy ý tưởng chủ đề, không lấy câu chữ |
| Tài liệu mã nguồn mở (CC-BY/GFDL) | 5 | Được dùng lại nếu ghi công đúng giấy phép |

Quy tắc thực thi được để tránh bản quyền: **đọc xong đóng tab rồi mới viết**. Bối cảnh hoá về công ty hư cấu (đổi tên hệ thống, đường dẫn, phòng ban). Thêm trường `source`/`license` vào frontmatter — `seed_kb.py:52-67` đã hỗ trợ khoá tuỳ ý nên **không cần sửa code**.

Khuôn mẫu bài chuẩn (mỗi mục 150–250 từ = đúng 1 chunk):
```markdown
## Triệu chứng            <- dùng ĐÚNG từ ngữ người dùng gõ
## Nguyên nhân thường gặp
## Cách tự khắc phục       <- các bước đánh số
## Khi nào cần tạo ticket  <- ranh giới phạm vi, nuôi tỉ lệ từ chối đúng
## Câu hỏi thường gặp      <- biến thể không dấu / viết tắt / tiếng Anh
## Nguồn tham khảo
```

Ước lượng: **~4,5 ngày người**, chia 3 người là 1,5 ngày lịch. Không phụ thuộc code, làm song song được.

### 3.7 Cơ hội đang bỏ lỡ: hybrid search

`kb_articles.search_vector` (tsvector + `immutable_unaccent`) **đã tồn tại** trong `migrations/versions/0004_search_triggers.py:52-55` và đang dùng ở `knowledge/repository.py:20-26`. Toàn bộ hạ tầng cho hybrid search đã có, chỉ chưa nối vào `Retriever`. Ghép BM25 + vector bằng RRF là **~3 giờ** và cứu đúng nhóm rủi ro mà `07` §7 gọi tên: "tiếng Việt không dấu, viết tắt, lẫn tiếng Anh".

---

## 4. Nghiệp vụ — chỗ kế hoạch tự nó chưa hợp lý

Code làm đúng kế hoạch vẫn sai. Cần sửa **tài liệu**, không phải chỉ sửa code.

### 4.1 Mở lại ticket — mâu thuẫn ba chiều

- `01 §11` chốt Q3 = "reopen trong 7 ngày", và hỏi về ticket đã **đóng**
- `03 §5` vẽ `CLOSED` là trạng thái cuối, không đường ra; reopen chỉ từ `RESOLVED`
- `02 US-14` bắt tự động `RESOLVED → CLOSED` sau **3 ngày**

⇒ Cửa sổ 7 ngày thực tế **chỉ còn 3 ngày**. Người dùng đi công tác một tuần về, sự cố tái diễn, buộc tạo ticket mới ⇒ chỉ số "tỉ lệ mở lại" mà `03 §5` tự hào đo được sẽ **luôn ≈ 0**.

Nặng hơn: **không có user story nào cho hành động reopen**. Nó có trong máy trạng thái, trong enum `REOPENED`, trong ma trận quyền — nhưng không story, không AC, không SP, không PIC. Code đã cài (`_check_reopen_window`) mà không ai review theo AC.

> **Đề xuất:** sửa `01 §11` Q3 cho khớp `03 §5`; đặt `AUTO_CLOSE_AFTER_DAYS = 7` bằng đúng cửa sổ reopen (hoặc thêm `CLOSED → IN_PROGRESS` cho Admin); thêm **US-44 "Người yêu cầu mở lại ticket" — M, 3 SP**.

### 4.2 `PENDING_REQUESTER` là hố đen

Ba tài liệu nói ba công thức SLA khác nhau:

| Nơi | Nói gì |
|---|---|
| `03 §6` quy tắc 2 | Thời gian chờ khách **không tính**, cộng dồn `paused_duration_seconds` |
| `03 §6` bảng trạng thái | `BREACHED` = quá `sla_resolution_due_at` — không nhắc paused |
| `04 §10` truy vấn 2 | Job SLA **vẫn cảnh báo** cả ticket đang chờ khách |

Và không tài liệu nào trả lời: **khách không phản hồi thì sao?** Không nhắc lại, không tự đóng, SLA thì "đã dừng" nên ticket **không bao giờ hiện `AT_RISK` hay `BREACHED`** — biến mất khỏi mọi màn hình giám sát, không ai chịu trách nhiệm.

> **Đề xuất:** `03 §6` nêu **một** công thức duy nhất, `04 §10` loại `PENDING_REQUESTER` và trừ `paused_seconds`. Thêm **US-45 "Tạm dừng và nối lại đồng hồ SLA" — M, 3 SP** và **US-46 "Nhắc và tự đóng ticket chờ khách" — S, 3 SP**.

### 4.3 `AT_RISK` trộn đồng hồ treo tường với giờ làm việc

`03 §6` định nghĩa `AT_RISK` = "còn ≤ 25% thời gian", `04 §10` cài bằng `(due_at - created_at) * 0.25` — lấy **thời gian thực tế trôi qua**, trong khi hạn tính theo **giờ làm việc**.

Ticket URGENT tạo 17:00 thứ Sáu, hạn 11:30 thứ Hai: tổng 66,5 giờ, 25% = 16,6 giờ ⇒ ticket chuyển **vàng từ tối Chủ nhật**, khi chưa tiêu một phút giờ làm việc nào. Sáng thứ Hai toàn bộ hàng chờ đỏ/vàng ⇒ Agent học cách bỏ qua màu.

> **Đề xuất:** `03 §6` ghi rõ "25% **ngân sách giờ làm việc còn lại**"; bổ sung `business_minutes_between(a, b)`. **1 SP**.

### 4.4 Không phân biệt Sự cố và Yêu cầu dịch vụ

`01 §3` ghi phạm vi là "Incident + Service Request". Nhưng `03 §1` **cấm dùng từ "request"**, và `04 §4.3` bảng `tickets` **không có cột `type`**. SLA suy ra 100% từ `priority`.

"Mất mạng toàn văn phòng" và "Cấp quyền truy cập thư mục" cùng MEDIUM ⇒ cùng hạn 4 giờ/24 giờ, trong khi yêu cầu cấp quyền thường cần **duyệt của quản lý** (không phải lỗi IT) và không có khái niệm "phản hồi đầu tiên". Báo cáo US-38 gộp hai loại vào một trung vị ⇒ số vô nghĩa.

> **Đề xuất:** thêm `ticket_type` NOT NULL DEFAULT 'INCIDENT'; `sla_policies` đổi UNIQUE thành `(priority, ticket_type)`. **US-47 — S, 3 SP**.

### 4.5 Gợi ý người xử lý dựa trên dữ liệu không tồn tại

`07 §2.4` viết công thức có `W_DUTY * agent.is_on_duty(now)`, nhưng `03 §3`/`04 §4` **không có bảng ca trực nào**, và **không story nào** cho phép nhập lịch trực hay nghỉ phép. Tương tự `agent_skills` có bảng và có `PUT /users/{id}/skills` trong `06`, nhưng US-07 không nhắc tới kỹ năng ⇒ w1 (trọng số lớn nhất, 0,5) không có đường nhập liệu.

> **Đề xuất:** **US-48 "Trạng thái sẵn sàng của Agent" — M, 5 SP** (bảng `agent_availability`, agent `ON_LEAVE` **bị loại khỏi gợi ý, không phải trừ điểm**) và **US-49 "Quản lý kỹ năng Agent" — M, 2 SP**. Thêm trần cứng `WIP_LIMIT` mặc định 10.

### 4.6 Không có leo thang

`03 §10` tự nhận "auto-escalation: chưa có", `US-35` chỉ gửi thông báo — **cho assignee**, chính là người đang nghỉ phép/ốm, tức nguyên nhân gây trễ. Ticket URGENT nằm im, không ai được cảnh báo.

> **Đề xuất:** **US-50 "Leo thang khi vi phạm SLA" — S, 5 SP**: quá hạn phản hồi ⇒ tự bỏ assignee, trả về hàng chờ, ghi event `UNASSIGNED` (enum **đã có sẵn giá trị này** nhưng không ai dùng). Bổ sung `ASSIGNED → NEW` vào bảng `03 §5` — hiện **Agent không có cách nào trả lại ticket nhận nhầm**.

### 4.7 Đánh giá hài lòng — ẩn danh giả, chấm nhầm lần xử lý

- `US-42/43` yêu cầu ẩn tên người đánh giá với Agent. Nhưng `US-11` yêu cầu chi tiết ticket trả về đánh giá, và mỗi ticket chỉ có một requester ⇒ Agent mở ticket là biết ngay ai chấm. **Ẩn danh là giả** — mâu thuẫn trực tiếp giữa hai AC.
- `US-41`: 1 đánh giá/ticket + sửa trong 24h. Kết hợp reopen: khách chấm 1 sao lần đầu → mở lại → Agent xử lý tốt lần hai → **không cách nào chấm lại**. Điểm Agent phản ánh lần thất bại.

> **Đề xuất:** bỏ yêu cầu ẩn danh (không thực thi được) hoặc `US-11` không trả `rater_id`; `US-41` thêm AC: reopen ⇒ đánh giá cũ `is_superseded`, cho chấm lại sau lần resolve thứ hai.

### 4.8 Không tạo được ticket thay mặt người khác

`BR-01`: "`requester_id` **luôn** là người đang đăng nhập". Quy tắc chống giả mạo đúng đắn — nhưng nó **cấm luôn** nghiệp vụ phổ biến nhất của mọi helpdesk: nhân viên gọi điện, Agent nhập hộ.

Dây chuyền hậu quả: ticket ghi tên Agent ⇒ nhân viên thật **không thấy ticket của mình** (BR-09) ⇒ không nhận thông báo ⇒ **lời mời đánh giá gửi cho chính Agent đã xử lý**. `01 §1` nêu vấn đề "yêu cầu nằm rải rác trong inbox" nhưng kế hoạch lại chặn con đường đưa yêu cầu ngoài luồng vào hệ thống ⇒ **G1 (tập trung hoá 100%) không đạt được về mặt thiết kế**.

> **Đề xuất:** **US-52 — S, 3 SP**: thêm `created_by_id`; `requester_id` được khác `created_by_id` **chỉ khi** người tạo là Agent/Admin. Sửa `BR-01` cho đúng.

### 4.9 Không có cách xử lý sự cố diện rộng

Mất mạng toàn văn phòng ⇒ 50 nhân viên tạo 50 ticket URGENT trong 10 phút ⇒ 50 lần gọi LLM, 50 đồng hồ SLA, sau đó **50 lượt vi phạm đồng loạt**, dashboard méo, Agent gõ cùng một `resolution_note` 50 lần.

> **Đề xuất:** **US-55 "Gộp ticket trùng" — S, 5 SP** (`parent_ticket_id`). Tỉ lệ giá trị/chi phí cao nhất trong danh sách bổ sung.

### 4.10 Ba mục tiêu đo bằng chỉ số tự thiên vị

- **G1** "mọi ticket có assignee sau ≤ 5 phút" — nhưng US-20 chốt "gợi ý, không tự động giao". Không cơ chế nào đạt được G1.
- **G2** "≥ 70% AI gán đúng" đo bằng "Agent không sửa ⇒ `was_accepted = true`". **Im lặng bị tính là đồng ý.** Agent không bao giờ mở tab phân loại thì độ chính xác báo cáo là 100%.
- **G3** "≥ 20% phiên chat không tạo ticket" — người dùng chat thất bại rồi tự vào form tạo ticket bị tính là **tự phục vụ thành công**.

### 4.11 Mâu thuẫn nhỏ giữa tài liệu (sửa 30 phút)

| Vấn đề | Nơi A | Nơi B |
|---|---|---|
| Mã ticket 4 hay 5 chữ số | `02 US-08`: `NNNN` | `04 §4.3` `lpad(...,5)` |
| Phân trang snake hay camel | `02 US-10`: `page_size` | `06 §4`: `pageSize` |
| Tên cột SLA đã báo trễ | `02 US-35`: `sla_breached_notified_at` | `04 §4.3`: `sla_breached_at` |
| Ai đóng ticket RESOLVED | `03 §5`: Requester/Hệ thống/Admin | `06 §5` + code: mọi vai trò |
| Tổng SP | `02 §0`: 177 SP | Cộng lại 43 story = **169 SP** |

Dòng cuối đáng lưu ý: cảnh báo năng lực ở `02 §0` ("177 SP / năng lực 160 ⇒ không có vùng đệm") tính trên con số sai.

---

## 5. Tiến độ thật — đối chiếu từng AC

| Nhóm | SP | Tỉ lệ |
|---|---|---|
| Must đạt đủ AC (US-02, 03, 04, 19, 29) | **20 / 96** | **21%** |
| Must có code nhưng chưa đạt AC | 71 / 96 | 74% |
| Must chưa có gì (US-07) | 5 / 96 | 5% |

**Feature bằng 0:** F6 Thông báo (15 SP) · F7 Dashboard (16 SP) · F8 Đánh giá (8 SP) · US-09 đính kèm file (5 SP).

**Xếp theo mức chặn demo:**
1. F7 Dashboard — Admin vào là thấy trang trống (`recharts` đã cài nhưng không import ở đâu)
2. US-07 quản trị người dùng — không demo được UC-06, phải seed tay
3. F6 Thông báo — ngoài việc thiếu, còn làm worker báo lỗi mỗi 5 phút
4. F8 Đánh giá — UC-07 không demo được
5. US-09 đính kèm — "gửi ảnh chụp lỗi" là kịch bản demo tự nhiên nhất của helpdesk

**Cột và bảng đã migrate nhưng không dòng code nào ghi:** `paused_seconds`, `sla_warned_at`, `sla_breached_at`, `idempotency_keys`, `ticket_ratings`, `notifications`. Nhìn ERD tưởng đã xong.

---

## 6. Những chỗ làm tốt — giữ nguyên khi refactor

Không phải khách sáo. Đây là các biện pháp đã bị tấn công thật và không phá được:

**Phân quyền**
- Cách ly ticket áp ngay trong `WHERE` (`policies.py:21-29`, `repository.py:97`) — không đường nào đọc ticket mà bỏ qua nó. `totalItems` đúng phạm vi: E1=17, E2=1, Admin=18, không rò tổng số ticket hệ thống.
- **404 thay vì 403** nhất quán trên cả 6 endpoint con của ticket.
- **Phiên chat riêng tư tuyệt đối** — kể cả ADMIN nhận 404. Route SSE kiểm quyền **trước** khi mở luồng, tránh bẫy "đã stream thì không trả mã lỗi được".
- **Bản nháp KB kín cả ba hướng** (ép `?status=DRAFT`, mở thẳng slug, `/suggest`). `retriever.py:33` lọc `PUBLISHED` ngay trong SQL ⇒ **RAG không rò nội dung nháp**.
- **Chống leo thang qua schema:** `StrictModel` đặt `extra="forbid"` toàn cục; `UpdateProfileRequest` cố tình không có `role`/`isActive`/`email`, và đã có test riêng.

**Xác thực**
- Xoay vòng refresh token hoạt động; **dùng lại token cũ thu hồi toàn bộ chuỗi**. Lưu SHA-256, cookie `HttpOnly`+`SameSite=Strict`.
- **Vai trò lấy từ DB, không tin claim JWT** — token có `role:"ADMIN"` giả vẫn trả `EMPLOYEE`. Tốt hơn mức tài liệu yêu cầu.
- `alg=none` bị chặn; thuật toán cố định từ cấu hình nên không có algorithm confusion. bcrypt cost 12 xác nhận từ dữ liệu thật. Chống timing attack hoạt động (0,24s vs 0,25s).

**Dữ liệu**
- **Model khớp migration tuyệt đối:** 0 lệch cột, 13/13 CHECK, 12/12 UNIQUE, 36/36 FK kèm `ondelete`, 9/9 enum đủ giá trị, 22 model ↔ 22 bảng. `vector(1536)` khớp `EMBEDDING_DIMENSIONS`.
- **SQL injection không có đường vào:** `plainto_tsquery` + bindparam, `sortBy` qua danh sách trắng. `x'); DROP TABLE tickets;--` trả 0 kết quả, bảng còn nguyên.
- Phân trang ticket có tie-breaker `Ticket.id.desc()` đúng cách; `pagination.py:18` chặn `ge=1, le=100`.
- Soi hết 14 chỗ `except Exception` — tất cả đều có `logger.warning`/`logger.exception` hoặc `raise ... from exc`.
- `suggestions.py:198-201` xử lý đúng bẫy LEFT JOIN NULL bằng `case((Ticket.id.is_(None), 0), ...)`.

**AI**
- **Chống bịa đặt được thiết kế trên mức yêu cầu:** khi `not retrieval.has_context` thì `return` trước khi chạm `stream()`; `build_rag_prompt()` **ném `ValueError`** nếu chunks rỗng (chốt chặn thứ hai chống lập trình viên tương lai đi vòng); `FakeLlmClient` đếm riêng `complete_count` và `stream_count` chính xác để test khẳng định model không bị gọi.
- `RAG_SYSTEM` bắt buộc trích dẫn, cấm kiến thức ngoài, có cảnh báo injection và quy tắc về mật khẩu — vượt yêu cầu thiết kế.
- `prompts.py:133-143` **tự ghi rõ rằng 74% là của tầng dự phòng, không phải của AI**. Hiếm đồ án nào tự thú như vậy.
- `AssigneeScorer` là lớp thuần, `now` truyền từ ngoài, một truy vấn tránh N+1.
- Tập đánh giá 50 ca có ghi `note` giải thích nhãn cho ca khó; 3 ca tricky thật sự sâu sắc.

**Frontend**
- Không có `dangerouslySetInnerHTML` ở đâu cả — đầu ra LLM render qua React text node, hiện không tạo được XSS.

---

## 7. Thứ tự đề xuất

### Tuần này (P0)
| # | Việc | Ước lượng |
|---|---|---|
| 1 | `__mapper_args__` cho `Ticket` + bắt `StaleDataError` | 1 giờ |
| 2 | `BUSINESS_TIMEZONE` cho `sla.py` và `is_on_duty()` | 2 giờ |
| 3 | Sửa `FakeLlmClient` (2 luật + hạ confidence) | 30 phút |
| 4 | BR-13 bảo vệ cả `priority` | 1 giờ |
| 5 | Gỡ hoặc viết 2 task của Celery beat | 30 phút |
| 6 | 4 ô máy trạng thái (P0-7) + test đủ 49 ô | 2 giờ |
| 7 | `UpdateOwnTicketRequest` cho Employee | 1 giờ |
| 8 | Đổi đích đăng nhập của ADMIN sang `/queue` | 15 phút |
| 9 | Cắm embedding thật + reindex | 1 giờ |

### Tuần sau (P1)
`scripts/eval_rag.py` (4h) · test ma trận phân quyền (2h) · `include_object` cho alembic (30ph) · seed vào CI + bỏ skip DB khi `CI=true` (1h) · security header (30ph) · commit trước khi `await` LLM (1h) · tie-breaker lịch sử (15ph) · `paused_seconds` (3h) · `Idempotency-Key` (3h) · sửa luật phân loại (1,5h) · trọng số gợi ý + ngưỡng sàn (1,5h)

### Song song, không phụ thuộc code
Bổ sung kho KB lên 45–50 bài (**4,5 ngày người, chia 3 người = 1,5 ngày lịch**) · mở rộng `rag_eval.jsonl` 10 → 30 ca · thêm 25 ca phân loại (không dấu, viết tắt, `other`, LOW/URGENT)

### Cần quyết định của Scrum Master
12 story bổ sung, **40 SP**, trong đó Must là US-44, US-45, US-48, US-49, US-54 (**16 SP**). Xem §4.

---

## 8. Ghi chú vận hành

- **Dọn dữ liệu thử nghiệm trước demo:** 3 ticket rác trong DB dev (`HD-202608-02137` "Audit test ticket", `02139` "Ticket thu hai kiem thu", `02142` "Ticket cua employee2"), 1 bài KB nháp slug `nhap-mat-khau-root-may-chu`, 1 phiên chat rỗng.
- **`migrations/versions/0005` chẩn đoán sai nguyên nhân:** không phải SQLAlchemy tính `now()` một lần lúc sinh migration, mà `0002_initial_schema.py` ghi `server_default="now()"` dạng **chuỗi** nên PostgreSQL đóng băng lúc `CREATE TABLE` — mỗi môi trường đông cứng một mốc khác nhau. Dòng `:25` nói "sáu cột" trong khi thực tế là 10. Nên sửa docstring kẻo người sau hiểu sai.
- **Rate limiter dò Redis đúng một lần lúc import** (`rate_limit.py:144-164`). Redis chớp tắt lúc khởi động ⇒ tụt về bộ nhớ **vĩnh viễn**, chỉ một dòng warning. Với `--workers 4`, giới hạn thành 4×5 = 20 lần thử/15 phút.
- **`DEBUG` và `is_production` khai báo nhưng không dòng nào đọc.** Đặt `DEBUG=false` hiện không có tác dụng gì.
- **Frontend mặc định chạy MSW** (`.env.example:7` `VITE_USE_MOCK=true`), và `handlers.ts:606` mock `/notifications/unread-count` trả cứng `{count: 3}` cho endpoint **không tồn tại ở backend**. Rủi ro: demo chạy trơn tru trên mock mà không ai nhận ra backend chưa có.
- **Khoá tài khoản từ chối dịch vụ:** bộ đếm theo email, không kết hợp IP ⇒ 5 request mỗi 15 phút giữ `admin@company.com` ngoài hệ thống vô thời hạn. Đã tái hiện.
- **Không có hệ thống audit** — không bảng, không model, không writer. Phá vỡ US-05 và AC của US-06. Gap ở tầng schema, cần migration.
