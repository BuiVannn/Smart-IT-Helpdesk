# Quy định Quản lý Nhánh & Quy trình Git

| | |
|---|---|
| Áp dụng cho | Toàn bộ 9 thành viên dự án Smart IT Helpdesk |
| Căn cứ | Mock Project Guideline §5 (Git, Pull Request, Code Review) |
| Người quản trị repo | Bùi Mậu Văn (Scrum Master) |

> **Đọc mục 4 trước nếu bạn chỉ cần biết làm gì hằng ngày.** Các mục khác là để hiểu tại sao.

---

## 1. Mô hình nhánh

```
main        ●───────────────────────●──────────────────●
            ▲                       ▲                  ▲
            │ merge cuối Sprint 1   │ cuối Sprint 2    │ bản nộp
            │                       │                  │
develop     ●──●──●──●──●──●──●──●──●──●──●──●──●──●──●
            ▲     ▲     ▲        ▲     ▲     ▲
            │     │     │        │     │     │  (merge từ PR)
         feature feature feature feature feature feature
```

| Nhánh | Ai được tạo | Sống bao lâu | Quy tắc |
|---|---|---|---|
| **`main`** | Không ai tạo mới | Vĩnh viễn | **Luôn ở trạng thái demo được.** Chỉ nhận merge từ `develop`. Mỗi lần merge = một bản phát hành |
| **`develop`** | Không ai tạo mới | Vĩnh viễn | Nhánh tích hợp. **CI phải luôn xanh.** Mọi feature merge vào đây |
| **`feature/*`** | Mọi thành viên | Vài giờ → tối đa 3 ngày | Tách từ `develop`, merge lại `develop` qua PR, **xoá ngay sau khi merge** |
| **`hotfix/*`** | Scrum Master / DevOps | Vài giờ | Chỉ khi `main` hỏng gấp. Tách từ `main`, merge vào **cả** `main` và `develop` |

### Vì sao cần cả `main` lẫn `develop`

Trainer có thể yêu cầu xem demo bất cứ lúc nào. Nếu chỉ có một nhánh, `git pull` lúc đó rất dễ dính code dở dang của người khác. Tách ra:

- `develop` có thể đang dở → không sao, đó là nơi để ráp
- `main` luôn là bản đã chạy được → mở ra demo là chạy

**Không được đảo ngược:** không bao giờ merge `feature/*` thẳng vào `main`.

---

## 2. Quy tắc đặt tên nhánh

```
feature/<mã-feature>-<mô-tả-ngắn>
hotfix/<mô-tả-ngắn>
```

Mô tả viết **không dấu**, chữ thường, nối bằng dấu gạch ngang.

| Đúng | Sai | Vì sao sai |
|---|---|---|
| `feature/F1-jwt-auth` | `feature/van` | Tên người không cho biết nhánh làm gì |
| `feature/F2-ticket-crud` | `feature/fix` | Quá mơ hồ |
| `feature/F4-rag-pipeline` | `feature/Ticket_Quản_Lý` | Có dấu và viết hoa — dễ lỗi trên hệ thống phân biệt hoa/thường |
| `hotfix/login-500-error` | `test` | Không có tiền tố, không biết loại nhánh |

Mã feature lấy từ `docs/design/01-requirement-analysis.md` §6: F1 → F8. Việc nền tảng dùng `feature/base-<mô-tả>`.

---

## 3. Quy tắc đặt tên commit

Theo chuẩn **Conventional Commits** — giúp đọc lịch sử và tự sinh changelog:

```
<loại>(<phạm vi>): <mô tả ngắn, không viết hoa đầu, không dấu chấm cuối>

<phần thân, tuỳ chọn — giải thích VÌ SAO, không phải LÀM GÌ>
```

| Loại | Dùng khi |
|---|---|
| `feat` | Thêm tính năng mới |
| `fix` | Sửa lỗi |
| `refactor` | Đổi cấu trúc code, không đổi hành vi |
| `test` | Thêm/sửa test |
| `docs` | Tài liệu |
| `chore` | Cấu hình, dependency, CI |
| `perf` | Cải thiện hiệu năng |

Ví dụ tốt:
```
feat(tickets): thêm optimistic lock khi nhận ticket

Hai Agent cùng bấm "Nhận" gây tranh chấp. Dùng cột version
thay vì SELECT FOR UPDATE để tránh giữ khoá lâu.
```

Ví dụ nên tránh: `update`, `fix bug`, `commit lần 3`, `abc`.

---

## 4. Quy trình hằng ngày — 6 bước

### Bước 1 — Đồng bộ trước khi bắt đầu

```bash
git checkout develop
git pull origin develop
```

**Luôn làm bước này** trước khi tạo nhánh mới. Bỏ qua nó là nguyên nhân số một gây conflict.

### Bước 2 — Tạo nhánh cho task của mình

```bash
git checkout -b feature/F2-ticket-crud
```

Một task trong `tasks/todo.md` = một nhánh = một PR. Đừng gộp 3 task vào một nhánh.

### Bước 3 — Code và commit nhỏ, thường xuyên

```bash
git add app/modules/tickets/service.py
git commit -m "feat(tickets): thêm TicketService.create"
```

Commit nhỏ, mỗi commit một ý. Đừng đợi đến cuối ngày rồi `git add .` một cục — lúc conflict sẽ không biết bỏ cái gì giữ cái gì.

### Bước 4 — Đẩy lên GitHub

```bash
git push -u origin feature/F2-ticket-crud
```

Lần đầu cần `-u`, các lần sau chỉ cần `git push`.

**Nên push mỗi ngày** kể cả khi chưa xong — code chỉ nằm trên máy bạn là code có thể mất.

### Bước 5 — Mở Pull Request

Vào GitHub → tab **Pull requests** → **New pull request**
- base: `develop` ← compare: `feature/F2-ticket-crud`
- Điền theo mẫu ở mục 6
- Gán **Reviewer** (một người trong nhóm, xem bảng mục 7)
- Gán **Assignee** là chính bạn

### Bước 6 — Sau khi được approve

Bấm **Squash and merge** → **Confirm** → **Delete branch**.

Rồi dọn trên máy:
```bash
git checkout develop
git pull origin develop
git branch -d feature/F2-ticket-crud
```

---

## 5. Ba cách merge — dùng cái nào

| Cách | Kết quả trên `develop` | Khi nào dùng |
|---|---|---|
| **Squash and merge** | Gộp cả nhánh thành **1 commit** | ✅ **Mặc định của nhóm.** Lịch sử `develop` sạch, mỗi PR một dòng |
| Merge commit | Giữ toàn bộ commit + 1 commit merge | Chỉ khi merge `develop` → `main` |
| Rebase and merge | Giữ commit, không có commit merge | Không dùng — dễ rối với người mới |

**Quy định: PR vào `develop` dùng "Squash and merge". PR `develop` → `main` dùng "Create a merge commit".**

---

## 6. Mẫu Pull Request

Tạo file `.github/pull_request_template.md` để GitHub tự điền sẵn:

```markdown
## Thay đổi gì
<!-- Mô tả ngắn gọn -->

## Task liên quan
<!-- Mã task trong tasks/todo.md + link thẻ Trello -->
- Task: T__
- Trello:

## Đã kiểm tra
- [ ] Code chạy được ở máy cá nhân
- [ ] Đã viết/cập nhật unit test, test pass
- [ ] Đã chạy `pytest` toàn bộ, không làm hỏng test có sẵn
- [ ] Đã cập nhật tài liệu liên quan (API doc / README)
- [ ] Không commit file `.env`, API key, hay dữ liệu thật

## Cách người review kiểm chứng
<!-- Chỉ rõ: chạy lệnh gì, vào màn hình nào, mong đợi thấy gì -->

## Ảnh chụp màn hình
<!-- Nếu là thay đổi giao diện -->
```

**Yêu cầu bắt buộc theo Guideline §5.2:** mỗi PR phải có mô tả thay đổi, link task, và reviewer.

---

## 7. Quy định review

| Người mở PR | Người review |
|---|---|
| Lại Duy Đông (auth) | Chu Quang Vũ |
| Chu Quang Vũ (tickets) | Lại Duy Đông |
| Nguyễn Đăng Trường (DB/migration) | Cao Mạnh Hà |
| Nguyễn Tiến Lưỡng (knowledge/reports) | Chu Quang Vũ |
| Cao Mạnh Hà (hạ tầng/CI) | Bùi Mậu Văn |
| Bùi Mậu Văn (AI) | Nguyễn Đăng Trường |
| Nguyễn Văn Quang / Dũng (frontend) | Người còn lại trong 2 người |
| Trần Quang Ngọc (test) | Người sở hữu module được test |

### Người review kiểm gì

Theo Guideline §5.3 — không chỉ đọc lướt:

1. **Logic** — code có làm đúng cái PR mô tả không? Có xử lý trường hợp lỗi không?
2. **Quy ước** — có theo khuôn mẫu module ở `docs/design/05` §4.5 không? Có vi phạm ranh giới module không?
3. **Bảo mật** — có kiểm tra quyền không? Có validate input không? Có lộ thông tin nhạy cảm trong log/response không?
4. **Test** — có test cho phần logic mới không? Test có thật sự kiểm chứng điều gì không?
5. **Hiệu năng** — có N+1 query không? Có endpoint danh sách nào thiếu phân trang không?

### Quy tắc ứng xử khi review

- Nhận xét về **code**, không về **người**. "Hàm này thiếu kiểm tra quyền" chứ không phải "bạn hay quên phân quyền".
- Nếu chỉ là góp ý không bắt buộc, ghi rõ `nit:` ở đầu — người kia biết là không chặn merge.
- **Không tự approve PR của chính mình.**
- Review trong vòng **4 giờ làm việc**. PR nằm chờ 2 ngày là nhánh sẽ conflict.

---

## 8. Thiết lập Branch Protection trên GitHub

### 8.1 Tạo nhánh `develop` trước

```bash
git checkout main
git pull origin main
git checkout -b develop
git push -u origin develop
```

Sau đó vào **Settings → General → Default branch** → đổi mặc định thành **`develop`**.
Lý do: người mới clone về sẽ ở `develop`, và PR mới mặc định nhắm vào `develop` thay vì `main` — tránh nhầm lẫn phổ biến nhất.

### 8.2 Đặt luật bảo vệ

Vào **Settings → Branches → Add branch protection rule** (hoặc **Rules → Rulesets** ở giao diện mới).

**Luật cho `main`** — nghiêm ngặt nhất:

| Tuỳ chọn | Bật? | Ý nghĩa |
|---|---|---|
| Branch name pattern: `main` | — | Áp dụng cho nhánh nào |
| Require a pull request before merging | ✅ | **Cấm `git push` thẳng** — luật quan trọng nhất |
| → Require approvals: **1** | ✅ | Phải có ≥1 người duyệt |
| → Dismiss stale approvals when new commits are pushed | ✅ | Push thêm code sau khi được duyệt ⇒ phải duyệt lại |
| Require status checks to pass | ✅ *(bật sau khi có CI — task T05)* | Test đỏ thì không merge được |
| → Require branches to be up to date | ✅ | Phải cập nhật code mới nhất trước khi merge |
| Require conversation resolution | ✅ | Mọi comment phải được giải quyết |
| Do not allow bypassing the above settings | ✅ | **Kể cả admin cũng phải theo luật** |
| Allow force pushes | ❌ | Force push xoá lịch sử của người khác |
| Allow deletions | ❌ | Chống xoá nhầm nhánh chính |

**Luật cho `develop`** — giống `main` nhưng nới 2 điểm:
- *Do not allow bypassing* → **tắt** (để Scrum Master xử lý được tình huống gấp)
- *Dismiss stale approvals* → **tuỳ chọn**

### 8.3 Nếu không thấy tuỳ chọn Branch Protection

Repo **private** trên gói GitHub Free thường không có tính năng này (repo public thì miễn phí). Ba cách xử lý:

1. **Đăng ký GitHub Student Developer Pack** — `education.github.com/pack`. Sinh viên được **GitHub Pro miễn phí**, có đầy đủ branch protection cho repo private. Đây là cách nên làm.
2. **Để repo public** — nhưng phải chắc chắn không có tài liệu nội bộ FSA hay thông tin cá nhân (xem `.gitignore` hiện tại).
3. **Tạm thời áp dụng bằng quy ước** — cả nhóm cam kết không push thẳng, thêm file `CODEOWNERS` để GitHub tự gợi ý reviewer. Kém hiệu quả vì không có gì chặn thật.

### 8.4 File `CODEOWNERS` (nên có)

Tạo `.github/CODEOWNERS` — GitHub sẽ **tự động gán reviewer** đúng người theo thư mục:

```
# Mặc định
*                                   @BuiVannn

# Backend theo module
/backend/app/modules/auth/          @lai-duy-dong
/backend/app/modules/users/         @lai-duy-dong
/backend/app/modules/tickets/       @chu-quang-vu
/backend/app/modules/knowledge/     @nguyen-tien-luong
/backend/app/modules/chatbot/       @BuiVannn
/backend/app/ai/                    @BuiVannn

# Migration — CHỈ MỘT NGƯỜI sở hữu
/backend/migrations/                @nguyen-dang-truong

# Hạ tầng
/docker-compose.yml                 @cao-manh-ha
/.github/                           @cao-manh-ha

# Frontend
/frontend/                          @nguyen-van-quang @nguyen-van-dung

# Tài liệu thiết kế
/docs/design/                       @BuiVannn
```

> Thay `@tên-github` bằng username GitHub thật của từng người.

---

## 9. Ba tình huống hay gặp

### 9.1 Nhánh của tôi bị conflict với `develop`

Xảy ra khi người khác merge trước bạn và động vào cùng file.

```bash
git checkout develop && git pull origin develop
git checkout feature/F2-ticket-crud
git merge develop              # conflict hiện ra ở đây
# Mở file có dấu <<<<<<< ======= >>>>>>>, sửa cho đúng
git add <file-đã-sửa>
git commit
git push
```

**Cách phòng tránh tốt nhất:** nhánh sống ngắn. Nhánh mở 3 ngày gần như chắc chắn conflict; nhánh mở 4 giờ thì hiếm khi.

### 9.2 Conflict ở file migration Alembic

Đây là loại conflict khó nhất: hai người cùng tạo migration, cả hai đều đặt `down_revision` trỏ vào cùng một migration cha → lịch sử migration bị rẽ nhánh.

**Phòng tránh:** chỉ **một người** (Nguyễn Đăng Trường) được tạo file trong `backend/migrations/`. Ai cần bảng mới thì báo, không tự tạo.

**Nếu đã lỡ:** người merge sau phải sửa `down_revision` trong file của mình trỏ vào migration của người merge trước, rồi chạy lại `alembic upgrade head` để kiểm tra.

### 9.3 Tôi lỡ commit vào `develop`/`main` thay vì nhánh riêng

Nếu **chưa push**:
```bash
git branch feature/F2-ticket-crud     # tạo nhánh giữ lại commit
git reset --hard origin/develop       # trả develop về đúng trạng thái remote
git checkout feature/F2-ticket-crud   # sang nhánh mới làm tiếp
```

Nếu **đã push** — báo Scrum Master, đừng tự `git push --force`. Force push xoá commit của người khác.

---

## 10. Những điều tuyệt đối không làm

| Không được | Vì sao |
|---|---|
| `git push --force` vào `main`/`develop` | Xoá vĩnh viễn commit của người khác |
| Push thẳng vào `main`/`develop`, không qua PR | Vi phạm Guideline §5.2; không ai review |
| Tự approve và merge PR của mình | Mất hoàn toàn giá trị của code review |
| Commit file `.env`, API key, mật khẩu thật | Rò rỉ bí mật. Xoá commit sau đó **không** làm nó biến mất khỏi lịch sử |
| Commit code không chạy được | Guideline §6: "Không commit code không chạy" |
| Để nhánh sống quá 3 ngày | Conflict tăng theo cấp số nhân |
| `git add .` mà không xem `git status` | Rất dễ lỡ tay commit file rác hoặc file bí mật |
| Commit file `node_modules/`, `.venv/` | Repo phình to, clone chậm, PR không đọc nổi |

---

## 11. Checklist thiết lập ban đầu (một lần duy nhất — Scrum Master)

- [ ] Tạo và push nhánh `develop`
- [ ] Đổi default branch sang `develop`
- [ ] Đặt branch protection cho `main` (mục 8.2)
- [ ] Đặt branch protection cho `develop`
- [ ] Tạo `.github/pull_request_template.md`
- [ ] Tạo `.github/CODEOWNERS`
- [ ] Mời đủ 8 thành viên vào repo với quyền **Write** (không phải Admin)
- [ ] Gửi link tài liệu này cho cả nhóm, xác nhận từng người đã đọc
- [ ] Sau khi có CI (task T05): bật *Require status checks to pass*
