# 10 — Chiến lược Kiểm thử

| | |
|---|---|
| Phiên bản | 1.0 (bản khung — QA hoàn thiện thành Test Plan / Test Case / Test Report) |
| PIC | Trần Quang Ngọc (QA/Tester), mỗi module owner chịu trách nhiệm unit test của module mình |
| Deliverable bắt buộc | Test Plan, Test Cases, Test Report (Guideline §11) |

> Tài liệu này định nghĩa **chiến lược**: test cái gì, ở tầng nào, và cái gì bắt buộc phải có. Test case chi tiết là deliverable riêng do QA soạn dựa trên tiêu chí chấp nhận ở tài liệu 02.

---

## 1. Kim tự tháp kiểm thử

```
            ╱╲          Manual / Exploratory  — QA, mỗi sprint
           ╱  ╲         ~15 kịch bản đầu-cuối
          ╱────╲
         ╱      ╲       API Tests  — ~60 test
        ╱        ╲      Đi qua HTTP, DB thật, LLM giả
       ╱──────────╲
      ╱            ╲    Integration Tests  — ~40 test
     ╱              ╲   Repository + Service với DB thật
    ╱────────────────╲
   ╱                  ╲ Unit Tests  — ~120 test
  ╱____________________╲ Lớp thuần, KHÔNG chạm DB, chạy trong mili-giây
```

**Nguyên tắc phân bổ:** logic dễ sai nhất của hệ thống (máy trạng thái, tính SLA, chính sách phân quyền, chia chunk, tính điểm gợi ý) đều là **lớp thuần không I/O** — nên được test dày nhất ở tầng rẻ nhất và nhanh nhất.

| Tầng | Số lượng | Thời gian chạy | Phụ thuộc | Chạy khi nào |
|---|---|---|---|---|
| Unit | ~120 | < 5 giây | Không | Mỗi lần lưu file |
| Integration | ~40 | < 60 giây | PostgreSQL | Mỗi commit |
| API | ~60 | < 90 giây | PostgreSQL, Redis, LLM giả | Mỗi PR |
| Manual | ~15 kịch bản | ~2 giờ | Staging đầy đủ | Cuối mỗi sprint |

**Mục tiêu độ phủ: ≥ 70%** cho tầng service và các lớp thuần (yêu cầu bắt buộc từ DoD). Độ phủ không phải mục tiêu tự thân — nhưng dưới 70% ở tầng service nghĩa là có nhánh nghiệp vụ chưa ai chạy thử bao giờ.

---

## 2. Unit test — nơi tập trung giá trị

Các lớp bắt buộc phải có độ phủ **≥ 90%**:

| Lớp | File test | Ca kiểm thử trọng tâm |
|---|---|---|
| `TicketStateMachine` | `test_state_machine.py` | **Toàn bộ 49 ô** của bảng bước chuyển ở tài liệu 03 §5 — cả ô cho phép lẫn ô bị cấm. Kiểm tra theo từng vai trò |
| `SlaCalculator` | `test_sla_calculator.py` | Ticket tạo 17:00 thứ Sáu; tạo đúng 17:30; tạo trong ngày lễ; SLA vắt qua nhiều ngày; trừ thời gian `PENDING_REQUESTER` |
| `TicketAccessPolicy` | `test_access_policy.py` | Từng vai trò × từng hành động; Employee xem ticket người khác; Agent đổi trạng thái ticket không phải của mình |
| `TextChunker` | `test_chunker.py` | Bài viết không có tiêu đề; tiêu đề lồng nhau; chunk vượt kích thước tối đa; chunk quá ngắn bị gộp; văn bản tiếng Việt có dấu |
| `AssigneeRecommender` | `test_recommender.py` | Không có Agent nào rảnh; tất cả cùng tải; Agent bị khoá; không ai có kỹ năng khớp |
| `PasswordHasher`, `TokenService` | `test_security.py` | Token hết hạn; token sai chữ ký; token bị sửa payload; refresh token tái sử dụng |

**Quy tắc:** unit test **không được** dùng `Session`, không được gọi mạng, không được đọc file. Nếu một test cần những thứ đó, nó thuộc tầng integration.

### Ví dụ ca biên phải có

```python
def test_sla_ticket_created_friday_evening():
    """Ticket URGENT (SLA 4 giờ làm việc) tạo lúc 17:00 thứ Sáu GIỜ VIỆT NAM
    phải có hạn là 12:00 trưa thứ Hai, không phải 21:00 thứ Sáu.

    Mốc đầu vào phải dựng theo giờ Việt Nam rồi quy về UTC. Dựng thẳng bằng
    `tzinfo=UTC` rồi đọc như giờ làm việc là cách test và code cùng sai một
    kiểu và che nhau — đã xảy ra một lần."""

def test_state_machine_cannot_skip_from_new_to_resolved():
    """Không được nhảy thẳng NEW → RESOLVED, bỏ qua việc giao việc."""

def test_employee_cannot_view_other_users_ticket():
    """visible_filter của Employee phải loại trừ ticket của người khác."""

def test_chatbot_refuses_when_no_relevant_document():
    """Điểm similarity cao nhất < ngưỡng ⇒ trả về câu từ chối, KHÔNG gọi LLM sinh câu trả lời."""
```

---

## 3. Integration test

Dùng PostgreSQL thật (testcontainers hoặc một database test riêng). Mỗi test chạy trong transaction và rollback ở cuối.

| Nhóm | Kiểm tra gì |
|---|---|
| Repository | Truy vấn trả đúng dữ liệu; phân trang đúng; bộ lọc quyền được áp dụng; `EXPLAIN` không có `Seq Scan` trên bảng lớn |
| Service | Transaction đúng: đổi trạng thái **và** ghi `ticket_events` cùng lúc; lỗi giữa chừng thì rollback cả hai |
| Ràng buộc DB | Vi phạm CHECK constraint bị chặn; UNIQUE trên `ticket_ratings.ticket_id` hoạt động; không xoá được category còn bài viết |
| Optimistic lock | Hai lệnh nhận ticket đồng thời — đúng một cái thành công |
| Idempotency | Job SLA chạy 3 lần chỉ sinh 1 thông báo; index lại bài viết 2 lần không tạo chunk trùng |
| Migration | `upgrade head` → `downgrade -1` → `upgrade head` chạy sạch |

---

## 4. API test

Đi qua HTTP thật với `TestClient`, DB thật, và `FakeLlmClient`.

| Nhóm | Ví dụ |
|---|---|
| Luồng hạnh phúc | Đăng ký → đăng nhập → tạo ticket → Agent nhận → xử lý → đóng → đánh giá |
| **Bảo vệ endpoint** | Test quét toàn bộ route, khẳng định không có endpoint nghiệp vụ nào thiếu xác thực (tài liệu 08 §2.4) |
| **Ma trận phân quyền** | Sinh tham số từ bảng ở tài liệu 06 §5 — mỗi ô có test cho phép và test từ chối |
| Validation | Tiêu đề 4 ký tự ⇒ 422 với thông điệp đúng field; gửi field lạ ⇒ 422 (do `extra="forbid"`) |
| Định dạng lỗi | Mọi mã lỗi trả về đúng hình dạng `{error: {code, message, requestId}}` |
| Phân trang | `pageSize=1000` bị chặn ở 100; `page` vượt tổng số trang trả `data: []` |
| Rate limit | Đăng nhập sai 6 lần ⇒ 429 kèm `Retry-After` |
| Idempotency | Gửi `POST /tickets` hai lần cùng `Idempotency-Key` ⇒ chỉ một ticket được tạo |
| SSE | Stream chatbot trả về đúng thứ tự sự kiện: `citations` → `token`* → `done` |

---

## 5. Kiểm thử AI

AI không tất định — không thể assert bằng so sánh chuỗi. Chiến lược hai tầng:

| Tầng | Cách làm |
|---|---|
| **Test tự động (CI)** | Dùng `FakeLlmClient` trả về kết quả đặt trước. Kiểm tra **luồng xử lý**: confidence thấp thì không áp dụng; LLM lỗi thì `ai_status=FAILED`; AI không ghi đè lựa chọn của người; retry đúng số lần; circuit breaker mở sau 5 lỗi |
| **Đánh giá chất lượng (thủ công, định kỳ)** | Chạy `scripts/eval_classification.py` và `scripts/eval_rag.py` trên tập đánh giá ở tài liệu 07 §5. Ghi kết quả vào Test Report |

**Năm câu hỏi bắt buộc phải từ chối** (tài liệu 07 §5.2) là test quan trọng nhất của F4. Tỉ lệ mục tiêu: **100%**. Chatbot bịa ra các bước thao tác IT sai có thể khiến nhân viên làm hỏng máy — đây là lỗi nghiêm trọng hơn mọi lỗi giao diện.

---

## 6. Kiểm thử phi chức năng

| Loại | Cách làm | Tiêu chí đạt |
|---|---|---|
| Hiệu năng | `locust` hoặc `k6`: 100 người dùng ảo, 5 phút, luồng đọc-nhiều | p95 < 500 ms, 0 lỗi |
| Hiệu năng DB | `EXPLAIN ANALYZE` các truy vấn ở tài liệu 04 §10 với **≥ 30.000 ticket giả** | Không có `Seq Scan` trên `tickets` |
| Bảo mật | Thử thủ công: đổi ID trong URL để xem ticket người khác; gửi thêm field `role` khi đăng ký; upload file `.html`; XSS trong tiêu đề ticket | Tất cả bị chặn |
| Bảo mật (tự động) | `gitleaks` quét bí mật; `pip-audit` quét CVE trong dependency | Không có phát hiện nghiêm trọng |
| Khôi phục | Diễn tập khôi phục từ backup | Khôi phục thành công, ghi lại thời gian thực tế |
| Suy giảm chức năng | Tắt LLM ⇒ tạo ticket vẫn được. Tắt Redis ⇒ hệ thống vẫn chạy. Tắt worker ⇒ ticket vẫn tạo/xử lý được | Đúng như thiết kế ở tài liệu 08 §9 |

**Bài kiểm thử suy giảm chức năng là bắt buộc.** Thiết kế tuyên bố "AI hỏng không chặn vòng đời ticket" — điều đó chỉ đúng nếu đã thực sự thử tắt LLM và xác nhận.

---

## 7. Kịch bản kiểm thử thủ công (dùng cho demo)

15 kịch bản đầu-cuối, cũng chính là kịch bản diễn tập trước buổi demo với Trainer:

| # | Kịch bản | Vai trò |
|---|---|---|
| 1 | Đăng ký → đăng nhập → thấy màn hình đúng vai trò | Employee |
| 2 | Tạo ticket, thấy gợi ý bài viết KB khi đang gõ | Employee |
| 3 | Ticket được AI phân loại trong 30 giây, hiện đúng category + độ tin cậy | Employee |
| 4 | Agent thấy ticket trong hàng chờ, sắp xếp theo SLA | IT Agent |
| 5 | Agent nhận ticket, hai Agent cùng nhận thì chỉ một thành công | IT Agent |
| 6 | Agent bình luận, Employee nhận được thông báo | Cả hai |
| 7 | Agent viết ghi chú nội bộ, **Employee không thấy** | Cả hai |
| 8 | Agent chuyển RESOLVED (bắt buộc nhập ghi chú xử lý) | IT Agent |
| 9 | Employee đánh giá 5 sao, không đánh giá lại được lần hai | Employee |
| 10 | Hỏi chatbot câu **có** trong tài liệu → trả lời đúng kèm trích dẫn | Employee |
| 11 | Hỏi chatbot câu **không** có trong tài liệu → **từ chối, không bịa** | Employee |
| 12 | Chuyển từ chat sang tạo ticket, thông tin được điền sẵn | Employee |
| 13 | Admin đăng bài KB mới → chatbot trả lời được câu liên quan sau ≤ 5 phút | Admin |
| 14 | Dashboard hiển thị đủ 6 chỉ số, đổi khoảng thời gian thì số liệu đổi theo | Admin |
| 15 | Employee thử mở URL ticket của người khác → nhận 404 | Employee |

Kịch bản **11** và **15** là hai kịch bản dễ hỏng nhất và cũng là hai kịch bản gây ấn tượng mạnh nhất khi demo thành công.

---

## 8. Dữ liệu kiểm thử

| Loại | Nguồn |
|---|---|
| Fixture unit test | Đối tượng dựng trong bộ nhớ, không chạm DB |
| Fixture integration | `factory-boy` — `UserFactory`, `TicketFactory`, `ArticleFactory` |
| Dữ liệu staging | `scripts/seed.py` — 60 ticket, 20 bài KB, 9 người dùng đủ 3 vai trò |
| Dữ liệu kiểm thử hiệu năng | `scripts/seed_perf.py` — 30.000 ticket, chỉ chạy ở môi trường riêng |
| Tập đánh giá AI | `tests/fixtures/classification_eval.jsonl` (50 ca), `rag_eval.jsonl` (30 ca) |

**Nguyên tắc:** mỗi test tự dựng dữ liệu của mình, không phụ thuộc thứ tự chạy, không phụ thuộc dữ liệu do test khác để lại. Test phụ thuộc thứ tự sẽ hỏng ngẫu nhiên trong CI và làm cả nhóm mất niềm tin vào bộ test.

---

## 9. Cổng chất lượng trong CI

Pipeline **chặn merge** nếu bất kỳ bước nào thất bại:

| # | Cổng | Chặn merge? |
|---|---|---|
| 1 | `ruff` + `black --check` | Có |
| 2 | `mypy` | Có |
| 3 | `lint-imports` (ranh giới module) | Có |
| 4 | Unit test | Có |
| 5 | Integration + API test | Có |
| 6 | Migration lên/xuống/lên | Có |
| 7 | Độ phủ ≥ 70% | Có |
| 8 | `gitleaks` | Có |
| 9 | `pip-audit` | Chỉ cảnh báo |

---

## 10. Deliverable của QA

| Tài liệu | Nội dung | Hạn |
|---|---|---|
| **Test Plan** | Phạm vi, chiến lược (tài liệu này), môi trường, lịch, tiêu chí vào/ra, rủi ro | Cuối Sprint 0 |
| **Test Cases** | Bảng chi tiết: mã, mô tả, tiền điều kiện, các bước, kết quả mong đợi, kết quả thực tế. Sinh từ tiêu chí chấp nhận ở tài liệu 02 | Xuyên suốt Sprint 1 |
| **Test Report** | Số test đã chạy/đạt/trượt, danh sách bug theo mức nghiêm trọng, độ phủ, kết quả đánh giá AI, kết luận sẵn sàng phát hành | Cuối Sprint 2 |
| **Bug log** | Trên Trello, gắn nhãn theo mức: Critical / Major / Minor / Trivial | Xuyên suốt |

**Tiêu chí ra (điều kiện được coi là sẵn sàng nộp):**
- 0 bug mức Critical, 0 bug mức Major chưa xử lý
- 100% kịch bản thủ công ở §7 đạt
- Ma trận phân quyền đạt 100%
- Chatbot từ chối đúng 5/5 câu ngoài phạm vi tài liệu
- Độ phủ ≥ 70%
- Đã diễn tập khôi phục từ backup thành công một lần
