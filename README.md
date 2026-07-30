# Smart IT Helpdesk

Hệ thống hỗ trợ IT nội bộ thông minh, tích hợp AI phân loại ticket và chatbot RAG.
Mock Project — FSA/FPT Software · Agile Scrum · 9 thành viên · 4 tuần.

> **Trạng thái hiện tại:** đang ở giai đoạn phân tích & thiết kế. Chưa bắt đầu code.

---

## Thành viên

| STT | Họ và tên | Vai trò |
|---|---|---|
| 1 | Bùi Mậu Văn | Nhóm trưởng (Scrum Master) kiêm AI/RAG Engineer |
| 2 | Lại Duy Đông | Backend Developer |
| 3 | Chu Quang Vũ | Backend Developer |
| 4 | Nguyễn Đăng Trường | Backend Developer |
| 5 | Nguyễn Tiến Lưỡng | Backend Developer |
| 6 | Nguyễn Văn Quang | Frontend Developer |
| 7 | Nguyễn Văn Dũng | Frontend Developer |
| 8 | Trần Quang Ngọc | QA / Tester |
| 9 | Cao Mạnh Hà | Backend & DevOps |

Product Owner / Khách hàng: **Trainer**

---

## Tài liệu

Bắt đầu từ [`docs/design/00-README.md`](docs/design/00-README.md) — chỉ mục và thứ tự đọc.

| Tài liệu | Nội dung |
|---|---|
| [01 — Phân tích yêu cầu](docs/design/01-requirement-analysis.md) | Actor, use case, non-goals, NFR có số, ước lượng dung lượng |
| [02 — User Stories](docs/design/02-user-stories.md) | 43 story + tiêu chí chấp nhận |
| [03 — Mô hình miền](docs/design/03-domain-model.md) | Sơ đồ lớp, máy trạng thái ticket, quy tắc nghiệp vụ |
| [04 — ERD & Database](docs/design/04-erd-and-database.md) | ERD, schema, index, migration |
| [05 — Kiến trúc & Module](docs/design/05-architecture-and-modules.md) | C4, phân chia module/package |
| [06 — API Design](docs/design/06-api-design.md) | Hợp đồng API, ma trận phân quyền |
| [07 — Thiết kế AI](docs/design/07-ai-design.md) | Pipeline phân loại + RAG, đánh giá chất lượng |
| [08 — Bảo mật & Vận hành](docs/design/08-nfr-security-ops.md) | Threat model, phân quyền, observability |
| [09 — Frontend](docs/design/09-frontend-design.md) | Route, wireframe, component |
| [10 — Chiến lược kiểm thử](docs/design/10-test-strategy.md) | Kim tự tháp test, kịch bản demo |
| [ADR](docs/design/adr/) | 11 quyết định kiến trúc kèm lý do |

**Kế hoạch triển khai:** [`tasks/plan.md`](tasks/plan.md) · **Checklist theo dõi:** [`tasks/todo.md`](tasks/todo.md)

---

## Công nghệ

| Tầng | Công nghệ |
|---|---|
| Backend | Python · FastAPI · SQLAlchemy 2.x · Alembic · Pydantic v2 |
| Database | PostgreSQL 16 + pgvector |
| Hàng đợi / Cache | Redis · Celery |
| Lưu trữ file | MinIO (dev) / S3 (prod) |
| AI | LLM API · RAG (pgvector) |
| Frontend | React 18 · TypeScript · Vite · TanStack Query · Tailwind · shadcn/ui |
| Hạ tầng | Docker Compose · Nginx · GitHub Actions |

---

## Cài đặt & chạy

> Sẽ cập nhật khi hoàn thành Task T01–T02 trong [`tasks/plan.md`](tasks/plan.md).

```bash
git clone git@github.com:BuiVannn/Smart-IT-Helpdesk.git
cd Smart-IT-Helpdesk
cp .env.example .env
docker compose up
```

---

## Cấu trúc project

```
Smart-IT-Helpdesk/
├── docs/design/        Tài liệu phân tích & thiết kế
├── tasks/              Kế hoạch triển khai và checklist
├── backend/            FastAPI (chưa có)
├── frontend/           React + Vite (chưa có)
└── docker-compose.yml  (chưa có)
```

---

## Quy trình làm việc

- Nhánh: `main` (phát hành) ← `develop` (tích hợp) ← `feature/<mã-feature>-<mô-tả>`
- Mọi thay đổi qua Pull Request, có ít nhất 1 reviewer. **Cấm push thẳng vào `main`.**
- Definition of Done: code merge qua PR có review · có unit test và test pass · đã deploy staging · tài liệu liên quan đã cập nhật.
- Quản lý công việc: Trello — board "Smart IT Helpdesk - Mock Project".
